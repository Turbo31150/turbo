#!/usr/bin/env python3
"""win_app_controller.py — Controle avance des applications Windows.

Lance/ferme/focus apps par nom, profils de workspace,
ctypes user32.dll integration.

Usage:
    python dev/win_app_controller.py --once
    python dev/win_app_controller.py --launch "Code"
    python dev/win_app_controller.py --close "Notepad"
    python dev/win_app_controller.py --focus "Chrome"
    python dev/win_app_controller.py --list
    python dev/win_app_controller.py --profiles
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
DB_PATH = DEV / "data" / "app_controller.db"

APP_PATHS = {
    "code": "code", "vscode": "code",
    "chrome": "chrome", "google chrome": "chrome",
    "edge": "msedge",
    "terminal": "wt", "windowsterminal": "wt",
    "notepad": "notepad",
    "explorer": "explorer",
    "discord": os.path.expandvars(r"%LOCALAPPDATA%\Discord\app-*\Discord.exe"),
    "spotify": os.path.expandvars(r"%APPDATA%\Spotify\Spotify.exe"),
}

PROFILES = {
    "dev": ["Code", "WindowsTerminal", "Chrome"],
    "trading": ["Chrome", "WindowsTerminal"],
    "monitoring": ["Chrome"],
    "gaming": ["Steam"],
}


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS actions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, action TEXT, app TEXT, result TEXT)""")
    db.commit()
    return db


def get_windows():
    """List all visible windows."""
    windows = []
    user32 = ctypes.windll.user32

    def callback(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                if buf.value:
                    windows.append({"hwnd": hwnd, "title": buf.value[:100]})
        return True

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
    user32.EnumWindows(WNDENUMPROC(callback), 0)
    return windows


def find_window(app_name):
    """Find a window by app name."""
    windows = get_windows()
    app_lower = app_name.lower()
    for w in windows:
        if app_lower in w["title"].lower():
            return w
    return None


def launch_app(app_name):
    """Launch an application."""
    cmd = APP_PATHS.get(app_name.lower(), app_name)
    try:
        subprocess.Popen(cmd, shell=True)
        return {"ok": True, "app": app_name, "action": "launched"}
    except Exception as e:
        return {"ok": False, "app": app_name, "error": str(e)}


def focus_app(app_name):
    """Focus a window by app name."""
    w = find_window(app_name)
    if w:
        user32 = ctypes.windll.user32
        user32.ShowWindow(w["hwnd"], 9)  # SW_RESTORE
        user32.SetForegroundWindow(w["hwnd"])
        return {"ok": True, "app": app_name, "title": w["title"]}
    return {"ok": False, "app": app_name, "error": "window not found"}


def close_app(app_name):
    """Close a window by app name."""
    w = find_window(app_name)
    if w:
        user32 = ctypes.windll.user32
        WM_CLOSE = 0x0010
        user32.PostMessageW(w["hwnd"], WM_CLOSE, 0, 0)
        return {"ok": True, "app": app_name, "title": w["title"]}
    return {"ok": False, "app": app_name, "error": "window not found"}


def apply_profile(profile_name):
    """Apply a workspace profile."""
    apps = PROFILES.get(profile_name.lower(), [])
    if not apps:
        return {"error": f"Profile '{profile_name}' not found"}
    results = []
    for app in apps:
        w = find_window(app)
        if w:
            results.append(focus_app(app))
        else:
            results.append(launch_app(app))
    return {"profile": profile_name, "apps": results}


def list_windows():
    """List all visible windows."""
    windows = get_windows()
    return [{"title": w["title"]} for w in windows if len(w["title"]) > 2]


def main():
    parser = argparse.ArgumentParser(description="Windows App Controller")
    parser.add_argument("--once", action="store_true", help="List windows")
    parser.add_argument("--launch", metavar="APP", help="Launch app")
    parser.add_argument("--close", metavar="APP", help="Close app")
    parser.add_argument("--focus", metavar="APP", help="Focus app")
    parser.add_argument("--list", action="store_true", help="List windows")
    parser.add_argument("--profiles", action="store_true", help="Show profiles")
    parser.add_argument("--profile", metavar="NAME", help="Apply profile")
    args = parser.parse_args()

    db = init_db()

    if args.launch:
        result = launch_app(args.launch)
        db.execute("INSERT INTO actions (ts, action, app, result) VALUES (?,?,?,?)",
                   (time.time(), "launch", args.launch, json.dumps(result)))
        db.commit()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.close:
        result = close_app(args.close)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.focus:
        result = focus_app(args.focus)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.profile:
        result = apply_profile(args.profile)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.profiles:
        print(json.dumps(PROFILES, ensure_ascii=False, indent=2))
    else:
        result = list_windows()
        print(json.dumps(result, ensure_ascii=False, indent=2))

    db.close()


if __name__ == "__main__":
    main()
