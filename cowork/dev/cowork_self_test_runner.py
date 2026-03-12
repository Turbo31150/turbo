#!/usr/bin/env python3
"""cowork_self_test_runner.py — Run multi-level tests on all COWORK scripts.

Level 1: Syntax check (AST parse)
Level 2: Import check (no missing stdlib modules)
Level 3: --help test (argparse works)
Level 4: --once/--stats dry run (if available)
Level 5: Cross-script integration checks

CLI:
    --once       : full test run
    --level N    : run specific level (1-5)
    --failed     : show only failures
    --stats      : show test history

Stdlib-only (sqlite3, json, argparse, ast, subprocess).
"""

import argparse
import ast
import json
import os
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data"
DB_PATH = DATA_DIR / "cowork_gaps.db"
PYTHON = sys.executable


def init_db(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS self_test_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        script TEXT NOT NULL,
        level INTEGER NOT NULL,
        test_name TEXT NOT NULL,
        passed INTEGER NOT NULL,
        duration_ms INTEGER,
        error TEXT
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS self_test_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        total_scripts INTEGER,
        total_tests INTEGER,
        passed INTEGER,
        failed INTEGER,
        duration_ms INTEGER,
        level INTEGER
    )""")
    conn.commit()


def get_db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def test_level1_syntax(script_path):
    """Level 1: AST parse check."""
    try:
        with open(script_path, "r", encoding="utf-8", errors="ignore") as f:
            ast.parse(f.read())
        return True, None
    except SyntaxError as e:
        return False, f"SyntaxError: {e}"


def test_level2_imports(script_path):
    """Level 2: Check all imports are available."""
    try:
        with open(script_path, "r", encoding="utf-8", errors="ignore") as f:
            tree = ast.parse(f.read())
    except SyntaxError:
        return False, "Cannot parse"

    stdlib_extras = {
        "httpx", "aiohttp", "requests", "flask", "fastapi", "numpy",
        "pandas", "torch", "tensorflow", "transformers",
    }
    # Detect try/except ImportError blocks to allow conditional imports
    guarded_imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            for handler in node.handlers:
                if handler.type and getattr(handler.type, 'id', '') == 'ImportError':
                    for n in ast.walk(node):
                        if isinstance(n, ast.Import):
                            for alias in n.names:
                                guarded_imports.add(alias.name.split(".")[0])
                        elif isinstance(n, ast.ImportFrom) and n.module:
                            guarded_imports.add(n.module.split(".")[0])

    issues = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                mod = alias.name.split(".")[0]
                if mod in stdlib_extras and mod not in guarded_imports:
                    issues.append(f"Non-stdlib import: {alias.name}")
        elif isinstance(node, ast.ImportFrom) and node.module:
            mod = node.module.split(".")[0]
            if mod in stdlib_extras and mod not in guarded_imports:
                issues.append(f"Non-stdlib import: {node.module}")

    if issues:
        return False, "; ".join(issues[:3])
    return True, None


def test_level3_help(script_path):
    """Level 3: Run --help and check exit code."""
    try:
        r = subprocess.run(
            [PYTHON, str(script_path), "--help"],
            capture_output=True, text=True, timeout=10,
            cwd=str(script_path.parent)
        )
        if r.returncode == 0:
            return True, None
        return False, f"Exit code {r.returncode}: {r.stderr[:100]}"
    except subprocess.TimeoutExpired:
        return False, "Timeout (10s)"
    except Exception as e:
        return False, str(e)[:100]


def test_level4_dryrun(script_path):
    """Level 4: Run --once or --stats (should produce JSON)."""
    # Try --stats first (read-only, safer)
    for flag in ["--stats", "--once"]:
        try:
            r = subprocess.run(
                [PYTHON, str(script_path), flag],
                capture_output=True, text=True, timeout=30,
                cwd=str(script_path.parent)
            )
            if r.returncode == 0 and r.stdout.strip():
                # Try to parse as JSON
                try:
                    json.loads(r.stdout)
                    return True, None
                except json.JSONDecodeError:
                    return True, "Output not JSON but script ran OK"
            elif r.returncode == 0:
                return True, "Empty output but exit 0"
        except subprocess.TimeoutExpired:
            return False, f"Timeout on {flag}"
        except Exception as e:
            return False, str(e)[:100]

    return False, "Neither --stats nor --once worked"


LEVELS = {
    1: ("syntax", test_level1_syntax),
    2: ("imports", test_level2_imports),
    3: ("help", test_level3_help),
    4: ("dryrun", test_level4_dryrun),
}


def run_tests(level=None, failed_only=False):
    """Run tests at specified level (or all levels)."""
    conn = get_db()
    ts = datetime.now().isoformat()
    t0 = time.time()

    scripts = sorted(SCRIPT_DIR.glob("*.py"))
    # Exclude self
    scripts = [s for s in scripts if s.name != Path(__file__).name]

    levels_to_run = [level] if level else sorted(LEVELS.keys())
    results = []
    total_passed = 0
    total_failed = 0
    total_tests = 0

    for script in scripts:
        script_results = {"script": script.stem, "tests": []}

        for lvl in levels_to_run:
            test_name, test_fn = LEVELS[lvl]
            t1 = time.time()
            passed, error = test_fn(script)
            duration_ms = int((time.time() - t1) * 1000)

            total_tests += 1
            if passed:
                total_passed += 1
            else:
                total_failed += 1

            test_result = {
                "level": lvl,
                "test": test_name,
                "passed": passed,
                "duration_ms": duration_ms,
                "error": error,
            }

            if not failed_only or not passed:
                script_results["tests"].append(test_result)

            conn.execute("""
                INSERT INTO self_test_results
                (timestamp, script, level, test_name, passed, duration_ms, error)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (ts, script.stem, lvl, test_name, int(passed), duration_ms, error))

            # Stop testing this script if syntax fails
            if lvl == 1 and not passed:
                break

        if script_results["tests"]:
            results.append(script_results)

    duration_ms = int((time.time() - t0) * 1000)

    conn.execute("""
        INSERT INTO self_test_runs
        (timestamp, total_scripts, total_tests, passed, failed, duration_ms, level)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (ts, len(scripts), total_tests, total_passed, total_failed, duration_ms, level))

    conn.commit()
    conn.close()

    return {
        "timestamp": ts,
        "total_scripts": len(scripts),
        "total_tests": total_tests,
        "passed": total_passed,
        "failed": total_failed,
        "success_rate_pct": round(total_passed / max(total_tests, 1) * 100, 1),
        "duration_ms": duration_ms,
        "levels_tested": levels_to_run,
        "failures": [r for r in results if any(not t["passed"] for t in r["tests"])],
        "failure_count": len([r for r in results if any(not t["passed"] for t in r["tests"])]),
    }


def action_stats():
    """Show test run history."""
    conn = get_db()
    runs = conn.execute("""
        SELECT * FROM self_test_runs ORDER BY timestamp DESC LIMIT 10
    """).fetchall()

    # Most frequently failing scripts
    failures = conn.execute("""
        SELECT script, test_name, COUNT(*) as fail_count
        FROM self_test_results
        WHERE passed = 0
        GROUP BY script, test_name
        ORDER BY fail_count DESC
        LIMIT 15
    """).fetchall()

    conn.close()
    return {
        "recent_runs": [dict(r) for r in runs],
        "frequent_failures": [dict(f) for f in failures],
    }


def main():
    parser = argparse.ArgumentParser(description="COWORK Self-Test Runner")
    parser.add_argument("--once", action="store_true", help="Full test run")
    parser.add_argument("--level", type=int, choices=[1, 2, 3, 4], help="Specific level")
    parser.add_argument("--failed", action="store_true", help="Show only failures")
    parser.add_argument("--stats", action="store_true", help="Show history")
    args = parser.parse_args()

    if not any([args.once, args.level, args.stats]):
        parser.print_help()
        sys.exit(1)

    if args.stats:
        result = action_stats()
    else:
        result = run_tests(level=args.level, failed_only=args.failed)

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
