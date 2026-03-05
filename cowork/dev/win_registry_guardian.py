#!/usr/bin/env python3
"""Windows Registry Guardian — Monitor, backup, and protect registry keys.

Watches critical registry keys, detects unauthorized changes,
creates backups, and can restore to known-good states.
"""
import argparse
import json
import sqlite3
import subprocess
import time
from pathlib import Path

DB_PATH = Path(__file__).parent / "registry_guardian.db"
BACKUP_DIR = Path(__file__).parent / "registry_backups"

# Critical registry keys to monitor
WATCHED_KEYS = {
    "HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run": "Startup programs (machine)",
    "HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run": "Startup programs (user)",
    "HKLM\\SYSTEM\\CurrentControlSet\\Services": "Windows services",
    "HKLM\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\Winlogon": "Login settings",
    "HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Explorer\\Advanced": "Explorer settings",
    "HKLM\\SOFTWARE\\Policies": "Group policies",
    "HKCU\\Environment": "User environment variables",
}

def init_db():
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS snapshots (
        id INTEGER PRIMARY KEY, ts REAL, reg_key TEXT,
        value_hash TEXT, value_count INTEGER, raw_data TEXT)""")
    db.execute("""CREATE TABLE IF NOT EXISTS changes (
        id INTEGER PRIMARY KEY, ts REAL, reg_key TEXT,
        change_type TEXT, details TEXT, severity TEXT)""")
    db.execute("""CREATE TABLE IF NOT EXISTS backups (
        id INTEGER PRIMARY KEY, ts REAL, reg_key TEXT,
        backup_path TEXT, size_bytes INTEGER)""")
    db.commit()
    return db

def query_registry(key):
    """Query a registry key and return its values."""
    try:
        r = subprocess.run(
            ["reg", "query", key, "/s"],
            capture_output=True, text=True, timeout=10, encoding="utf-8", errors="replace")
        if r.returncode == 0:
            return r.stdout
    except (subprocess.TimeoutExpired, OSError):
        pass
    return ""

def hash_content(content):
    """Hash registry content for change detection."""
    import hashlib
    return hashlib.sha256(content.encode("utf-8", errors="replace")).hexdigest()[:16]

def take_snapshot(db):
    """Snapshot all watched registry keys."""
    changes_detected = 0
    for key, desc in WATCHED_KEYS.items():
        content = query_registry(key)
        if not content:
            continue

        h = hash_content(content)
        value_count = content.count("REG_")

        # Check for changes
        prev = db.execute(
            "SELECT value_hash, value_count FROM snapshots WHERE reg_key=? ORDER BY ts DESC LIMIT 1",
            (key,)).fetchone()

        if prev and prev[0] != h:
            diff = value_count - prev[1]
            severity = "high" if "Run" in key or "Services" in key else "medium"
            details = f"Hash changed: {prev[0]}→{h}, values: {prev[1]}→{value_count} ({diff:+d})"
            db.execute(
                "INSERT INTO changes (ts, reg_key, change_type, details, severity) VALUES (?,?,?,?,?)",
                (time.time(), key, "modified", details, severity))
            changes_detected += 1

        db.execute(
            "INSERT INTO snapshots (ts, reg_key, value_hash, value_count, raw_data) VALUES (?,?,?,?,?)",
            (time.time(), key, h, value_count, content[:5000]))

    db.commit()
    return changes_detected

def backup_key(db, key):
    """Export a registry key to .reg file."""
    BACKUP_DIR.mkdir(exist_ok=True)
    safe_name = key.replace("\\", "_").replace("/", "_")[:50]
    backup_path = BACKUP_DIR / f"{safe_name}_{time.strftime('%Y%m%d_%H%M')}.reg"
    try:
        r = subprocess.run(
            ["reg", "export", key, str(backup_path), "/y"],
            capture_output=True, text=True, timeout=15)
        if r.returncode == 0 and backup_path.exists():
            size = backup_path.stat().st_size
            db.execute(
                "INSERT INTO backups (ts, reg_key, backup_path, size_bytes) VALUES (?,?,?,?)",
                (time.time(), key, str(backup_path), size))
            db.commit()
            return str(backup_path), size
    except (subprocess.TimeoutExpired, OSError):
        pass
    return None, 0

def get_recent_changes(db, hours=24):
    """Get recent registry changes."""
    return db.execute(
        "SELECT ts, reg_key, change_type, details, severity FROM changes WHERE ts > ? ORDER BY ts DESC",
        (time.time() - hours * 3600,)).fetchall()

def main():
    parser = argparse.ArgumentParser(description="Windows Registry Guardian")
    parser.add_argument("--once", action="store_true", help="Single snapshot")
    parser.add_argument("--loop", action="store_true", help="Continuous monitoring")
    parser.add_argument("--backup", type=str, help="Backup a specific registry key")
    parser.add_argument("--backup-all", action="store_true", help="Backup all watched keys")
    parser.add_argument("--changes", action="store_true", help="Show recent changes")
    parser.add_argument("--interval", type=int, default=3600, help="Seconds between snapshots")
    args = parser.parse_args()

    db = init_db()

    if args.backup:
        path, size = backup_key(db, args.backup)
        if path:
            print(f"Backed up to {path} ({size} bytes)")
        else:
            print(f"Backup failed for {args.backup}")
        return

    if args.backup_all:
        for key, desc in WATCHED_KEYS.items():
            path, size = backup_key(db, key)
            if path:
                print(f"  OK {desc}: {size} bytes")
            else:
                print(f"  FAIL {desc}")
        return

    if args.changes:
        changes = get_recent_changes(db)
        print(f"=== Registry Changes (24h) — {len(changes)} ===")
        for ts, key, ctype, details, sev in changes:
            t = time.strftime('%H:%M', time.localtime(ts))
            icon = {"high": "🔴", "medium": "🟡"}.get(sev, "⚪")
            print(f"  {icon} [{t}] {key.split(chr(92))[-1]}: {details[:80]}")
        return

    if args.once or not args.loop:
        changes = take_snapshot(db)
        print(f"Registry snapshot: {len(WATCHED_KEYS)} keys monitored, {changes} changes detected")
        if changes:
            for c in get_recent_changes(db, 0.01):
                print(f"  ⚠ {c[3][:80]}")

    if args.loop:
        print("Registry Guardian en boucle continue...")
        while True:
            try:
                changes = take_snapshot(db)
                ts = time.strftime('%H:%M')
                print(f"[{ts}] Snapshot: {changes} changes")
                if changes > 0:
                    # Auto-backup changed keys
                    recent = get_recent_changes(db, 0.01)
                    for _, key, _, _, sev in recent:
                        if sev == "high":
                            backup_key(db, key)
                time.sleep(args.interval)
            except KeyboardInterrupt:
                break

if __name__ == "__main__":
    main()
