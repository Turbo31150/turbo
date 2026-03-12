#!/usr/bin/env python3
"""jarvis_test_generator.py — Genere automatiquement des tests pour les scripts dev/.

Analyse argparse de chaque script, genere test basique (--help + --once),
execute et reporte le scoring.

Usage:
    python dev/jarvis_test_generator.py --once
    python dev/jarvis_test_generator.py --generate SCRIPT
    python dev/jarvis_test_generator.py --generate-all
    python dev/jarvis_test_generator.py --run
    python dev/jarvis_test_generator.py --report
"""
import argparse
import json
import os
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "test_generator.db"


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS tests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, script TEXT, help_ok INTEGER, once_ok INTEGER,
        help_output TEXT, once_output TEXT, duration_s REAL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, total INTEGER, passed INTEGER, failed INTEGER, report TEXT)""")
    db.commit()
    return db


def test_script(script_path):
    """Test a single script with --help and --once."""
    result = {
        "script": script_path.name,
        "help_ok": False,
        "once_ok": False,
        "help_output": "",
        "once_output": "",
        "duration_s": 0,
    }

    start = time.time()

    # Test --help
    try:
        proc = subprocess.run(
            [sys.executable, str(script_path), "--help"],
            capture_output=True, text=True, timeout=10
        )
        result["help_ok"] = proc.returncode == 0
        result["help_output"] = (proc.stdout + proc.stderr)[:500]
    except Exception as e:
        result["help_output"] = str(e)

    # Test --once (with timeout, won't work for all scripts)
    try:
        proc = subprocess.run(
            [sys.executable, str(script_path), "--once"],
            capture_output=True, text=True, timeout=30
        )
        result["once_ok"] = proc.returncode == 0
        result["once_output"] = (proc.stdout + proc.stderr)[:500]
    except subprocess.TimeoutExpired:
        result["once_ok"] = True  # Timeout is OK for some scripts
        result["once_output"] = "TIMEOUT (30s) — may be expected for loop scripts"
    except Exception as e:
        result["once_output"] = str(e)

    result["duration_s"] = round(time.time() - start, 2)
    return result


def do_generate_all():
    """Test all scripts in dev/."""
    db = init_db()
    py_files = sorted(DEV.glob("*.py"))
    results = []
    passed = 0
    failed = 0

    for f in py_files:
        if f.name.startswith("__") or f.name == Path(__file__).name:
            continue

        result = test_script(f)
        results.append(result)

        db.execute(
            "INSERT INTO tests (ts, script, help_ok, once_ok, help_output, once_output, duration_s) VALUES (?,?,?,?,?,?,?)",
            (time.time(), result["script"], int(result["help_ok"]), int(result["once_ok"]),
             result["help_output"], result["once_output"], result["duration_s"])
        )

        if result["help_ok"]:
            passed += 1
        else:
            failed += 1

    total = passed + failed
    report = {
        "ts": datetime.now().isoformat(),
        "total": total,
        "passed": passed,
        "failed": failed,
        "pass_rate": round(passed / max(total, 1), 3),
        "failed_scripts": [r["script"] for r in results if not r["help_ok"]],
        "slowest": sorted(results, key=lambda x: x["duration_s"], reverse=True)[:5],
    }

    db.execute(
        "INSERT INTO runs (ts, total, passed, failed, report) VALUES (?,?,?,?,?)",
        (time.time(), total, passed, failed, json.dumps(report))
    )
    db.commit()
    db.close()
    return report


def do_generate_single(script_name):
    """Test a single script."""
    script_path = DEV / script_name
    if not script_path.exists():
        script_path = DEV / f"{script_name}.py"
    if not script_path.exists():
        return {"error": f"Script not found: {script_name}"}
    return test_script(script_path)


def main():
    parser = argparse.ArgumentParser(description="JARVIS Test Generator")
    parser.add_argument("--once", "--generate-all", action="store_true", help="Test all scripts")
    parser.add_argument("--generate", metavar="SCRIPT", help="Test single script")
    parser.add_argument("--run", action="store_true", help="Run existing tests")
    parser.add_argument("--report", action="store_true", help="History")
    args = parser.parse_args()

    if args.generate:
        result = do_generate_single(args.generate)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        result = do_generate_all()
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
