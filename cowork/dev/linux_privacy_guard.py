#!/usr/bin/env python3
"""win_privacy_guard.py — Audit et durcissement vie privee Windows.

Verifie telemetrie, tracking, permissions apps, score privacy 0-100.

Usage:
    python dev/win_privacy_guard.py --once
    python dev/win_privacy_guard.py --scan
    python dev/win_privacy_guard.py --telemetry
    python dev/win_privacy_guard.py --report
"""
import argparse
import json
import os
import sqlite3
import time
import winreg
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "privacy_guard.db"

PRIVACY_CHECKS = [
    {"name": "DiagTrack", "path": r"SYSTEM\CurrentControlSet\Services\DiagTrack", "key": "Start",
     "hive": "HKLM", "good_value": 4, "desc": "Telemetrie diagnostique", "weight": 15},
    {"name": "AdvertisingID", "path": r"SOFTWARE\Microsoft\Windows\CurrentVersion\AdvertisingInfo",
     "key": "Enabled", "hive": "HKCU", "good_value": 0, "desc": "ID publicitaire", "weight": 10},
    {"name": "ConnectedUser", "path": r"SOFTWARE\Policies\Microsoft\Windows\DataCollection",
     "key": "AllowTelemetry", "hive": "HKLM", "good_value": 0, "desc": "Telemetrie utilisateur", "weight": 15},
    {"name": "LocationService", "path": r"SOFTWARE\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\location",
     "key": "Value", "hive": "HKCU", "good_value": "Deny", "desc": "Service localisation", "weight": 10},
    {"name": "Camera", "path": r"SOFTWARE\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\webcam",
     "key": "Value", "hive": "HKCU", "good_value": "Deny", "desc": "Acces camera", "weight": 5},
    {"name": "Microphone", "path": r"SOFTWARE\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\microphone",
     "key": "Value", "hive": "HKCU", "good_value": "Allow", "desc": "Acces micro (requis JARVIS)", "weight": 0},
    {"name": "ActivityHistory", "path": r"SOFTWARE\Policies\Microsoft\Windows\System",
     "key": "PublishUserActivities", "hive": "HKLM", "good_value": 0, "desc": "Historique activites", "weight": 10},
    {"name": "Cortana", "path": r"SOFTWARE\Policies\Microsoft\Windows\Windows Search",
     "key": "AllowCortana", "hive": "HKLM", "good_value": 0, "desc": "Cortana", "weight": 5},
    {"name": "WiFiSense", "path": r"SOFTWARE\Microsoft\WcmSvc\wifinetworkmanager\config",
     "key": "AutoConnectAllowedOEM", "hive": "HKLM", "good_value": 0, "desc": "WiFi Sense", "weight": 5},
    {"name": "ErrorReporting", "path": r"SOFTWARE\Microsoft\Windows\Windows Error Reporting",
     "key": "Disabled", "hive": "HKLM", "good_value": 1, "desc": "Rapport d'erreurs", "weight": 5},
]


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS scans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, score INTEGER, checks_passed INTEGER,
        checks_total INTEGER, report TEXT)""")
    db.commit()
    return db


def check_registry(check):
    """Check a single registry privacy setting."""
    hive = winreg.HKEY_CURRENT_USER if check["hive"] == "HKCU" else winreg.HKEY_LOCAL_MACHINE
    try:
        key = winreg.OpenKey(hive, check["path"])
        value, _ = winreg.QueryValueEx(key, check["key"])
        winreg.CloseKey(key)
        is_good = value == check["good_value"]
        return {"name": check["name"], "desc": check["desc"], "current": value,
                "expected": check["good_value"], "ok": is_good, "weight": check["weight"]}
    except FileNotFoundError:
        return {"name": check["name"], "desc": check["desc"], "current": "NOT_SET",
                "expected": check["good_value"], "ok": False, "weight": check["weight"]}
    except Exception as e:
        return {"name": check["name"], "desc": check["desc"], "current": f"ERROR: {e}",
                "expected": check["good_value"], "ok": False, "weight": check["weight"]}


def do_scan():
    """Run full privacy scan."""
    db = init_db()
    results = []
    total_weight = sum(c["weight"] for c in PRIVACY_CHECKS)
    earned_weight = 0

    for check in PRIVACY_CHECKS:
        result = check_registry(check)
        results.append(result)
        if result["ok"]:
            earned_weight += result["weight"]

    # Base score starts at 20 (Windows always has some privacy)
    score = 20 + int(80 * earned_weight / max(total_weight, 1))
    passed = sum(1 for r in results if r["ok"])

    report = {
        "ts": datetime.now().isoformat(),
        "privacy_score": score,
        "checks_passed": passed,
        "checks_total": len(results),
        "results": results,
        "recommendations": [r for r in results if not r["ok"] and r["weight"] > 0],
    }

    db.execute(
        "INSERT INTO scans (ts, score, checks_passed, checks_total, report) VALUES (?,?,?,?,?)",
        (time.time(), score, passed, len(results), json.dumps(report))
    )
    db.commit()
    db.close()
    return report


def main():
    parser = argparse.ArgumentParser(description="Windows Privacy Guard")
    parser.add_argument("--once", "--scan", action="store_true", help="Full privacy scan")
    parser.add_argument("--telemetry", action="store_true", help="Check telemetry only")
    parser.add_argument("--report", action="store_true", help="History")
    args = parser.parse_args()

    result = do_scan()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
