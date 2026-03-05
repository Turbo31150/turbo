#!/usr/bin/env python3
"""win_smart_launcher_v2.py — Smart launcher v2 (#244).

Learns from process creation patterns, predicts which apps to launch
by hour/weekday, maintains launch profiles, auto-suggest.

Usage:
    python dev/win_smart_launcher_v2.py --once
    python dev/win_smart_launcher_v2.py --launch APP
    python dev/win_smart_launcher_v2.py --learn
    python dev/win_smart_launcher_v2.py --predict
    python dev/win_smart_launcher_v2.py --history
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
DB_PATH = DEV / "data" / "smart_launcher_v2.db"


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("""CREATE TABLE IF NOT EXISTS launches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        app_name TEXT NOT NULL,
        exe_path TEXT,
        hour INTEGER,
        weekday INTEGER,
        source TEXT DEFAULT 'observed'
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS profiles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        profile_name TEXT UNIQUE NOT NULL,
        apps TEXT NOT NULL,
        created_at TEXT NOT NULL,
        last_used TEXT
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS predictions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        hour INTEGER,
        weekday INTEGER,
        predicted_apps TEXT,
        confidence REAL
    )""")
    db.commit()
    return db


def get_running_processes():
    """Get list of running processes via tasklist."""
    try:
        out = subprocess.check_output(
            ["tasklist", "/fo", "csv", "/nh"],
            stderr=subprocess.DEVNULL, text=True, timeout=15
        )
        processes = []
        for line in out.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            parts = line.split('","')
            if len(parts) >= 2:
                name = parts[0].strip('"')
                pid = parts[1].strip('"')
                processes.append({"name": name, "pid": pid})
        return processes
    except Exception as e:
        return [{"error": str(e)}]


def do_learn():
    """Learn from currently running processes."""
    db = init_db()
    now = datetime.now()
    processes = get_running_processes()
    # Filter to meaningful user apps (skip system processes)
    system_procs = {
        "system", "registry", "smss.exe", "csrss.exe", "wininit.exe", "services.exe",
        "lsass.exe", "svchost.exe", "fontdrvhost.exe", "dwm.exe", "conhost.exe",
        "sihost.exe", "taskhostw.exe", "ctfmon.exe", "runtimebroker.exe",
        "shellexperiencehost.exe", "searchhost.exe", "startmenuexperiencehost.exe",
        "textinputhost.exe", "widgetservice.exe", "systemsettings.exe",
        "applicationframehost.exe", "dllhost.exe", "tasklist.exe", "cmd.exe",
        "searchindexer.exe", "searchprotocolhost.exe", "searchfilterhost.exe",
        "securityhealthservice.exe", "securityhealthsystray.exe", "audiodg.exe",
        "spoolsv.exe", "wudfhost.exe", "dashost.exe", "msiexec.exe",
    }

    learned = []
    seen = set()
    for p in processes:
        name = p.get("name", "").lower()
        if name in system_procs or name in seen or "error" in p:
            continue
        seen.add(name)
        db.execute(
            "INSERT INTO launches (ts, app_name, hour, weekday, source) VALUES (?,?,?,?,?)",
            (now.isoformat(), name, now.hour, now.weekday(), "learned"),
        )
        learned.append(name)

    db.commit()
    result = {
        "ts": now.isoformat(),
        "action": "learn",
        "processes_scanned": len(processes),
        "apps_learned": len(learned),
        "apps": learned[:30],
        "hour": now.hour,
        "weekday": now.strftime("%A"),
    }
    db.close()
    return result


def do_predict():
    """Predict which apps should be launched now based on history."""
    db = init_db()
    now = datetime.now()
    hour = now.hour
    weekday = now.weekday()

    # Get apps frequently launched at this hour
    hour_apps = db.execute(
        "SELECT app_name, COUNT(*) as cnt FROM launches WHERE hour=? GROUP BY app_name ORDER BY cnt DESC LIMIT 10",
        (hour,),
    ).fetchall()

    # Get apps frequently launched on this weekday
    weekday_apps = db.execute(
        "SELECT app_name, COUNT(*) as cnt FROM launches WHERE weekday=? GROUP BY app_name ORDER BY cnt DESC LIMIT 10",
        (weekday,),
    ).fetchall()

    # Combined scoring
    scores = Counter()
    for name, cnt in hour_apps:
        scores[name] += cnt * 2  # Hour match weighted more
    for name, cnt in weekday_apps:
        scores[name] += cnt

    total_records = db.execute("SELECT COUNT(*) FROM launches").fetchone()[0]
    predictions = []
    for name, score in scores.most_common(10):
        confidence = min(score / max(total_records * 0.1, 1), 1.0)
        predictions.append({"app": name, "score": score, "confidence": round(confidence, 3)})

    # Store prediction
    db.execute(
        "INSERT INTO predictions (ts, hour, weekday, predicted_apps, confidence) VALUES (?,?,?,?,?)",
        (now.isoformat(), hour, weekday, json.dumps([p["app"] for p in predictions[:5]]),
         predictions[0]["confidence"] if predictions else 0),
    )
    db.commit()

    result = {
        "ts": now.isoformat(),
        "action": "predict",
        "hour": hour,
        "weekday": now.strftime("%A"),
        "predictions": predictions,
        "total_history_records": total_records,
    }
    db.close()
    return result


def do_launch(app_name):
    """Launch an application and record it."""
    db = init_db()
    now = datetime.now()

    # Try to launch
    try:
        subprocess.Popen(
            ["cmd", "/c", "start", "", app_name],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        launched = True
        error = None
    except Exception as e:
        launched = False
        error = str(e)

    db.execute(
        "INSERT INTO launches (ts, app_name, hour, weekday, source) VALUES (?,?,?,?,?)",
        (now.isoformat(), app_name, now.hour, now.weekday(), "manual"),
    )
    db.commit()

    result = {
        "ts": now.isoformat(),
        "action": "launch",
        "app": app_name,
        "launched": launched,
        "error": error,
    }
    db.close()
    return result


def do_history():
    """Show launch history."""
    db = init_db()
    recent = db.execute(
        "SELECT ts, app_name, hour, weekday, source FROM launches ORDER BY id DESC LIMIT 50"
    ).fetchall()

    # Stats
    total = db.execute("SELECT COUNT(*) FROM launches").fetchone()[0]
    top_apps = db.execute(
        "SELECT app_name, COUNT(*) as cnt FROM launches GROUP BY app_name ORDER BY cnt DESC LIMIT 10"
    ).fetchall()
    by_hour = db.execute(
        "SELECT hour, COUNT(*) as cnt FROM launches GROUP BY hour ORDER BY cnt DESC LIMIT 5"
    ).fetchall()

    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    result = {
        "ts": datetime.now().isoformat(),
        "action": "history",
        "total_launches": total,
        "top_apps": [{"app": a, "count": c} for a, c in top_apps],
        "peak_hours": [{"hour": h, "count": c} for h, c in by_hour],
        "recent": [
            {"ts": r[0], "app": r[1], "hour": r[2], "weekday": days[r[3]] if r[3] is not None else "?", "source": r[4]}
            for r in recent[:20]
        ],
    }
    db.close()
    return result


def do_status():
    """Overall launcher status."""
    db = init_db()
    total = db.execute("SELECT COUNT(*) FROM launches").fetchone()[0]
    profiles = db.execute("SELECT COUNT(*) FROM profiles").fetchone()[0]
    predictions = db.execute("SELECT COUNT(*) FROM predictions").fetchone()[0]
    unique_apps = db.execute("SELECT COUNT(DISTINCT app_name) FROM launches").fetchone()[0]

    result = {
        "ts": datetime.now().isoformat(),
        "script": "win_smart_launcher_v2.py",
        "script_id": 244,
        "db": str(DB_PATH),
        "total_launches": total,
        "unique_apps": unique_apps,
        "profiles": profiles,
        "predictions_made": predictions,
        "status": "ok",
    }
    db.close()
    return result


def main():
    parser = argparse.ArgumentParser(description="win_smart_launcher_v2.py — Smart launcher v2 (#244)")
    parser.add_argument("--launch", type=str, metavar="APP", help="Launch an application")
    parser.add_argument("--learn", action="store_true", help="Learn from current running processes")
    parser.add_argument("--predict", action="store_true", help="Predict apps to launch now")
    parser.add_argument("--history", action="store_true", help="Show launch history")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    args = parser.parse_args()

    if args.launch:
        result = do_launch(args.launch)
    elif args.learn:
        result = do_learn()
    elif args.predict:
        result = do_predict()
    elif args.history:
        result = do_history()
    else:
        result = do_status()

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
