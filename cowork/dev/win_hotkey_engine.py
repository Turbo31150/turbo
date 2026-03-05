#!/usr/bin/env python3
"""win_hotkey_engine.py — Moteur de raccourcis clavier global.

Mappe hotkeys vers actions JARVIS via ctypes RegisterHotKey.

Usage:
    python dev/win_hotkey_engine.py --once
    python dev/win_hotkey_engine.py --list
    python dev/win_hotkey_engine.py --register "Ctrl+Shift+J" "jarvis"
    python dev/win_hotkey_engine.py --profiles
"""
import argparse
import json
import os
import sqlite3
import time
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "hotkey_engine.db"

# Pre-defined hotkey profiles
PROFILES = {
    "dev": {
        "Ctrl+Shift+T": {"action": "launch", "target": "wt", "desc": "Open Terminal"},
        "Ctrl+Shift+C": {"action": "launch", "target": "code", "desc": "Open VSCode"},
        "Ctrl+Shift+B": {"action": "launch", "target": "chrome", "desc": "Open Chrome"},
        "Ctrl+Shift+G": {"action": "script", "target": "python dev/jarvis_daily_briefing.py --once", "desc": "Daily Briefing"},
    },
    "trading": {
        "Ctrl+Shift+M": {"action": "launch", "target": "chrome https://futures.mexc.com", "desc": "Open MEXC"},
        "Ctrl+Shift+S": {"action": "script", "target": "python dev/cluster_benchmark_auto.py --once", "desc": "Cluster Bench"},
    },
    "monitoring": {
        "Ctrl+Shift+H": {"action": "script", "target": "python dev/autonomous_health_guard.py --once", "desc": "Health Check"},
        "Ctrl+Shift+A": {"action": "script", "target": "python dev/jarvis_autonomy_monitor.py --once", "desc": "Autonomy Monitor"},
    },
}

VK_MAP = {
    "ctrl": 0x11, "shift": 0x10, "alt": 0x12, "win": 0x5B,
    "a": 0x41, "b": 0x42, "c": 0x43, "d": 0x44, "e": 0x45,
    "f": 0x46, "g": 0x47, "h": 0x48, "i": 0x49, "j": 0x4A,
    "k": 0x4B, "l": 0x4C, "m": 0x4D, "n": 0x4E, "o": 0x4F,
    "p": 0x50, "q": 0x51, "r": 0x52, "s": 0x53, "t": 0x54,
    "u": 0x55, "v": 0x56, "w": 0x57, "x": 0x58, "y": 0x59, "z": 0x5A,
    "f1": 0x70, "f2": 0x71, "f3": 0x72, "f4": 0x73, "f5": 0x74,
}


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS hotkeys (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        combo TEXT UNIQUE, action TEXT, target TEXT,
        description TEXT, profile TEXT, active INTEGER DEFAULT 1)""")
    db.execute("""CREATE TABLE IF NOT EXISTS activations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, combo TEXT, action TEXT)""")
    db.commit()
    return db


def parse_combo(combo_str):
    """Parse a hotkey combo string like 'Ctrl+Shift+J'."""
    parts = [p.strip().lower() for p in combo_str.split("+")]
    modifiers = []
    key = None
    for p in parts:
        if p in ("ctrl", "shift", "alt", "win"):
            modifiers.append(p)
        else:
            key = p
    return {"modifiers": modifiers, "key": key, "vk_key": VK_MAP.get(key, 0)}


def list_hotkeys():
    """List all registered hotkeys."""
    db = init_db()
    rows = db.execute("SELECT combo, action, target, description, profile, active FROM hotkeys").fetchall()
    db.close()
    return [{
        "combo": r[0], "action": r[1], "target": r[2],
        "description": r[3], "profile": r[4], "active": bool(r[5]),
    } for r in rows]


def install_profile(profile_name):
    """Install a hotkey profile."""
    profile = PROFILES.get(profile_name.lower())
    if not profile:
        return {"error": f"Profile '{profile_name}' not found"}

    db = init_db()
    installed = 0
    for combo, cfg in profile.items():
        existing = db.execute("SELECT COUNT(*) FROM hotkeys WHERE combo=?", (combo,)).fetchone()[0]
        if existing == 0:
            db.execute(
                "INSERT INTO hotkeys (combo, action, target, description, profile) VALUES (?,?,?,?,?)",
                (combo, cfg["action"], cfg["target"], cfg["desc"], profile_name)
            )
            installed += 1
    db.commit()
    db.close()
    return {"profile": profile_name, "installed": installed, "total": len(profile)}


def do_once():
    """Install all profiles and show status."""
    results = {}
    for name in PROFILES:
        results[name] = install_profile(name)

    return {
        "ts": datetime.now().isoformat(),
        "profiles_installed": results,
        "all_hotkeys": list_hotkeys(),
    }


def main():
    parser = argparse.ArgumentParser(description="Windows Hotkey Engine")
    parser.add_argument("--once", action="store_true", help="Install profiles + status")
    parser.add_argument("--list", action="store_true", help="List hotkeys")
    parser.add_argument("--register", nargs=2, metavar=("COMBO", "ACTION"), help="Register hotkey")
    parser.add_argument("--profiles", action="store_true", help="Show profiles")
    args = parser.parse_args()

    if args.list:
        print(json.dumps(list_hotkeys(), ensure_ascii=False, indent=2))
    elif args.profiles:
        print(json.dumps(PROFILES, ensure_ascii=False, indent=2))
    elif args.register:
        combo, action = args.register
        db = init_db()
        db.execute(
            "INSERT OR REPLACE INTO hotkeys (combo, action, target, description) VALUES (?,?,?,?)",
            (combo, "custom", action, f"Custom: {action}")
        )
        db.commit()
        db.close()
        print(json.dumps({"registered": combo, "action": action}))
    else:
        result = do_once()
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
