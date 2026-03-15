#!/usr/bin/env python3
"""win_workspace_profiles.py — Profils workspace Windows.

Sauvegarde/restore positions fenetres par contexte.

Usage:
    python dev/win_workspace_profiles.py --once
    python dev/win_workspace_profiles.py --create NAME
    python dev/win_workspace_profiles.py --activate NAME
    python dev/win_workspace_profiles.py --list
"""
import argparse
import ctypes
import json
import os
import sqlite3
import time
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "workspace_profiles.db"


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS profiles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, name TEXT UNIQUE, description TEXT,
        windows TEXT, activate_count INTEGER DEFAULT 0)""")
    db.commit()
    return db


def get_visible_windows():
    windows = []
    user32 = ctypes.windll.user32

    def enum_callback(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                title = buf.value
                if title and title.strip():
                    rect = ctypes.wintypes.RECT()
                    user32.GetWindowRect(hwnd, ctypes.byref(rect))
                    if rect.right - rect.left > 50 and rect.bottom - rect.top > 50:
                        windows.append({
                            "hwnd": hwnd,
                            "title": title[:100],
                            "x": rect.left, "y": rect.top,
                            "w": rect.right - rect.left,
                            "h": rect.bottom - rect.top,
                        })
        return True

    try:
        import ctypes.wintypes
        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.POINTER(ctypes.c_int))
        user32.EnumWindows(WNDENUMPROC(enum_callback), 0)
    except Exception:
        pass
    return windows


def do_list():
    db = init_db()
    # Seed defaults if empty
    count = db.execute("SELECT COUNT(*) FROM profiles").fetchone()[0]
    if count == 0:
        defaults = [
            ("dev", "Development workspace", []),
            ("trading", "Trading workspace", []),
            ("meeting", "Meeting workspace", []),
        ]
        for name, desc, wins in defaults:
            db.execute("INSERT OR IGNORE INTO profiles (ts, name, description, windows) VALUES (?,?,?,?)",
                       (time.time(), name, desc, json.dumps(wins)))
        db.commit()

    rows = db.execute("SELECT name, description, windows, activate_count FROM profiles ORDER BY name").fetchall()
    db.close()

    profiles = []
    for name, desc, wins_json, act_count in rows:
        wins = json.loads(wins_json) if wins_json else []
        profiles.append({
            "name": name,
            "description": desc,
            "windows_saved": len(wins),
            "activate_count": act_count,
        })

    current_windows = get_visible_windows()

    return {
        "ts": datetime.now().isoformat(),
        "profiles": profiles,
        "total_profiles": len(profiles),
        "current_windows": len(current_windows),
        "current_window_titles": [w["title"][:60] for w in current_windows[:10]],
    }


def do_create(name):
    db = init_db()
    windows = get_visible_windows()
    # Remove hwnd (not persistent)
    save_wins = [{"title": w["title"], "x": w["x"], "y": w["y"], "w": w["w"], "h": w["h"]} for w in windows]
    db.execute("INSERT OR REPLACE INTO profiles (ts, name, description, windows) VALUES (?,?,?,?)",
               (time.time(), name, f"Profile '{name}' — {len(save_wins)} windows",
                json.dumps(save_wins)))
    db.commit()
    db.close()
    return {"created": name, "windows_saved": len(save_wins)}


def main():
    parser = argparse.ArgumentParser(description="Windows Workspace Profiles")
    parser.add_argument("--once", "--list", action="store_true", help="List profiles")
    parser.add_argument("--create", metavar="NAME", help="Create profile")
    parser.add_argument("--activate", metavar="NAME", help="Activate profile")
    parser.add_argument("--export", action="store_true", help="Export profiles")
    args = parser.parse_args()

    if args.create:
        print(json.dumps(do_create(args.create), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(do_list(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
