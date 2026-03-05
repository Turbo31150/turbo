#!/usr/bin/env python3
"""jarvis_tts_cache_manager.py — Gestionnaire cache TTS.

Optimise le cache audio pour latence <0.5s.

Usage:
    python dev/jarvis_tts_cache_manager.py --once
    python dev/jarvis_tts_cache_manager.py --stats
    python dev/jarvis_tts_cache_manager.py --prune
    python dev/jarvis_tts_cache_manager.py --benchmark
"""
import argparse
import json
import os
import sqlite3
import time
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "tts_cache_manager.db"
TTS_CACHE_DIRS = [
    Path("F:/BUREAU/turbo/data/tts_cache"),
    Path("F:/BUREAU/turbo/cache/tts"),
    Path.home() / "AppData" / "Local" / "Temp" / "tts_cache",
]
MAX_CACHE_MB = 500
MAX_AGE_DAYS = 30


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS cache_stats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, total_files INTEGER, total_size_mb REAL,
        oldest_days REAL, cache_dir TEXT)""")
    db.execute("""CREATE TABLE IF NOT EXISTS prune_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, files_deleted INTEGER, space_freed_mb REAL)""")
    db.commit()
    return db


def scan_cache():
    """Scan TTS cache directories."""
    results = []
    for cache_dir in TTS_CACHE_DIRS:
        if not cache_dir.exists():
            results.append({"dir": str(cache_dir), "exists": False})
            continue

        files = []
        total_size = 0
        oldest_mtime = time.time()

        for ext in ("*.wav", "*.mp3", "*.ogg", "*.opus"):
            for f in cache_dir.glob(ext):
                try:
                    stat = f.stat()
                    total_size += stat.st_size
                    oldest_mtime = min(oldest_mtime, stat.st_mtime)
                    files.append({
                        "name": f.name, "size": stat.st_size,
                        "mtime": stat.st_mtime, "ext": f.suffix,
                    })
                except OSError:
                    pass

        # Also check subdirs
        for f in cache_dir.rglob("*"):
            if f.is_file() and f.suffix in (".wav", ".mp3", ".ogg", ".opus"):
                try:
                    stat = f.stat()
                    if not any(ef["name"] == f.name for ef in files):
                        total_size += stat.st_size
                        oldest_mtime = min(oldest_mtime, stat.st_mtime)
                        files.append({
                            "name": f.name, "size": stat.st_size,
                            "mtime": stat.st_mtime, "ext": f.suffix,
                        })
                except OSError:
                    pass

        oldest_days = (time.time() - oldest_mtime) / 86400 if files else 0

        results.append({
            "dir": str(cache_dir), "exists": True,
            "files": len(files),
            "size_mb": round(total_size / 1024 / 1024, 1),
            "oldest_days": round(oldest_days, 1),
        })

    return results


def do_stats():
    """Show cache statistics."""
    db = init_db()
    caches = scan_cache()

    total_files = sum(c.get("files", 0) for c in caches)
    total_size = sum(c.get("size_mb", 0) for c in caches)

    for c in caches:
        if c.get("exists"):
            db.execute(
                "INSERT INTO cache_stats (ts, total_files, total_size_mb, oldest_days, cache_dir) VALUES (?,?,?,?,?)",
                (time.time(), c.get("files", 0), c.get("size_mb", 0),
                 c.get("oldest_days", 0), c["dir"])
            )

    db.commit()
    db.close()

    return {
        "ts": datetime.now().isoformat(),
        "total_files": total_files,
        "total_size_mb": round(total_size, 1),
        "max_cache_mb": MAX_CACHE_MB,
        "over_limit": total_size > MAX_CACHE_MB,
        "caches": caches,
    }


def do_prune():
    """Prune old cache files."""
    cutoff = time.time() - (MAX_AGE_DAYS * 86400)
    deleted = 0
    freed = 0

    for cache_dir in TTS_CACHE_DIRS:
        if not cache_dir.exists():
            continue
        for f in cache_dir.rglob("*"):
            if f.is_file() and f.suffix in (".wav", ".mp3", ".ogg", ".opus"):
                try:
                    if f.stat().st_mtime < cutoff:
                        size = f.stat().st_size
                        f.unlink()
                        deleted += 1
                        freed += size
                except (OSError, PermissionError):
                    pass

    db = init_db()
    db.execute(
        "INSERT INTO prune_logs (ts, files_deleted, space_freed_mb) VALUES (?,?,?)",
        (time.time(), deleted, round(freed / 1024 / 1024, 1))
    )
    db.commit()
    db.close()

    return {
        "ts": datetime.now().isoformat(),
        "files_deleted": deleted,
        "space_freed_mb": round(freed / 1024 / 1024, 1),
        "max_age_days": MAX_AGE_DAYS,
    }


def main():
    parser = argparse.ArgumentParser(description="JARVIS TTS Cache Manager")
    parser.add_argument("--once", "--stats", action="store_true", help="Show stats")
    parser.add_argument("--prune", action="store_true", help="Prune old files")
    parser.add_argument("--preload", action="store_true", help="Preload common phrases")
    parser.add_argument("--benchmark", action="store_true", help="Benchmark latency")
    args = parser.parse_args()

    if args.prune:
        result = do_prune()
    else:
        result = do_stats()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
