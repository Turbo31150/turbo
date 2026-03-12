#!/usr/bin/env python3
"""jarvis_secret_scanner.py — Scanner de secrets JARVIS.

Detecte credentials/API keys exposes dans le code.

Usage:
    python dev/jarvis_secret_scanner.py --once
    python dev/jarvis_secret_scanner.py --scan
    python dev/jarvis_secret_scanner.py --files
    python dev/jarvis_secret_scanner.py --report
"""
import argparse
import json
import os
import re
import sqlite3
import time
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "secret_scanner.db"
SCAN_DIRS = [DEV, DEV.parent]

SECRET_PATTERNS = [
    (r'(?i)(?:api[_-]?key|apikey)\s*[=:]\s*["\']([a-zA-Z0-9_\-]{20,})["\']', "API Key"),
    (r'(?i)(?:password|passwd|pwd)\s*[=:]\s*["\']([^"\']{8,})["\']', "Password"),
    (r'(?i)(?:secret|token)\s*[=:]\s*["\']([a-zA-Z0-9_\-]{16,})["\']', "Secret/Token"),
    (r'(?i)(?:bearer)\s+([a-zA-Z0-9_\-\.]{20,})', "Bearer Token"),
    (r'sk-[a-zA-Z0-9]{20,}', "OpenAI-style Key"),
    (r'(?i)mongodb(?:\+srv)?://[^\s"\']+', "MongoDB Connection String"),
    (r'(?i)(?:postgres|mysql)://[^\s"\']+', "DB Connection String"),
]

SAFE_PATTERNS = [
    r'sk-lm-',  # LM Studio keys (local, not sensitive)
    r'example', r'placeholder', r'your[_-]?key', r'xxx',
]


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS scans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, files_scanned INTEGER, secrets_found INTEGER,
        severity TEXT, report TEXT)""")
    db.commit()
    return db


def is_safe(match_text):
    for safe in SAFE_PATTERNS:
        if re.search(safe, match_text, re.IGNORECASE):
            return True
    return False


def scan_file(filepath):
    findings = []
    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
        for pattern, secret_type in SECRET_PATTERNS:
            for m in re.finditer(pattern, content):
                matched = m.group(0)
                if not is_safe(matched):
                    line_num = content[:m.start()].count("\n") + 1
                    findings.append({
                        "file": str(filepath.relative_to(DEV.parent)),
                        "line": line_num,
                        "type": secret_type,
                        "preview": matched[:30] + "..." if len(matched) > 30 else matched,
                        "severity": "HIGH" if "password" in secret_type.lower() else "MEDIUM",
                    })
    except Exception:
        pass
    return findings


def do_scan():
    db = init_db()
    all_findings = []
    files_scanned = 0

    for scan_dir in SCAN_DIRS:
        if not scan_dir.exists():
            continue
        for ext in ("*.py", "*.js", "*.json", "*.yaml", "*.yml", "*.env", "*.toml"):
            for f in scan_dir.glob(ext):
                if f.stat().st_size > 500000:  # Skip >500KB
                    continue
                files_scanned += 1
                findings = scan_file(f)
                all_findings.extend(findings)

    # Check for .env files
    for scan_dir in SCAN_DIRS:
        for env in scan_dir.glob("**/.env"):
            all_findings.append({
                "file": str(env.relative_to(DEV.parent)),
                "line": 0,
                "type": ".env file",
                "preview": ".env file detected",
                "severity": "HIGH",
            })

    severity = "CLEAN"
    if any(f["severity"] == "HIGH" for f in all_findings):
        severity = "HIGH"
    elif all_findings:
        severity = "MEDIUM"

    db.execute("INSERT INTO scans (ts, files_scanned, secrets_found, severity, report) VALUES (?,?,?,?,?)",
               (time.time(), files_scanned, len(all_findings), severity,
                json.dumps(all_findings[:50])))
    db.commit()
    db.close()

    return {
        "ts": datetime.now().isoformat(),
        "files_scanned": files_scanned,
        "secrets_found": len(all_findings),
        "severity": severity,
        "by_type": {t: sum(1 for f in all_findings if f["type"] == t)
                    for t in set(f["type"] for f in all_findings)},
        "findings": all_findings[:20],
    }


def main():
    parser = argparse.ArgumentParser(description="JARVIS Secret Scanner")
    parser.add_argument("--once", "--scan", action="store_true", help="Scan for secrets")
    parser.add_argument("--files", action="store_true", help="List affected files")
    parser.add_argument("--env", action="store_true", help="Check .env files")
    parser.add_argument("--report", action="store_true", help="Report")
    args = parser.parse_args()
    print(json.dumps(do_scan(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
