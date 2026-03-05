#!/usr/bin/env python3
"""win_network_analyzer.py — Analyse reseau Windows.

Connexions actives, bande passante, resolution DNS.

Usage:
    python dev/win_network_analyzer.py --once
    python dev/win_network_analyzer.py --scan
    python dev/win_network_analyzer.py --connections
    python dev/win_network_analyzer.py --dns
"""
import argparse
import json
import os
import socket
import sqlite3
import subprocess
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "network_analyzer.db"

CLUSTER_IPS = {
    "127.0.0.1": "localhost",
    "10.5.0.2": "M1_docker",
    "192.168.1.26": "M2",
    "192.168.1.113": "M3",
    "0.0.0.0": "all_interfaces",
}


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS scans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, total_connections INTEGER, established INTEGER,
        listening INTEGER, suspicious INTEGER, report TEXT)""")
    db.execute("""CREATE TABLE IF NOT EXISTS connections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, local_addr TEXT, remote_addr TEXT,
        state TEXT, process TEXT, suspicious INTEGER DEFAULT 0)""")
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
        for line in result.stdout.split("\n"):
            parts = line.split()
            if len(parts) >= 4 and parts[0] == "TCP":
                local = parts[1]
                remote = parts[2]
                state = parts[3]
                connections.append({
                    "local": local, "remote": remote, "state": state,
                })
    except Exception:
        pass
    return connections


def analyze_connections(connections):
    """Analyze connections for suspicious activity."""
    suspicious = []
    by_state = defaultdict(int)
    by_remote = defaultdict(int)

    for conn in connections:
        by_state[conn["state"]] += 1

        remote_ip = conn["remote"].rsplit(":", 1)[0] if ":" in conn["remote"] else conn["remote"]
        by_remote[remote_ip] += 1

        # Check if suspicious
        if conn["state"] == "ESTABLISHED":
            if remote_ip not in CLUSTER_IPS and remote_ip != "*":
                # External connection
                port = conn["remote"].rsplit(":", 1)[-1] if ":" in conn["remote"] else "0"
                try:
                    port_num = int(port)
                    if port_num not in (80, 443, 53, 8080, 3389):
                        suspicious.append({
                            "remote": conn["remote"],
                            "local": conn["local"],
                            "reason": f"external_port_{port_num}",
                        })
                except ValueError:
                    pass

    return {
        "by_state": dict(by_state),
        "top_remotes": sorted(by_remote.items(), key=lambda x: x[1], reverse=True)[:10],
        "suspicious": suspicious[:10],
    }


def test_dns(domains=None):
    """Test DNS resolution times."""
    if domains is None:
        domains = ["google.com", "github.com", "anthropic.com", "pypi.org"]

    results = []
    for domain in domains:
        try:
            start = time.time()
            ip = socket.gethostbyname(domain)
            latency = (time.time() - start) * 1000
            results.append({"domain": domain, "ip": ip, "latency_ms": round(latency, 1), "ok": True})
        except Exception:
            results.append({"domain": domain, "ip": "", "latency_ms": 0, "ok": False})

    return results


def do_scan():
    """Full network scan."""
    db = init_db()
    connections = get_connections()
    analysis = analyze_connections(connections)
    dns = test_dns()

    established = sum(1 for c in connections if c["state"] == "ESTABLISHED")
    listening = sum(1 for c in connections if c["state"] == "LISTENING")

    # Store
    for conn in connections[:100]:
        is_suspicious = 1 if any(s["remote"] == conn["remote"] for s in analysis["suspicious"]) else 0
        db.execute(
            "INSERT INTO connections (ts, local_addr, remote_addr, state, suspicious) VALUES (?,?,?,?,?)",
            (time.time(), conn["local"], conn["remote"], conn["state"], is_suspicious)
        )

    report = {
        "ts": datetime.now().isoformat(),
        "total_connections": len(connections),
        "established": established,
        "listening": listening,
        "suspicious": len(analysis["suspicious"]),
        "states": analysis["by_state"],
        "top_remotes": [{"ip": ip, "count": c} for ip, c in analysis["top_remotes"]],
        "suspicious_connections": analysis["suspicious"],
        "dns_results": dns,
    }

    db.execute(
        "INSERT INTO scans (ts, total_connections, established, listening, suspicious, report) VALUES (?,?,?,?,?,?)",
        (time.time(), len(connections), established, listening, len(analysis["suspicious"]), json.dumps(report))
    )
    db.commit()
    db.close()
    return report


def main():
    parser = argparse.ArgumentParser(description="Windows Network Analyzer")
    parser.add_argument("--once", "--scan", action="store_true", help="Full scan")
    parser.add_argument("--connections", action="store_true", help="List connections")
    parser.add_argument("--dns", action="store_true", help="DNS test")
    parser.add_argument("--bandwidth", action="store_true", help="Bandwidth test")
    args = parser.parse_args()

    if args.dns:
        print(json.dumps(test_dns(), ensure_ascii=False, indent=2))
    else:
        result = do_scan()
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
