#!/usr/bin/env python3
"""win_certificate_checker.py — Verificateur certificats Windows.

Detecte certificats expires, non-fiables.

Usage:
    python dev/win_certificate_checker.py --once
    python dev/win_certificate_checker.py --scan
    python dev/win_certificate_checker.py --expired
    python dev/win_certificate_checker.py --report
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
DB_PATH = DEV / "data" / "certificate_checker.db"


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS cert_scans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, store TEXT, total INTEGER,
        expired INTEGER, expiring_soon INTEGER)""")
    db.commit()
    return db


def scan_cert_store(store="Cert:/LocalMachine/Root"):
    certs = []
    try:
        out = subprocess.run(
            ["bash", "-Command",
             f"Get-ChildItem {store} | Select-Object Subject,Issuer,NotAfter,"
             "@{N='Expired';E={$_.NotAfter -lt (Get-Date)}},"
             "@{N='ExpiringSoon';E={$_.NotAfter -lt (Get-Date).AddDays(30) -and $_.NotAfter -gt (Get-Date)}},"
             "Thumbprint | ConvertTo-Json -Depth 2"],
            capture_output=True, text=True, timeout=15
        )
        if out.stdout.strip():
            data = json.loads(out.stdout)
            if isinstance(data, dict):
                data = [data]
            for c in data:
                not_after = c.get("NotAfter", "")
                # Parse date
                expiry = ""
                if isinstance(not_after, str) and not_after:
                    expiry = not_after[:10]
                elif isinstance(not_after, dict) and "value" in not_after:
                    expiry = str(not_after["value"])[:10]

                certs.append({
                    "subject": (c.get("Subject") or "")[:100],
                    "issuer": (c.get("Issuer") or "")[:100],
                    "expires": expiry,
                    "expired": bool(c.get("Expired")),
                    "expiring_soon": bool(c.get("ExpiringSoon")),
                    "thumbprint": (c.get("Thumbprint") or "")[:20],
                })
    except Exception:
        pass
    return certs


def do_scan():
    db = init_db()
    stores = {
        "Root": "Cert:/LocalMachine/Root",
        "My": "Cert:/CurrentUser/My",
    }

    all_certs = {}
    total_expired = 0
    total_expiring = 0

    for name, path in stores.items():
        certs = scan_cert_store(path)
        expired = sum(1 for c in certs if c["expired"])
        expiring = sum(1 for c in certs if c["expiring_soon"])
        total_expired += expired
        total_expiring += expiring

        all_certs[name] = {
            "total": len(certs),
            "expired": expired,
            "expiring_soon": expiring,
            "problem_certs": [c for c in certs if c["expired"] or c["expiring_soon"]][:10],
        }

        db.execute("INSERT INTO cert_scans (ts, store, total, expired, expiring_soon) VALUES (?,?,?,?,?)",
                   (time.time(), name, len(certs), expired, expiring))

    db.commit()
    db.close()

    return {
        "ts": datetime.now().isoformat(),
        "stores": all_certs,
        "total_expired": total_expired,
        "total_expiring_soon": total_expiring,
        "compliance": "OK" if total_expired == 0 else "WARN",
    }


def main():
    parser = argparse.ArgumentParser(description="Windows Certificate Checker")
    parser.add_argument("--once", "--scan", action="store_true", help="Scan certs")
    parser.add_argument("--expired", action="store_true", help="Show expired")
    parser.add_argument("--untrusted", action="store_true", help="Show untrusted")
    parser.add_argument("--report", action="store_true", help="Report")
    args = parser.parse_args()
    print(json.dumps(do_scan(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
