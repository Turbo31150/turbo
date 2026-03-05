#!/usr/bin/env python3
"""win_temp_cleaner.py — Nettoyeur temp intelligent.

Nettoie %TEMP%, prefetch, logs, thumbnails avec securite.

Usage:
    python dev/win_temp_cleaner.py --once
    python dev/win_temp_cleaner.py --scan
    python dev/win_temp_cleaner.py --clean
    python dev/win_temp_cleaner.py --stats
"""
import argparse
import json
import os
import sqlite3
import time
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "temp_cleaner.db"

TEMP_DIRS = [
    {"name": "TEMP", "path": os.environ.get("TEMP", "C:\\Users\\franc\\AppData\\Local\\Temp")},
    {"name": "Windows_Temp", "path": "C:\\Windows\\Temp"},
    {"name": "Prefetch", "path": "C:\\Windows\\Prefetch"},
    {"name": "ThumbCache", "path": os.path.expanduser("~\\AppData\\Local\\Microsoft\\Windows\\Explorer")},
]

SAFE_EXTENSIONS = {".tmp", ".log", ".bak", ".old", ".dmp", ".etl", ".cache"}
MAX_AGE_DAYS = 7


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS scans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, total_files INTEGER, total_size_mb REAL,
        cleanable_files INTEGER, cleanable_size_mb REAL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS cleans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, files_deleted INTEGER, space_freed_mb REAL,
        errors INTEGER)""")
    db.commit()
    return db


def scan_temp_dir(dir_info):
    """Scan a temp directory."""
    path = Path(dir_info["path"])
    if not path.exists():
        return {"name": dir_info["name"], "exists": False, "files": 0, "size_mb": 0}

    total_files = 0
    total_size = 0
    cleanable_files = 0
    cleanable_size = 0
    cutoff = time.time() - (MAX_AGE_DAYS * 86400)

    try:
        for item in path.iterdir():
            try:
                if item.is_file():
                    total_files += 1
                    size = item.stat().st_size
                    total_size += size
                    mtime = item.stat().st_mtime

                    # Cleanable if old enough and safe extension
                    if mtime < cutoff:
                        ext = item.suffix.lower()
                        if ext in SAFE_EXTENSIONS or dir_info["name"] in ("TEMP", "Windows_Temp"):
                            cleanable_files += 1
                            cleanable_size += size
            except (PermissionError, OSError):
                pass
    except (PermissionError, OSError):
        pass

    return {
        "name": dir_info["name"],
        "exists": True,
        "total_files": total_files,
        "total_size_mb": round(total_size / 1024 / 1024, 1),
        "cleanable_files": cleanable_files,
        "cleanable_size_mb": round(cleanable_size / 1024 / 1024, 1),
    }


def do_scan():
    """Scan all temp directories."""
    db = init_db()
    results = []

    for d in TEMP_DIRS:
        result = scan_temp_dir(d)
        results.append(result)

    total_files = sum(r.get("total_files", 0) for r in results)
    total_size = sum(r.get("total_size_mb", 0) for r in results)
    cleanable_files = sum(r.get("cleanable_files", 0) for r in results)
    cleanable_size = sum(r.get("cleanable_size_mb", 0) for r in results)

    db.execute(
        "INSERT INTO scans (ts, total_files, total_size_mb, cleanable_files, cleanable_size_mb) VALUES (?,?,?,?,?)",
        (time.time(), total_files, total_size, cleanable_files, cleanable_size)
    )
    db.commit()
    db.close()

    return {
        "ts": datetime.now().isoformat(),
        "total_files": total_files,
        "total_size_mb": round(total_size, 1),
        "cleanable_files": cleanable_files,
        "cleanable_size_mb": round(cleanable_size, 1),
        "max_age_days": MAX_AGE_DAYS,
        "directories": results,
    }


def do_clean():
    """Clean old temp files."""
    db = init_db()
    cutoff = time.time() - (MAX_AGE_DAYS * 86400)
    deleted = 0
    freed = 0
    errors = 0

    for d in TEMP_DIRS:
        path = Path(d["path"])
        if not path.exists():
            continue
        try:
            for item in path.iterdir():
                try:
                    if item.is_file() and item.stat().st_mtime < cutoff:
                        ext = item.suffix.lower()
                        if ext in SAFE_EXTENSIONS or d["name"] in ("TEMP", "Windows_Temp"):
                            size = item.stat().st_size
                            item.unlink()
                            deleted += 1
                            freed += size
                except (PermissionError, OSError):
                    errors += 1
        except (PermissionError, OSError):
            pass

    db.execute(
        "INSERT INTO cleans (ts, files_deleted, space_freed_mb, errors) VALUES (?,?,?,?)",
        (time.time(), deleted, round(freed / 1024 / 1024, 1), errors)
    )
    db.commit()
    db.close()

    return {
        "ts": datetime.now().isoformat(),
        "files_deleted": deleted,
        "space_freed_mb": round(freed / 1024 / 1024, 1),
        "errors": errors,
    }


def main():
    parser = argparse.ArgumentParser(description="Windows Temp Cleaner")
    parser.add_argument("--once", "--scan", action="store_true", help="Scan temp dirs")
    parser.add_argument("--clean", action="store_true", help="Clean old files")
    parser.add_argument("--schedule", action="store_true", help="Schedule cleaning")
    parser.add_argument("--stats", action="store_true", help="Cleaning history")
    args = parser.parse_args()

    if args.clean:
        result = do_clean()
    else:
        result = do_scan()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
