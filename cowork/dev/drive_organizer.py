#!/usr/bin/env python3
"""drive_organizer.py — Organize and index files on C:/F:/H: drives."""
import argparse
import json
import os
import shutil
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "etoile.db")
DRIVES = ["C:/", "F:/", "H:/"]
TEMP_DIRS = [
    os.path.expandvars(r"%LOCALAPPDATA%\Temp"),
    os.path.expandvars(r"%LOCALAPPDATA%\pip\cache"),
    os.path.expandvars(r"%APPDATA%\npm-cache"),
]
INDEX_EXTS = {".py", ".js", ".json"}
SEVEN_DAYS = 7 * 86400


def init_db():
    con = sqlite3.connect(DB_PATH)
    con.execute(
        "CREATE TABLE IF NOT EXISTS memories ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, category TEXT, content TEXT)"
    )
    con.commit()
    return con


def log_memory(con, category, content):
    con.execute(
        "INSERT INTO memories (ts, category, content) VALUES (?, ?, ?)",
        (datetime.now().isoformat(), category, json.dumps(content, ensure_ascii=False)),
    )
    con.commit()


def scan_recent(drives, max_depth=3):
    """Scan top-level dirs for recently modified files."""
    cutoff = time.time() - SEVEN_DAYS
    new_files = []
    scanned = 0
    for drive in drives:
        if not os.path.isdir(drive):
            continue
        for root, dirs, files in os.walk(drive):
            depth = root.replace(drive, "").count(os.sep)
            if depth >= max_depth:
                dirs.clear()
                continue
            scanned += 1
            for f in files:
                fp = os.path.join(root, f)
                try:
                    if os.path.getmtime(fp) > cutoff:
                        new_files.append(fp)
                except OSError:
                    pass
    return scanned, new_files


def clean_temp():
    """Remove temp files, pip cache, npm cache. Returns MB freed."""
    freed = 0
    for d in TEMP_DIRS:
        if not os.path.isdir(d):
            continue
        for root, dirs, files in os.walk(d, topdown=False):
            for f in files:
                fp = os.path.join(root, f)
                try:
                    sz = os.path.getsize(fp)
                    os.remove(fp)
                    freed += sz
                except OSError:
                    pass
            for dd in dirs:
                dp = os.path.join(root, dd)
                try:
                    shutil.rmtree(dp, ignore_errors=True)
                except OSError:
                    pass
    return round(freed / (1024 * 1024), 2)


def index_files(drives, max_depth=4):
    """Index .py/.js/.json files modified in last 7 days."""
    cutoff = time.time() - SEVEN_DAYS
    indexed = []
    for drive in drives:
        if not os.path.isdir(drive):
            continue
        for root, dirs, files in os.walk(drive):
            depth = root.replace(drive, "").count(os.sep)
            if depth >= max_depth:
                dirs.clear()
                continue
            # Skip hidden/system dirs
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in {"node_modules", "__pycache__", ".git"}]
            for f in files:
                ext = os.path.splitext(f)[1].lower()
                if ext not in INDEX_EXTS:
                    continue
                fp = os.path.join(root, f)
                try:
                    mtime = os.path.getmtime(fp)
                    if mtime > cutoff:
                        indexed.append({"path": fp, "size": os.path.getsize(fp), "modified": datetime.fromtimestamp(mtime).isoformat()})
                except OSError:
                    pass
    return indexed


def main():
    parser = argparse.ArgumentParser(description="Drive organizer — scan, clean, index")
    parser.add_argument("--once", action="store_true", help="Scan recent files, index new ones, report")
    parser.add_argument("--clean", action="store_true", help="Clean temp/pip/npm caches")
    parser.add_argument("--index", action="store_true", help="Index .py/.js/.json modified in last 7 days")
    args = parser.parse_args()
    if not args.once and not args.clean and not args.index:
        args.once = True

    result = {"scanned_dirs": 0, "new_files": 0, "cleaned_mb": 0, "indexed": 0}

    if args.once or args.index:
        indexed = index_files(DRIVES)
        result["indexed"] = len(indexed)

    if args.once:
        scanned, new = scan_recent(DRIVES)
        result["scanned_dirs"] = scanned
        result["new_files"] = len(new)

    if args.clean:
        result["cleaned_mb"] = clean_temp()

    con = init_db()
    log_memory(con, "drive_index", result)
    con.close()

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
