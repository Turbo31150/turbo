#!/usr/bin/env python3
"""win_notification_ai.py — Filtre notifications Windows intelligent.

Groupe, priorise, resume les notifications.

Usage:
    python dev/win_notification_ai.py --once
    python dev/win_notification_ai.py --watch
    python dev/win_notification_ai.py --filter
    python dev/win_notification_ai.py --history
"""
import argparse
import json
import os
import sqlite3
import subprocess
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "notification_ai.db"
SPAM_APPS = {"microsoft.windows.cortana", "windows.immersivecontrolpanel", "microsoft.getstarted"}
URGENT_KEYWORDS = ["error", "critical", "failed", "urgent", "security", "virus", "threat"]


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, app TEXT, title TEXT, priority TEXT, grouped INTEGER)""")
    db.commit()
    return db


def get_recent_notifications():
    notifs = []
    try:
        out = subprocess.run(
            ["bash", "-Command",
             "Get-Process | Where-Object {$_.MainWindowTitle -ne ''} | "
             "Select-Object ProcessName,MainWindowTitle | ConvertTo-Json"],
            capture_output=True, text=True, timeout=10
        )
        if out.stdout.strip():
            data = json.loads(out.stdout)
            if isinstance(data, dict):
                data = [data]
            for w in data:
                notifs.append({
                    "app": w.get("ProcessName", "unknown"),
                    "title": w.get("MainWindowTitle", ""),
                })
    except Exception:
        pass
    return notifs


def classify_priority(title, app):
    title_lower = (title or "").lower()
    app_lower = (app or "").lower()
    if any(kw in title_lower for kw in URGENT_KEYWORDS):
        return "urgent"
    if app_lower in SPAM_APPS:
        return "spam"
    if any(kw in title_lower for kw in ["update", "download", "install"]):
        return "low"
    return "info"


def do_scan():
    db = init_db()
    notifs = get_recent_notifications()

    classified = []
    by_app = Counter()
    for n in notifs:
        priority = classify_priority(n["title"], n["app"])
        classified.append({**n, "priority": priority})
        by_app[n["app"]] += 1
        db.execute("INSERT INTO notifications (ts, app, title, priority, grouped) VALUES (?,?,?,?,?)",
                   (time.time(), n["app"], n["title"][:200], priority, 0))

    db.commit()
    db.close()

    return {
        "ts": datetime.now().isoformat(),
        "total": len(classified),
        "by_priority": {
            "urgent": sum(1 for c in classified if c["priority"] == "urgent"),
            "info": sum(1 for c in classified if c["priority"] == "info"),
            "low": sum(1 for c in classified if c["priority"] == "low"),
            "spam": sum(1 for c in classified if c["priority"] == "spam"),
        },
        "by_app": dict(by_app.most_common(10)),
        "urgent_items": [c for c in classified if c["priority"] == "urgent"],
        "recent": classified[:15],
    }


def main():
    parser = argparse.ArgumentParser(description="Windows Notification AI")
    parser.add_argument("--once", "--watch", action="store_true", help="Scan notifications")
    parser.add_argument("--filter", action="store_true", help="Filter")
    parser.add_argument("--smart-group", action="store_true", help="Smart grouping")
    parser.add_argument("--history", action="store_true", help="History")
    args = parser.parse_args()
    print(json.dumps(do_scan(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
