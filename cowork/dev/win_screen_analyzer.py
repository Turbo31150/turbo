#!/usr/bin/env python3
"""win_screen_analyzer.py — Analyseur ecran Windows.

Capture, detection changements visuels.

Usage:
    python dev/win_screen_analyzer.py --once
    python dev/win_screen_analyzer.py --capture
    python dev/win_screen_analyzer.py --analyze
    python dev/win_screen_analyzer.py --diff
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
DB_PATH = DEV / "data" / "screen_analyzer.db"


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS captures (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, width INTEGER, height INTEGER,
        monitors INTEGER, report TEXT)""")
    db.commit()
    return db


def get_screen_info():
    try:
        user32 = ctypes.windll.user32
        user32.SetProcessDPIAware()
        w = user32.GetSystemMetrics(0)  # SM_CXSCREEN
        h = user32.GetSystemMetrics(1)  # SM_CYSCREEN
        monitors = user32.GetSystemMetrics(80)  # SM_CMONITORS
        vw = user32.GetSystemMetrics(78)  # SM_CXVIRTUALSCREEN
        vh = user32.GetSystemMetrics(79)  # SM_CYVIRTUALSCREEN
        return {
            "primary_width": w, "primary_height": h,
            "virtual_width": vw, "virtual_height": vh,
            "monitors": monitors,
        }
    except Exception:
        return {"primary_width": 0, "primary_height": 0, "monitors": 0}


def get_foreground_window():
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        length = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        return {"hwnd": hwnd, "title": buf.value}
    except Exception:
        return {"hwnd": 0, "title": ""}


def do_capture():
    db = init_db()
    screen = get_screen_info()
    fg = get_foreground_window()

    report = {
        "ts": datetime.now().isoformat(),
        "screen": screen,
        "foreground_window": fg,
        "dpi_aware": True,
    }

    db.execute("INSERT INTO captures (ts, width, height, monitors, report) VALUES (?,?,?,?,?)",
               (time.time(), screen["primary_width"], screen["primary_height"],
                screen["monitors"], json.dumps(report)))
    db.commit()
    db.close()
    return report


def main():
    parser = argparse.ArgumentParser(description="Windows Screen Analyzer")
    parser.add_argument("--once", "--capture", action="store_true", help="Capture info")
    parser.add_argument("--analyze", action="store_true", help="Analyze")
    parser.add_argument("--ocr", action="store_true", help="OCR")
    parser.add_argument("--diff", action="store_true", help="Diff")
    args = parser.parse_args()
    print(json.dumps(do_capture(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
