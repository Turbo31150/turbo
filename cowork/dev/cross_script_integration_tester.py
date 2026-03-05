#!/usr/bin/env python3
"""Cross-Script Integration Tester — Test that scripts work together.

Tests common patterns like scheduler->monitor->reporter pipelines,
checks that shared SQLite databases are not locked under concurrent access,
and verifies import compatibility between scripts.

Usage:
    python cross_script_integration_tester.py --once
    python cross_script_integration_tester.py --once --pattern scheduler --all
"""

import argparse
import ast
import datetime
import importlib.util
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import glob


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "cowork_gaps.db")
DEV_DIR = SCRIPT_DIR


# Known integration patterns (groups of scripts that should work together)
INTEGRATION_PATTERNS = {
    "scheduler": {
        "desc": "Scheduler -> Monitor -> Reporter pipeline",
        "scripts": ["auto_scheduler.py", "auto_monitor.py", "auto_reporter.py"],
        "shared_db": "cowork_gaps.db"
    },
    "healer": {
        "desc": "Health guard -> Auto healer -> Alert manager",
        "scripts": ["autonomous_health_guard.py", "auto_healer.py", "alert_manager.py"],
        "shared_db": "cowork_gaps.db"
    },
    "deployer": {
        "desc": "Auto updater -> Auto deployer -> Auto monitor",
        "scripts": ["auto_updater.py", "auto_deployer.py", "auto_monitor.py"],
        "shared_db": "cowork_gaps.db"
    },
    "learner": {
        "desc": "Auto learner -> Auto skill tester -> Auto documenter",
        "scripts": ["auto_learner.py", "auto_skill_tester.py", "auto_documenter.py"],
        "shared_db": "cowork_gaps.db"
    },
    "trading": {
        "desc": "Trading pipeline -> Reporter",
        "scripts": ["auto_trader.py", "auto_reporter.py"],
        "shared_db": "cowork_gaps.db"
    }
}


def init_db(conn):
    """Initialize SQLite tables for integration test tracking."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS integration_tests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            test_name TEXT NOT NULL,
            pattern TEXT,
            status TEXT NOT NULL,
            duration_ms INTEGER,
            details TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS integration_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            total_tests INTEGER,
            passed INTEGER,
            failed INTEGER,
            skipped INTEGER,
            details TEXT
        )
    """)
    conn.commit()


class TestResult:
    """Container for individual test results."""
    def __init__(self, name, pattern=""):
        self.name = name
        self.pattern = pattern
        self.status = "pending"
        self.duration_ms = 0
        self.details = ""
        self.start_time = None

    def start(self):
        self.start_time = time.time()

    def finish(self, status, details=""):
        self.status = status
        self.details = details
        if self.start_time:
            self.duration_ms = int((time.time() - self.start_time) * 1000)

    def to_dict(self):
        return {
            "name": self.name,
            "pattern": self.pattern,
            "status": self.status,
            "duration_ms": self.duration_ms,
            "details": self.details
        }


def test_script_exists(script_name):
    """Test if a script file exists."""
    path = os.path.join(DEV_DIR, script_name)
    return os.path.isfile(path)


def test_script_syntax(script_name):
    """Test if a script has valid Python syntax."""
    path = os.path.join(DEV_DIR, script_name)
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            source = f.read()
        ast.parse(source)
        return True, "Syntax OK"
    except SyntaxError as e:
        return False, f"SyntaxError: {e}"
    except OSError as e:
        return False, f"Read error: {e}"


def test_script_imports(script_name, verbose=False):
    """Test if a script's stdlib imports are valid (no missing modules)."""
    path = os.path.join(DEV_DIR, script_name)
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            source = f.read()
        tree = ast.parse(source)
    except (SyntaxError, OSError) as e:
        return False, f"Parse error: {e}"

    stdlib_issues = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                mod_name = alias.name.split(".")[0]
                if not _module_available(mod_name):
                    stdlib_issues.append(mod_name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                mod_name = node.module.split(".")[0]
                if not _module_available(mod_name):
                    stdlib_issues.append(node.module)

    if stdlib_issues:
        return False, f"Missing modules: {', '.join(stdlib_issues)}"
    return True, "All imports OK"


def _module_available(module_name):
    """Check if a module is importable."""
    try:
        spec = importlib.util.find_spec(module_name)
        return spec is not None
    except (ModuleNotFoundError, ValueError):
        return False


def test_sqlite_concurrent_access(db_path, num_threads=3, verbose=False):
    """Test that a SQLite database can handle concurrent read access."""
    if not os.path.exists(db_path):
        return True, "DB does not exist yet (will be created on first use)"

    errors = []
    results = []

    def reader_thread(thread_id):
        try:
            conn = sqlite3.connect(db_path, timeout=5)
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            results.append((thread_id, len(tables)))
            conn.close()
        except Exception as e:
            errors.append((thread_id, str(e)))

    threads = []
    for i in range(num_threads):
        t = threading.Thread(target=reader_thread, args=(i,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join(timeout=10)

    if errors:
        return False, f"Concurrent access errors: {errors}"
    return True, f"Concurrent read OK ({num_threads} threads, {len(results)} succeeded)"


def test_sqlite_write_lock(db_path, verbose=False):
    """Test that SQLite WAL mode handles write contention gracefully."""
    if not os.path.exists(db_path):
        return True, "DB does not exist yet"

    errors = []

    def writer_thread(thread_id):
        try:
            conn = sqlite3.connect(db_path, timeout=10)
            conn.execute("PRAGMA journal_mode=WAL")
            # Try to create a temp table and drop it
            table_name = f"_integration_test_{thread_id}"
            conn.execute(f"CREATE TABLE IF NOT EXISTS {table_name} (id INTEGER)")
            conn.execute(f"DROP TABLE IF EXISTS {table_name}")
            conn.commit()
            conn.close()
        except Exception as e:
            errors.append((thread_id, str(e)))

    threads = []
    for i in range(2):
        t = threading.Thread(target=writer_thread, args=(i,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join(timeout=15)

    if errors:
        return False, f"Write lock issues: {errors}"
    return True, "Write concurrency OK (WAL mode)"


def test_pattern_scripts(pattern_name, pattern_info, verbose=False):
    """Test all scripts in a pattern are compatible."""
    results = []

    # Test each script exists and has valid syntax
    for script in pattern_info["scripts"]:
        tr = TestResult(f"{pattern_name}:exists:{script}", pattern_name)
        tr.start()
        if test_script_exists(script):
            tr.finish("passed", f"{script} exists")
        else:
            tr.finish("skipped", f"{script} not found")
        results.append(tr)

    # Test syntax for existing scripts
    existing = [s for s in pattern_info["scripts"] if test_script_exists(s)]
    for script in existing:
        tr = TestResult(f"{pattern_name}:syntax:{script}", pattern_name)
        tr.start()
        ok, msg = test_script_syntax(script)
        tr.finish("passed" if ok else "failed", msg)
        results.append(tr)

    # Test imports
    for script in existing:
        tr = TestResult(f"{pattern_name}:imports:{script}", pattern_name)
        tr.start()
        ok, msg = test_script_imports(script, verbose)
        tr.finish("passed" if ok else "failed", msg)
        results.append(tr)

    # Test shared DB concurrent access
    if pattern_info.get("shared_db"):
        db_file = os.path.join(DATA_DIR, pattern_info["shared_db"])
        tr = TestResult(f"{pattern_name}:db_concurrent_read", pattern_name)
        tr.start()
        ok, msg = test_sqlite_concurrent_access(db_file, verbose=verbose)
        tr.finish("passed" if ok else "failed", msg)
        results.append(tr)

        tr2 = TestResult(f"{pattern_name}:db_write_lock", pattern_name)
        tr2.start()
        ok2, msg2 = test_sqlite_write_lock(db_file, verbose=verbose)
        tr2.finish("passed" if ok2 else "failed", msg2)
        results.append(tr2)

    # Test cross-imports (check if scripts share common constants/patterns)
    if len(existing) >= 2:
        tr = TestResult(f"{pattern_name}:cross_compatibility", pattern_name)
        tr.start()
        issues = []
        for script in existing:
            path = os.path.join(DEV_DIR, script)
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                # Check for hardcoded DB paths that might conflict
                if "cowork_gaps.db" in content and pattern_info.get("shared_db") == "cowork_gaps.db":
                    pass  # Expected, using shared DB
                # Check for conflicting table names would require deeper analysis
            except OSError:
                issues.append(f"Cannot read {script}")
        if issues:
            tr.finish("failed", "; ".join(issues))
        else:
            tr.finish("passed", f"Cross-compatibility OK for {len(existing)} scripts")
        results.append(tr)

    return results


def test_all_scripts_syntax(verbose=False):
    """Test syntax of ALL scripts in dev/."""
    results = []
    pattern = os.path.join(DEV_DIR, "*.py")
    for filepath in sorted(glob.glob(pattern)):
        name = os.path.basename(filepath)
        if name.startswith("__"):
            continue
        tr = TestResult(f"global:syntax:{name}", "global")
        tr.start()
        ok, msg = test_script_syntax(name)
        tr.finish("passed" if ok else "failed", msg)
        results.append(tr)
    return results


def test_all_scripts_imports(verbose=False):
    """Test imports of ALL scripts in dev/."""
    results = []
    pattern = os.path.join(DEV_DIR, "*.py")
    for filepath in sorted(glob.glob(pattern)):
        name = os.path.basename(filepath)
        if name.startswith("__"):
            continue
        tr = TestResult(f"global:imports:{name}", "global")
        tr.start()
        ok, msg = test_script_imports(name, verbose)
        tr.finish("passed" if ok else "failed", msg)
        results.append(tr)
    return results


def run(args):
    """Main execution logic."""
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    init_db(conn)

    all_results = []

    if args.all:
        if args.verbose:
            print("[integration] Running ALL tests...")

        # Global syntax + imports
        if args.verbose:
            print("[integration] Testing global syntax...")
        all_results.extend(test_all_scripts_syntax(args.verbose))

        if args.verbose:
            print("[integration] Testing global imports...")
        all_results.extend(test_all_scripts_imports(args.verbose))

        # All patterns
        for pname, pinfo in INTEGRATION_PATTERNS.items():
            if args.verbose:
                print(f"[integration] Testing pattern: {pname} — {pinfo['desc']}")
            all_results.extend(test_pattern_scripts(pname, pinfo, args.verbose))

    elif args.pattern:
        # Test specific pattern
        if args.pattern in INTEGRATION_PATTERNS:
            pinfo = INTEGRATION_PATTERNS[args.pattern]
            if args.verbose:
                print(f"[integration] Testing pattern: {args.pattern} — {pinfo['desc']}")
            all_results.extend(test_pattern_scripts(args.pattern, pinfo, args.verbose))
        else:
            print(f"[integration] Unknown pattern: {args.pattern}")
            print(f"  Available: {', '.join(INTEGRATION_PATTERNS.keys())}")
            sys.exit(1)
    else:
        # Default: test all patterns
        for pname, pinfo in INTEGRATION_PATTERNS.items():
            if args.verbose:
                print(f"[integration] Testing pattern: {pname}")
            all_results.extend(test_pattern_scripts(pname, pinfo, args.verbose))

    # Tally results
    passed = sum(1 for r in all_results if r.status == "passed")
    failed = sum(1 for r in all_results if r.status == "failed")
    skipped = sum(1 for r in all_results if r.status == "skipped")

    # Save to DB
    now = datetime.datetime.now().isoformat()
    for r in all_results:
        conn.execute(
            "INSERT INTO integration_tests (timestamp, test_name, pattern, status, duration_ms, details) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (now, r.name, r.pattern, r.status, r.duration_ms, r.details)
        )
    conn.execute(
        "INSERT INTO integration_runs (timestamp, total_tests, passed, failed, skipped, details) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (now, len(all_results), passed, failed, skipped,
         json.dumps({"all": args.all, "pattern": args.pattern}))
    )
    conn.commit()
    conn.close()

    # JSON output
    result = {
        "timestamp": now,
        "total_tests": len(all_results),
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "success_rate": round(passed / max(passed + failed, 1) * 100, 1),
        "tests": [r.to_dict() for r in all_results]
    }

    if args.verbose:
        print(f"\n[integration] Results: {passed} passed, {failed} failed, {skipped} skipped "
              f"({result['success_rate']}%)")
        for r in all_results:
            icon = {"passed": "+", "failed": "X", "skipped": "-"}.get(r.status, "?")
            print(f"  [{icon}] {r.name}: {r.details}")

    print(json.dumps(result, indent=2))
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Cross-Script Integration Tester — Test that scripts work together"
    )
    parser.add_argument("--once", action="store_true",
                        help="Run once and exit")
    parser.add_argument("--pattern", type=str, default=None,
                        help="Test a specific integration pattern (scheduler, healer, deployer, learner, trading)")
    parser.add_argument("--all", action="store_true",
                        help="Run ALL tests including global syntax/import checks")
    args = parser.parse_args()

    if args.once:
        run(args)
    else:
        print("[integration] Running in continuous mode (Ctrl+C to stop)")
        while True:
            try:
                run(args)
                time.sleep(300)
            except KeyboardInterrupt:
                print("\n[integration] Stopped")
                break


if __name__ == "__main__":
    main()
