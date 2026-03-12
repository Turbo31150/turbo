#!/usr/bin/env python3
"""jarvis_self_improver.py — Auto-amelioration JARVIS.

Analyse les echecs recents et propose des fixes autonomes.

Usage:
    python dev/jarvis_self_improver.py --once
    python dev/jarvis_self_improver.py --analyze
    python dev/jarvis_self_improver.py --suggest
    python dev/jarvis_self_improver.py --report
"""
import argparse
import ast
import json
import os
import sqlite3
import time
import urllib.request
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "self_improver.db"
OL1_URL = "http://127.0.0.1:11434/api/chat"


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS analyses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, errors_found INTEGER, fixes_suggested INTEGER,
        fixes_applied INTEGER, report TEXT)""")
    db.execute("""CREATE TABLE IF NOT EXISTS fixes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, source_db TEXT, error_pattern TEXT,
        fix_description TEXT, applied INTEGER DEFAULT 0,
        success INTEGER DEFAULT 0)""")
    db.commit()
    return db


def scan_error_databases():
    """Scan all dev/data/*.db for error entries."""
    errors = []
    data_dir = DEV / "data"
    if not data_dir.exists():
        return errors

    for db_file in sorted(data_dir.glob("*.db")):
        try:
            db = sqlite3.connect(str(db_file))
            tables = [t[0] for t in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]

            for table in tables:
                # Get column info
                cols = db.execute(f"PRAGMA table_info([{table}])").fetchall()
                col_names = [c[1] for c in cols]

                # Look for error-related columns
                error_cols = [c for c in col_names if "error" in c.lower() or "status" in c.lower()]
                for ecol in error_cols:
                    try:
                        rows = db.execute(
                            f"SELECT [{ecol}] FROM [{table}] WHERE [{ecol}] IS NOT NULL AND [{ecol}] != '' AND [{ecol}] != 'ok' ORDER BY rowid DESC LIMIT 10"
                        ).fetchall()
                        for r in rows:
                            if r[0] and str(r[0]).strip():
                                errors.append({
                                    "db": db_file.name,
                                    "table": table,
                                    "column": ecol,
                                    "value": str(r[0])[:200],
                                })
                    except Exception:
                        pass

            db.close()
        except Exception:
            pass

    return errors


def categorize_errors(errors):
    """Categorize errors by pattern."""
    categories = {
        "timeout": [], "syntax": [], "network": [],
        "database": [], "runtime": [], "other": [],
    }

    for e in errors:
        val = e["value"].lower()
        if "timeout" in val or "timed out" in val:
            categories["timeout"].append(e)
        elif "syntax" in val or "parse" in val:
            categories["syntax"].append(e)
        elif "connection" in val or "refused" in val or "network" in val:
            categories["network"].append(e)
        elif "database" in val or "sqlite" in val or "locked" in val:
            categories["database"].append(e)
        elif "error" in val or "exception" in val or "fail" in val:
            categories["runtime"].append(e)
        else:
            categories["other"].append(e)

    return {k: v for k, v in categories.items() if v}


def generate_fix_suggestions(categories):
    """Generate fix suggestions for each error category."""
    suggestions = []

    for cat, errors in categories.items():
        if cat == "timeout":
            suggestions.append({
                "category": "timeout",
                "count": len(errors),
                "suggestion": "Augmenter les timeouts ou ajouter retry logic",
                "action": "increase_timeout",
                "safe": True,
            })
        elif cat == "network":
            suggestions.append({
                "category": "network",
                "count": len(errors),
                "suggestion": "Verifier connectivite cluster, ajouter fallback endpoints",
                "action": "check_connectivity",
                "safe": True,
            })
        elif cat == "syntax":
            suggestions.append({
                "category": "syntax",
                "count": len(errors),
                "suggestion": "Valider les reponses IA avant ast.parse",
                "action": "add_validation",
                "safe": True,
            })
        elif cat == "database":
            suggestions.append({
                "category": "database",
                "count": len(errors),
                "suggestion": "Ajouter WAL mode + retry sur database locked",
                "action": "enable_wal",
                "safe": True,
            })
        elif cat == "runtime":
            suggestions.append({
                "category": "runtime",
                "count": len(errors),
                "suggestion": "Revoir error handling dans les scripts concernes",
                "action": "review_scripts",
                "safe": False,
                "affected_dbs": list(set(e["db"] for e in errors[:5])),
            })

    return suggestions


def do_analyze():
    """Full analysis and suggestion cycle."""
    db = init_db()

    errors = scan_error_databases()
    categories = categorize_errors(errors)
    suggestions = generate_fix_suggestions(categories)

    # Store fixes
    for s in suggestions:
        db.execute(
            "INSERT INTO fixes (ts, source_db, error_pattern, fix_description, applied) VALUES (?,?,?,?,?)",
            (time.time(), json.dumps([e["db"] for e in categories.get(s["category"], [])[:3]]),
             s["category"], s["suggestion"], 0)
        )

    report = {
        "ts": datetime.now().isoformat(),
        "total_errors_scanned": len(errors),
        "categories": {k: len(v) for k, v in categories.items()},
        "suggestions": suggestions,
        "top_errors": errors[:10],
    }

    db.execute(
        "INSERT INTO analyses (ts, errors_found, fixes_suggested, fixes_applied, report) VALUES (?,?,?,?,?)",
        (time.time(), len(errors), len(suggestions), 0, json.dumps(report))
    )
    db.commit()
    db.close()

    return report


def main():
    parser = argparse.ArgumentParser(description="JARVIS Self Improver")
    parser.add_argument("--once", "--analyze", action="store_true", help="Analyze and suggest")
    parser.add_argument("--suggest", action="store_true", help="Show suggestions")
    parser.add_argument("--apply", action="store_true", help="Apply safe fixes")
    parser.add_argument("--report", action="store_true", help="Report")
    args = parser.parse_args()

    if args.suggest:
        db = init_db()
        rows = db.execute(
            "SELECT error_pattern, fix_description, applied FROM fixes ORDER BY ts DESC LIMIT 10"
        ).fetchall()
        db.close()
        print(json.dumps([{
            "pattern": r[0], "fix": r[1], "applied": bool(r[2])
        } for r in rows], indent=2))
    else:
        result = do_analyze()
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
