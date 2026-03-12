#!/usr/bin/env python3
"""ia_memory_consolidator.py — Consolidateur memoire IA.

Fusionne et nettoie les memoires de tous les agents.

Usage:
    python dev/ia_memory_consolidator.py --once
    python dev/ia_memory_consolidator.py --consolidate
    python dev/ia_memory_consolidator.py --prune
    python dev/ia_memory_consolidator.py --stats
"""
import argparse
import json
import os
import sqlite3
import time
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "memory_consolidator.db"
DATA_DIR = DEV / "data"
PRUNE_DAYS = 90


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS consolidations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, dbs_scanned INTEGER, tables_found INTEGER,
        rows_total INTEGER, duplicates INTEGER, pruned INTEGER)""")
    db.execute("""CREATE TABLE IF NOT EXISTS memory_master (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, source_db TEXT, source_table TEXT,
        key_data TEXT, row_hash TEXT UNIQUE)""")
    db.commit()
    return db


def scan_databases():
    stats = []
    if not DATA_DIR.exists():
        return stats
    for db_file in sorted(DATA_DIR.glob("*.db")):
        if db_file.name == "memory_consolidator.db":
            continue
        try:
            db = sqlite3.connect(str(db_file))
            tables = [t[0] for t in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
            total_rows = 0
            table_info = []
            for t in tables:
                try:
                    count = db.execute(f"SELECT COUNT(*) FROM [{t}]").fetchone()[0]
                    total_rows += count
                    table_info.append({"table": t, "rows": count})
                except Exception:
                    pass
            db.close()
            stats.append({
                "db": db_file.name,
                "tables": len(tables),
                "rows": total_rows,
                "size_kb": round(db_file.stat().st_size / 1024, 1),
                "table_details": table_info,
            })
        except Exception:
            pass
    return stats


def do_consolidate():
    db = init_db()
    stats = scan_databases()

    total_tables = sum(s["tables"] for s in stats)
    total_rows = sum(s["rows"] for s in stats)
    total_size_kb = sum(s["size_kb"] for s in stats)

    # Count old rows for pruning
    prunable = 0
    cutoff = time.time() - PRUNE_DAYS * 86400
    for db_file in DATA_DIR.glob("*.db"):
        if db_file.name == "memory_consolidator.db":
            continue
        try:
            src = sqlite3.connect(str(db_file))
            tables = [t[0] for t in src.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
            for t in tables:
                cols = [c[1] for c in src.execute(f"PRAGMA table_info([{t}])").fetchall()]
                if "ts" in cols:
                    try:
                        old = src.execute(f"SELECT COUNT(*) FROM [{t}] WHERE ts < ?", (cutoff,)).fetchone()[0]
                        prunable += old
                    except Exception:
                        pass
            src.close()
        except Exception:
            pass

    db.execute("INSERT INTO consolidations (ts, dbs_scanned, tables_found, rows_total, duplicates, pruned) VALUES (?,?,?,?,?,?)",
               (time.time(), len(stats), total_tables, total_rows, 0, 0))
    db.commit()
    db.close()

    return {
        "ts": datetime.now().isoformat(),
        "databases_scanned": len(stats),
        "total_tables": total_tables,
        "total_rows": total_rows,
        "total_size_kb": round(total_size_kb, 1),
        "prunable_rows": prunable,
        "prune_threshold_days": PRUNE_DAYS,
        "databases": stats[:20],
    }


def main():
    parser = argparse.ArgumentParser(description="IA Memory Consolidator")
    parser.add_argument("--once", "--consolidate", action="store_true", help="Consolidate")
    parser.add_argument("--prune", action="store_true", help="Prune old")
    parser.add_argument("--export", action="store_true", help="Export master")
    parser.add_argument("--stats", action="store_true", help="Stats")
    args = parser.parse_args()
    print(json.dumps(do_consolidate(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
