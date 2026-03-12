#!/usr/bin/env python3
"""win_registry_guard.py — Surveillance registre Windows.

Detecte modifications suspectes (startup, services, shell).

Usage:
    python dev/win_registry_guard.py --once
    python dev/win_registry_guard.py --scan
    python dev/win_registry_guard.py --whitelist
    python dev/win_registry_guard.py --restore
"""
import argparse
import json
import os
import sqlite3
import time
import winreg
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "registry_guard.db"

MONITORED_KEYS = [
    (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", "HKCU_Run"),
    (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\RunOnce", "HKCU_RunOnce"),
    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run", "HKLM_Run"),
    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\RunOnce", "HKLM_RunOnce"),
    (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders", "HKCU_ShellFolders"),
]


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, key_path TEXT, values_json TEXT)""")
    db.execute("""CREATE TABLE IF NOT EXISTS changes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, key_path TEXT, change_type TEXT,
        name TEXT, old_value TEXT, new_value TEXT, whitelisted INTEGER DEFAULT 0)""")
    db.execute("""CREATE TABLE IF NOT EXISTS whitelist (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        key_path TEXT, name TEXT)""")
    db.commit()
    return db


def read_registry_key(hive, subkey):
    """Read all values from a registry key."""
    values = {}
    try:
        key = winreg.OpenKey(hive, subkey, 0, winreg.KEY_READ)
        i = 0
        while True:
            try:
                name, data, _ = winreg.EnumValue(key, i)
                values[name] = str(data)[:500]
                i += 1
            except OSError:
                break
        winreg.CloseKey(key)
    except OSError:
        pass
    return values


def do_scan():
    """Scan monitored registry keys and detect changes."""
    db = init_db()
    results = []
    changes_found = []

    for hive, subkey, label in MONITORED_KEYS:
        current = read_registry_key(hive, subkey)

        # Get previous snapshot
        prev_row = db.execute(
            "SELECT values_json FROM snapshots WHERE key_path=? ORDER BY ts DESC LIMIT 1",
            (label,)
        ).fetchone()
        previous = json.loads(prev_row[0]) if prev_row else {}

        # Detect changes
        for name, value in current.items():
            if name not in previous:
                changes_found.append({"key": label, "type": "added", "name": name, "value": value[:100]})
                db.execute(
                    "INSERT INTO changes (ts, key_path, change_type, name, old_value, new_value) VALUES (?,?,?,?,?,?)",
                    (time.time(), label, "added", name, "", value[:200])
                )
            elif previous[name] != value:
                changes_found.append({"key": label, "type": "modified", "name": name})
                db.execute(
                    "INSERT INTO changes (ts, key_path, change_type, name, old_value, new_value) VALUES (?,?,?,?,?,?)",
                    (time.time(), label, "modified", name, previous[name][:200], value[:200])
                )

        for name in previous:
            if name not in current:
                changes_found.append({"key": label, "type": "removed", "name": name})
                db.execute(
                    "INSERT INTO changes (ts, key_path, change_type, name, old_value, new_value) VALUES (?,?,?,?,?,?)",
                    (time.time(), label, "removed", name, previous[name][:200], "")
                )

        # Save snapshot
        db.execute(
            "INSERT INTO snapshots (ts, key_path, values_json) VALUES (?,?,?)",
            (time.time(), label, json.dumps(current))
        )
        results.append({"key": label, "entries": len(current)})

    db.commit()
    db.close()
    return {
        "ts": datetime.now().isoformat(),
        "keys_scanned": len(results),
        "changes_detected": len(changes_found),
        "changes": changes_found[:20],
        "keys": results,
    }


def show_whitelist():
    """Show whitelisted entries."""
    db = init_db()
    rows = db.execute("SELECT key_path, name FROM whitelist").fetchall()
    db.close()
    return [{"key": r[0], "name": r[1]} for r in rows]


def main():
    parser = argparse.ArgumentParser(description="Windows Registry Guard")
    parser.add_argument("--once", "--scan", action="store_true", help="Scan registry")
    parser.add_argument("--whitelist", action="store_true", help="Show whitelist")
    parser.add_argument("--restore", action="store_true", help="Show change history")
    args = parser.parse_args()

    if args.whitelist:
        print(json.dumps(show_whitelist(), ensure_ascii=False, indent=2))
    elif args.restore:
        db = init_db()
        rows = db.execute("SELECT ts, key_path, change_type, name FROM changes ORDER BY ts DESC LIMIT 20").fetchall()
        db.close()
        print(json.dumps([{
            "ts": datetime.fromtimestamp(r[0]).isoformat(), "key": r[1], "type": r[2], "name": r[3]
        } for r in rows], indent=2))
    else:
        result = do_scan()
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
