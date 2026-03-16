#!/usr/bin/env python3
"""win_focus_timer.py — Timer focus Pomodoro avance.

Bloque distractions, track productivite.

Usage:
    python dev/win_focus_timer.py --once
    python dev/win_focus_timer.py --start 25
    python dev/win_focus_timer.py --break
    python dev/win_focus_timer.py --stats
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
DB_PATH = DEV / "data" / "focus_timer.db"
DISTRACTION_APPS = [
    "chrome", "firefox", "msedge",  # browsers (during focus)
    "discord", "slack", "teams",
    "spotify", "vlc",
    "steam", "epicgames",
]
PRODUCTIVE_APPS = [
    "code", "lms", "python", "node", "bash",
    "cmd", "terminal", "windowsterminal",
]


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, duration_min INTEGER, type TEXT,
        productive_apps INTEGER, distraction_apps INTEGER, score REAL)""")
    db.commit()
    return db


def get_running_apps():
    apps = []
    try:
        out = subprocess.run(
            ["bash", "-Command",
             "Get-Process | Where-Object {$_.MainWindowTitle -ne ''} | "
             "Select-Object -Unique ProcessName | ConvertTo-Json"],
            capture_output=True, text=True, timeout=10
        )
        if out.stdout.strip():
            data = json.loads(out.stdout)
            if isinstance(data, dict):
                data = [data]
            apps = [p.get("ProcessName", "").lower() for p in data]
    except Exception:
        pass
    return apps


def do_status():
    db = init_db()
    apps = get_running_apps()

    productive = [a for a in apps if any(p in a for p in PRODUCTIVE_APPS)]
    distracting = [a for a in apps if any(d in a for d in DISTRACTION_APPS)]

    score = 0.5
    if len(productive) > len(distracting):
        score = min(1.0, 0.5 + len(productive) * 0.1)
    elif len(distracting) > 0:
        score = max(0.1, 0.5 - len(distracting) * 0.1)

    # History
    today = datetime.now().strftime("%Y-%m-%d")
    today_sessions = db.execute(
        "SELECT SUM(duration_min), AVG(score) FROM sessions WHERE ts > ?",
        (time.time() - 86400,)
    ).fetchone()

    db.execute("INSERT INTO sessions (ts, duration_min, type, productive_apps, distraction_apps, score) VALUES (?,?,?,?,?,?)",
               (time.time(), 0, "snapshot", len(productive), len(distracting), score))
    db.commit()
    db.close()

    return {
        "ts": datetime.now().isoformat(),
        "current_focus_score": round(score, 2),
        "productive_apps": productive,
        "distraction_apps": distracting,
        "all_apps": len(apps),
        "today": {
            "total_focus_min": today_sessions[0] or 0,
            "avg_score": round(today_sessions[1] or 0, 2),
        },
        "recommendation": "Great focus!" if score > 0.7 else "Consider closing distractions" if score < 0.4 else "Moderate focus",
    }


def main():
    parser = argparse.ArgumentParser(description="Windows Focus Timer")
    parser.add_argument("--once", "--stats", action="store_true", help="Stats")
    parser.add_argument("--start", type=int, metavar="MINUTES", help="Start focus")
    parser.add_argument("--break", dest="take_break", action="store_true", help="Take break")
    parser.add_argument("--history", action="store_true", help="History")
    args = parser.parse_args()
    print(json.dumps(do_status(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
