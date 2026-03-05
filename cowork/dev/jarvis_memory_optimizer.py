#!/usr/bin/env python3
"""jarvis_memory_optimizer.py — Optimise la memoire JARVIS.

Compacte les bases, purge les anciennes donnees.

Usage:
    python dev/jarvis_memory_optimizer.py --once
    python dev/jarvis_memory_optimizer.py --analyze
    python dev/jarvis_memory_optimizer.py --compact
    python dev/jarvis_memory_optimizer.py --prune 90
"""
import argparse
import json
import os
import sqlite3
import time
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "memory_optimizer.db"

# Databases to optimize
DATABASES = [
    {"name": "etoile", "path": "F:/BUREAU/turbo/data/etoile.db"},
    {"name": "jarvis", "path": "F:/BUREAU/turbo/data/jarvis.db"},
    {"name": "sniper", "path": "F:/BUREAU/turbo/data/sniper.db"},
    {"name": "finetuning", "path": "F:/BUREAU/turbo/finetuning/data/finetuning.db"},
]

# Tables with timestamp columns that can be pruned
PRUNABLE_TABLES = {
    "etoile": [("tool_metrics", "ts"), ("benchmark_runs", "ts")],
    "jarvis": [("queries", "ts"), ("voice_logs", "ts")],
}


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS optimizations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, db_name TEXT, action TEXT,
        size_before INTEGER, size_after INTEGER, rows_pruned INTEGER)""")
    db.commit()
    return db


def analyze_db(db_info):
    """Analyze a database for optimization opportunities."""
    path = Path(db_info["path"])
    if not path.exists():
        return {"name": db_info["name"], "exists": False}

    size = path.stat().st_size
    try:
        db = sqlite3.connect(str(path))
        tables = db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        total_rows = 0
        table_info = []
        for t in tables:
            count = db.execute(f"SELECT COUNT(*) FROM [{t[0]}]").fetchone()[0]
            total_rows += count
            table_info.append({"table": t[0], "rows": count})

        # Check fragmentation
        page_count = db.execute("PRAGMA page_count").fetchone()[0]
        freelist_count = db.execute("PRAGMA freelist_count").fetchone()[0]
        fragmentation = round(freelist_count / max(page_count, 1) * 100, 1)

        db.close()
        return {
            "name": db_info["name"], "exists": True,
            "size_mb": round(size / 1024 / 1024, 2),
            "tables": len(tables), "total_rows": total_rows,
            "fragmentation_pct": fragmentation,
            "top_tables": sorted(table_info, key=lambda x: x["rows"], reverse=True)[:5],
        }
    except Exception as e:
        return {"name": db_info["name"], "exists": True, "error": str(e)[:100]}


def compact_db(db_info):
    """VACUUM a database."""
    path = Path(db_info["path"])
    if not path.exists():
        return {"name": db_info["name"], "status": "not_found"}

    size_before = path.stat().st_size
    try:
        db = sqlite3.connect(str(path))
        db.execute("VACUUM")
        db.close()
        size_after = path.stat().st_size
        saved = size_before - size_after
        return {
            "name": db_info["name"], "status": "vacuumed",
            "before_mb": round(size_before / 1024 / 1024, 2),
            "after_mb": round(size_after / 1024 / 1024, 2),
            "saved_kb": round(saved / 1024, 1),
        }
    except Exception as e:
        return {"name": db_info["name"], "status": "error", "error": str(e)[:100]}


def prune_old_data(max_age_days):
    """Prune data older than max_age_days."""
    cutoff = time.time() - (max_age_days * 86400)
    results = []

    for db_name, tables in PRUNABLE_TABLES.items():
        db_info = next((d for d in DATABASES if d["name"] == db_name), None)
        if not db_info or not Path(db_info["path"]).exists():
            continue

        try:
            db = sqlite3.connect(db_info["path"])
            for table, ts_col in tables:
                try:
                    before = db.execute(f"SELECT COUNT(*) FROM [{table}]").fetchone()[0]
                    db.execute(f"DELETE FROM [{table}] WHERE [{ts_col}] < ?", (cutoff,))
                    after = db.execute(f"SELECT COUNT(*) FROM [{table}]").fetchone()[0]
                    pruned = before - after
                    if pruned > 0:
                        results.append({
                            "db": db_name, "table": table,
                            "before": before, "after": after, "pruned": pruned,
                        })
                except Exception:
                    pass
            db.commit()
            db.close()
        except Exception:
            pass

    return results


def do_analyze():
    """Full analysis."""
    opt_db = init_db()
    analyses = [analyze_db(d) for d in DATABASES]
    total_size = sum(a.get("size_mb", 0) for a in analyses)
    total_rows = sum(a.get("total_rows", 0) for a in analyses)

    report = {
        "ts": datetime.now().isoformat(),
        "databases": len(DATABASES),
        "total_size_mb": round(total_size, 2),
        "total_rows": total_rows,
        "analyses": analyses,
    }

    opt_db.close()
    return report


def main():
    parser = argparse.ArgumentParser(description="JARVIS Memory Optimizer")
    parser.add_argument("--once", "--analyze", action="store_true", help="Analyze databases")
    parser.add_argument("--compact", action="store_true", help="VACUUM all databases")
    parser.add_argument("--prune", metavar="AGE", type=int, help="Prune data older than N days")
    parser.add_argument("--stats", action="store_true", help="Show optimization history")
    args = parser.parse_args()

    if args.compact:
        results = [compact_db(d) for d in DATABASES]
        print(json.dumps(results, ensure_ascii=False, indent=2))
    elif args.prune:
        results = prune_old_data(args.prune)
        print(json.dumps({"pruned_tables": results, "max_age_days": args.prune}, indent=2))
    else:
        result = do_analyze()
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
