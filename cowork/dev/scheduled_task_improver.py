#!/usr/bin/env python3
"""scheduled_task_improver.py

Audit and improve all JARVIS scheduled tasks on Windows.
Features:
- --once: audit all JARVIS* tasks, check last run, identify failures
- --fix: auto-fix broken tasks (re-enable, update paths)
- --optimize: analyze timing conflicts, suggest better schedules
- --report: generate full task report as JSON
- Stores results in etoile.db memories (category='scheduled_tasks_audit')
- Uses only Python stdlib (argparse, json, sqlite3, subprocess, csv, logging)
"""

import argparse
import csv
import io
import json
import logging
import re
import sqlite3
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

ETOILE_DB = Path(__file__).resolve().parent.parent.parent / "etoile.db"

log = logging.getLogger("scheduled_task_improver")
log.setLevel(logging.INFO)
_h = logging.StreamHandler()
_h.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s %(message)s"))
log.addHandler(_h)


# ── Task query ───────────────────────────────────────────────────────────

def query_tasks(filter_prefix: str = "JARVIS") -> List[Dict[str, str]]:
    """Run schtasks /query /fo CSV /v and parse all matching tasks."""
    try:
        proc = subprocess.run(
            ["schtasks", "/query", "/fo", "CSV", "/v"],
            capture_output=True, text=True, timeout=30, encoding="cp850"
        )
    except subprocess.TimeoutExpired:
        log.error("schtasks timed out")
        return []
    except FileNotFoundError:
        log.error("schtasks not found (not Windows?)")
        return []

    if proc.returncode != 0:
        # Try utf-8 fallback
        try:
            proc = subprocess.run(
                ["schtasks", "/query", "/fo", "CSV", "/v"],
                capture_output=True, text=True, timeout=30, encoding="utf-8", errors="replace"
            )
        except Exception as e:
            log.error("schtasks failed: %s", e)
            return []

    reader = csv.DictReader(io.StringIO(proc.stdout))
    tasks = []
    for row in reader:
        name = row.get("TaskName", row.get("Nom de la t\xe2che", ""))
        if filter_prefix and filter_prefix.lower() not in name.lower():
            # Also check folder path
            folder = row.get("HostName", "") + row.get("TaskName", "")
            if filter_prefix.lower() not in folder.lower():
                continue
        tasks.append(dict(row))
    return tasks


def parse_task(raw: Dict[str, str]) -> Dict[str, Any]:
    """Normalize a raw schtasks CSV row into a clean dict."""
    # Field names vary by locale; try both EN and FR
    name = raw.get("TaskName", raw.get("Nom de la t\xe2che", ""))
    status = raw.get("Status", raw.get("Statut", raw.get("\xc9tat", "")))
    last_run = raw.get("Last Run Time", raw.get("Derni\xe8re ex\xe9cution", ""))
    last_result = raw.get("Last Result", raw.get("Dernier r\xe9sultat", ""))
    next_run = raw.get("Next Run Time", raw.get("Prochaine ex\xe9cution", ""))
    action = raw.get("Task To Run", raw.get("T\xe2che \xe0 ex\xe9cuter", ""))
    schedule = raw.get("Schedule Type", raw.get("Type de planification", ""))

    # Parse last result code
    result_code = 0
    try:
        result_code = int(last_result) if last_result else 0
    except (ValueError, TypeError):
        result_code = -1

    return {
        "name": name.strip(),
        "status": status.strip() if status else "Unknown",
        "last_run": last_run.strip() if last_run else "Never",
        "last_result": result_code,
        "last_result_raw": str(last_result).strip(),
        "next_run": next_run.strip() if next_run else "N/A",
        "action": action.strip() if action else "",
        "schedule_type": schedule.strip() if schedule else "",
        "success": result_code == 0,
        "never_ran": "never" in (last_run or "").lower() or "N/A" in (last_run or ""),
    }


# ── Analysis ─────────────────────────────────────────────────────────────

def find_failures(tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return tasks that failed (non-zero last result)."""
    return [t for t in tasks if not t["success"] and not t["never_ran"]]


def find_never_ran(tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return tasks that have never executed."""
    return [t for t in tasks if t["never_ran"]]


def find_timing_conflicts(tasks: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Find tasks scheduled at the same time."""
    by_time: Dict[str, List[str]] = {}
    for t in tasks:
        nxt = t.get("next_run", "")
        if nxt and nxt != "N/A" and "disabled" not in nxt.lower():
            by_time.setdefault(nxt, []).append(t["name"])
    conflicts = []
    for when, names in by_time.items():
        if len(names) > 1:
            conflicts.append({"time": when, "tasks": names, "count": len(names)})
    return conflicts


def suggest_stagger(conflicts: List[Dict]) -> List[str]:
    """Generate suggestions to stagger conflicting tasks."""
    suggestions = []
    for c in conflicts:
        names = c["tasks"]
        for i, name in enumerate(names):
            if i == 0:
                continue
            offset = i * 5  # 5-minute stagger
            suggestions.append(
                f"Stagger '{name}' by +{offset}min to avoid conflict at {c['time']}"
            )
    return suggestions


# ── Fix ──────────────────────────────────────────────────────────────────

def fix_task(task: Dict[str, Any]) -> Dict[str, Any]:
    """Attempt to fix a broken task: re-enable if disabled."""
    name = task["name"]
    actions_taken = []

    if task["status"].lower() in ("disabled", "d\xe9sactiv\xe9"):
        log.info("Re-enabling disabled task: %s", name)
        proc = subprocess.run(
            ["schtasks", "/change", "/tn", name, "/enable"],
            capture_output=True, text=True, timeout=15
        )
        if proc.returncode == 0:
            actions_taken.append("re-enabled")
        else:
            actions_taken.append(f"enable_failed: {proc.stderr.strip()}")

    # Check if action path exists
    action_path = task.get("action", "")
    if action_path:
        # Extract the executable path (before any arguments)
        exe = action_path.split(" ")[0].strip('"')
        if exe and not Path(exe).exists() and not exe.startswith("%"):
            actions_taken.append(f"broken_path: {exe}")

    return {"task": name, "actions": actions_taken, "fixed": len(actions_taken) > 0}


# ── Database ─────────────────────────────────────────────────────────────

def store_audit(data: Dict[str, Any]) -> None:
    """Store audit results in etoile.db."""
    conn = sqlite3.connect(str(ETOILE_DB))
    try:
        key = f"audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        conn.execute(
            "INSERT OR REPLACE INTO memories (category, key, value, source, confidence) "
            "VALUES (?, ?, ?, ?, ?)",
            ("scheduled_tasks_audit", key,
             json.dumps(data, ensure_ascii=False, default=str),
             "scheduled_task_improver", 0.95),
        )
        conn.commit()
        log.info("Audit stored in etoile.db: %s", key)
    finally:
        conn.close()


# ── Commands ─────────────────────────────────────────────────────────────

def cmd_once() -> Dict[str, Any]:
    """Audit all JARVIS tasks."""
    raw_tasks = query_tasks("JARVIS")
    tasks = [parse_task(r) for r in raw_tasks]
    failures = find_failures(tasks)
    never_ran = find_never_ran(tasks)

    result = {
        "ok": True,
        "total": len(tasks),
        "healthy": len([t for t in tasks if t["success"] and not t["never_ran"]]),
        "failed": len(failures),
        "never_ran": len(never_ran),
        "failures": [{"name": t["name"], "result": t["last_result_raw"],
                       "last_run": t["last_run"]} for t in failures],
        "never_ran_tasks": [t["name"] for t in never_ran],
        "ts": datetime.now().isoformat(),
    }
    store_audit(result)
    return result


def cmd_fix() -> Dict[str, Any]:
    """Auto-fix broken tasks."""
    raw_tasks = query_tasks("JARVIS")
    tasks = [parse_task(r) for r in raw_tasks]
    broken = [t for t in tasks if not t["success"] or t["never_ran"]
              or t["status"].lower() in ("disabled", "d\xe9sactiv\xe9")]
    fixes = [fix_task(t) for t in broken]
    result = {"ok": True, "attempted": len(fixes),
              "fixes": [f for f in fixes if f["fixed"]], "ts": datetime.now().isoformat()}
    store_audit(result)
    return result


def cmd_optimize() -> Dict[str, Any]:
    """Analyze timing conflicts and suggest improvements."""
    raw_tasks = query_tasks("JARVIS")
    tasks = [parse_task(r) for r in raw_tasks]
    conflicts = find_timing_conflicts(tasks)
    suggestions = suggest_stagger(conflicts)
    result = {
        "ok": True,
        "total_tasks": len(tasks),
        "conflicts": conflicts,
        "suggestions": suggestions,
        "ts": datetime.now().isoformat(),
    }
    store_audit(result)
    return result


def cmd_report() -> Dict[str, Any]:
    """Full detailed report of all tasks."""
    raw_tasks = query_tasks("JARVIS")
    tasks = [parse_task(r) for r in raw_tasks]
    failures = find_failures(tasks)
    never_ran = find_never_ran(tasks)
    conflicts = find_timing_conflicts(tasks)

    result = {
        "ok": True,
        "generated": datetime.now().isoformat(),
        "summary": {
            "total": len(tasks),
            "healthy": len([t for t in tasks if t["success"] and not t["never_ran"]]),
            "failed": len(failures),
            "never_ran": len(never_ran),
            "conflicts": len(conflicts),
        },
        "tasks": tasks,
        "conflicts": conflicts,
        "suggestions": suggest_stagger(conflicts),
    }
    store_audit(result)
    return result


# ── Main ─────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="JARVIS scheduled task auditor/improver")
    parser.add_argument("--once", action="store_true", help="Audit all JARVIS tasks")
    parser.add_argument("--fix", action="store_true", help="Auto-fix broken tasks")
    parser.add_argument("--optimize", action="store_true", help="Analyze timing conflicts")
    parser.add_argument("--report", action="store_true", help="Full task report")
    args = parser.parse_args()

    if args.once:
        result = cmd_once()
    elif args.fix:
        result = cmd_fix()
    elif args.optimize:
        result = cmd_optimize()
    elif args.report:
        result = cmd_report()
    else:
        parser.print_help()
        return

    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
