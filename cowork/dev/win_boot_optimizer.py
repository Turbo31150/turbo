#!/usr/bin/env python3
"""win_boot_optimizer.py — Optimisation boot Windows.

Mesure temps demarrage, identifie services lents.

Usage:
    python dev/win_boot_optimizer.py --once
    python dev/win_boot_optimizer.py --analyze
    python dev/win_boot_optimizer.py --benchmark
    python dev/win_boot_optimizer.py --report
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
DB_PATH = DEV / "data" / "boot_optimizer.db"

SAFE_TO_DISABLE = [
    "DiagTrack", "dmwappushservice", "MapsBroker", "lfsvc",
    "RetailDemo", "wisvc", "WMPNetworkSvc", "WSearch",
]

NEVER_DISABLE = [
    "Winmgmt", "RpcSs", "DcomLaunch", "LSM", "Dhcp", "Dnscache",
    "EventLog", "PlugPlay", "Power", "Schedule", "SENS",
    "SystemEventsBroker", "Themes", "UserManager",
]


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS boot_times (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, boot_time_s REAL, services_auto INTEGER,
        services_running INTEGER)""")
    db.execute("""CREATE TABLE IF NOT EXISTS suggestions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, service TEXT, current_start TEXT,
        suggested_start TEXT, reason TEXT)""")
    db.commit()
    return db


def get_boot_time():
    """Get last boot time."""
    try:
        result = subprocess.run(
            ["powershell", "-Command",
             "(Get-CimInstance Win32_OperatingSystem).LastBootUpTime | Get-Date -Format 'yyyy-MM-dd HH:mm:ss'"],
            capture_output=True, text=True, timeout=10
        )
        boot_str = result.stdout.strip()
        if boot_str:
            boot_dt = datetime.strptime(boot_str, "%Y-%m-%d %H:%M:%S")
            uptime_s = (datetime.now() - boot_dt).total_seconds()
            return {"boot_time": boot_str, "uptime_hours": round(uptime_s / 3600, 1)}
    except Exception:
        pass
    return {"boot_time": "unknown", "uptime_hours": 0}


def get_startup_services():
    """Get auto-start services."""
    services = []
    try:
        result = subprocess.run(
            ["powershell", "-Command",
             "Get-Service | Where-Object {$_.StartType -eq 'Automatic'} | Select-Object Name,Status,DisplayName | ConvertTo-Json"],
            capture_output=True, text=True, timeout=15
        )
        data = json.loads(result.stdout)
        if isinstance(data, dict):
            data = [data]
        for item in data:
            services.append({
                "name": item.get("Name", ""),
                "status": str(item.get("Status", "")),
                "display": item.get("DisplayName", ""),
                "start_type": "Automatic",
            })
    except Exception:
        pass
    return services


def analyze_startup(services):
    """Analyze startup services for optimization."""
    suggestions = []

    for svc in services:
        name = svc["name"]
        if name in SAFE_TO_DISABLE:
            suggestions.append({
                "service": name,
                "display": svc["display"],
                "current": "Automatic",
                "suggested": "Manual",
                "reason": "non_essential",
                "safe": True,
            })
        elif name not in NEVER_DISABLE and "status" in svc:
            # Check if stopped but auto-start
            status_val = svc["status"]
            if status_val in ("1", "Stopped"):
                suggestions.append({
                    "service": name,
                    "display": svc["display"],
                    "current": "Automatic",
                    "suggested": "Manual",
                    "reason": "auto_but_stopped",
                    "safe": False,
                })

    return suggestions


def do_analyze():
    """Full boot analysis."""
    db = init_db()
    boot = get_boot_time()
    services = get_startup_services()
    suggestions = analyze_startup(services)

    running = sum(1 for s in services if s.get("status") in ("4", "Running"))

    db.execute(
        "INSERT INTO boot_times (ts, boot_time_s, services_auto, services_running) VALUES (?,?,?,?)",
        (time.time(), boot["uptime_hours"] * 3600, len(services), running)
    )

    for s in suggestions:
        db.execute(
            "INSERT INTO suggestions (ts, service, current_start, suggested_start, reason) VALUES (?,?,?,?,?)",
            (time.time(), s["service"], s["current"], s["suggested"], s["reason"])
        )

    db.commit()
    db.close()

    return {
        "ts": datetime.now().isoformat(),
        "boot": boot,
        "auto_services": len(services),
        "running": running,
        "optimization_suggestions": len(suggestions),
        "safe_to_disable": [s for s in suggestions if s.get("safe")],
        "review_needed": [s for s in suggestions if not s.get("safe")][:10],
    }


def main():
    parser = argparse.ArgumentParser(description="Windows Boot Optimizer")
    parser.add_argument("--once", "--analyze", action="store_true", help="Analyze boot")
    parser.add_argument("--benchmark", action="store_true", help="Benchmark")
    parser.add_argument("--disable", metavar="SERVICE", help="Disable service")
    parser.add_argument("--report", action="store_true", help="Report")
    args = parser.parse_args()

    result = do_analyze()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
