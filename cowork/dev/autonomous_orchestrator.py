#!/usr/bin/env python3
"""autonomous_orchestrator.py — Autonomous JARVIS orchestration engine.

Master scheduler that runs the right maintenance scripts at the right time:
- Heartbeat: every 2 min
- Crypto alerts: every 5 min
- Quality benchmark: every 30 min
- Learning cycle: every hour
- Health summary: every 15 min
- Log compression: daily

Adapts scheduling based on system state (more frequent during issues).

CLI:
    --once         : Run all tasks once
    --watch        : Continuous orchestration
    --status       : Show task schedule status
    --dry-run      : Show what would run without executing

Stdlib-only (json, argparse, subprocess, sqlite3, time).
"""

import argparse
import json
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data"
DB_PATH = DATA_DIR / "cowork_gaps.db"

TELEGRAM_TOKEN = "TELEGRAM_TOKEN_REDACTED"
TELEGRAM_CHAT_ID = "2010747443"

# Task definitions: name -> (script, args, interval_minutes, priority)
TASKS = {
    "heartbeat": {
        "script": "cluster_heartbeat.py",
        "args": ["--once"],
        "interval_min": 2,
        "priority": 1,
        "category": "health",
    },
    "crypto_alert": {
        "script": "crypto_price_alert.py",
        "args": ["--once", "--pairs", "IPUSDT,ASTERUSDT"],
        "interval_min": 5,
        "priority": 2,
        "category": "trading",
    },
    "health_summary": {
        "script": "cowork_health_summary.py",
        "args": ["--once"],
        "interval_min": 15,
        "priority": 2,
        "category": "health",
    },
    "dispatch_quality": {
        "script": "dispatch_quality_tracker.py",
        "args": ["--once"],
        "interval_min": 15,
        "priority": 3,
        "category": "dispatch",
    },
    "quality_benchmark": {
        "script": "dispatch_quality_tracker.py",
        "args": ["--benchmark"],
        "interval_min": 30,
        "priority": 4,
        "category": "dispatch",
        "timeout_s": 300,
    },
    "dispatch_learning": {
        "script": "dispatch_learner.py",
        "args": ["--learn"],
        "interval_min": 60,
        "priority": 3,
        "category": "dispatch",
    },
    "routing_update": {
        "script": "smart_routing_engine.py",
        "args": ["--once"],
        "interval_min": 30,
        "priority": 3,
        "category": "routing",
    },
    "log_compress": {
        "script": "log_compressor.py",
        "args": ["--once"],
        "interval_min": 1440,  # daily
        "priority": 5,
        "category": "maintenance",
    },
    "failure_predict": {
        "script": "failure_predictor.py",
        "args": ["--once", "--telegram"],
        "interval_min": 30,
        "priority": 3,
        "category": "health",
    },
    "metrics_collect": {
        "script": "metrics_aggregator.py",
        "args": ["--once"],
        "interval_min": 15,
        "priority": 3,
        "category": "metrics",
    },
    "self_test": {
        "script": "cowork_self_test_runner.py",
        "args": ["--once"],
        "interval_min": 360,  # every 6h
        "priority": 5,
        "category": "testing",
        "timeout_s": 300,
    },
    "daily_report": {
        "script": "daily_cowork_report.py",
        "args": ["--once"],
        "interval_min": 1440,  # daily
        "priority": 5,
        "category": "reporting",
    },
    "error_analysis": {
        "script": "dispatch_error_analyzer.py",
        "args": ["--once"],
        "interval_min": 60,
        "priority": 4,
        "category": "dispatch",
    },
    "auto_heal": {
        "script": "cluster_auto_healer.py",
        "args": ["--once"],
        "interval_min": 30,
        "priority": 2,
        "category": "health",
    },
    "grade_optimize": {
        "script": "grade_optimizer.py",
        "args": ["--once"],
        "interval_min": 60,
        "priority": 4,
        "category": "optimization",
    },
    "quick_status": {
        "script": "telegram_quick_status.py",
        "args": ["--once"],
        "interval_min": 30,
        "priority": 3,
        "category": "reporting",
    },
    "latency_monitor": {
        "script": "latency_monitor.py",
        "args": ["--once", "--alert"],
        "interval_min": 5,
        "priority": 2,
        "category": "monitoring",
    },
}


def get_db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    conn.execute("""CREATE TABLE IF NOT EXISTS orchestrator_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        task_name TEXT NOT NULL,
        success INTEGER DEFAULT 0,
        duration_ms INTEGER DEFAULT 0,
        output_summary TEXT
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS orchestrator_schedule (
        task_name TEXT PRIMARY KEY,
        last_run TEXT,
        next_run TEXT,
        run_count INTEGER DEFAULT 0,
        fail_count INTEGER DEFAULT 0
    )""")
    conn.commit()
    return conn


def run_task(task_name, task_def, dry_run=False):
    """Execute a task and return result."""
    script = SCRIPT_DIR / task_def["script"]
    if not script.exists():
        return {"success": False, "error": f"Script not found: {script}"}

    cmd = [sys.executable, str(script)] + task_def["args"]
    timeout = task_def.get("timeout_s", 120)

    if dry_run:
        return {"success": True, "dry_run": True, "cmd": " ".join(cmd)}

    start = time.time()
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, cwd=str(SCRIPT_DIR)
        )
        elapsed_ms = int((time.time() - start) * 1000)
        output = result.stdout[-500:] if result.stdout else ""
        error = result.stderr[-200:] if result.stderr else ""
        return {
            "success": result.returncode == 0,
            "duration_ms": elapsed_ms,
            "output": output,
            "error": error,
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": f"Timeout after {timeout}s",
                "duration_ms": int(timeout * 1000)}
    except Exception as e:
        return {"success": False, "error": str(e)[:200],
                "duration_ms": int((time.time() - start) * 1000)}


def should_run(conn, task_name, interval_min):
    """Check if a task should run based on schedule."""
    row = conn.execute(
        "SELECT last_run FROM orchestrator_schedule WHERE task_name=?",
        (task_name,)
    ).fetchone()

    if not row or not row["last_run"]:
        return True

    try:
        last = datetime.fromisoformat(row["last_run"])
        elapsed = (datetime.now() - last).total_seconds() / 60
        return elapsed >= interval_min
    except Exception:
        return True


def record_run(conn, task_name, result):
    """Record task execution."""
    now = datetime.now().isoformat()
    conn.execute("""
        INSERT INTO orchestrator_runs (timestamp, task_name, success, duration_ms, output_summary)
        VALUES (?, ?, ?, ?, ?)
    """, (now, task_name, 1 if result["success"] else 0,
          result.get("duration_ms", 0),
          (result.get("output", "") + result.get("error", ""))[:500]))

    conn.execute("""
        INSERT INTO orchestrator_schedule (task_name, last_run, run_count, fail_count)
        VALUES (?, ?, 1, ?)
        ON CONFLICT(task_name) DO UPDATE SET
            last_run = ?,
            run_count = run_count + 1,
            fail_count = fail_count + ?
    """, (task_name, now, 0 if result["success"] else 1,
          now, 0 if result["success"] else 1))
    conn.commit()


def send_telegram(text):
    import urllib.parse, urllib.request
    data = urllib.parse.urlencode({
        "chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"
    }).encode()
    try:
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", data
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass


def run_all(conn, dry_run=False, verbose=False):
    """Run all due tasks in priority order."""
    due_tasks = []
    for name, task_def in TASKS.items():
        if should_run(conn, name, task_def["interval_min"]):
            due_tasks.append((name, task_def))

    # Sort by priority
    due_tasks.sort(key=lambda x: x[1]["priority"])

    results = {}
    for name, task_def in due_tasks:
        ts = datetime.now().strftime("%H:%M:%S")
        if verbose or dry_run:
            print(f"  [{ts}] Running {name}...")

        result = run_task(name, task_def, dry_run)
        results[name] = result

        if not dry_run:
            record_run(conn, name, result)

        status = "OK" if result["success"] else "FAIL"
        dur = result.get("duration_ms", 0)
        if verbose:
            print(f"  [{ts}] {name}: {status} ({dur}ms)")

    return results


def get_schedule_status(conn):
    """Show current schedule status."""
    rows = conn.execute("""
        SELECT task_name, last_run, run_count, fail_count
        FROM orchestrator_schedule ORDER BY task_name
    """).fetchall()
    return [dict(r) for r in rows]


def main():
    parser = argparse.ArgumentParser(description="Autonomous Orchestrator")
    parser.add_argument("--once", action="store_true", help="Run all due tasks once")
    parser.add_argument("--watch", action="store_true", help="Continuous orchestration")
    parser.add_argument("--status", action="store_true", help="Show schedule status")
    parser.add_argument("--dry-run", action="store_true", help="Show what would run")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--interval", type=int, default=1, help="Check interval (min)")
    args = parser.parse_args()

    if not any([args.once, args.watch, args.status, args.dry_run]):
        parser.print_help()
        sys.exit(1)

    conn = get_db()

    if args.status:
        status = get_schedule_status(conn)
        for s in status:
            task_def = TASKS.get(s["task_name"], {})
            interval = task_def.get("interval_min", "?")
            print(f"  {s['task_name']:25} runs={s['run_count']} fails={s['fail_count']} "
                  f"interval={interval}m last={s.get('last_run', 'never')}")
        conn.close()
        return

    if args.dry_run:
        print("=== Dry Run ===")
        results = run_all(conn, dry_run=True, verbose=True)
        for name, r in results.items():
            print(f"  {name}: {r.get('cmd', '?')}")
        conn.close()
        return

    if args.once:
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"[{ts}] Running all due tasks...")
        results = run_all(conn, verbose=True)
        ok = sum(1 for r in results.values() if r["success"])
        total = len(results)
        print(f"\n[{ts}] Done: {ok}/{total} succeeded")

        if total > 0:
            lines = [f"<b>Orchestrator</b> <code>{ts}</code>",
                     f"Tasks: {ok}/{total} OK"]
            for name, r in results.items():
                s = "+" if r["success"] else "-"
                lines.append(f"  {s} {name} ({r.get('duration_ms', 0)}ms)")
            send_telegram("\n".join(lines))

        result = {
            "timestamp": datetime.now().isoformat(),
            "tasks_run": total, "succeeded": ok,
            "results": {k: {"success": v["success"], "duration_ms": v.get("duration_ms", 0)}
                        for k, v in results.items()},
        }
        print(json.dumps(result, indent=2))
        conn.close()
        return

    if args.watch:
        print(f"Autonomous orchestration (check every {args.interval}m)")
        send_telegram(f"<b>Orchestrator Started</b>\n{len(TASKS)} tasks registered")
        cycle = 0
        while True:
            try:
                cycle += 1
                results = run_all(conn, verbose=args.verbose)
                ts = datetime.now().strftime("%H:%M:%S")
                if results:
                    ok = sum(1 for r in results.values() if r["success"])
                    print(f"[{ts}] Cycle {cycle}: {ok}/{len(results)} tasks OK")
                else:
                    if args.verbose:
                        print(f"[{ts}] Cycle {cycle}: No tasks due")
                time.sleep(args.interval * 60)
            except KeyboardInterrupt:
                print("\nOrchestrator stopped")
                break

    conn.close()


if __name__ == "__main__":
    main()
