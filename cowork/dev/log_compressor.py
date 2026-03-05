#!/usr/bin/env python3
"""log_compressor.py

Compress and archive old log files automatically.

Fonctionnalites :
* Scanne F:/BUREAU/turbo/data/ et dev/data/ pour les fichiers .log et .jsonl
* Compresse les fichiers de plus de 7 jours avec gzip
* Enregistre les statistiques de compression dans SQLite (cowork_gaps.db)
* Produit un rapport JSON

CLI :
    --once      : scan, compresse et affiche le resume JSON
    --stats     : affiche les statistiques de compression depuis la DB
    --dry-run   : montre ce qui serait compresse sans rien toucher

Stdlib-only (os, gzip, sqlite3, json, argparse, datetime, pathlib).
"""

import argparse
import gzip
import json
import os
import shutil
import sqlite3
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data"
DB_PATH = DATA_DIR / "cowork_gaps.db"

SCAN_DIRS = [
    Path(r"F:/BUREAU/turbo/data"),
    DATA_DIR,
]

FILE_EXTENSIONS = {".log", ".jsonl"}
MAX_AGE_DAYS = 7

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
def init_db(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS log_compression (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            original_path TEXT NOT NULL,
            compressed_path TEXT NOT NULL,
            original_size INTEGER NOT NULL,
            compressed_size INTEGER NOT NULL,
            ratio REAL NOT NULL,
            age_days REAL NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS compression_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            files_scanned INTEGER NOT NULL,
            files_compressed INTEGER NOT NULL,
            bytes_saved INTEGER NOT NULL,
            duration_ms INTEGER NOT NULL
        )
    """)
    conn.commit()

def get_db() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def human_bytes(num: int) -> str:
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if abs(num) < 1024.0:
            return f"{num:.1f}{unit}"
        num /= 1024.0
    return f"{num:.1f}PB"


def file_age_days(path: Path) -> float:
    mtime = path.stat().st_mtime
    age = time.time() - mtime
    return age / 86400.0


def find_compressible_files() -> list[dict]:
    """Find .log and .jsonl files older than MAX_AGE_DAYS."""
    results = []
    for base_dir in SCAN_DIRS:
        if not base_dir.is_dir():
            continue
        for root, _dirs, files in os.walk(str(base_dir)):
            for fname in files:
                fpath = Path(root) / fname
                if fpath.suffix.lower() not in FILE_EXTENSIONS:
                    continue
                # Skip already-compressed files
                if fpath.name.endswith(".gz"):
                    continue
                try:
                    age = file_age_days(fpath)
                    size = fpath.stat().st_size
                    if age >= MAX_AGE_DAYS and size > 0:
                        results.append({
                            "path": str(fpath),
                            "size": size,
                            "age_days": round(age, 1),
                        })
                except OSError:
                    continue
    return results


def compress_file(src: Path) -> dict:
    """Gzip a file in place, returning stats."""
    dst = src.with_suffix(src.suffix + ".gz")
    original_size = src.stat().st_size

    with open(src, "rb") as f_in:
        with gzip.open(str(dst), "wb", compresslevel=6) as f_out:
            shutil.copyfileobj(f_in, f_out)

    compressed_size = dst.stat().st_size
    ratio = compressed_size / original_size if original_size > 0 else 1.0

    # Remove original after successful compression
    src.unlink()

    return {
        "original_path": str(src),
        "compressed_path": str(dst),
        "original_size": original_size,
        "compressed_size": compressed_size,
        "ratio": round(ratio, 4),
        "saved": original_size - compressed_size,
    }

# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------
def action_once(dry_run: bool = False) -> dict:
    """Scan and compress old log files."""
    start_ms = int(time.time() * 1000)
    candidates = find_compressible_files()
    results = {
        "timestamp": datetime.now().isoformat(),
        "action": "dry-run" if dry_run else "compress",
        "files_scanned": len(candidates),
        "files_compressed": 0,
        "bytes_saved": 0,
        "details": [],
    }

    conn = get_db() if not dry_run else None

    for item in candidates:
        src = Path(item["path"])
        if dry_run:
            results["details"].append({
                "file": str(src),
                "size": human_bytes(item["size"]),
                "age_days": item["age_days"],
                "action": "would_compress",
            })
            results["files_compressed"] += 1
        else:
            try:
                stats = compress_file(src)
                results["details"].append(stats)
                results["files_compressed"] += 1
                results["bytes_saved"] += stats["saved"]

                # Record in DB
                conn.execute("""
                    INSERT INTO log_compression
                    (timestamp, original_path, compressed_path, original_size,
                     compressed_size, ratio, age_days)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    datetime.now().isoformat(),
                    stats["original_path"],
                    stats["compressed_path"],
                    stats["original_size"],
                    stats["compressed_size"],
                    stats["ratio"],
                    item["age_days"],
                ))
            except Exception as e:
                results["details"].append({
                    "file": str(src),
                    "error": str(e),
                })

    duration_ms = int(time.time() * 1000) - start_ms
    results["duration_ms"] = duration_ms
    results["bytes_saved_human"] = human_bytes(results["bytes_saved"])

    if conn:
        conn.execute("""
            INSERT INTO compression_runs
            (timestamp, files_scanned, files_compressed, bytes_saved, duration_ms)
            VALUES (?, ?, ?, ?, ?)
        """, (
            results["timestamp"],
            results["files_scanned"],
            results["files_compressed"],
            results["bytes_saved"],
            duration_ms,
        ))
        conn.commit()
        conn.close()

    return results


def action_stats() -> dict:
    """Show compression statistics from DB."""
    conn = get_db()

    # Overall stats
    row = conn.execute("""
        SELECT
            COUNT(*) as total_files,
            COALESCE(SUM(original_size), 0) as total_original,
            COALESCE(SUM(compressed_size), 0) as total_compressed,
            COALESCE(SUM(original_size - compressed_size), 0) as total_saved,
            COALESCE(AVG(ratio), 0) as avg_ratio
        FROM log_compression
    """).fetchone()

    # Run history
    runs = conn.execute("""
        SELECT * FROM compression_runs
        ORDER BY timestamp DESC LIMIT 10
    """).fetchall()

    conn.close()

    return {
        "timestamp": datetime.now().isoformat(),
        "action": "stats",
        "totals": {
            "files_compressed": row["total_files"],
            "original_size": human_bytes(row["total_original"]),
            "compressed_size": human_bytes(row["total_compressed"]),
            "space_saved": human_bytes(row["total_saved"]),
            "avg_compression_ratio": round(row["avg_ratio"], 4),
        },
        "recent_runs": [dict(r) for r in runs],
    }

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Compress and archive old log files (.log, .jsonl) older than 7 days."
    )
    parser.add_argument("--once", action="store_true",
                        help="Scan and compress old logs, output JSON summary")
    parser.add_argument("--stats", action="store_true",
                        help="Show compression statistics from database")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be compressed without touching files")
    args = parser.parse_args()

    if not any([args.once, args.stats, args.dry_run]):
        parser.print_help()
        sys.exit(1)

    if args.stats:
        result = action_stats()
    elif args.dry_run:
        result = action_once(dry_run=True)
    elif args.once:
        result = action_once(dry_run=False)
    else:
        parser.print_help()
        sys.exit(1)

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
