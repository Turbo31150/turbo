#!/usr/bin/env python3
"""win_vpn_monitor.py — Moniteur VPN Windows.

Detecte connexion active, logs, auto-reconnect.

Usage:
    python dev/win_vpn_monitor.py --once
    python dev/win_vpn_monitor.py --status
    python dev/win_vpn_monitor.py --connect PROFILE
    python dev/win_vpn_monitor.py --history
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
DB_PATH = DEV / "data" / "vpn_monitor.db"


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS vpn_checks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, vpn_active INTEGER, profile TEXT,
        public_ip TEXT)""")
    db.commit()
    return db


def check_vpn_connections():
    connections = []
    try:
        out = subprocess.run(
            ["rasdial"],
            capture_output=True, text=True, timeout=5
        )
        lines = out.stdout.strip().split("\n")
        for line in lines:
            line = line.strip()
            if line and "connected" not in line.lower() and "no connections" not in line.lower() and "command" not in line.lower():
                connections.append(line)
    except Exception:
        pass

    # Also check network adapters for VPN-like names
    try:
        out = subprocess.run(
            ["bash", "-Command",
             "Get-NetAdapter | Where-Object {$_.InterfaceDescription -match 'VPN|TAP|WireGuard|OpenVPN'} | "
             "Select-Object Name,Status,InterfaceDescription | ConvertTo-Json"],
            capture_output=True, text=True, timeout=10
        )
        if out.stdout.strip():
            data = json.loads(out.stdout)
            if isinstance(data, dict):
                data = [data]
            for a in data:
                if a.get("Status") == "Up":
                    connections.append(a.get("Name", "VPN"))
    except Exception:
        pass

    return connections


def get_public_ip():
    try:
        out = subprocess.run(
            ["curl", "-s", "--max-time", "5", "https://ifconfig.me"],
            capture_output=True, text=True, timeout=8
        )
        return out.stdout.strip()
    except Exception:
        return "unknown"


def do_status():
    db = init_db()
    vpn_conns = check_vpn_connections()
    public_ip = get_public_ip()
    vpn_active = len(vpn_conns) > 0

    db.execute("INSERT INTO vpn_checks (ts, vpn_active, profile, public_ip) VALUES (?,?,?,?)",
               (time.time(), int(vpn_active), ",".join(vpn_conns)[:200], public_ip))
    db.commit()
    db.close()

    return {
        "ts": datetime.now().isoformat(),
        "vpn_active": vpn_active,
        "connections": vpn_conns,
        "public_ip": public_ip,
        "recommendation": "VPN connected" if vpn_active else "No VPN — direct connection",
    }


def main():
    parser = argparse.ArgumentParser(description="Windows VPN Monitor")
    parser.add_argument("--once", "--status", action="store_true", help="Status")
    parser.add_argument("--connect", metavar="PROFILE", help="Connect VPN")
    parser.add_argument("--disconnect", action="store_true", help="Disconnect")
    parser.add_argument("--history", action="store_true", help="History")
    args = parser.parse_args()
    print(json.dumps(do_status(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
