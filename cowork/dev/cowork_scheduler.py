#!/usr/bin/env python3
"""cowork_scheduler.py — Centralized scheduler for all COWORK periodic tasks.

Manages a SQLite-backed schedule of recurring COWORK scripts.
Checks which tasks are due, runs them via subprocess, tracks results.

CLI:
    --once       : run all due tasks (next_run <= now)
    --status     : show all scheduled tasks and next run (JSON)
    --register   : add/update a task (--task-name, --script, --args, --interval)
    --list       : list all tasks (JSON)
    --enable     : enable a task by name (--task-name)
    --disable    : disable a task by name (--task-name)
    --run-task   : force-run a specific task by name (--task-name)
    --reset      : reset all schedules (next_run = now)
    --init       : initialize DB with default tasks

Stdlib-only (sqlite3, json, argparse, subprocess, time).
"""

import argparse
import json
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data"
DB_PATH = DATA_DIR / "cowork_gaps.db"
PYTHON = sys.executable

# ── Default tasks ────────────────────────────────────────────────────────────

DEFAULT_TASKS = [
    {
        "task_name": "health_check",
        "script_name": "cluster_health_watchdog.py",
        "args": ["--once"],
        "interval_minutes": 5,
    },
    {
        "task_name": "alert_monitor",
        "script_name": "proactive_alert_monitor.py",
        "args": ["--once"],
        "interval_minutes": 5,
    },
    {
        "task_name": "quality_check",
        "script_name": "dispatch_quality_scorer.py",
        "args": ["--once"],
        "interval_minutes": 15,
    },
    {
        "task_name": "trend_analysis",
        "script_name": "dispatch_trend_analyzer.py",
        "args": ["--once"],
        "interval_minutes": 30,
    },
    {
        "task_name": "full_cycle",
        "script_name": "cowork_full_cycle.py",
        "args": ["--quick"],
        "interval_minutes": 60,
    },
    {
        "task_name": "daily_report",
        "script_name": "daily_cowork_report.py",
        "args": ["--once"],
        "interval_minutes": 1440,
    },
    {
        "task_name": "auto_improve",
        "script_name": "cowork_auto_improver.py",
        "args": ["--once"],
        "interval_minutes": 120,
    },
    {
        "task_name": "self_tests",
        "script_name": "cowork_self_test_runner.py",
        "args": ["--level", "3"],
        "interval_minutes": 360,
    },
]

# ── Database ─────────────────────────────────────────────────────────────────


def init_db(conn):
    """Create the cowork_schedules table if it does not exist."""
    conn.execute("""CREATE TABLE IF NOT EXISTS cowork_schedules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_name TEXT UNIQUE NOT NULL,
        script_name TEXT NOT NULL,
        args TEXT NOT NULL DEFAULT '[]',
        interval_minutes INTEGER NOT NULL DEFAULT 60,
        last_run TEXT,
        next_run TEXT NOT NULL,
        enabled INTEGER NOT NULL DEFAULT 1,
        run_count INTEGER NOT NULL DEFAULT 0,
        last_status TEXT
    )""")
    conn.commit()


def get_db():
    """Open (and initialize) the database."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def seed_defaults(conn):
    """Insert default tasks (skip if already present)."""
    now = datetime.now().isoformat()
    inserted = 0
    for task in DEFAULT_TASKS:
        try:
            conn.execute(
                """INSERT INTO cowork_schedules
                   (task_name, script_name, args, interval_minutes, next_run, enabled, run_count)
                   VALUES (?, ?, ?, ?, ?, 1, 0)""",
                (
                    task["task_name"],
                    task["script_name"],
                    json.dumps(task["args"]),
                    task["interval_minutes"],
                    now,
                ),
            )
            inserted += 1
        except sqlite3.IntegrityError:
            pass  # already exists
    conn.commit()
    return inserted


# ── Task execution ───────────────────────────────────────────────────────────


def run_task(task_row):
    """Run a single scheduled task via subprocess. Returns result dict."""
    script_path = SCRIPT_DIR / task_row["script_name"]
    args_list = json.loads(task_row["args"]) if task_row["args"] else []

    if not script_path.exists():
        return {
            "task_name": task_row["task_name"],
            "status": "missing",
            "error": f"{task_row['script_name']} not found",
            "duration_ms": 0,
        }

    cmd = [PYTHON, str(script_path)] + args_list
    t0 = time.time()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(SCRIPT_DIR),
        )
        elapsed_ms = int((time.time() - t0) * 1000)

        status = "ok" if result.returncode == 0 else "error"
        output_summary = None
        if result.stdout.strip():
            try:
                parsed = json.loads(result.stdout)
                output_summary = _extract_summary(parsed)
            except json.JSONDecodeError:
                output_summary = {"output_lines": len(result.stdout.strip().split("\n"))}

        return {
            "task_name": task_row["task_name"],
            "script": task_row["script_name"],
            "status": status,
            "returncode": result.returncode,
            "duration_ms": elapsed_ms,
            "summary": output_summary,
            "error": result.stderr[:300] if result.returncode != 0 and result.stderr else None,
        }

    except subprocess.TimeoutExpired:
        return {
            "task_name": task_row["task_name"],
            "script": task_row["script_name"],
            "status": "timeout",
            "duration_ms": 120000,
        }
    except Exception as e:
        return {
            "task_name": task_row["task_name"],
            "script": task_row["script_name"],
            "status": "error",
            "duration_ms": int((time.time() - t0) * 1000),
            "error": str(e)[:300],
        }


def _extract_summary(data):
    """Pull top-level scalar/small values from script output for the summary."""
    if not isinstance(data, dict):
        return None
    summary = {}
    for key, value in list(data.items())[:8]:
        if isinstance(value, (str, int, float, bool, type(None))):
            summary[key] = value
    return summary if summary else {"keys": list(data.keys())[:5]}


def update_after_run(conn, task_name, status, now_iso):
    """Update last_run, next_run, run_count, last_status after execution."""
    row = conn.execute(
        "SELECT interval_minutes, run_count FROM cowork_schedules WHERE task_name = ?",
        (task_name,),
    ).fetchone()
    if not row:
        return
    next_run = (
        datetime.fromisoformat(now_iso) + timedelta(minutes=row["interval_minutes"])
    ).isoformat()
    conn.execute(
        """UPDATE cowork_schedules
           SET last_run = ?, next_run = ?, run_count = ?, last_status = ?
           WHERE task_name = ?""",
        (now_iso, next_run, row["run_count"] + 1, status, task_name),
    )
    conn.commit()


# ── CLI commands ─────────────────────────────────────────────────────────────


def cmd_once(conn):
    """Run all due tasks (next_run <= now)."""
    now = datetime.now()
    now_iso = now.isoformat()

    due_tasks = conn.execute(
        "SELECT * FROM cowork_schedules WHERE enabled = 1 AND next_run <= ? ORDER BY next_run",
        (now_iso,),
    ).fetchall()

    results = []
    for task in due_tasks:
        result = run_task(task)
        update_after_run(conn, task["task_name"], result["status"], now_iso)
        results.append(result)

    total_ok = sum(1 for r in results if r["status"] == "ok")
    total_err = sum(1 for r in results if r["status"] != "ok")
    total_ms = sum(r.get("duration_ms", 0) for r in results)

    # Count tasks not yet due
    not_due = conn.execute(
        "SELECT COUNT(*) as cnt FROM cowork_schedules WHERE enabled = 1 AND next_run > ?",
        (now_iso,),
    ).fetchone()["cnt"]

    return {
        "timestamp": now_iso,
        "command": "once",
        "tasks_due": len(due_tasks),
        "tasks_not_due": not_due,
        "ok": total_ok,
        "errors": total_err,
        "total_duration_ms": total_ms,
        "results": results,
    }


def cmd_status(conn):
    """Show all scheduled tasks with status and time until next run."""
    now = datetime.now()
    now_iso = now.isoformat()
    rows = conn.execute(
        "SELECT * FROM cowork_schedules ORDER BY enabled DESC, next_run ASC"
    ).fetchall()

    tasks = []
    for row in rows:
        next_run = row["next_run"]
        try:
            next_dt = datetime.fromisoformat(next_run)
            delta = next_dt - now
            seconds_until = int(delta.total_seconds())
            is_due = seconds_until <= 0
            if is_due:
                time_until = "DUE NOW"
            else:
                hours, remainder = divmod(seconds_until, 3600)
                minutes, secs = divmod(remainder, 60)
                parts = []
                if hours > 0:
                    parts.append(f"{hours}h")
                if minutes > 0:
                    parts.append(f"{minutes}m")
                if secs > 0 and hours == 0:
                    parts.append(f"{secs}s")
                time_until = " ".join(parts) if parts else "< 1s"
        except (ValueError, TypeError):
            seconds_until = 0
            is_due = True
            time_until = "UNKNOWN"

        tasks.append({
            "task_name": row["task_name"],
            "script_name": row["script_name"],
            "args": json.loads(row["args"]) if row["args"] else [],
            "interval_minutes": row["interval_minutes"],
            "enabled": bool(row["enabled"]),
            "run_count": row["run_count"],
            "last_run": row["last_run"],
            "next_run": row["next_run"],
            "last_status": row["last_status"],
            "is_due": is_due,
            "time_until_next": time_until,
            "seconds_until_next": max(0, seconds_until),
        })

    due_count = sum(1 for t in tasks if t["is_due"] and t["enabled"])
    enabled_count = sum(1 for t in tasks if t["enabled"])

    return {
        "timestamp": now_iso,
        "command": "status",
        "total_tasks": len(tasks),
        "enabled": enabled_count,
        "disabled": len(tasks) - enabled_count,
        "due_now": due_count,
        "tasks": tasks,
    }


def cmd_list(conn):
    """List all tasks (compact view)."""
    rows = conn.execute(
        "SELECT task_name, script_name, interval_minutes, enabled, run_count, last_status "
        "FROM cowork_schedules ORDER BY task_name"
    ).fetchall()

    tasks = []
    for row in rows:
        tasks.append({
            "task_name": row["task_name"],
            "script_name": row["script_name"],
            "interval_minutes": row["interval_minutes"],
            "enabled": bool(row["enabled"]),
            "run_count": row["run_count"],
            "last_status": row["last_status"],
        })

    return {
        "timestamp": datetime.now().isoformat(),
        "command": "list",
        "total_tasks": len(tasks),
        "tasks": tasks,
    }


def cmd_register(conn, task_name, script_name, args_list, interval):
    """Add or update a scheduled task."""
    now_iso = datetime.now().isoformat()
    args_json = json.dumps(args_list)

    existing = conn.execute(
        "SELECT id FROM cowork_schedules WHERE task_name = ?", (task_name,)
    ).fetchone()

    if existing:
        conn.execute(
            """UPDATE cowork_schedules
               SET script_name = ?, args = ?, interval_minutes = ?
               WHERE task_name = ?""",
            (script_name, args_json, interval, task_name),
        )
        action = "updated"
    else:
        conn.execute(
            """INSERT INTO cowork_schedules
               (task_name, script_name, args, interval_minutes, next_run, enabled, run_count)
               VALUES (?, ?, ?, ?, ?, 1, 0)""",
            (task_name, script_name, args_json, interval, now_iso),
        )
        action = "created"
    conn.commit()

    return {
        "timestamp": now_iso,
        "command": "register",
        "action": action,
        "task_name": task_name,
        "script_name": script_name,
        "args": args_list,
        "interval_minutes": interval,
    }


def cmd_toggle(conn, task_name, enable):
    """Enable or disable a task."""
    row = conn.execute(
        "SELECT id FROM cowork_schedules WHERE task_name = ?", (task_name,)
    ).fetchone()
    if not row:
        return {
            "timestamp": datetime.now().isoformat(),
            "command": "enable" if enable else "disable",
            "status": "error",
            "error": f"Task '{task_name}' not found",
        }
    conn.execute(
        "UPDATE cowork_schedules SET enabled = ? WHERE task_name = ?",
        (1 if enable else 0, task_name),
    )
    conn.commit()
    return {
        "timestamp": datetime.now().isoformat(),
        "command": "enable" if enable else "disable",
        "status": "ok",
        "task_name": task_name,
        "enabled": enable,
    }


def cmd_run_task(conn, task_name):
    """Force-run a specific task regardless of schedule."""
    row = conn.execute(
        "SELECT * FROM cowork_schedules WHERE task_name = ?", (task_name,)
    ).fetchone()
    if not row:
        return {
            "timestamp": datetime.now().isoformat(),
            "command": "run-task",
            "status": "error",
            "error": f"Task '{task_name}' not found",
        }
    now_iso = datetime.now().isoformat()
    result = run_task(row)
    update_after_run(conn, task_name, result["status"], now_iso)
    return {
        "timestamp": now_iso,
        "command": "run-task",
        "result": result,
    }


def cmd_reset(conn):
    """Reset all next_run to now (all tasks become due)."""
    now_iso = datetime.now().isoformat()
    conn.execute("UPDATE cowork_schedules SET next_run = ?", (now_iso,))
    conn.commit()
    count = conn.execute("SELECT COUNT(*) as cnt FROM cowork_schedules").fetchone()["cnt"]
    return {
        "timestamp": now_iso,
        "command": "reset",
        "status": "ok",
        "tasks_reset": count,
    }


def cmd_init(conn):
    """Initialize DB with default tasks."""
    inserted = seed_defaults(conn)
    total = conn.execute("SELECT COUNT(*) as cnt FROM cowork_schedules").fetchone()["cnt"]
    return {
        "timestamp": datetime.now().isoformat(),
        "command": "init",
        "status": "ok",
        "inserted": inserted,
        "total_tasks": total,
    }


# ── Main ─────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="COWORK Scheduler — centralized periodic task runner"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--once", action="store_true", help="Run all due tasks")
    group.add_argument("--status", action="store_true", help="Show task statuses (JSON)")
    group.add_argument("--register", action="store_true", help="Register/update a task")
    group.add_argument("--list", action="store_true", help="List all tasks (JSON)")
    group.add_argument("--enable", action="store_true", help="Enable a task")
    group.add_argument("--disable", action="store_true", help="Disable a task")
    group.add_argument("--run-task", action="store_true", help="Force-run a task")
    group.add_argument("--reset", action="store_true", help="Reset all schedules to now")
    group.add_argument("--init", action="store_true", help="Initialize with default tasks")

    # Parameters for --register
    parser.add_argument("--task-name", type=str, help="Task name (for register/enable/disable/run-task)")
    parser.add_argument("--script", type=str, help="Script filename (for register)")
    parser.add_argument("--args", type=str, default="[]", help='Args as JSON array (for register), e.g. \'["--once"]\'')
    parser.add_argument("--interval", type=int, help="Interval in minutes (for register)")

    args = parser.parse_args()

    conn = get_db()

    # Auto-seed defaults on first use if table is empty
    count = conn.execute("SELECT COUNT(*) as cnt FROM cowork_schedules").fetchone()["cnt"]
    if count == 0:
        seed_defaults(conn)

    try:
        if args.once:
            result = cmd_once(conn)
        elif args.status:
            result = cmd_status(conn)
        elif args.list:
            result = cmd_list(conn)
        elif args.register:
            if not args.task_name or not args.script or args.interval is None:
                print(json.dumps({
                    "error": "--register requires --task-name, --script, and --interval",
                    "usage": "cowork_scheduler.py --register --task-name NAME --script SCRIPT.py --args '[\"--once\"]' --interval 60",
                }))
                sys.exit(1)
            try:
                args_list = json.loads(args.args)
            except json.JSONDecodeError:
                args_list = [args.args]
            result = cmd_register(conn, args.task_name, args.script, args_list, args.interval)
        elif args.enable:
            if not args.task_name:
                print(json.dumps({"error": "--enable requires --task-name"}))
                sys.exit(1)
            result = cmd_toggle(conn, args.task_name, True)
        elif args.disable:
            if not args.task_name:
                print(json.dumps({"error": "--disable requires --task-name"}))
                sys.exit(1)
            result = cmd_toggle(conn, args.task_name, False)
        elif args.run_task:
            if not args.task_name:
                print(json.dumps({"error": "--run-task requires --task-name"}))
                sys.exit(1)
            result = cmd_run_task(conn, args.task_name)
        elif args.reset:
            result = cmd_reset(conn)
        elif args.init:
            result = cmd_init(conn)
        else:
            parser.print_help()
            sys.exit(1)

        print(json.dumps(result, indent=2, ensure_ascii=False))

    finally:
        conn.close()


if __name__ == "__main__":
    main()
