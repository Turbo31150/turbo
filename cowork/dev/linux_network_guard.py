#!/usr/bin/env python3
"""win_network_guard.py — Surveillance reseau Windows.

Detecte connexions suspectes, whitelist cluster IPs,
alerte ports inhabituels.

Usage:
    python dev/win_network_guard.py --once
    python dev/win_network_guard.py --scan
    python dev/win_network_guard.py --whitelist
    python dev/win_network_guard.py --report
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
DB_PATH = DEV / "data" / "network_guard.db"

WHITELIST_IPS = {"127.0.0.1", "192.168.1.26", "192.168.1.113", "0.0.0.0", "::1", "::"}
KNOWN_PORTS = {
    1234: "LM Studio", 11434: "Ollama", 18789: "OpenClaw",
    9742: "FastAPI WS", 8080: "Dashboard", 18800: "Direct Proxy",
    5678: "n8n", 9222: "Chrome DevTools", 3000: "Node",
}


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS scans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, total_connections INTEGER, suspicious INTEGER,
        known_services INTEGER, report TEXT)""")
    db.commit()
    return db


def get_connections():
    """Get active TCP connections via netstat."""
    connections = []
    try:
        result = subprocess.run(
            ["netstat", "-an", "-p", "TCP"],
            capture_output=True, text=True, timeout=10
        )
        for line in result.stdout.strip().split("\n"):
            parts = line.split()
            if len(parts) >= 4 and parts[0] == "TCP":
                local = parts[1]
                remote = parts[2]
                state = parts[3]
                local_ip, local_port = local.rsplit(":", 1) if ":" in local else (local, "0")
                remote_ip, remote_port = remote.rsplit(":", 1) if ":" in remote else (remote, "0")
                try:
                    connections.append({
                        "local_ip": local_ip, "local_port": int(local_port),
                        "remote_ip": remote_ip, "remote_port": int(remote_port),
                        "state": state,
                    })
                except ValueError:
                    continue
    except Exception as e:
        print(f"[WARN] get_connections: {e}")
    return connections


def analyze_connections(connections):
    """Analyze connections for suspicious activity."""
    suspicious = []
    known = []

    for conn in connections:
        local_port = conn["local_port"]
        remote_ip = conn["remote_ip"]

        # Known service
        if local_port in KNOWN_PORTS:
            known.append({**conn, "service": KNOWN_PORTS[local_port]})
            continue

        # Check if remote IP is in whitelist
        if remote_ip not in WHITELIST_IPS and conn["state"] == "ESTABLISHED":
            # External connection — flag if on unusual port
            if local_port not in KNOWN_PORTS and conn["remote_port"] not in {80, 443, 53}:
                suspicious.append({
                    **conn,
                    "reason": f"External connection on port {local_port}",
                })

    return known, suspicious


def do_scan():
    """Full network scan."""
    db = init_db()
    connections = get_connections()
    known, suspicious = analyze_connections(connections)

    report = {
        "ts": datetime.now().isoformat(),
        "total_connections": len(connections),
        "known_services": len(known),
        "suspicious": len(suspicious),
        "known_details": known[:20],
        "suspicious_details": suspicious[:10],
        "listening_ports": sorted(set(
            c["local_port"] for c in connections if c["state"] == "LISTENING"
        )),
    }

    db.execute(
        "INSERT INTO scans (ts, total_connections, suspicious, known_services, report) VALUES (?,?,?,?,?)",
        (time.time(), len(connections), len(suspicious), len(known), json.dumps(report))
    )
    db.commit()
    db.close()
    return report


def main():
    parser = argparse.ArgumentParser(description="Windows Network Guard")
    parser.add_argument("--once", "--scan", action="store_true", help="Full scan")
    parser.add_argument("--whitelist", action="store_true", help="Show whitelist")
    parser.add_argument("--report", action="store_true", help="History")
    args = parser.parse_args()

    if args.whitelist:
        print(json.dumps({"ips": sorted(WHITELIST_IPS), "ports": KNOWN_PORTS}, indent=2))
    else:
        result = do_scan()
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
