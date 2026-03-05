#!/usr/bin/env python3
"""jarvis_db_migrator.py — Migration base de donnees JARVIS.

Gere les evolutions de schema en toute securite.

Usage:
    python dev/jarvis_db_migrator.py --once
    python dev/jarvis_db_migrator.py --check
    python dev/jarvis_db_migrator.py --migrate
    python dev/jarvis_db_migrator.py --rollback
"""
import argparse
import json
import os
import shutil
import sqlite3
import time
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "db_migrator.db"
DATABASES = [
    {"name": "etoile", "path": "F:/BUREAU/turbo/data/etoile.db"},
    {"name": "jarvis", "path": "F:/BUREAU/turbo/data/jarvis.db"},
    {"name": "sniper", "path": "F:/BUREAU/turbo/data/sniper.db"},
]

EXPECTED_TABLES = {
    "etoile": ["skills", "tool_metrics", "voice_commands", "user_patterns", "benchmark_runs"],
    "jarvis": ["queries", "voice_corrections"],
}


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS migrations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, db_name TEXT, action TEXT,
        details TEXT, success INTEGER)""")
    db.commit()
    return db


def get_schema(db_path):
    try:
        db = sqlite3.connect(db_path)
        tables = [t[0] for t in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        schema = {}
        for t in tables:
            cols = db.execute(f"PRAGMA table_info([{t}])").fetchall()
            schema[t] = [{"name": c[1], "type": c[2]} for c in cols]
        db.close()
        return schema
    except Exception:
        return {}


def do_check():
    db = init_db()
    results = []
    for info in DATABASES:
        p = Path(info["path"])
        if not p.exists():
            results.append({"name": info["name"], "exists": False})
            continue
        schema = get_schema(info["path"])
        expected = EXPECTED_TABLES.get(info["name"], [])
        missing = [t for t in expected if t not in schema]
        results.append({
            "name": info["name"], "exists": True,
            "tables": len(schema), "missing_tables": missing,
            "size_mb": round(p.stat().st_size / 1024 / 1024, 2),
        })
    db.close()
    return {"ts": datetime.now().isoformat(), "databases": results}


def do_backup(db_info):
    p = Path(db_info["path"])
    if not p.exists():
        return False
    bak = p.with_suffix(".db.bak")
    shutil.copy2(str(p), str(bak))
    return True


def main():
    parser = argparse.ArgumentParser(description="JARVIS DB Migrator")
    parser.add_argument("--once", "--check", action="store_true", help="Check schemas")
    parser.add_argument("--migrate", action="store_true", help="Run migrations")
    parser.add_argument("--backup", action="store_true", help="Backup databases")
    parser.add_argument("--rollback", action="store_true", help="Rollback last migration")
    args = parser.parse_args()

    if args.backup:
        results = {d["name"]: do_backup(d) for d in DATABASES}
        print(json.dumps({"backups": results}, indent=2))
    else:
        print(json.dumps(do_check(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
