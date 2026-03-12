#!/usr/bin/env python3
"""jarvis_macro_recorder.py — Enregistreur de macros JARVIS.

Capture sequences d'actions, rejoue a la demande.

Usage:
    python dev/jarvis_macro_recorder.py --once
    python dev/jarvis_macro_recorder.py --record
    python dev/jarvis_macro_recorder.py --play NAME
    python dev/jarvis_macro_recorder.py --list
"""
import argparse
import json
import os
import sqlite3
import time
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "macro_recorder.db"


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS macros (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, name TEXT UNIQUE, description TEXT,
        steps TEXT, run_count INTEGER DEFAULT 0)""")
    db.execute("""CREATE TABLE IF NOT EXISTS macro_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, macro_name TEXT, status TEXT, duration_s REAL)""")
    db.commit()
    return db


def list_macros():
    db = init_db()
    rows = db.execute("SELECT name, description, steps, run_count FROM macros ORDER BY name").fetchall()
    db.close()
    macros = []
    for name, desc, steps_json, runs in rows:
        steps = json.loads(steps_json) if steps_json else []
        macros.append({
            "name": name, "description": desc,
            "steps": len(steps), "run_count": runs,
        })
    return macros


def create_sample_macros():
    db = init_db()
    samples = [
        {
            "name": "morning_startup",
            "description": "Routine matinale JARVIS",
            "steps": [
                {"action": "health_check", "params": {}},
                {"action": "cluster_status", "params": {}},
                {"action": "email_check", "params": {"account": "all"}},
                {"action": "trading_scan", "params": {"mode": "quick"}},
            ],
        },
        {
            "name": "dev_session",
            "description": "Prepare session developpement",
            "steps": [
                {"action": "gpu_status", "params": {}},
                {"action": "model_check", "params": {"node": "M1"}},
                {"action": "workspace_clean", "params": {}},
            ],
        },
        {
            "name": "night_shutdown",
            "description": "Routine de nuit",
            "steps": [
                {"action": "backup_db", "params": {"all": True}},
                {"action": "log_rotate", "params": {}},
                {"action": "thermal_report", "params": {}},
            ],
        },
    ]
    for m in samples:
        try:
            db.execute("INSERT OR IGNORE INTO macros (ts, name, description, steps) VALUES (?,?,?,?)",
                       (time.time(), m["name"], m["description"], json.dumps(m["steps"])))
        except Exception:
            pass
    db.commit()
    db.close()
    return len(samples)


def do_status():
    create_sample_macros()
    macros = list_macros()
    db = init_db()
    recent = db.execute(
        "SELECT ts, macro_name, status, duration_s FROM macro_runs ORDER BY ts DESC LIMIT 10"
    ).fetchall()
    db.close()

    return {
        "ts": datetime.now().isoformat(),
        "total_macros": len(macros),
        "macros": macros,
        "recent_runs": [
            {"ts": datetime.fromtimestamp(r[0]).isoformat(), "macro": r[1],
             "status": r[2], "duration_s": r[3]}
            for r in recent
        ],
    }


def main():
    parser = argparse.ArgumentParser(description="JARVIS Macro Recorder")
    parser.add_argument("--once", "--list", action="store_true", help="List macros")
    parser.add_argument("--record", action="store_true", help="Record")
    parser.add_argument("--play", metavar="NAME", help="Play macro")
    parser.add_argument("--edit", metavar="NAME", help="Edit macro")
    args = parser.parse_args()
    print(json.dumps(do_status(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
