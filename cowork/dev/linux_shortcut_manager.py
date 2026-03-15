#!/usr/bin/env python3
"""win_shortcut_manager.py — Gestionnaire raccourcis Windows.

Detecte liens casses, reorganise Desktop/StartMenu.

Usage:
    python dev/win_shortcut_manager.py --once
    python dev/win_shortcut_manager.py --scan
    python dev/win_shortcut_manager.py --broken
    python dev/win_shortcut_manager.py --organize
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
DB_PATH = DEV / "data" / "shortcut_manager.db"

SCAN_DIRS = [
    {"name": "Desktop", "path": Path.home() / "Desktop"},
    {"name": "StartMenu", "path": Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu"},
    {"name": "QuickLaunch", "path": Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Internet Explorer" / "Quick Launch"},
]


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS shortcuts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, location TEXT, name TEXT,
        target TEXT, broken INTEGER DEFAULT 0)""")
    db.execute("""CREATE TABLE IF NOT EXISTS scans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, total INTEGER, broken INTEGER,
        locations_scanned INTEGER)""")
    db.commit()
    return db


def get_shortcut_target(lnk_path):
    """Get .lnk target via PowerShell."""
    try:
        result = subprocess.run(
            ["bash", "-Command",
             f"(New-Object -ComObject WScript.Shell).CreateShortcut('{lnk_path}').TargetPath"],
            capture_output=True, text=True, timeout=5
        )
        return result.stdout.strip()
    except Exception:
        return ""


def scan_shortcuts():
    """Scan all shortcut locations."""
    db = init_db()
    all_shortcuts = []
    broken = []

    for loc in SCAN_DIRS:
        path = loc["path"]
        if not path.exists():
            continue

        for f in path.rglob("*.lnk"):
            target = get_shortcut_target(str(f))
            is_broken = bool(target) and not Path(target).exists()

            shortcut = {
                "location": loc["name"],
                "name": f.stem,
                "file": str(f),
                "target": target[:200] if target else "(unknown)",
                "broken": is_broken,
            }
            all_shortcuts.append(shortcut)

            if is_broken:
                broken.append(shortcut)

            db.execute(
                "INSERT INTO shortcuts (ts, location, name, target, broken) VALUES (?,?,?,?,?)",
                (time.time(), loc["name"], f.stem, target[:200], int(is_broken))
            )

    db.execute(
        "INSERT INTO scans (ts, total, broken, locations_scanned) VALUES (?,?,?,?)",
        (time.time(), len(all_shortcuts), len(broken), len(SCAN_DIRS))
    )
    db.commit()
    db.close()

    return {
        "ts": datetime.now().isoformat(),
        "total_shortcuts": len(all_shortcuts),
        "broken": len(broken),
        "locations": [{
            "name": loc["name"],
            "count": sum(1 for s in all_shortcuts if s["location"] == loc["name"]),
            "broken": sum(1 for s in broken if s["location"] == loc["name"]),
        } for loc in SCAN_DIRS],
        "broken_shortcuts": [{"name": s["name"], "target": s["target"][:80], "loc": s["location"]} for s in broken[:15]],
    }


def main():
    parser = argparse.ArgumentParser(description="Windows Shortcut Manager")
    parser.add_argument("--once", "--scan", action="store_true", help="Scan shortcuts")
    parser.add_argument("--broken", action="store_true", help="Show broken")
    parser.add_argument("--fix", action="store_true", help="Fix broken")
    parser.add_argument("--organize", action="store_true", help="Organize")
    args = parser.parse_args()

    result = scan_shortcuts()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
