#!/usr/bin/env python3
"""win_firewall_analyzer.py — Analyse regles firewall Windows.

Detecte ports ouverts inutiles, suggere durcissement.

Usage:
    python dev/win_firewall_analyzer.py --once
    python dev/win_firewall_analyzer.py --rules
    python dev/win_firewall_analyzer.py --audit
    python dev/win_firewall_analyzer.py --suggest
"""
import argparse
import json
import os
import socket
import sqlite3
import subprocess
import time
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "firewall_analyzer.db"

KNOWN_SAFE_PORTS = {
    80: "HTTP", 443: "HTTPS", 22: "SSH", 53: "DNS",
    1234: "LM Studio", 11434: "Ollama", 9742: "JARVIS WS",
    8080: "Dashboard", 18800: "OpenClaw Proxy", 5678: "n8n",
    8901: "MCP SSE", 18789: "OpenClaw Gateway",
}


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS scans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, rules_count INTEGER, open_ports INTEGER,
        suspicious_count INTEGER, report TEXT)""")
    db.execute("""CREATE TABLE IF NOT EXISTS rules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, name TEXT, direction TEXT, action TEXT,
        protocol TEXT, local_port TEXT, enabled TEXT)""")
    db.commit()
    return db


def get_firewall_rules():
    """Get firewall rules via netsh."""
    rules = []
    try:
        result = subprocess.run(
            ["netsh", "advfirewall", "firewall", "show", "rule", "name=all", "dir=in"],
            capture_output=True, text=True, timeout=30
        )
        current = {}
        for line in result.stdout.split("\n"):
            line = line.strip()
            if line.startswith("Rule Name:"):
                if current:
                    rules.append(current)
                current = {"name": line.split(":", 1)[1].strip()}
            elif ":" in line and current:
                key, val = line.split(":", 1)
                current[key.strip().lower().replace(" ", "_")] = val.strip()
        if current:
            rules.append(current)
    except Exception:
        pass
    return rules


def scan_open_ports(start=1, end=1024):
    """Quick scan for open TCP ports."""
    open_ports = []
    for port in list(range(start, min(end, 100))) + list(KNOWN_SAFE_PORTS.keys()):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.1)
            if s.connect_ex(("127.0.0.1", port)) == 0:
                open_ports.append({
                    "port": port,
                    "service": KNOWN_SAFE_PORTS.get(port, "unknown"),
                    "known": port in KNOWN_SAFE_PORTS,
                })
            s.close()
        except Exception:
            pass
    return open_ports


def do_audit():
    """Full firewall audit."""
    db = init_db()
    rules = get_firewall_rules()
    open_ports = scan_open_ports()

    # Analyze rules
    enabled_inbound = [r for r in rules if r.get("enabled", "").lower() == "yes"]
    allow_rules = [r for r in enabled_inbound if r.get("action", "").lower() == "allow"]

    # Detect suspicious
    suspicious = [p for p in open_ports if not p["known"]]

    # Suggestions
    suggestions = []
    if len(allow_rules) > 50:
        suggestions.append("Trop de regles Allow inbound — reviser les regles inutiles")
    if suspicious:
        suggestions.append(f"{len(suspicious)} ports ouverts non-reconnus — verifier")
    if not any(r.get("name", "").lower().find("block") >= 0 for r in rules[:100]):
        suggestions.append("Peu de regles Block explicites — ajouter des blocages")

    report = {
        "ts": datetime.now().isoformat(),
        "total_rules": len(rules),
        "enabled_inbound": len(enabled_inbound),
        "allow_rules": len(allow_rules),
        "open_ports": len(open_ports),
        "suspicious_ports": len(suspicious),
        "known_services": [p for p in open_ports if p["known"]],
        "unknown_ports": suspicious[:10],
        "suggestions": suggestions,
    }

    db.execute(
        "INSERT INTO scans (ts, rules_count, open_ports, suspicious_count, report) VALUES (?,?,?,?,?)",
        (time.time(), len(rules), len(open_ports), len(suspicious), json.dumps(report))
    )
    db.commit()
    db.close()
    return report


def main():
    parser = argparse.ArgumentParser(description="Windows Firewall Analyzer")
    parser.add_argument("--once", "--audit", action="store_true", help="Full audit")
    parser.add_argument("--rules", action="store_true", help="List rules")
    parser.add_argument("--suggest", action="store_true", help="Suggestions")
    args = parser.parse_args()

    if args.rules:
        rules = get_firewall_rules()
        print(json.dumps(rules[:30], ensure_ascii=False, indent=2))
    else:
        result = do_audit()
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
