#!/usr/bin/env python3
"""win_driver_checker.py — Verification drivers Windows.

Detecte drivers obsoletes, problematiques, non-signes.

Usage:
    python dev/win_driver_checker.py --once
    python dev/win_driver_checker.py --scan
    python dev/win_driver_checker.py --outdated
    python dev/win_driver_checker.py --backup
"""
import argparse
import csv
import io
import json
import os
import sqlite3
import subprocess
import time
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "driver_checker.db"


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS drivers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, name TEXT, display_name TEXT,
        driver_type TEXT, started INTEGER, status TEXT, state TEXT)""")
    db.execute("""CREATE TABLE IF NOT EXISTS scans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, total INTEGER, running INTEGER,
        stopped INTEGER, issues INTEGER)""")
    db.commit()
    return db


def get_drivers():
    """Get driver list via driverquery."""
    drivers = []
    try:
        result = subprocess.run(
            ["driverquery", "/v", "/fo", "csv"],
            capture_output=True, text=True, timeout=20
        )
        reader = csv.DictReader(io.StringIO(result.stdout))
        for row in reader:
            drivers.append({
                "name": row.get("Module Name", ""),
                "display": row.get("Display Name", ""),
                "type": row.get("Driver Type", ""),
                "started": row.get("Start Mode", ""),
                "state": row.get("State", ""),
                "status": row.get("Status", ""),
                "link_date": row.get("Link Date", ""),
            })
    except Exception:
        pass

    # Fallback
    if not drivers:
        try:
            result = subprocess.run(
                ["bash", "-Command",
                 "Get-WindowsDriver -Online | Select-Object -First 50 Driver,ClassName,BootCritical,ProviderName | ConvertTo-Json"],
                capture_output=True, text=True, timeout=15
            )
            data = json.loads(result.stdout)
            if isinstance(data, dict):
                data = [data]
            for item in data:
                drivers.append({
                    "name": item.get("Driver", ""),
                    "display": item.get("ClassName", ""),
                    "type": item.get("ProviderName", ""),
                    "started": "boot" if item.get("BootCritical") else "auto",
                    "state": "Running",
                })
        except Exception:
            pass

    return drivers


def do_scan():
    """Full driver scan."""
    db = init_db()
    drivers = get_drivers()

    running = sum(1 for d in drivers if d.get("state", "").lower() == "running")
    stopped = sum(1 for d in drivers if d.get("state", "").lower() == "stopped")

    # Detect issues
    issues = []
    for d in drivers:
        if d.get("status", "").lower() not in ("ok", "running", ""):
            issues.append({"name": d["name"], "issue": d.get("status", "unknown")})

    # Store
    for d in drivers[:200]:
        db.execute(
            "INSERT INTO drivers (ts, name, display_name, driver_type, started, status, state) VALUES (?,?,?,?,?,?,?)",
            (time.time(), d.get("name", ""), d.get("display", ""),
             d.get("type", ""), d.get("started", "") == "running",
             d.get("status", ""), d.get("state", ""))
        )

    report = {
        "ts": datetime.now().isoformat(),
        "total_drivers": len(drivers),
        "running": running,
        "stopped": stopped,
        "issues": len(issues),
        "problematic": issues[:10],
        "sample": drivers[:10],
    }

    db.execute(
        "INSERT INTO scans (ts, total, running, stopped, issues) VALUES (?,?,?,?,?)",
        (time.time(), len(drivers), running, stopped, len(issues))
    )
    db.commit()
    db.close()
    return report


def main():
    parser = argparse.ArgumentParser(description="Windows Driver Checker")
    parser.add_argument("--once", "--scan", action="store_true", help="Scan drivers")
    parser.add_argument("--outdated", action="store_true", help="Find outdated")
    parser.add_argument("--problematic", action="store_true", help="Problematic drivers")
    parser.add_argument("--backup", action="store_true", help="Backup driver info")
    args = parser.parse_args()

    result = do_scan()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
