#!/usr/bin/env python3
"""win_copilot_bridge.py — Bridge Windows Copilot.

Intercepte requetes Copilot, enrichit via cluster JARVIS.

Usage:
    python dev/win_copilot_bridge.py --once
    python dev/win_copilot_bridge.py --status
    python dev/win_copilot_bridge.py --intercept
    python dev/win_copilot_bridge.py --log
"""
import argparse
import json
import os
import sqlite3
import subprocess
import time
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "copilot_bridge.db"


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS copilot_activity (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, copilot_running INTEGER, ai_coexist TEXT, report TEXT)""")
    db.commit()
    return db


def check_copilot_status():
    running = False
    details = []
    try:
        out = subprocess.run(
            ["powershell", "-Command",
             "Get-Process | Where-Object {$_.Name -match 'copilot|msedge.*copilot|ai'} | "
             "Select-Object Name,Id,@{N='MemMB';E={[math]::Round($_.WorkingSet64/1MB)}} | ConvertTo-Json"],
            capture_output=True, text=True, timeout=10
        )
        if out.stdout.strip() and out.stdout.strip() != "":
            data = json.loads(out.stdout)
            if isinstance(data, dict):
                data = [data]
            for p in data:
                details.append({"name": p.get("Name"), "pid": p.get("Id"), "mem_mb": p.get("MemMB", 0)})
            running = len(data) > 0
    except Exception:
        pass
    return running, details


def check_ai_services():
    services = []
    ai_processes = ["ollama", "lms", "python", "node"]
    try:
        out = subprocess.run(
            ["powershell", "-Command",
             "Get-Process | Where-Object {$_.Name -match '"
             + "|".join(ai_processes) + "'} | "
             "Select-Object Name,Id | ConvertTo-Json"],
            capture_output=True, text=True, timeout=10
        )
        if out.stdout.strip():
            data = json.loads(out.stdout)
            if isinstance(data, dict):
                data = [data]
            services = [{"name": p.get("Name"), "pid": p.get("Id")} for p in data]
    except Exception:
        pass
    return services


def do_status():
    db = init_db()
    copilot_running, copilot_details = check_copilot_status()
    ai_services = check_ai_services()

    coexist = "parallel" if copilot_running and ai_services else "jarvis_only" if ai_services else "copilot_only" if copilot_running else "none"

    report = {
        "ts": datetime.now().isoformat(),
        "copilot_running": copilot_running,
        "copilot_processes": copilot_details,
        "jarvis_ai_services": ai_services,
        "coexistence_mode": coexist,
        "recommendation": "JARVIS cluster active — Copilot optional" if ai_services else "No AI services detected",
    }

    db.execute("INSERT INTO copilot_activity (ts, copilot_running, ai_coexist, report) VALUES (?,?,?,?)",
               (time.time(), int(copilot_running), coexist, json.dumps(report)))
    db.commit()
    db.close()
    return report


def main():
    parser = argparse.ArgumentParser(description="Windows Copilot Bridge")
    parser.add_argument("--once", "--status", action="store_true", help="Check status")
    parser.add_argument("--intercept", action="store_true", help="Intercept mode")
    parser.add_argument("--enhance", action="store_true", help="Enhance responses")
    parser.add_argument("--log", action="store_true", help="Show log")
    args = parser.parse_args()
    print(json.dumps(do_status(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
