#!/usr/bin/env python3
"""win_task_scheduler_pro.py — Task scheduler pro. Uses schtasks /query /fo csv. List/add/remove tasks.
Usage: python dev/win_task_scheduler_pro.py --list --once
"""
import argparse, json, os, sqlite3, subprocess, time, csv, io
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "task_scheduler_pro.db"


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL,
        task_name TEXT,
        next_run TEXT,
        status TEXT,
        last_run TEXT,
        last_result TEXT,
        author TEXT,
        schedule_type TEXT
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS managed_tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL,
        task_name TEXT UNIQUE,
        command TEXT,
        schedule TEXT,
        active INTEGER DEFAULT 1,
        created_by TEXT DEFAULT 'jarvis'
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS actions_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL,
        action TEXT,
        task_name TEXT,
        success INTEGER,
        details TEXT
    )""")
    db.commit()
    return db


def query_schtasks():
    """Query Windows Task Scheduler via schtasks."""
    try:
        proc = subprocess.run(
            ["schtasks", "/query", "/fo", "csv", "/v"],
            capture_output=True, text=True, timeout=30
        )
        output = proc.stdout
        if not output.strip():
            # Try without /v
            proc = subprocess.run(
                ["schtasks", "/query", "/fo", "csv"],
                capture_output=True, text=True, timeout=30
            )
            output = proc.stdout

        reader = csv.DictReader(io.StringIO(output))
        tasks = []
        for row in reader:
            # Headers may vary by locale
            task_name = (row.get("TaskName") or row.get("Nom de la t\u00e2che") or
                        row.get(list(row.keys())[0] if row.keys() else "", "")).strip('"').strip()
            next_run = (row.get("Next Run Time") or row.get("Prochaine ex\u00e9cution") or "").strip('"').strip()
            status = (row.get("Status") or row.get("Statut") or row.get("\u00c9tat") or "").strip('"').strip()
            last_run = (row.get("Last Run Time") or row.get("Derni\u00e8re ex\u00e9cution") or "").strip('"').strip()
            last_result = (row.get("Last Result") or row.get("Dernier r\u00e9sultat") or "").strip('"').strip()
            author = (row.get("Author") or row.get("Auteur") or "").strip('"').strip()
            schedule_type = (row.get("Schedule Type") or row.get("Type de planification") or "").strip('"').strip()

            if task_name:
                tasks.append({
                    "task_name": task_name,
                    "next_run": next_run,
                    "status": status,
                    "last_run": last_run,
                    "last_result": last_result,
                    "author": author,
                    "schedule_type": schedule_type
                })
        return tasks
    except Exception as e:
        return [{"error": str(e)}]


def do_list():
    """List all scheduled tasks."""
    db = init_db()
    tasks = query_schtasks()
    if tasks and "error" in tasks[0]:
        db.close()
        return {"ts": datetime.now().isoformat(), "error": tasks[0]["error"]}

    # Store in DB
    for t in tasks[:200]:
        db.execute(
            "INSERT INTO tasks (ts, task_name, next_run, status, last_run, last_result, author, schedule_type) VALUES (?,?,?,?,?,?,?,?)",
            (time.time(), t["task_name"], t.get("next_run", ""), t.get("status", ""),
             t.get("last_run", ""), t.get("last_result", ""), t.get("author", ""),
             t.get("schedule_type", ""))
        )
    db.commit()

    # Filter JARVIS tasks
    jarvis_tasks = [t for t in tasks if "jarvis" in t["task_name"].lower()]
    ready = [t for t in tasks if t.get("status", "").lower() in ("ready", "pr\u00eat")]
    running = [t for t in tasks if t.get("status", "").lower() in ("running", "en cours")]
    disabled = [t for t in tasks if t.get("status", "").lower() in ("disabled", "d\u00e9sactiv\u00e9")]

    db.close()
    return {
        "ts": datetime.now().isoformat(),
        "total_tasks": len(tasks),
        "ready": len(ready),
        "running": len(running),
        "disabled": len(disabled),
        "jarvis_tasks": len(jarvis_tasks),
        "sample_tasks": [
            {"name": t["task_name"], "status": t.get("status", ""), "next_run": t.get("next_run", "")}
            for t in tasks[:20]
        ]
    }


def do_add(task_name=None, command=None, schedule=None):
    """Add a new scheduled task."""
    db = init_db()
    if not task_name:
        task_name = f"JARVIS_Task_{int(time.time())}"
    if not command:
        command = f"python {DEV / 'auto_monitor.py'} --once"
    if not schedule:
        schedule = "DAILY"

    # Map schedule to schtasks format
    schedule_map = {
        "DAILY": "/sc DAILY /st 06:00",
        "HOURLY": "/sc HOURLY",
        "WEEKLY": "/sc WEEKLY /d MON /st 06:00",
        "MINUTE": "/sc MINUTE /mo 30",
        "ONCE": "/sc ONCE /st 23:59 /sd 01/01/2030"
    }
    sched_args = schedule_map.get(schedule.upper(), f"/sc {schedule}")

    try:
        cmd_str = f'schtasks /create /tn "{task_name}" /tr "{command}" {sched_args} /f'
        proc = subprocess.run(
            cmd_str, shell=True, capture_output=True, text=True, timeout=15
        )
        success = proc.returncode == 0

        db.execute(
            "INSERT OR REPLACE INTO managed_tasks (ts, task_name, command, schedule, active) VALUES (?,?,?,?,?)",
            (time.time(), task_name, command, schedule, 1)
        )
        db.execute(
            "INSERT INTO actions_log (ts, action, task_name, success, details) VALUES (?,?,?,?,?)",
            (time.time(), "add", task_name, int(success), proc.stdout + proc.stderr)
        )
        db.commit()
        db.close()

        return {
            "ts": datetime.now().isoformat(),
            "action": "add",
            "task_name": task_name,
            "command": command,
            "schedule": schedule,
            "success": success,
            "output": (proc.stdout + proc.stderr).strip()[:300]
        }
    except Exception as e:
        db.close()
        return {"ts": datetime.now().isoformat(), "action": "add", "error": str(e)}


def do_remove(task_name=None):
    """Remove a scheduled task."""
    db = init_db()
    if not task_name:
        # Remove last managed task
        row = db.execute(
            "SELECT task_name FROM managed_tasks WHERE active=1 ORDER BY ts DESC LIMIT 1"
        ).fetchone()
        if row:
            task_name = row[0]
        else:
            db.close()
            return {"ts": datetime.now().isoformat(), "action": "remove", "status": "no_task_to_remove"}

    try:
        proc = subprocess.run(
            f'schtasks /delete /tn "{task_name}" /f',
            shell=True, capture_output=True, text=True, timeout=15
        )
        success = proc.returncode == 0
        db.execute("UPDATE managed_tasks SET active=0 WHERE task_name=?", (task_name,))
        db.execute(
            "INSERT INTO actions_log (ts, action, task_name, success, details) VALUES (?,?,?,?,?)",
            (time.time(), "remove", task_name, int(success), proc.stdout + proc.stderr)
        )
        db.commit()
        db.close()
        return {
            "ts": datetime.now().isoformat(),
            "action": "remove",
            "task_name": task_name,
            "success": success
        }
    except Exception as e:
        db.close()
        return {"ts": datetime.now().isoformat(), "action": "remove", "error": str(e)}


def do_status():
    """Show task scheduler status."""
    db = init_db()
    managed = db.execute("SELECT COUNT(*) FROM managed_tasks WHERE active=1").fetchone()[0]
    total_actions = db.execute("SELECT COUNT(*) FROM actions_log").fetchone()[0]
    recent_actions = db.execute(
        "SELECT action, task_name, success, ts FROM actions_log ORDER BY ts DESC LIMIT 5"
    ).fetchall()
    db.close()

    return {
        "ts": datetime.now().isoformat(),
        "status": "ok",
        "db": str(DB_PATH),
        "managed_tasks": managed,
        "total_actions": total_actions,
        "recent_actions": [
            {"action": r[0], "task": r[1], "success": bool(r[2]),
             "ts": datetime.fromtimestamp(r[3]).isoformat()}
            for r in recent_actions
        ]
    }


def main():
    parser = argparse.ArgumentParser(description="Task scheduler pro — Windows scheduled tasks management")
    parser.add_argument("--list", action="store_true", help="List all scheduled tasks")
    parser.add_argument("--add", action="store_true", help="Add a new scheduled task")
    parser.add_argument("--remove", action="store_true", help="Remove a scheduled task")
    parser.add_argument("--status", action="store_true", help="Show scheduler status")
    parser.add_argument("--task-name", metavar="NAME", help="Task name for add/remove")
    parser.add_argument("--command", metavar="CMD", help="Command for new task")
    parser.add_argument("--schedule", metavar="SCHED", default="DAILY", help="Schedule type (DAILY/HOURLY/WEEKLY)")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    args = parser.parse_args()

    if args.list:
        result = do_list()
    elif args.add:
        result = do_add(args.task_name, args.command, args.schedule)
    elif args.remove:
        result = do_remove(args.task_name)
    elif args.status:
        result = do_status()
    else:
        result = do_status()

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
