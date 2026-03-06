#!/usr/bin/env python3
"""log_compressor.py — Compress and archive old log data to keep DBs lean.

Compacts old dispatch logs, alert history, and monitoring data.

CLI:
    --once       : compress and archive
    --dry-run    : show what would be compressed
    --stats      : show DB sizes and row counts

Stdlib-only (sqlite3, json, argparse, os).
"""

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data"
DB_PATH = DATA_DIR / "cowork_gaps.db"
from _paths import ETOILE_DB

ARCHIVE_DAYS = 7
EVENTS_KEEP_DAYS = 3

def get_db_size(path):
    try:
        return os.path.getsize(path) // 1024
    except OSError:
        return 0

def count_rows(conn, table):
    try:
        return conn.execute(f"SELECT COUNT(*) FROM [{table}]").fetchone()[0]
    except Exception:
        return 0

def get_tables(conn):
    return [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]

def get_stats():
    stats = {}
    for name, path in [("etoile", ETOILE_DB), ("cowork_gaps", DB_PATH)]:
        if not path.exists():
            continue
        conn = sqlite3.connect(str(path), timeout=10)
        tables = get_tables(conn)
        rows = {t: count_rows(conn, t) for t in tables}
        conn.close()
        stats[name] = {
            "size_kb": get_db_size(path),
            "tables": len(tables),
            "total_rows": sum(rows.values()),
            "top_tables": dict(sorted(rows.items(), key=lambda x: -x[1])[:5]),
        }
    return stats

def clean_old(dry_run=False):
    results = {}
    if DB_PATH.exists():
        conn = sqlite3.connect(str(DB_PATH), timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        for table, days in [("realtime_events", 3), ("proactive_alerts", 7), ("telegram_reports", 7)]:
            cut = (datetime.now() - timedelta(days=days)).isoformat()
            try:
                old = conn.execute(f"SELECT COUNT(*) FROM [{table}] WHERE timestamp < ?", (cut,)).fetchone()[0]
            except Exception:
                old = 0
            if old > 0 and not dry_run:
                conn.execute(f"DELETE FROM [{table}] WHERE timestamp < ?", (cut,))
            results[table] = old
        conn.commit()
        if not dry_run:
            conn.execute("VACUUM")
        conn.close()
    return results

def main():
    parser = argparse.ArgumentParser(description="Log Compressor")
    parser.add_argument("--once", action="store_true", help="Compress and archive")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    parser.add_argument("--stats", action="store_true", help="DB statistics")
    args = parser.parse_args()

    if not any([args.once, args.dry_run, args.stats]):
        parser.print_help()
        sys.exit(1)

    if args.stats:
        result = get_stats()
    else:
        result = {
            "timestamp": datetime.now().isoformat(),
            "dry_run": args.dry_run,
            "cleaned": clean_old(args.dry_run),
            "db_stats": get_stats(),
        }
    print(json.dumps(result, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
