#!/usr/bin/env python3
"""Continuous Test Runner — Run JARVIS test suites and track regressions.

Executes all test suites (528+ tests), tracks pass/fail rates,
detects regressions, and generates quality reports.
"""
import argparse
import json
import os
import sqlite3
import subprocess
import time
from pathlib import Path

DB_PATH = Path(__file__).parent / "test_runner.db"
TURBO = Path("F:/BUREAU/turbo")
TESTS_DIR = TURBO / "tests"

# Known test suites
TEST_SUITES = [
    ("test_phase1", "Phase 1 — Core"),
    ("test_phase2", "Phase 2 — Cluster"),
    ("test_phase3", "Phase 3 — Trading"),
    ("test_phase4", "Phase 4 — Orchestrator"),
    ("test_phase5", "Phase 5 — Metrics"),
    ("test_phase6", "Phase 6 — Workflow"),
    ("test_phase7", "Phase 7 — Config"),
    ("test_phase8", "Phase 8 — Rate Limiter"),
    ("test_phase9", "Phase 9 — Plugin"),
    ("test_phase10", "Phase 10 — Retry"),
    ("test_phase11", "Phase 11 — Cache+Vault"),
    ("test_telegram_bot", "Telegram Bot"),
]

def init_db():
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS suite_results (
        id INTEGER PRIMARY KEY, ts REAL, suite TEXT, display_name TEXT,
        passed INTEGER, failed INTEGER, errors INTEGER, skipped INTEGER,
        duration_s REAL, output TEXT)""")
    db.execute("""CREATE TABLE IF NOT EXISTS runs (
        id INTEGER PRIMARY KEY, ts REAL, total_suites INTEGER,
        total_passed INTEGER, total_failed INTEGER, total_errors INTEGER,
        duration_s REAL, grade TEXT)""")
    db.commit()
    return db

def run_suite(suite_name):
    """Run a single test suite via pytest."""
    test_file = TESTS_DIR / f"{suite_name}.py"
    if not test_file.exists():
        return None

    try:
        r = subprocess.run(
            ["python", "-m", "pytest", str(test_file), "-q", "--tb=line", "--no-header"],
            capture_output=True, text=True, timeout=60,
            cwd=str(TURBO),
            env={**os.environ, "PYTHONPATH": str(TURBO)})

        output = r.stdout + r.stderr
        # Parse pytest output: "X passed, Y failed, Z error"
        passed = failed = errors = skipped = 0
        for line in output.splitlines():
            if "passed" in line or "failed" in line or "error" in line:
                import re
                p = re.search(r"(\d+) passed", line)
                f = re.search(r"(\d+) failed", line)
                e = re.search(r"(\d+) error", line)
                s = re.search(r"(\d+) skipped", line)
                if p: passed = int(p.group(1))
                if f: failed = int(f.group(1))
                if e: errors = int(e.group(1))
                if s: skipped = int(s.group(1))

        return {
            "passed": passed, "failed": failed, "errors": errors,
            "skipped": skipped, "output": output[-500:]
        }
    except subprocess.TimeoutExpired:
        return {"passed": 0, "failed": 0, "errors": 1, "skipped": 0, "output": "TIMEOUT"}
    except OSError as e:
        return {"passed": 0, "failed": 0, "errors": 1, "skipped": 0, "output": str(e)}

def run_all_suites(db):
    """Run all test suites and store results."""
    start = time.time()
    total_passed = total_failed = total_errors = 0
    suite_count = 0

    for suite_name, display_name in TEST_SUITES:
        t0 = time.time()
        result = run_suite(suite_name)
        duration = time.time() - t0

        if result is None:
            continue

        suite_count += 1
        total_passed += result["passed"]
        total_failed += result["failed"]
        total_errors += result["errors"]

        db.execute(
            "INSERT INTO suite_results (ts, suite, display_name, passed, failed, errors, skipped, duration_s, output) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (time.time(), suite_name, display_name, result["passed"], result["failed"],
             result["errors"], result["skipped"], duration, result["output"]))

        status = "✓" if result["failed"] == 0 and result["errors"] == 0 else "✗"
        print(f"  {status} {display_name}: {result['passed']}✓ {result['failed']}✗ {result['errors']}E ({duration:.1f}s)")

    total_duration = time.time() - start
    total = total_passed + total_failed + total_errors
    pct = (total_passed / total * 100) if total > 0 else 0
    grade = "A" if pct >= 95 else "B" if pct >= 85 else "C" if pct >= 70 else "D" if pct >= 50 else "F"

    db.execute(
        "INSERT INTO runs (ts, total_suites, total_passed, total_failed, total_errors, duration_s, grade) "
        "VALUES (?,?,?,?,?,?,?)",
        (time.time(), suite_count, total_passed, total_failed, total_errors, total_duration, grade))
    db.commit()

    return {
        "suites": suite_count, "passed": total_passed, "failed": total_failed,
        "errors": total_errors, "duration": total_duration, "grade": grade, "pct": pct
    }

def detect_regressions(db):
    """Compare with previous run."""
    runs = db.execute(
        "SELECT total_passed, total_failed, grade FROM runs ORDER BY ts DESC LIMIT 2"
    ).fetchall()
    if len(runs) < 2:
        return None
    curr, prev = runs
    if curr[1] > prev[1]:
        return f"REGRESSION: {curr[1]} failures (was {prev[1]}), grade {prev[2]}→{curr[2]}"
    if curr[0] > prev[0]:
        return f"IMPROVEMENT: +{curr[0] - prev[0]} tests passing"
    return None

def send_telegram_report(result, regression=None):
    """Send test results to Telegram."""
    try:
        edb = sqlite3.connect(str(TURBO / "data" / "etoile.db"))
        row = edb.execute("SELECT value FROM memories WHERE key='telegram_bot_token'").fetchone()
        token = row[0] if row else ""
        edb.close()
    except Exception:
        return

    if not token:
        return

    icon = {"A": "🟢", "B": "🟡", "C": "🟠", "D": "🔴", "F": "⛔"}.get(result["grade"], "⚪")
    msg = (
        f"{icon} *Tests JARVIS — Grade {result['grade']}*\n"
        f"✅ {result['passed']} | ❌ {result['failed']} | ⚠️ {result['errors']}\n"
        f"Suites: {result['suites']} | {result['duration']:.0f}s | {result['pct']:.0f}%"
    )
    if regression:
        msg += f"\n📊 {regression}"

    try:
        body = json.dumps({"chat_id": "2010747443", "text": msg, "parse_mode": "Markdown"}).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=body, headers={"Content-Type": "application/json"})
        import urllib.request
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass

def main():
    parser = argparse.ArgumentParser(description="Continuous Test Runner")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--interval", type=int, default=86400, help="Seconds between runs (default: daily)")
    parser.add_argument("--notify", action="store_true", help="Send Telegram notification")
    args = parser.parse_args()

    db = init_db()

    if args.once or not args.loop:
        print("=== JARVIS Test Runner ===")
        result = run_all_suites(db)
        print(f"\nGrade: {result['grade']} | {result['passed']}/{result['passed']+result['failed']+result['errors']} ({result['pct']:.0f}%) in {result['duration']:.0f}s")
        regression = detect_regressions(db)
        if regression:
            print(f"📊 {regression}")
        if args.notify:
            send_telegram_report(result, regression)

    if args.loop:
        print("Test Runner en boucle continue...")
        while True:
            try:
                result = run_all_suites(db)
                regression = detect_regressions(db)
                ts = time.strftime('%H:%M')
                print(f"\n[{ts}] Grade {result['grade']}: {result['passed']}✓ {result['failed']}✗ ({result['pct']:.0f}%)")
                if regression:
                    print(f"  📊 {regression}")
                time.sleep(args.interval)
            except KeyboardInterrupt:
                break

if __name__ == "__main__":
    main()
