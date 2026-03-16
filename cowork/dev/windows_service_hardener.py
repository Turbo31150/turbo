#!/usr/bin/env python3
"""Windows Service Hardener — Monitor, optimize, and secure Windows services.

Checks for unnecessary services, optimizes startup types,
monitors resource usage, and hardens security.
"""
import argparse
import json
import os
import sqlite3
import subprocess
import time
from pathlib import Path

DB_PATH = Path(__file__).parent / "services_audit.db"
REPORT_DIR = Path(__file__).parent / "reports"

# Services known to be safe to disable for a dev workstation
DISABLE_CANDIDATES = {
    "DiagTrack": "Telemetry (Connected User Experiences)",
    "dmwappushservice": "WAP Push Message Routing",
    "MapsBroker": "Downloaded Maps Manager",
    "lfsvc": "Geolocation Service",
    "RetailDemo": "Retail Demo Service",
    "wisvc": "Windows Insider Service",
    "WMPNetworkSvc": "Windows Media Player Sharing",
}

# Critical services that MUST be running
CRITICAL_SERVICES = {
    "LanmanWorkstation": "Workstation (network shares)",
    "Winmgmt": "WMI (system management)",
    "Schedule": "Task Scheduler",
    "Dhcp": "DHCP Client",
    "Dnscache": "DNS Client",
    "EventLog": "Windows Event Log",
    "nsi": "Network Store Interface",
}

def init_db():
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS service_snapshots (
        id INTEGER PRIMARY KEY, ts REAL, name TEXT, display_name TEXT,
        status TEXT, start_type TEXT, pid INTEGER, memory_mb REAL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS audit_runs (
        id INTEGER PRIMARY KEY, ts REAL, total_services INTEGER,
        running INTEGER, stopped INTEGER, disabled_candidates INTEGER,
        critical_ok INTEGER, critical_fail INTEGER, recommendations TEXT)""")
    db.commit()
    return db

def get_services():
    """Get all Windows services via PowerShell."""
    ps = (
        "Get-Service | Select-Object Name, DisplayName, Status, StartType | "
        "ConvertTo-Json -Compress"
    )
    try:
        r = subprocess.run(
            ["bash", "-NoProfile", "-Command", ps],
            capture_output=True, text=True, timeout=15)
        if r.returncode == 0:
            data = json.loads(r.stdout)
            if isinstance(data, dict):
                data = [data]
            return data
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError) as e:
        print(f"Erreur PowerShell: {e}")
    return []

def get_service_memory(name):
    """Get memory usage for a running service."""
    ps = f"(Get-Process -Id (Get-WmiObject Win32_Service -Filter \"Name='{name}'\").ProcessId -ErrorAction SilentlyContinue).WorkingSet64 / 1MB"
    try:
        r = subprocess.run(
            ["bash", "-NoProfile", "-Command", ps],
            capture_output=True, text=True, timeout=5)
        if r.returncode == 0 and r.stdout.strip():
            return float(r.stdout.strip())
    except (subprocess.TimeoutExpired, ValueError, OSError):
        pass
    return 0.0

def audit_services(db):
    """Full service audit."""
    services = get_services()
    if not services:
        return "Impossible de lire les services Windows"

    now = time.time()
    running = stopped = 0
    disable_candidates = 0
    critical_ok = critical_fail = 0
    recommendations = []

    for svc in services:
        name = svc.get("Name", "")
        status = str(svc.get("Status", ""))
        # PowerShell returns numeric status codes
        if status == "4" or "Running" in status:
            status = "Running"
            running += 1
        else:
            status = "Stopped"
            stopped += 1

        start_type = str(svc.get("StartType", ""))
        display = svc.get("DisplayName", name)

        mem = 0.0
        if status == "Running" and name in CRITICAL_SERVICES:
            mem = get_service_memory(name)

        db.execute(
            "INSERT INTO service_snapshots (ts, name, display_name, status, start_type, pid, memory_mb) "
            "VALUES (?,?,?,?,?,0,?)", (now, name, display, status, start_type, mem))

        # Check disable candidates
        if name in DISABLE_CANDIDATES and status == "Running":
            disable_candidates += 1
            recommendations.append(f"DISABLE: {name} ({DISABLE_CANDIDATES[name]})")

        # Check critical
        if name in CRITICAL_SERVICES:
            if status == "Running":
                critical_ok += 1
            else:
                critical_fail += 1
                recommendations.append(f"CRITICAL DOWN: {name} ({CRITICAL_SERVICES[name]})")

    db.execute(
        "INSERT INTO audit_runs (ts, total_services, running, stopped, disabled_candidates, critical_ok, critical_fail, recommendations) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (now, len(services), running, stopped, disable_candidates, critical_ok, critical_fail, json.dumps(recommendations[:20])))
    db.commit()

    return {
        "total": len(services), "running": running, "stopped": stopped,
        "disable_candidates": disable_candidates,
        "critical": f"{critical_ok}/{critical_ok + critical_fail} OK",
        "recommendations": recommendations[:10],
    }

def generate_report(result):
    """Generate audit report."""
    REPORT_DIR.mkdir(exist_ok=True)
    lines = [
        "# Windows Services Audit",
        f"Date: {time.strftime('%Y-%m-%d %H:%M')}",
        f"Total: {result['total']} | Running: {result['running']} | Stopped: {result['stopped']}",
        f"Critical: {result['critical']}",
        f"Disable candidates actifs: {result['disable_candidates']}",
        "", "## Recommendations",
    ]
    for r in result.get("recommendations", []):
        lines.append(f"- {r}")
    rpath = REPORT_DIR / f"services_audit_{time.strftime('%Y%m%d_%H%M')}.md"
    rpath.write_text("\n".join(lines), encoding="utf-8")
    return rpath

def main():
    parser = argparse.ArgumentParser(description="Windows Service Hardener")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--interval", type=int, default=14400, help="Seconds between audits")
    args = parser.parse_args()

    db = init_db()
    if args.once or not args.loop:
        result = audit_services(db)
        if isinstance(result, dict):
            print(f"Services: {result['total']} total, {result['running']} running")
            print(f"Critical: {result['critical']}")
            print(f"Disable candidates actifs: {result['disable_candidates']}")
            for r in result.get("recommendations", []):
                print(f"  → {r}")
            generate_report(result)
        else:
            print(result)

    if args.loop:
        while True:
            try:
                result = audit_services(db)
                if isinstance(result, dict):
                    print(f"[{time.strftime('%H:%M')}] {result['running']} running | Critical: {result['critical']}")
                    generate_report(result)
                time.sleep(args.interval)
            except KeyboardInterrupt:
                break

if __name__ == "__main__":
    main()
