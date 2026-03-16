#!/usr/bin/env python3
"""win_service_analyzer.py — Analyse tous les services Windows.

Detecte services inutiles/dangereux, propose desactivation,
scoring securite, historique SQLite.

Usage:
    python dev/win_service_analyzer.py --once
    python dev/win_service_analyzer.py --scan
    python dev/win_service_analyzer.py --dangerous
    python dev/win_service_analyzer.py --report
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
DB_PATH = DEV / "data" / "service_analyzer.db"

ESSENTIAL_SERVICES = {
    "wuauserv", "windefend", "mpssvc", "eventlog", "plugplay",
    "rpcss", "dcomlaunch", "lsm", "samss", "schedule", "spooler",
    "dhcp", "dnscache", "nsi", "netprofm", "lanmanworkstation",
    "cryptsvc", "bits", "winmgmt", "power", "audioendpointbuilder",
}

BLOAT_SERVICES = {
    "diagnosticshub.standardcollector.service", "dmwappushservice",
    "retaildemo", "mapbroker", "lfsvc", "sharedaccess",
    "wisvc", "xblauthmanager", "xblgamesave", "xboxnetapisvc",
}

SUSPICIOUS_PATTERNS = ["remote", "telnet", "vnc", "teamviewer"]


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS scans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, total INTEGER, running INTEGER, stopped INTEGER,
        essential INTEGER, bloat INTEGER, suspicious INTEGER, report TEXT)""")
    db.commit()
    return db


def get_services():
    """Get all Windows services via PowerShell."""
    try:
        result = subprocess.run(
            ["bash", "-NoProfile", "-Command",
             "Get-Service | Select-Object Name, DisplayName, Status, StartType | ConvertTo-Json"],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode == 0:
            services = json.loads(result.stdout)
            if isinstance(services, dict):
                services = [services]
            return services
    except Exception as e:
        print(f"[WARN] get_services: {e}")
    return []


def categorize_service(svc):
    """Categorize a service."""
    name = (svc.get("Name") or "").lower()
    display = (svc.get("DisplayName") or "").lower()

    if name in ESSENTIAL_SERVICES:
        return "essential"
    if name in BLOAT_SERVICES:
        return "bloat"
    if any(p in name or p in display for p in SUSPICIOUS_PATTERNS):
        return "suspicious"
    return "optional"


def do_scan():
    """Full service scan."""
    db = init_db()
    services = get_services()

    categories = {"essential": 0, "optional": 0, "bloat": 0, "suspicious": 0}
    running = 0
    stopped = 0
    dangerous = []
    bloat_list = []

    for svc in services:
        cat = categorize_service(svc)
        categories[cat] += 1
        status = str(svc.get("Status", ""))
        if status == "4" or "running" in status.lower():
            running += 1
        else:
            stopped += 1
        if cat == "suspicious":
            dangerous.append({"name": svc["Name"], "display": svc.get("DisplayName"), "status": status})
        if cat == "bloat" and ("running" in status.lower() or status == "4"):
            bloat_list.append({"name": svc["Name"], "display": svc.get("DisplayName")})

    score = 100
    score -= len(dangerous) * 10
    score -= len(bloat_list) * 2
    score = max(0, score)

    report = {
        "ts": datetime.now().isoformat(),
        "total": len(services),
        "running": running, "stopped": stopped,
        "categories": categories,
        "security_score": score,
        "suspicious": dangerous[:10],
        "bloat_running": bloat_list[:10],
    }

    db.execute(
        "INSERT INTO scans (ts, total, running, stopped, essential, bloat, suspicious, report) VALUES (?,?,?,?,?,?,?,?)",
        (time.time(), len(services), running, stopped,
         categories["essential"], categories["bloat"], categories["suspicious"],
         json.dumps(report))
    )
    db.commit()
    db.close()
    return report


def main():
    parser = argparse.ArgumentParser(description="Windows Service Analyzer")
    parser.add_argument("--once", "--scan", action="store_true", help="Full scan")
    parser.add_argument("--dangerous", action="store_true", help="Show suspicious services only")
    parser.add_argument("--report", action="store_true", help="History")
    args = parser.parse_args()

    if args.dangerous:
        services = get_services()
        sus = [s for s in services if categorize_service(s) == "suspicious"]
        print(json.dumps(sus, ensure_ascii=False, indent=2))
    else:
        result = do_scan()
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
