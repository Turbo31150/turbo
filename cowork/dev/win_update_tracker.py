#!/usr/bin/env python3
"""win_update_tracker.py — Suivi mises a jour Windows.

Historique, KB pendantes, rapport compliance.

Usage:
    python dev/win_update_tracker.py --once
    python dev/win_update_tracker.py --check
    python dev/win_update_tracker.py --history
    python dev/win_update_tracker.py --report
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
DB_PATH = DEV / "data" / "update_tracker.db"


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS updates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        kb_id TEXT, description TEXT, installed_on TEXT,
        hotfix_id TEXT, scan_ts REAL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS scans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, total_installed INTEGER, newest_date TEXT,
        oldest_date TEXT, report TEXT)""")
    db.commit()
    return db


def get_installed_updates():
    """Get installed Windows updates via wmic."""
    updates = []
    try:
        result = subprocess.run(
            ["wmic", "qfe", "get", "HotFixID,Description,InstalledOn", "/format:csv"],
            capture_output=True, text=True, timeout=30
        )
        for line in result.stdout.strip().split("\n"):
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 4 and parts[1]:
                updates.append({
                    "description": parts[1],
                    "hotfix_id": parts[2],
                    "installed_on": parts[3],
                })
    except Exception:
        pass

    # Fallback: PowerShell
    if not updates:
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-HotFix | Select-Object HotFixID,Description,InstalledOn | ConvertTo-Json"],
                capture_output=True, text=True, timeout=30
            )
            data = json.loads(result.stdout)
            if isinstance(data, dict):
                data = [data]
            for item in data:
                updates.append({
                    "hotfix_id": item.get("HotFixID", ""),
                    "description": item.get("Description", ""),
                    "installed_on": str(item.get("InstalledOn", ""))[:20],
                })
        except Exception:
            pass

    return updates


def do_check():
    """Check Windows update status."""
    db = init_db()
    updates = get_installed_updates()

    # Store updates
    for u in updates:
        existing = db.execute(
            "SELECT COUNT(*) FROM updates WHERE hotfix_id=?", (u["hotfix_id"],)
        ).fetchone()[0]
        if existing == 0:
            db.execute(
                "INSERT INTO updates (kb_id, description, installed_on, hotfix_id, scan_ts) VALUES (?,?,?,?,?)",
                (u["hotfix_id"], u["description"], u["installed_on"], u["hotfix_id"], time.time())
            )

    # Analyze dates
    dates = [u["installed_on"] for u in updates if u["installed_on"]]
    newest = max(dates) if dates else "N/A"
    oldest = min(dates) if dates else "N/A"

    # Categorize
    security = [u for u in updates if "security" in u.get("description", "").lower()]
    other = [u for u in updates if "security" not in u.get("description", "").lower()]

    report = {
        "ts": datetime.now().isoformat(),
        "total_installed": len(updates),
        "security_updates": len(security),
        "other_updates": len(other),
        "newest_update": newest,
        "oldest_update": oldest,
        "recent_updates": updates[:10],
    }

    db.execute(
        "INSERT INTO scans (ts, total_installed, newest_date, oldest_date, report) VALUES (?,?,?,?,?)",
        (time.time(), len(updates), newest, oldest, json.dumps(report))
    )
    db.commit()
    db.close()
    return report


def show_history():
    """Show update scan history."""
    db = init_db()
    rows = db.execute(
        "SELECT ts, total_installed, newest_date FROM scans ORDER BY ts DESC LIMIT 10"
    ).fetchall()
    db.close()
    return [{
        "ts": datetime.fromtimestamp(r[0]).isoformat(),
        "total": r[1], "newest": r[2],
    } for r in rows]


def main():
    parser = argparse.ArgumentParser(description="Windows Update Tracker")
    parser.add_argument("--once", "--check", action="store_true", help="Check updates")
    parser.add_argument("--history", action="store_true", help="Show history")
    parser.add_argument("--report", action="store_true", help="Report")
    args = parser.parse_args()

    if args.history:
        print(json.dumps(show_history(), ensure_ascii=False, indent=2))
    else:
        result = do_check()
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
