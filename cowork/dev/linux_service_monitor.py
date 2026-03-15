#!/usr/bin/env python3
"""win_service_monitor.py — Service monitoring (#254).

Uses sc query state= all, identifies critical stopped services,
auto-start services that should be running.

Usage:
    python dev/win_service_monitor.py --once
    python dev/win_service_monitor.py --scan
    python dev/win_service_monitor.py --critical
    python dev/win_service_monitor.py --stopped
    python dev/win_service_monitor.py --auto-start
"""
import argparse
import json
import os
import re
import sqlite3
import subprocess
import time
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "service_monitor.db"

CRITICAL_SERVICES = {
    "wuauserv": "Windows Update",
    "windefend": "Windows Defender",
    "mpssvc": "Windows Firewall",
    "eventlog": "Windows Event Log",
    "schedule": "Task Scheduler",
    "rpcss": "RPC",
    "dnscache": "DNS Client",
    "dhcp": "DHCP Client",
    "lanmanworkstation": "Workstation",
    "cryptsvc": "Cryptographic Services",
    "bits": "BITS",
    "wmi": "WMI",
    "winmgmt": "WMI",
}


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("""CREATE TABLE IF NOT EXISTS service_scans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        total_services INTEGER,
        running INTEGER,
        stopped INTEGER,
        critical_stopped INTEGER
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS services (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        scan_id INTEGER,
        ts TEXT NOT NULL,
        service_name TEXT NOT NULL,
        display_name TEXT,
        state TEXT,
        start_type TEXT,
        is_critical INTEGER DEFAULT 0
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS actions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        action TEXT NOT NULL,
        service TEXT NOT NULL,
        success INTEGER,
        details TEXT
    )""")
    db.commit()
    return db


def parse_sc_query():
    """Parse sc query state= all output."""
    services = []
    try:
        out = subprocess.check_output(
            ["sc", "query", "state=", "all"],
            stderr=subprocess.DEVNULL, text=True, timeout=30,
        )
        current = {}
        for line in out.split("\n"):
            line = line.strip()
            if line.startswith("SERVICE_NAME:"):
                if current:
                    services.append(current)
                current = {"service_name": line.split(":", 1)[1].strip()}
            elif line.startswith("DISPLAY_NAME:"):
                current["display_name"] = line.split(":", 1)[1].strip()
            elif line.startswith("STATE"):
                # STATE : 4  RUNNING
                match = re.search(r'\d+\s+(\w+)', line)
                if match:
                    current["state"] = match.group(1)
            elif line.startswith("TYPE"):
                pass
            elif line.startswith("START_TYPE"):
                match = re.search(r'\d+\s+(\w+)', line)
                if match:
                    current["start_type"] = match.group(1)

        if current:
            services.append(current)
    except Exception as e:
        services.append({"service_name": "ERROR", "error": str(e)})
    return services


def get_service_start_type(service_name):
    """Get service start type via sc qc."""
    try:
        out = subprocess.check_output(
            ["sc", "qc", service_name],
            stderr=subprocess.DEVNULL, text=True, timeout=10,
        )
        for line in out.split("\n"):
            if "START_TYPE" in line:
                if "AUTO_START" in line:
                    return "auto"
                elif "DEMAND_START" in line:
                    return "manual"
                elif "DISABLED" in line:
                    return "disabled"
    except Exception:
        pass
    return "unknown"


def do_scan():
    """Full service scan."""
    db = init_db()
    now = datetime.now()
    services = parse_sc_query()

    running = sum(1 for s in services if s.get("state") == "RUNNING")
    stopped = sum(1 for s in services if s.get("state") == "STOPPED")
    critical_stopped = 0

    for s in services:
        sname = s.get("service_name", "").lower()
        is_critical = sname in CRITICAL_SERVICES
        if is_critical and s.get("state") == "STOPPED":
            critical_stopped += 1
        s["is_critical"] = is_critical

    scan_id = db.execute(
        "INSERT INTO service_scans (ts, total_services, running, stopped, critical_stopped) VALUES (?,?,?,?,?)",
        (now.isoformat(), len(services), running, stopped, critical_stopped),
    ).lastrowid

    for s in services[:300]:
        db.execute(
            "INSERT INTO services (scan_id, ts, service_name, display_name, state, start_type, is_critical) VALUES (?,?,?,?,?,?,?)",
            (scan_id, now.isoformat(), s.get("service_name", ""), s.get("display_name", ""),
             s.get("state", ""), s.get("start_type", ""), int(s.get("is_critical", False))),
        )

    db.commit()
    result = {
        "ts": now.isoformat(), "action": "scan", "scan_id": scan_id,
        "total_services": len(services), "running": running,
        "stopped": stopped, "critical_stopped": critical_stopped,
    }
    db.close()
    return result


def do_critical():
    """Show critical services status."""
    services = parse_sc_query()
    critical = []
    for s in services:
        sname = s.get("service_name", "").lower()
        if sname in CRITICAL_SERVICES:
            critical.append({
                "service": s.get("service_name"),
                "display_name": CRITICAL_SERVICES.get(sname, s.get("display_name", "")),
                "state": s.get("state", "UNKNOWN"),
                "ok": s.get("state") == "RUNNING",
            })

    result = {
        "ts": datetime.now().isoformat(), "action": "critical",
        "total_critical": len(critical),
        "running": sum(1 for c in critical if c["ok"]),
        "stopped": sum(1 for c in critical if not c["ok"]),
        "services": critical,
    }
    return result


def do_stopped():
    """Show all stopped services."""
    services = parse_sc_query()
    stopped = [
        {
            "service": s.get("service_name"), "display_name": s.get("display_name", ""),
            "is_critical": s.get("service_name", "").lower() in CRITICAL_SERVICES,
        }
        for s in services if s.get("state") == "STOPPED"
    ]

    result = {
        "ts": datetime.now().isoformat(), "action": "stopped",
        "total_stopped": len(stopped),
        "critical_stopped": sum(1 for s in stopped if s["is_critical"]),
        "services": stopped[:50],
    }
    return result


def do_auto_start():
    """Check auto-start services that should be running."""
    db = init_db()
    services = parse_sc_query()
    issues = []

    for s in services:
        sname = s.get("service_name", "")
        if s.get("state") == "STOPPED":
            start_type = get_service_start_type(sname)
            if start_type == "auto":
                issues.append({
                    "service": sname,
                    "display_name": s.get("display_name", ""),
                    "start_type": "auto",
                    "state": "STOPPED",
                    "action": "should_be_running",
                })

    result = {
        "ts": datetime.now().isoformat(), "action": "auto_start",
        "auto_start_stopped": len(issues),
        "services": issues[:30],
    }
    db.close()
    return result


def do_status():
    db = init_db()
    result = {
        "ts": datetime.now().isoformat(), "script": "win_service_monitor.py", "script_id": 254,
        "db": str(DB_PATH),
        "total_scans": db.execute("SELECT COUNT(*) FROM service_scans").fetchone()[0],
        "total_actions": db.execute("SELECT COUNT(*) FROM actions").fetchone()[0],
        "status": "ok",
    }
    db.close()
    return result


def main():
    parser = argparse.ArgumentParser(description="win_service_monitor.py — Service monitoring (#254)")
    parser.add_argument("--scan", action="store_true", help="Full service scan")
    parser.add_argument("--critical", action="store_true", help="Show critical services")
    parser.add_argument("--stopped", action="store_true", help="Show stopped services")
    parser.add_argument("--auto-start", action="store_true", help="Check auto-start services")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    args = parser.parse_args()

    if args.scan:
        result = do_scan()
    elif args.critical:
        result = do_critical()
    elif args.stopped:
        result = do_stopped()
    elif args.auto_start:
        result = do_auto_start()
    else:
        result = do_status()

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
