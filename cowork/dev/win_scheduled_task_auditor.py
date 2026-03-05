#!/usr/bin/env python3
"""win_scheduled_task_auditor.py — Auditeur taches planifiees Windows.

Detecte taches suspectes/malveillantes.

Usage:
    python dev/win_scheduled_task_auditor.py --once
    python dev/win_scheduled_task_auditor.py --audit
    python dev/win_scheduled_task_auditor.py --suspicious
    python dev/win_scheduled_task_auditor.py --report
"""
import argparse
import csv
import io
import json
import os
import sqlite3
import subprocess
import time
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "scheduled_task_auditor.db"
TRUSTED_AUTHORS = {"microsoft", "microsoft corporation", "intel", "nvidia", "realtek", "adobe"}
SUSPICIOUS_PATHS = ["%temp%", "appdata\\local\\temp", "downloads\\", "public\\"]


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS audits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, total_tasks INTEGER, suspicious INTEGER,
        microsoft INTEGER, third_party INTEGER)""")
    db.commit()
    return db


def get_scheduled_tasks():
    tasks = []
    try:
        out = subprocess.run(
            ["schtasks", "/query", "/fo", "csv", "/v"],
            capture_output=True, text=True, timeout=30
        )
        reader = csv.DictReader(io.StringIO(out.stdout))
        for row in reader:
            tasks.append({
                "name": row.get("TaskName", "").strip(),
                "status": row.get("Status", "").strip(),
                "author": row.get("Author", "").strip(),
                "task_to_run": row.get("Task To Run", "").strip(),
                "next_run": row.get("Next Run Time", "").strip(),
                "last_run": row.get("Last Run Time", "").strip(),
            })
    except Exception:
        pass
    return tasks


def classify_task(task):
    author = (task.get("author") or "").lower()
    exe = (task.get("task_to_run") or "").lower()
    name = (task.get("name") or "").lower()

    is_microsoft = any(t in author for t in TRUSTED_AUTHORS)
    is_suspicious = False
    reasons = []

    if any(p in exe for p in SUSPICIOUS_PATHS):
        is_suspicious = True
        reasons.append("Suspicious executable path")
    if not task.get("author"):
        is_suspicious = True
        reasons.append("No author")
    if "powershell" in exe and "encoded" in exe.lower():
        is_suspicious = True
        reasons.append("Encoded PowerShell")
    if "cmd /c" in exe and ("http" in exe or "ftp" in exe):
        is_suspicious = True
        reasons.append("Network command in task")

    return {
        "is_microsoft": is_microsoft,
        "is_suspicious": is_suspicious,
        "reasons": reasons,
    }


def do_audit():
    db = init_db()
    tasks = get_scheduled_tasks()

    microsoft_count = 0
    third_party = 0
    suspicious = []

    for t in tasks:
        c = classify_task(t)
        if c["is_microsoft"]:
            microsoft_count += 1
        else:
            third_party += 1
        if c["is_suspicious"]:
            suspicious.append({**t, "reasons": c["reasons"]})

    db.execute("INSERT INTO audits (ts, total_tasks, suspicious, microsoft, third_party) VALUES (?,?,?,?,?)",
               (time.time(), len(tasks), len(suspicious), microsoft_count, third_party))
    db.commit()
    db.close()

    return {
        "ts": datetime.now().isoformat(),
        "total_tasks": len(tasks),
        "microsoft": microsoft_count,
        "third_party": third_party,
        "suspicious": len(suspicious),
        "suspicious_details": suspicious[:15],
    }


def main():
    parser = argparse.ArgumentParser(description="Windows Scheduled Task Auditor")
    parser.add_argument("--once", "--audit", action="store_true", help="Audit tasks")
    parser.add_argument("--suspicious", action="store_true", help="Show suspicious")
    parser.add_argument("--disable", metavar="NAME", help="Disable task")
    parser.add_argument("--report", action="store_true", help="Report")
    args = parser.parse_args()
    print(json.dumps(do_audit(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
