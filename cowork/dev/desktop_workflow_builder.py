#!/usr/bin/env python3
"""desktop_workflow_builder.py — Analyse les patterns desktop et cree des workflows.

Scanne les evenements window_manager (apps ouvertes, fenetre focus),
detecte les patterns d'utilisation, et genere des dominos desktop.

Usage:
    python dev/desktop_workflow_builder.py --once
    python dev/desktop_workflow_builder.py --scan
    python dev/desktop_workflow_builder.py --generate
"""
import argparse
import ctypes
import json
import os
import sqlite3
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "desktop_workflows.db"
from _paths import ETOILE_DB

# Known app categories
APP_CATEGORIES = {
    "code.exe": "dev", "code - insiders.exe": "dev",
    "windowsterminal.exe": "dev", "cmd.exe": "dev", "powershell.exe": "dev",
    "chrome.exe": "web", "msedge.exe": "web", "firefox.exe": "web",
    "explorer.exe": "files", "notepad.exe": "edit", "notepad++.exe": "edit",
    "discord.exe": "communication", "telegram.exe": "communication",
    "spotify.exe": "media", "vlc.exe": "media",
    "lm studio.exe": "ai", "ollama.exe": "ai",
    "electron.exe": "jarvis",
}

# Workflow templates based on detected patterns
WORKFLOW_TEMPLATES = {
    "dev_setup": {
        "name": "Setup Dev Environment",
        "triggers": ["mode dev", "setup dev", "environnement dev"],
        "steps": [
            {"action": "launch", "app": "WindowsTerminal"},
            {"action": "launch", "app": "Code"},
            {"action": "launch", "app": "Chrome", "url": "http://127.0.0.1:8080"},
            {"action": "snap", "window": "Code", "position": "left"},
            {"action": "snap", "window": "Chrome", "position": "right"},
        ],
    },
    "trading_setup": {
        "name": "Setup Trading Environment",
        "triggers": ["mode trading", "setup trading", "ouvre le trading"],
        "steps": [
            {"action": "launch", "app": "Chrome", "url": "https://futures.mexc.com"},
            {"action": "launch", "app": "WindowsTerminal"},
            {"action": "snap", "window": "Chrome", "position": "left"},
            {"action": "snap", "window": "Terminal", "position": "right"},
        ],
    },
    "monitoring_setup": {
        "name": "Setup Monitoring",
        "triggers": ["mode monitoring", "setup monitoring", "dashboard"],
        "steps": [
            {"action": "launch", "app": "Chrome", "url": "http://127.0.0.1:8080"},
            {"action": "maximize", "window": "Chrome"},
        ],
    },
}


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, windows TEXT, active_window TEXT, hour INTEGER, weekday INTEGER)""")
    db.execute("""CREATE TABLE IF NOT EXISTS workflows (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE, triggers TEXT, steps TEXT,
        created REAL, source TEXT DEFAULT 'detected')""")
    db.execute("""CREATE TABLE IF NOT EXISTS runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, snapshots INTEGER, workflows_generated INTEGER, report TEXT)""")
    db.commit()
    return db


def get_open_windows():
    """Get list of open windows via Win32 API."""
    windows = []
    try:
        user32 = ctypes.windll.user32

        def enum_callback(hwnd, _):
            if user32.IsWindowVisible(hwnd):
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buf = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buf, length + 1)
                    title = buf.value
                    if title and len(title) > 1:
                        # Get process name
                        pid = ctypes.c_ulong()
                        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                        windows.append({
                            "hwnd": hwnd,
                            "title": title[:100],
                            "pid": pid.value,
                        })
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
        user32.EnumWindows(WNDENUMPROC(enum_callback), 0)
    except Exception as e:
        print(f"[WARN] get_open_windows: {e}")

    return windows


def categorize_window(title):
    """Categorize a window by its title."""
    title_lower = title.lower()
    for app, cat in APP_CATEGORIES.items():
        if app.replace(".exe", "") in title_lower:
            return cat
    if "visual studio" in title_lower or ".py" in title_lower or ".js" in title_lower:
        return "dev"
    if "http" in title_lower or "www" in title_lower:
        return "web"
    if "trading" in title_lower or "mexc" in title_lower or "binance" in title_lower:
        return "trading"
    return "other"


def take_snapshot():
    """Take a snapshot of current desktop state."""
    windows = get_open_windows()
    now = datetime.now()

    snapshot = {
        "ts": time.time(),
        "hour": now.hour,
        "weekday": now.weekday(),
        "windows": [],
        "categories": Counter(),
    }

    for w in windows:
        cat = categorize_window(w["title"])
        snapshot["windows"].append({
            "title": w["title"],
            "category": cat,
        })
        snapshot["categories"][cat] += 1

    # Get active window
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        length = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        snapshot["active_window"] = buf.value[:100]
    except Exception:
        snapshot["active_window"] = ""

    snapshot["categories"] = dict(snapshot["categories"])
    return snapshot


def analyze_patterns(db, min_snapshots=5):
    """Analyze window patterns by hour/weekday."""
    rows = db.execute(
        "SELECT hour, weekday, windows, active_window FROM snapshots ORDER BY ts DESC LIMIT 200"
    ).fetchall()

    if len(rows) < min_snapshots:
        return []

    hourly_patterns = defaultdict(lambda: Counter())
    for r in rows:
        hour = r[0]
        try:
            windows = json.loads(r[2]) if r[2] else []
        except Exception:
            continue
        cats = [categorize_window(w.get("title", "")) for w in windows]
        for cat in cats:
            hourly_patterns[hour][cat] += 1

    patterns = []
    for hour, counts in sorted(hourly_patterns.items()):
        top_cats = counts.most_common(3)
        if top_cats:
            patterns.append({
                "hour": hour,
                "top_categories": [{"cat": c, "count": n} for c, n in top_cats],
                "total_windows": sum(counts.values()),
            })

    return patterns


def generate_workflow_from_pattern(pattern):
    """Generate a workflow suggestion from a detected pattern."""
    hour = pattern["hour"]
    cats = [c["cat"] for c in pattern["top_categories"]]

    if "dev" in cats and "web" in cats:
        return {
            "name": f"auto_dev_h{hour}",
            "description": f"Dev workflow detecte a {hour}h",
            "triggers": [f"mode dev {hour}h", f"setup {hour}h"],
            "steps": WORKFLOW_TEMPLATES["dev_setup"]["steps"],
            "source": f"pattern_h{hour}",
        }
    elif "trading" in cats:
        return {
            "name": f"auto_trading_h{hour}",
            "description": f"Trading workflow detecte a {hour}h",
            "triggers": [f"trading {hour}h"],
            "steps": WORKFLOW_TEMPLATES["trading_setup"]["steps"],
            "source": f"pattern_h{hour}",
        }
    return None


def do_scan():
    """Take a desktop snapshot and store it."""
    db = init_db()
    snapshot = take_snapshot()

    db.execute(
        "INSERT INTO snapshots (ts, windows, active_window, hour, weekday) VALUES (?,?,?,?,?)",
        (snapshot["ts"], json.dumps(snapshot["windows"]),
         snapshot.get("active_window", ""), snapshot["hour"], snapshot["weekday"])
    )
    db.commit()
    db.close()
    return snapshot


def do_once():
    """Full scan + analyze + generate cycle."""
    db = init_db()

    # Take snapshot
    snapshot = take_snapshot()
    db.execute(
        "INSERT INTO snapshots (ts, windows, active_window, hour, weekday) VALUES (?,?,?,?,?)",
        (snapshot["ts"], json.dumps(snapshot["windows"]),
         snapshot.get("active_window", ""), snapshot["hour"], snapshot["weekday"])
    )

    # Analyze patterns
    patterns = analyze_patterns(db)

    # Generate workflows
    workflows_generated = 0
    for p in patterns:
        wf = generate_workflow_from_pattern(p)
        if wf:
            existing = db.execute(
                "SELECT COUNT(*) FROM workflows WHERE name=?", (wf["name"],)
            ).fetchone()[0]
            if existing == 0:
                db.execute(
                    "INSERT INTO workflows (name, triggers, steps, created, source) VALUES (?,?,?,?,?)",
                    (wf["name"], json.dumps(wf["triggers"]),
                     json.dumps(wf["steps"]), time.time(), wf.get("source", "auto"))
                )
                workflows_generated += 1

    # Install templates
    for name, tmpl in WORKFLOW_TEMPLATES.items():
        existing = db.execute(
            "SELECT COUNT(*) FROM workflows WHERE name=?", (name,)
        ).fetchone()[0]
        if existing == 0:
            db.execute(
                "INSERT INTO workflows (name, triggers, steps, created, source) VALUES (?,?,?,?,?)",
                (name, json.dumps(tmpl["triggers"]),
                 json.dumps(tmpl["steps"]), time.time(), "template")
            )

    snap_count = db.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0]

    report = {
        "ts": datetime.now().isoformat(),
        "snapshot": {
            "windows": len(snapshot["windows"]),
            "categories": snapshot["categories"],
            "active": snapshot.get("active_window", ""),
        },
        "total_snapshots": snap_count,
        "patterns_found": len(patterns),
        "workflows_generated": workflows_generated,
    }

    db.execute(
        "INSERT INTO runs (ts, snapshots, workflows_generated, report) VALUES (?,?,?,?)",
        (time.time(), snap_count, workflows_generated, json.dumps(report))
    )
    db.commit()
    db.close()
    return report


def main():
    parser = argparse.ArgumentParser(description="Desktop Workflow Builder")
    parser.add_argument("--once", action="store_true", help="Full scan + analyze + generate")
    parser.add_argument("--scan", action="store_true", help="Take desktop snapshot only")
    parser.add_argument("--generate", action="store_true", help="Generate workflows from patterns")
    args = parser.parse_args()

    if args.scan:
        result = do_scan()
        print(json.dumps({
            "windows": len(result["windows"]),
            "categories": result["categories"],
            "active": result.get("active_window", ""),
        }, ensure_ascii=False, indent=2))
    else:
        result = do_once()
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
