#!/usr/bin/env python3
"""win_virtual_desktop.py — Gestion bureaux virtuels Windows.

Cree, switch, assigne apps aux bureaux thematiques.

Usage:
    python dev/win_virtual_desktop.py --once
    python dev/win_virtual_desktop.py --list
    python dev/win_virtual_desktop.py --create "Dev"
    python dev/win_virtual_desktop.py --switch 1
"""
import argparse
import ctypes
import json
import os
import sqlite3
import subprocess
import time
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "virtual_desktop.db"

DESKTOP_PROFILES = {
    "dev": {"name": "Dev", "apps": ["Code", "Terminal", "Chrome"], "layout": "split"},
    "trading": {"name": "Trading", "apps": ["Chrome"], "layout": "fullscreen"},
    "monitoring": {"name": "Monitoring", "apps": ["Chrome"], "layout": "fullscreen"},
    "gaming": {"name": "Gaming", "apps": ["Steam"], "layout": "fullscreen"},
}


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS desktops (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, action TEXT, desktop_name TEXT, details TEXT)""")
    db.commit()
    return db


def create_desktop():
    """Create a new virtual desktop via keyboard shortcut."""
    try:
        user32 = ctypes.windll.user32
        # Win+Ctrl+D = new desktop
        VK_LWIN = 0x5B
        VK_CONTROL = 0x11
        VK_D = 0x44
        user32.keybd_event(VK_LWIN, 0, 0, 0)
        user32.keybd_event(VK_CONTROL, 0, 0, 0)
        user32.keybd_event(VK_D, 0, 0, 0)
        time.sleep(0.1)
        user32.keybd_event(VK_D, 0, 2, 0)
        user32.keybd_event(VK_CONTROL, 0, 2, 0)
        user32.keybd_event(VK_LWIN, 0, 2, 0)
        return True
    except Exception:
        return False


def switch_desktop(direction="right"):
    """Switch to next/previous virtual desktop."""
    try:
        user32 = ctypes.windll.user32
        VK_LWIN = 0x5B
        VK_CONTROL = 0x11
        VK_LEFT = 0x25
        VK_RIGHT = 0x27
        vk_arrow = VK_RIGHT if direction == "right" else VK_LEFT
        user32.keybd_event(VK_LWIN, 0, 0, 0)
        user32.keybd_event(VK_CONTROL, 0, 0, 0)
        user32.keybd_event(vk_arrow, 0, 0, 0)
        time.sleep(0.1)
        user32.keybd_event(vk_arrow, 0, 2, 0)
        user32.keybd_event(VK_CONTROL, 0, 2, 0)
        user32.keybd_event(VK_LWIN, 0, 2, 0)
        return True
    except Exception:
        return False


def do_once():
    """Show current desktop status and profiles."""
    db = init_db()
    result = {
        "ts": datetime.now().isoformat(),
        "profiles": DESKTOP_PROFILES,
        "actions_available": ["create", "switch", "close"],
    }
    db.close()
    return result


def main():
    parser = argparse.ArgumentParser(description="Windows Virtual Desktop Manager")
    parser.add_argument("--once", "--list", action="store_true", help="List profiles")
    parser.add_argument("--create", metavar="NAME", help="Create new desktop")
    parser.add_argument("--switch", metavar="N", type=int, help="Switch desktop by index")
    args = parser.parse_args()

    if args.create:
        ok = create_desktop()
        print(json.dumps({"action": "create", "name": args.create, "ok": ok}))
    elif args.switch is not None:
        for _ in range(abs(args.switch)):
            switch_desktop("right" if args.switch > 0 else "left")
        print(json.dumps({"action": "switch", "direction": args.switch}))
    else:
        result = do_once()
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
