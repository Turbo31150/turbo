#!/usr/bin/env python3
"""telegram_ops_runner.py -- Dynamic runner for uncabled telegram_*.py scripts.

Scans the cowork/dev directory for telegram_*.py scripts not already wired
individually in the autonomous orchestrator, then runs each one sequentially
with --once, logging results to cowork_gaps.db.

Usage:
    python telegram_ops_runner.py --once          # Run all uncabled telegram scripts
    python telegram_ops_runner.py --list          # List discovered scripts
    python telegram_ops_runner.py --dry-run       # Show plan without executing

Stdlib-only (subprocess, sqlite3, pathlib, time, argparse, json).
"""

import argparse
import json
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

PREFIX = "telegram_"
RUNNER_NAME = Path(__file__).name
SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data"
DB_PATH = DATA_DIR / "cowork_gaps.db"
TABLE_NAME = "telegram_runner_log"
TIMEOUT = 60

# Scripts already wired individually in autonomous_orchestrator.py TASKS dict.
# These are EXCLUDED from the dynamic scan to avoid double-execution.
ALREADY_WIRED = {
    "telegram_quick_status.py",
}


def get_db():
    """Open DB connection and ensure log table exists."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.row_factory = sqlite3.Row
    conn.execute(f"""CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        script TEXT NOT NULL,
        success INTEGER DEFAULT 0,
        duration_ms INTEGER DEFAULT 0,
        output_tail TEXT,
        error_tail TEXT
    )""")
    conn.commit()
    return conn


def discover_scripts():
    """Find all telegram_*.py scripts excluding self and already-wired ones."""
    scripts = []
    for f in sorted(SCRIPT_DIR.glob(f"{PREFIX}*.py")):
        if f.name == RUNNER_NAME:
            continue
        if f.name in ALREADY_WIRED:
            continue
        scripts.append(f)
    return scripts


def run_script(script, dry_run=False):
    """Execute a single script with --once. Returns result dict."""
    cmd = [sys.executable, str(script), "--once"]
    result = {
        "script": script.name,
        "success": False,
        "duration_ms": 0,
        "output_tail": "",
        "error_tail": "",
    }

    if dry_run:
        result["success"] = True
        result["output_tail"] = "[dry-run] " + " ".join(cmd)
        return result

    start = time.time()
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
            cwd=str(SCRIPT_DIR),
        )
        elapsed_ms = int((time.time() - start) * 1000)
        result["duration_ms"] = elapsed_ms
        result["success"] = proc.returncode == 0
        result["output_tail"] = (proc.stdout or "")[-500:]
        result["error_tail"] = (proc.stderr or "")[-300:]
    except subprocess.TimeoutExpired:
        result["duration_ms"] = TIMEOUT * 1000
        result["error_tail"] = f"Timeout after {TIMEOUT}s"
    except Exception as e:
        result["duration_ms"] = int((time.time() - start) * 1000)
        result["error_tail"] = str(e)[:300]

    return result


def log_result(conn, result):
    """Insert execution result into DB with retry on lock."""
    now = datetime.now().isoformat()
    for attempt in range(5):
        try:
            conn.execute(f"""
                INSERT INTO {TABLE_NAME}
                    (timestamp, script, success, duration_ms, output_tail, error_tail)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                now,
                result["script"],
                1 if result["success"] else 0,
                result["duration_ms"],
                result["output_tail"],
                result["error_tail"],
            ))
            conn.commit()
            return
        except sqlite3.OperationalError as e:
            if "locked" in str(e) and attempt < 4:
                time.sleep(2 * (attempt + 1))
                continue
            raise


def main():
    parser = argparse.ArgumentParser(description=f"Dynamic runner for uncabled {PREFIX}*.py scripts")
    parser.add_argument("--once", action="store_true", help="Run all scripts once")
    parser.add_argument("--list", action="store_true", help="List discovered scripts")
    parser.add_argument("--dry-run", action="store_true", help="Show plan without executing")
    args = parser.parse_args()

    scripts = discover_scripts()

    if args.list:
        print(f"Discovered {len(scripts)} uncabled {PREFIX}*.py scripts:")
        for s in scripts:
            print(f"  {s.name}")
        print(f"\nAlready wired (excluded): {', '.join(sorted(ALREADY_WIRED))}")
        return

    if not args.once and not args.dry_run:
        parser.print_help()
        print(f"\nDiscovered {len(scripts)} scripts. Use --once to run.")
        return

    conn = get_db()
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {RUNNER_NAME}: {len(scripts)} scripts to run")

    ok = 0
    total = len(scripts)
    results = []

    for i, script in enumerate(scripts, 1):
        tag = f"[{i}/{total}]"
        print(f"  {tag} {script.name}...", end="", flush=True)
        result = run_script(script, dry_run=args.dry_run)
        results.append(result)

        if not args.dry_run:
            log_result(conn, result)

        status = "OK" if result["success"] else "FAIL"
        dur = result["duration_ms"]
        print(f" {status} ({dur}ms)")

        if result["success"]:
            ok += 1

    conn.close()

    summary = {
        "runner": RUNNER_NAME,
        "timestamp": datetime.now().isoformat(),
        "total": total,
        "succeeded": ok,
        "failed": total - ok,
        "scripts": [{
            "script": r["script"],
            "success": r["success"],
            "duration_ms": r["duration_ms"],
        } for r in results],
    }
    print(f"\n[{ts}] Done: {ok}/{total} succeeded")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
