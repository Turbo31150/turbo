#!/usr/bin/env python3
"""win_startup_optimizer.py — Startup optimization (#253).

Scans wmic startup, registry Run/RunOnce keys, scheduled tasks at logon.
Classifies impact, recommends disabling.

Usage:
    python dev/win_startup_optimizer.py --once
    python dev/win_startup_optimizer.py --scan
    python dev/win_startup_optimizer.py --disable NAME
    python dev/win_startup_optimizer.py --enable NAME
    python dev/win_startup_optimizer.py --impact
"""
import argparse
import json
import os
import sqlite3
import subprocess
import time
import winreg
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "startup_optimizer.db"

HIGH_IMPACT_KEYWORDS = ["update", "helper", "agent", "sync", "cloud", "telemetry", "report"]
LOW_IMPACT_KEYWORDS = ["security", "antivirus", "defender", "firewall", "audio", "display"]


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("""CREATE TABLE IF NOT EXISTS startup_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        name TEXT NOT NULL,
        command TEXT,
        location TEXT,
        source TEXT,
        impact TEXT DEFAULT 'medium',
        enabled INTEGER DEFAULT 1,
        recommendation TEXT
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS actions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        action TEXT NOT NULL,
        target TEXT NOT NULL,
        success INTEGER,
        details TEXT
    )""")
    db.commit()
    return db


def classify_impact(name, command):
    """Classify startup item impact."""
    combined = (name + " " + (command or "")).lower()
    if any(k in combined for k in LOW_IMPACT_KEYWORDS):
        return "low", "Critical system component - keep enabled"
    if any(k in combined for k in HIGH_IMPACT_KEYWORDS):
        return "high", "Consider disabling - non-essential background task"
    return "medium", "Review manually"


def scan_registry_run(hive, path, source_label):
    """Scan registry Run keys for startup items."""
    items = []
    try:
        key = winreg.OpenKey(hive, path)
        i = 0
        while True:
            try:
                name, value, vtype = winreg.EnumValue(key, i)
                impact, rec = classify_impact(name, value)
                items.append({
                    "name": name, "command": value, "location": path,
                    "source": source_label, "impact": impact, "recommendation": rec,
                    "enabled": True,
                })
                i += 1
            except OSError:
                break
        winreg.CloseKey(key)
    except FileNotFoundError:
        pass
    except OSError:
        pass
    return items


def scan_wmic_startup():
    """Scan startup items via wmic."""
    items = []
    try:
        out = subprocess.check_output(
            ["wmic", "startup", "get", "Caption,Command,Location", "/format:csv"],
            stderr=subprocess.DEVNULL, text=True, timeout=15,
        )
        for line in out.strip().split("\n"):
            parts = line.strip().split(",")
            if len(parts) >= 4:
                caption = parts[1].strip()
                command = parts[2].strip()
                location = parts[3].strip()
                if caption and caption != "Caption":
                    impact, rec = classify_impact(caption, command)
                    items.append({
                        "name": caption, "command": command, "location": location,
                        "source": "wmic", "impact": impact, "recommendation": rec,
                        "enabled": True,
                    })
    except Exception:
        pass
    return items


def scan_scheduled_logon():
    """Scan scheduled tasks that run at logon."""
    items = []
    try:
        out = subprocess.check_output(
            ["schtasks", "/query", "/fo", "csv", "/v"],
            stderr=subprocess.DEVNULL, text=True, timeout=30,
        )
        for line in out.strip().split("\n")[1:]:
            if "logon" in line.lower() or "At log on" in line:
                parts = line.split('","')
                if len(parts) >= 2:
                    name = parts[0].strip('"')
                    status = parts[2].strip('"') if len(parts) > 2 else "Unknown"
                    impact, rec = classify_impact(name, "")
                    items.append({
                        "name": name, "command": "", "location": "Task Scheduler",
                        "source": "schtasks_logon", "impact": impact,
                        "recommendation": rec, "enabled": status != "Disabled",
                    })
    except Exception:
        pass
    return items


def do_scan():
    """Full startup scan."""
    db = init_db()
    now = datetime.now()
    all_items = []

    # Registry HKCU Run
    all_items.extend(scan_registry_run(
        winreg.HKEY_CURRENT_USER,
        r"Software\Microsoft\Windows\CurrentVersion\Run",
        "HKCU_Run",
    ))
    # Registry HKCU RunOnce
    all_items.extend(scan_registry_run(
        winreg.HKEY_CURRENT_USER,
        r"Software\Microsoft\Windows\CurrentVersion\RunOnce",
        "HKCU_RunOnce",
    ))
    # Registry HKLM Run (may need admin)
    all_items.extend(scan_registry_run(
        winreg.HKEY_LOCAL_MACHINE,
        r"Software\Microsoft\Windows\CurrentVersion\Run",
        "HKLM_Run",
    ))
    # WMIC
    all_items.extend(scan_wmic_startup())
    # Scheduled tasks at logon
    all_items.extend(scan_scheduled_logon())

    # Deduplicate by name
    seen = set()
    unique_items = []
    for item in all_items:
        if item["name"] not in seen:
            seen.add(item["name"])
            unique_items.append(item)

    # Store
    db.execute("DELETE FROM startup_items")
    for item in unique_items:
        db.execute(
            "INSERT INTO startup_items (ts, name, command, location, source, impact, enabled, recommendation) VALUES (?,?,?,?,?,?,?,?)",
            (now.isoformat(), item["name"], item.get("command"), item.get("location"),
             item.get("source"), item["impact"], int(item.get("enabled", True)), item.get("recommendation")),
        )
    db.commit()

    result = {
        "ts": now.isoformat(), "action": "scan",
        "total_items": len(unique_items),
        "high_impact": sum(1 for i in unique_items if i["impact"] == "high"),
        "medium_impact": sum(1 for i in unique_items if i["impact"] == "medium"),
        "low_impact": sum(1 for i in unique_items if i["impact"] == "low"),
        "items": unique_items[:30],
    }
    db.close()
    return result


def do_disable(name):
    """Disable a startup item (registry Run keys only)."""
    db = init_db()
    now = datetime.now()
    success = False
    details = ""

    paths = [
        (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run"),
        (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\RunOnce"),
    ]

    for hive, path in paths:
        try:
            key = winreg.OpenKey(hive, path, 0, winreg.KEY_SET_VALUE)
            winreg.DeleteValue(key, name)
            winreg.CloseKey(key)
            success = True
            details = f"Removed '{name}' from {path}"
            break
        except FileNotFoundError:
            continue
        except OSError as e:
            details = f"Error: {e}"

    if not success and not details:
        details = f"'{name}' not found in user registry Run keys"

    db.execute(
        "INSERT INTO actions (ts, action, target, success, details) VALUES (?,?,?,?,?)",
        (now.isoformat(), "disable", name, int(success), details),
    )
    db.commit()

    result = {"ts": now.isoformat(), "action": "disable", "target": name, "success": success, "details": details}
    db.close()
    return result


def do_enable(name):
    """Re-enable is informational only (requires original command)."""
    db = init_db()
    now = datetime.now()

    db.execute(
        "INSERT INTO actions (ts, action, target, success, details) VALUES (?,?,?,?,?)",
        (now.isoformat(), "enable", name, 0, "Enable requires original command path. Check actions log for previously disabled items."),
    )
    db.commit()

    result = {
        "ts": now.isoformat(), "action": "enable", "target": name,
        "message": "Enable requires original command. Check history for disabled items.",
    }
    db.close()
    return result


def do_impact():
    """Show impact analysis."""
    db = init_db()
    items = db.execute(
        "SELECT name, command, source, impact, recommendation FROM startup_items ORDER BY CASE impact WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END"
    ).fetchall()

    result = {
        "ts": datetime.now().isoformat(), "action": "impact",
        "total": len(items),
        "items": [
            {"name": r[0], "command": (r[1] or "")[:80], "source": r[2],
             "impact": r[3], "recommendation": r[4]}
            for r in items
        ],
    }
    db.close()
    return result


def do_status():
    db = init_db()
    result = {
        "ts": datetime.now().isoformat(), "script": "win_startup_optimizer.py", "script_id": 253,
        "db": str(DB_PATH),
        "total_items": db.execute("SELECT COUNT(*) FROM startup_items").fetchone()[0],
        "total_actions": db.execute("SELECT COUNT(*) FROM actions").fetchone()[0],
        "status": "ok",
    }
    db.close()
    return result


def main():
    parser = argparse.ArgumentParser(description="win_startup_optimizer.py — Startup optimization (#253)")
    parser.add_argument("--scan", action="store_true", help="Full startup scan")
    parser.add_argument("--disable", type=str, metavar="NAME", help="Disable a startup item")
    parser.add_argument("--enable", type=str, metavar="NAME", help="Enable a startup item")
    parser.add_argument("--impact", action="store_true", help="Show impact analysis")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    args = parser.parse_args()

    if args.scan:
        result = do_scan()
    elif args.disable:
        result = do_disable(args.disable)
    elif args.enable:
        result = do_enable(args.enable)
    elif args.impact:
        result = do_impact()
    else:
        result = do_status()

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
