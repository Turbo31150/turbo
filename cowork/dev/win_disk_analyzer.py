#!/usr/bin/env python3
"""win_disk_analyzer.py — Analyse disque avancee.

Gros fichiers, doublons, arborescence par taille.

Usage:
    python dev/win_disk_analyzer.py --once
    python dev/win_disk_analyzer.py --scan C:
    python dev/win_disk_analyzer.py --large
    python dev/win_disk_analyzer.py --duplicates
"""
import argparse
import hashlib
import json
import os
import sqlite3
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "disk_analyzer.db"


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS scans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, drive TEXT, total_files INTEGER,
        total_size_gb REAL, large_files INTEGER, duplicates INTEGER)""")
    db.execute("""CREATE TABLE IF NOT EXISTS large_files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, filepath TEXT, size_mb REAL, extension TEXT)""")
    db.execute("""CREATE TABLE IF NOT EXISTS duplicates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, hash TEXT, filepath1 TEXT, filepath2 TEXT, size_mb REAL)""")
    db.commit()
    return db


def scan_directory(root, max_depth=4):
    """Scan directory for files."""
    files = []
    total_size = 0
    root_depth = str(root).count(os.sep)

    for dirpath, dirnames, filenames in os.walk(root):
        # Limit depth
        current_depth = dirpath.count(os.sep) - root_depth
        if current_depth >= max_depth:
            dirnames.clear()
            continue

        # Skip system directories
        skip = ["$Recycle.Bin", "System Volume Information", "Windows", "node_modules", ".git"]
        dirnames[:] = [d for d in dirnames if d not in skip]

        for f in filenames:
            try:
                fp = os.path.join(dirpath, f)
                size = os.path.getsize(fp)
                total_size += size
                files.append({"path": fp, "size": size, "ext": os.path.splitext(f)[1].lower()})
            except (OSError, PermissionError):
                pass

    return files, total_size


def find_large_files(files, min_mb=100):
    """Find files larger than min_mb."""
    threshold = min_mb * 1024 * 1024
    large = [f for f in files if f["size"] > threshold]
    return sorted(large, key=lambda x: x["size"], reverse=True)[:50]


def find_duplicates(files, min_mb=10):
    """Find duplicate files by size + partial hash."""
    threshold = min_mb * 1024 * 1024

    # Group by size
    by_size = defaultdict(list)
    for f in files:
        if f["size"] > threshold:
            by_size[f["size"]].append(f)

    duplicates = []
    for size, group in by_size.items():
        if len(group) < 2:
            continue

        # Hash first 4KB
        hashes = {}
        for f in group[:10]:  # Limit per group
            try:
                with open(f["path"], "rb") as fh:
                    h = hashlib.md5(fh.read(4096)).hexdigest()
                    if h in hashes:
                        duplicates.append({
                            "hash": h,
                            "file1": hashes[h][:150],
                            "file2": f["path"][:150],
                            "size_mb": round(size / 1024 / 1024, 1),
                        })
                    else:
                        hashes[h] = f["path"]
            except (OSError, PermissionError):
                pass

    return duplicates[:30]


def treemap(files, top_n=20):
    """Directory size treemap."""
    dir_sizes = defaultdict(int)
    for f in files:
        parent = os.path.dirname(f["path"])
        # Get top-level subdirectory
        parts = parent.split(os.sep)
        if len(parts) >= 2:
            top_dir = os.sep.join(parts[:3])
            dir_sizes[top_dir] += f["size"]

    sorted_dirs = sorted(dir_sizes.items(), key=lambda x: x[1], reverse=True)[:top_n]
    return [{"dir": d, "size_gb": round(s / 1024 / 1024 / 1024, 2)} for d, s in sorted_dirs]


def do_scan(drive="C:"):
    """Full disk analysis."""
    db = init_db()
    root = drive + os.sep if not drive.endswith(os.sep) else drive

    files, total_size = scan_directory(root)
    large = find_large_files(files)
    dupes = find_duplicates(files)

    # Store large files
    for f in large[:20]:
        db.execute(
            "INSERT INTO large_files (ts, filepath, size_mb, extension) VALUES (?,?,?,?)",
            (time.time(), f["path"][:300], round(f["size"] / 1024 / 1024, 1), f["ext"])
        )

    # Store duplicates
    for d in dupes[:10]:
        db.execute(
            "INSERT INTO duplicates (ts, hash, filepath1, filepath2, size_mb) VALUES (?,?,?,?,?)",
            (time.time(), d["hash"], d["file1"], d["file2"], d["size_mb"])
        )

    # Extension breakdown
    ext_sizes = defaultdict(int)
    for f in files:
        ext_sizes[f["ext"]] += f["size"]
    top_ext = sorted(ext_sizes.items(), key=lambda x: x[1], reverse=True)[:10]

    report = {
        "ts": datetime.now().isoformat(),
        "drive": drive,
        "total_files": len(files),
        "total_size_gb": round(total_size / 1024 / 1024 / 1024, 2),
        "large_files_count": len(large),
        "duplicates_count": len(dupes),
        "top_large": [{"path": f["path"][-80:], "mb": round(f["size"] / 1024 / 1024, 1)} for f in large[:10]],
        "top_extensions": [{"ext": e or "(none)", "gb": round(s / 1024 / 1024 / 1024, 2)} for e, s in top_ext],
        "treemap": treemap(files),
    }

    db.execute(
        "INSERT INTO scans (ts, drive, total_files, total_size_gb, large_files, duplicates) VALUES (?,?,?,?,?,?)",
        (time.time(), drive, len(files), report["total_size_gb"], len(large), len(dupes))
    )
    db.commit()
    db.close()
    return report


def main():
    parser = argparse.ArgumentParser(description="Windows Disk Analyzer")
    parser.add_argument("--once", action="store_true", help="Quick scan")
    parser.add_argument("--scan", metavar="DRIVE", help="Scan drive")
    parser.add_argument("--large", action="store_true", help="Show large files")
    parser.add_argument("--duplicates", action="store_true", help="Find duplicates")
    parser.add_argument("--treemap", action="store_true", help="Directory treemap")
    args = parser.parse_args()

    drive = args.scan or "C:"
    if args.large:
        db = init_db()
        rows = db.execute("SELECT filepath, size_mb FROM large_files ORDER BY size_mb DESC LIMIT 20").fetchall()
        db.close()
        print(json.dumps([{"path": r[0], "mb": r[1]} for r in rows], indent=2))
    elif args.duplicates:
        db = init_db()
        rows = db.execute("SELECT hash, filepath1, filepath2, size_mb FROM duplicates ORDER BY size_mb DESC LIMIT 20").fetchall()
        db.close()
        print(json.dumps([{"hash": r[0], "f1": r[1], "f2": r[2], "mb": r[3]} for r in rows], indent=2))
    else:
        result = do_scan(drive)
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
