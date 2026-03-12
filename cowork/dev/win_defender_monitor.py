#!/usr/bin/env python3
"""win_defender_monitor.py — Moniteur Windows Defender.

Statut protection, historique scans, menaces detectees.

Usage:
    python dev/win_defender_monitor.py --once
    python dev/win_defender_monitor.py --status
    python dev/win_defender_monitor.py --threats
    python dev/win_defender_monitor.py --exclusions
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
DB_PATH = DEV / "data" / "defender_monitor.db"


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS scans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, protection_enabled INTEGER, realtime_enabled INTEGER,
        definitions_age_days REAL, threats_found INTEGER, report TEXT)""")
    db.commit()
    return db


def get_defender_status():
    """Get Windows Defender status via PowerShell."""
    try:
        result = subprocess.run(
            ["powershell", "-Command",
             "Get-MpComputerStatus | Select-Object AntivirusEnabled,RealTimeProtectionEnabled,AntivirusSignatureAge,QuickScanAge,FullScanAge | ConvertTo-Json"],
            capture_output=True, text=True, timeout=15
        )
        return json.loads(result.stdout)
    except Exception:
        return {}


def get_threat_history():
    """Get recent threat detections."""
    try:
        result = subprocess.run(
            ["powershell", "-Command",
             "Get-MpThreatDetection | Select-Object -First 10 ThreatID,DomainUser,ProcessName,ActionSuccess | ConvertTo-Json"],
            capture_output=True, text=True, timeout=15
        )
        data = json.loads(result.stdout) if result.stdout.strip() else []
        if isinstance(data, dict):
            data = [data]
        return data
    except Exception:
        return []


def do_status():
    """Full Defender status check."""
    db = init_db()
    status = get_defender_status()
    threats = get_threat_history()

    av_enabled = status.get("AntivirusEnabled", False)
    rt_enabled = status.get("RealTimeProtectionEnabled", False)
    sig_age = status.get("AntivirusSignatureAge", -1)

    # Compliance scoring
    score = 0
    issues = []
    if av_enabled:
        score += 30
    else:
        issues.append("Antivirus disabled!")
    if rt_enabled:
        score += 30
    else:
        issues.append("Real-time protection disabled!")
    if isinstance(sig_age, (int, float)) and sig_age <= 3:
        score += 20
    else:
        issues.append(f"Definitions age: {sig_age} days")
    if not threats:
        score += 20
    else:
        issues.append(f"{len(threats)} threats detected")

    report = {
        "ts": datetime.now().isoformat(),
        "antivirus_enabled": av_enabled,
        "realtime_enabled": rt_enabled,
        "signature_age_days": sig_age,
        "quick_scan_age": status.get("QuickScanAge", -1),
        "full_scan_age": status.get("FullScanAge", -1),
        "threats_count": len(threats),
        "compliance_score": score,
        "issues": issues,
        "recent_threats": threats[:5],
    }

    db.execute(
        "INSERT INTO scans (ts, protection_enabled, realtime_enabled, definitions_age_days, threats_found, report) VALUES (?,?,?,?,?,?)",
        (time.time(), int(av_enabled), int(rt_enabled), sig_age, len(threats), json.dumps(report))
    )
    db.commit()
    db.close()
    return report


def main():
    parser = argparse.ArgumentParser(description="Windows Defender Monitor")
    parser.add_argument("--once", "--status", action="store_true", help="Check status")
    parser.add_argument("--scan-history", action="store_true", help="Scan history")
    parser.add_argument("--threats", action="store_true", help="Threat history")
    parser.add_argument("--exclusions", action="store_true", help="Show exclusions")
    args = parser.parse_args()

    result = do_status()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
