#!/usr/bin/env python3
"""jarvis_log_analyzer.py — Analyseur de logs JARVIS.

Parse tous les logs, detecte patterns d'erreurs recurrentes.

Usage:
    python dev/jarvis_log_analyzer.py --once
    python dev/jarvis_log_analyzer.py --analyze
    python dev/jarvis_log_analyzer.py --errors
    python dev/jarvis_log_analyzer.py --timeline
"""
import argparse
import json
import os
import sqlite3
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "log_analyzer.db"


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS analyses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, dbs_scanned INTEGER, errors_found INTEGER,
        patterns INTEGER, report TEXT)""")
    db.commit()
    return db


def scan_all_dbs():
    data_dir = DEV / "data"
    errors = []
    if not data_dir.exists():
        return errors
    for db_file in sorted(data_dir.glob("*.db")):
        try:
            db = sqlite3.connect(str(db_file))
            tables = [t[0] for t in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
            for table in tables:
                cols = [c[1] for c in db.execute(f"PRAGMA table_info([{table}])").fetchall()]
                err_cols = [c for c in cols if any(k in c.lower() for k in ["error", "status", "result"])]
                for col in err_cols:
                    try:
                        rows = db.execute(
                            f"SELECT [{col}] FROM [{table}] WHERE [{col}] IS NOT NULL AND [{col}] != '' AND [{col}] != 'ok' AND [{col}] != '1' LIMIT 20"
                        ).fetchall()
                        for r in rows:
                            val = str(r[0]).strip()
                            if val and len(val) > 2 and val not in ("0", "up", "running", "valid", "true"):
                                errors.append({"db": db_file.name, "table": table, "col": col, "val": val[:150]})
                    except Exception:
                        pass
            db.close()
        except Exception:
            pass
    return errors


def do_analyze():
    db = init_db()
    errors = scan_all_dbs()
    # Pattern detection
    patterns = Counter()
    for e in errors:
        val = e["val"].lower()
        for kw in ["timeout", "connection", "syntax", "locked", "refused", "fail", "error", "crash"]:
            if kw in val:
                patterns[kw] += 1
                break
        else:
            patterns["other"] += 1

    # By database
    by_db = Counter(e["db"] for e in errors)

    report = {
        "ts": datetime.now().isoformat(),
        "dbs_scanned": len(list((DEV / "data").glob("*.db"))) if (DEV / "data").exists() else 0,
        "total_errors": len(errors),
        "patterns": dict(patterns.most_common(10)),
        "by_database": dict(by_db.most_common(10)),
        "recent_errors": errors[:15],
    }
    db.execute("INSERT INTO analyses (ts, dbs_scanned, errors_found, patterns, report) VALUES (?,?,?,?,?)",
               (time.time(), report["dbs_scanned"], len(errors), len(patterns), json.dumps(report)))
    db.commit()
    db.close()
    return report


def main():
    parser = argparse.ArgumentParser(description="JARVIS Log Analyzer")
    parser.add_argument("--once", "--analyze", action="store_true", help="Analyze logs")
    parser.add_argument("--errors", action="store_true", help="Show errors")
    parser.add_argument("--patterns", action="store_true", help="Show patterns")
    parser.add_argument("--timeline", action="store_true", help="Timeline")
    args = parser.parse_args()
    print(json.dumps(do_analyze(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
