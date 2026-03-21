#!/usr/bin/env python3
"""Query Optimizer — Analyze etoile.db tables, add missing indexes, VACUUM.

Usage:
    python cowork/dev/query_optimizer.py --once
"""

import argparse
import json
import sqlite3
from datetime import datetime
from pathlib import Path

TURBO = Path(__file__).resolve().parent.parent.parent
DB_PATH = TURBO / "etoile.db"


def analyze_and_optimize(db_path):
    db = sqlite3.connect(str(db_path))
    db.row_factory = sqlite3.Row

    tables = [r["name"] for r in db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()]

    # Get existing indexes
    existing_idx = set(r["name"] for r in db.execute(
        "SELECT name FROM sqlite_master WHERE type='index'").fetchall())

    report = {"tables": [], "indexes_created": [], "vacuum": False}

    for t in tables:
        count = db.execute(f'SELECT COUNT(*) as c FROM [{t}]').fetchone()["c"]
        cols = [r["name"] for r in db.execute(f"PRAGMA table_info([{t}])").fetchall()]
        idx_count = len([r for r in db.execute(f"PRAGMA index_list([{t}])").fetchall()])

        report["tables"].append({"name": t, "rows": count, "columns": len(cols), "indexes": idx_count})

        # Add index on timestamp/id columns for large tables without indexes
        if count > 1000 and idx_count == 0:
            for col in cols:
                if col in ("timestamp", "created_at", "updated_at", "date"):
                    idx_name = f"idx_{t}_{col}"
                    if idx_name not in existing_idx:
                        try:
                            db.execute(f"CREATE INDEX [{idx_name}] ON [{t}] ([{col}])")
                            report["indexes_created"].append(idx_name)
                        except Exception:
                            pass

    db.commit()

    # VACUUM
    db.execute("VACUUM")
    report["vacuum"] = True

    # Size
    size = db_path.stat().st_size
    report["db_size_mb"] = round(size / 1024 / 1024, 2)
    report["total_tables"] = len(tables)
    report["timestamp"] = datetime.now().isoformat()

    db.close()
    return report


def main():
    parser = argparse.ArgumentParser(description="SQLite Query Optimizer")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument("--db", type=str, default=str(DB_PATH), help="Database path")
    args = parser.parse_args()

    report = analyze_and_optimize(Path(args.db))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
