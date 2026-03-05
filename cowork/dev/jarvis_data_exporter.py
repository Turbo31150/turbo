#!/usr/bin/env python3
"""jarvis_data_exporter.py — Exporteur donnees JARVIS.

Exporte n'importe quelle DB en JSON/CSV/Markdown.

Usage:
    python dev/jarvis_data_exporter.py --once
    python dev/jarvis_data_exporter.py --export etoile
    python dev/jarvis_data_exporter.py --format json
    python dev/jarvis_data_exporter.py --tables
"""
import argparse
import csv
import io
import json
import os
import sqlite3
import time
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "data_exporter.db"
EXPORT_DIR = DEV / "data" / "exports"
DATABASES = {
    "etoile": "F:/BUREAU/turbo/data/etoile.db",
    "jarvis": "F:/BUREAU/turbo/data/jarvis.db",
    "sniper": "F:/BUREAU/turbo/data/sniper.db",
    "finetuning": "F:/BUREAU/turbo/finetuning/data/finetuning.db",
}


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS exports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, db_name TEXT, format TEXT,
        tables_exported INTEGER, rows_exported INTEGER, file_path TEXT)""")
    db.commit()
    return db


def export_db(db_name, fmt="json"):
    db_path = DATABASES.get(db_name)
    if not db_path or not Path(db_path).exists():
        return {"error": f"Database '{db_name}' not found"}
    src = sqlite3.connect(db_path)
    tables = [t[0] for t in src.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    total_rows = 0
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    out_file = EXPORT_DIR / f"{db_name}_{ts}.{fmt}"

    if fmt == "json":
        data = {}
        for t in tables:
            cols = [c[1] for c in src.execute(f"PRAGMA table_info([{t}])").fetchall()]
            rows = src.execute(f"SELECT * FROM [{t}] LIMIT 10000").fetchall()
            data[t] = [dict(zip(cols, r)) for r in rows]
            total_rows += len(rows)
        out_file.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    elif fmt == "csv":
        buf = io.StringIO()
        for t in tables:
            cols = [c[1] for c in src.execute(f"PRAGMA table_info([{t}])").fetchall()]
            rows = src.execute(f"SELECT * FROM [{t}] LIMIT 10000").fetchall()
            total_rows += len(rows)
            writer = csv.writer(buf)
            writer.writerow([f"# TABLE: {t}"])
            writer.writerow(cols)
            writer.writerows(rows)
            writer.writerow([])
        out_file.write_text(buf.getvalue(), encoding="utf-8")
    src.close()
    return {"db": db_name, "format": fmt, "tables": len(tables), "rows": total_rows, "file": str(out_file)}


def do_stats():
    results = []
    for name, path in DATABASES.items():
        p = Path(path)
        if not p.exists():
            results.append({"name": name, "exists": False})
            continue
        db = sqlite3.connect(path)
        tables = [t[0] for t in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        total = sum(db.execute(f"SELECT COUNT(*) FROM [{t}]").fetchone()[0] for t in tables)
        db.close()
        results.append({"name": name, "tables": len(tables), "rows": total, "size_mb": round(p.stat().st_size/1024/1024, 2)})
    return {"ts": datetime.now().isoformat(), "databases": results}


def main():
    parser = argparse.ArgumentParser(description="JARVIS Data Exporter")
    parser.add_argument("--once", "--stats", action="store_true", help="Show stats")
    parser.add_argument("--export", metavar="DB", help="Export database")
    parser.add_argument("--format", metavar="FMT", choices=["json", "csv", "md"], default="json")
    parser.add_argument("--tables", action="store_true", help="List tables")
    args = parser.parse_args()

    if args.export:
        print(json.dumps(export_db(args.export, args.format), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(do_stats(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
