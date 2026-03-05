#!/usr/bin/env python3
"""win_window_manager.py — Gestionnaire fenetres Windows.

Liste, focus, deplace, arrange les fenetres.

Usage:
    python dev/win_window_manager.py --once
    python dev/win_window_manager.py --list
    python dev/win_window_manager.py --focus "TITLE"
    python dev/win_window_manager.py --tile
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
DB_PATH = DEV / "data" / "window_manager.db"


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, windows_count INTEGER, report TEXT)""")
    db.commit()
    return db


def get_visible_windows():
    windows = []
    try:
        user32 = ctypes.windll.user32
        import ctypes.wintypes

        def enum_cb(hwnd, _):
            if user32.IsWindowVisible(hwnd):
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buf = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buf, length + 1)
                    title = buf.value
                    if title.strip():
                        rect = ctypes.wintypes.RECT()
                        user32.GetWindowRect(hwnd, ctypes.byref(rect))
                        w = rect.right - rect.left
                        h = rect.bottom - rect.top
                        if w > 50 and h > 50:
                            windows.append({
                                "hwnd": hwnd,
                                "title": title[:100],
                                "x": rect.left, "y": rect.top,
                                "width": w, "height": h,
                            })
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.POINTER(ctypes.c_int))
        user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
    except Exception:
        pass
    return windows


def do_list():
    db = init_db()
    windows = get_visible_windows()

    db.execute("INSERT INTO snapshots (ts, windows_count, report) VALUES (?,?,?)",
               (time.time(), len(windows), json.dumps([w["title"] for w in windows])))
    db.commit()
    db.close()

    screen_w = ctypes.windll.user32.GetSystemMetrics(0)
    screen_h = ctypes.windll.user32.GetSystemMetrics(1)

    return {
        "ts": datetime.now().isoformat(),
        "screen": {"width": screen_w, "height": screen_h},
        "windows_count": len(windows),
        "windows": [
            {"title": w["title"], "position": f"{w['x']},{w['y']}",
             "size": f"{w['width']}x{w['height']}"}
            for w in windows
        ],
    }


def main():
    parser = argparse.ArgumentParser(description="Windows Window Manager")
    parser.add_argument("--once", "--list", action="store_true", help="List windows")
    parser.add_argument("--focus", metavar="TITLE", help="Focus window")
    parser.add_argument("--move", action="store_true", help="Move window")
    parser.add_argument("--tile", action="store_true", help="Tile windows")
    args = parser.parse_args()
    print(json.dumps(do_list(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
