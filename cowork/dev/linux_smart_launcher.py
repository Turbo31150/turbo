#!/usr/bin/env python3
"""win_smart_launcher.py — Lanceur intelligent Windows.

Lance les bonnes apps selon le contexte (heure, jour, tache).

Usage:
    python dev/win_smart_launcher.py --once
    python dev/win_smart_launcher.py --launch dev
    python dev/win_smart_launcher.py --learn
    python dev/win_smart_launcher.py --suggest
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
DB_PATH = DEV / "data" / "smart_launcher.db"
DEFAULT_PROFILES = {
    "dev": ["code", "WindowsTerminal", "LM Studio"],
    "trading": ["chrome --new-window https://www.mexc.com", "chrome --new-window https://www.tradingview.com"],
    "morning": ["chrome", "outlook"],
    "meeting": ["ms-teams", "notepad"],
}


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS launch_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, hour INTEGER, weekday INTEGER,
        context TEXT, apps TEXT)""")
    db.execute("""CREATE TABLE IF NOT EXISTS profiles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE, apps TEXT, auto_hour INTEGER)""")
    db.commit()
    return db


def seed_profiles():
    db = init_db()
    for name, apps in DEFAULT_PROFILES.items():
        try:
            db.execute("INSERT OR IGNORE INTO profiles (name, apps, auto_hour) VALUES (?,?,?)",
                       (name, json.dumps(apps), -1))
        except Exception:
            pass
    db.commit()
    db.close()


def get_running_apps():
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
            return [p.get("ProcessName", "") for p in data]
    except Exception:
        pass
    return []


def suggest_context():
    hour = datetime.now().hour
    weekday = datetime.now().weekday()
    if hour < 9:
        return "morning"
    elif hour < 12:
        return "dev"
    elif hour < 14:
        return "meeting"
    elif hour < 18:
        return "dev"
    elif weekday < 5:
        return "trading"
    return "dev"


def do_status():
    seed_profiles()
    db = init_db()

    profiles = db.execute("SELECT name, apps, auto_hour FROM profiles ORDER BY name").fetchall()
    running = get_running_apps()
    suggested = suggest_context()

    # Recent launches
    recent = db.execute(
        "SELECT ts, context, apps FROM launch_history ORDER BY ts DESC LIMIT 5"
    ).fetchall()
    db.close()

    return {
        "ts": datetime.now().isoformat(),
        "current_hour": datetime.now().hour,
        "weekday": datetime.now().strftime("%A"),
        "suggested_context": suggested,
        "running_apps": running[:10],
        "profiles": [
            {"name": r[0], "apps": json.loads(r[1]) if r[1] else [], "auto_hour": r[2]}
            for r in profiles
        ],
        "recent_launches": [
            {"ts": datetime.fromtimestamp(r[0]).isoformat(), "context": r[1]}
            for r in recent
        ],
    }


def main():
    parser = argparse.ArgumentParser(description="Windows Smart Launcher")
    parser.add_argument("--once", "--suggest", action="store_true", help="Suggest apps")
    parser.add_argument("--launch", metavar="CONTEXT", help="Launch context profile")
    parser.add_argument("--learn", action="store_true", help="Learn from usage")
    parser.add_argument("--history", action="store_true", help="History")
    args = parser.parse_args()
    print(json.dumps(do_status(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
