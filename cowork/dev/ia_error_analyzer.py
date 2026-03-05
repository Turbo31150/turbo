#!/usr/bin/env python3
"""ia_error_analyzer.py — Analyse toutes les erreurs des scripts dev/.

Categorise erreurs (syntax/runtime/timeout/network), trouve root cause
via cluster IA, propose fix.

Usage:
    python dev/ia_error_analyzer.py --once
    python dev/ia_error_analyzer.py --analyze
    python dev/ia_error_analyzer.py --categorize
    python dev/ia_error_analyzer.py --report
"""
import argparse
import json
import os
import sqlite3
import time
import urllib.request
from collections import Counter
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "error_analyzer.db"
M1_URL = "http://127.0.0.1:1234/api/v1/chat"

ERROR_CATEGORIES = {
    "SyntaxError": "syntax", "IndentationError": "syntax", "TabError": "syntax",
    "NameError": "runtime", "TypeError": "runtime", "ValueError": "runtime",
    "AttributeError": "runtime", "KeyError": "runtime", "IndexError": "runtime",
    "FileNotFoundError": "filesystem", "PermissionError": "filesystem",
    "ConnectionError": "network", "TimeoutError": "timeout", "URLError": "network",
    "sqlite3.OperationalError": "database", "json.JSONDecodeError": "parsing",
}


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS errors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, source TEXT, category TEXT,
        error_type TEXT, message TEXT, fix_suggestion TEXT)""")
    db.execute("""CREATE TABLE IF NOT EXISTS runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, errors_found INTEGER, categories TEXT, report TEXT)""")
    db.commit()
    return db


def scan_db_errors():
    """Scan all SQLite databases in dev/data/ for error records."""
    errors = []
    data_dir = DEV / "data"
    if not data_dir.exists():
        return errors

    for db_file in data_dir.glob("*.db"):
        try:
            conn = sqlite3.connect(str(db_file))
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            for (table_name,) in tables:
                # Look for columns that might contain errors
                try:
                    cols = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
                    col_names = [c[1] for c in cols]
                    error_cols = [c for c in col_names if "error" in c.lower() or "alert" in c.lower()]
                    for col in error_cols:
                        rows = conn.execute(
                            f"SELECT {col} FROM {table_name} WHERE {col} IS NOT NULL AND {col} != '' ORDER BY rowid DESC LIMIT 20"
                        ).fetchall()
                        for (val,) in rows:
                            if val and len(str(val)) > 5:
                                errors.append({
                                    "source": f"{db_file.name}/{table_name}",
                                    "message": str(val)[:300],
                                })
                except Exception:
                    continue
            conn.close()
        except Exception:
            continue

    return errors


def categorize_error(error_msg):
    """Categorize an error by its type."""
    for err_type, category in ERROR_CATEGORIES.items():
        if err_type.lower() in error_msg.lower():
            return category, err_type
    if "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
        return "timeout", "Timeout"
    if "connection" in error_msg.lower() or "unreachable" in error_msg.lower():
        return "network", "ConnectionError"
    if "permission" in error_msg.lower() or "denied" in error_msg.lower():
        return "filesystem", "PermissionError"
    return "unknown", "Unknown"


def get_fix_suggestion(error_msg, timeout=15):
    """Get fix suggestion from M1."""
    prompt = f"""Erreur JARVIS: {error_msg[:200]}
Propose un fix en 1 ligne. Reponds UNIQUEMENT avec le fix, pas d'explication."""
    try:
        data = json.dumps({
            "model": "qwen3-8b",
            "input": f"/nothink\n{prompt}",
            "temperature": 0.3, "max_output_tokens": 256,
            "stream": False, "store": False,
        }).encode()
        req = urllib.request.Request(M1_URL, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            result = json.loads(r.read().decode())
            for item in reversed(result.get("output", [])):
                if item.get("type") == "message":
                    for c in item.get("content", []):
                        if c.get("type") == "output_text":
                            return c.get("text", "")[:200]
    except Exception:
        pass
    return ""


def do_analyze():
    """Full error analysis cycle."""
    db = init_db()
    raw_errors = scan_db_errors()

    categorized = Counter()
    analyzed = []

    for err in raw_errors[:50]:
        cat, err_type = categorize_error(err["message"])
        categorized[cat] += 1

        entry = {
            "source": err["source"],
            "category": cat,
            "type": err_type,
            "message": err["message"][:200],
        }

        # Get fix only for non-trivial errors
        if cat in ("runtime", "syntax", "database") and len(analyzed) < 5:
            entry["fix"] = get_fix_suggestion(err["message"])

        analyzed.append(entry)
        db.execute(
            "INSERT INTO errors (ts, source, category, error_type, message, fix_suggestion) VALUES (?,?,?,?,?,?)",
            (time.time(), err["source"], cat, err_type, err["message"][:300],
             entry.get("fix", ""))
        )

    report = {
        "ts": datetime.now().isoformat(),
        "errors_found": len(raw_errors),
        "categories": dict(categorized),
        "top_errors": analyzed[:15],
    }

    db.execute(
        "INSERT INTO runs (ts, errors_found, categories, report) VALUES (?,?,?,?)",
        (time.time(), len(raw_errors), json.dumps(dict(categorized)), json.dumps(report))
    )
    db.commit()
    db.close()
    return report


def main():
    parser = argparse.ArgumentParser(description="IA Error Analyzer — Categorize & fix errors")
    parser.add_argument("--once", "--analyze", action="store_true", help="Full analysis")
    parser.add_argument("--categorize", action="store_true", help="Categorize only")
    parser.add_argument("--report", action="store_true", help="History")
    args = parser.parse_args()

    result = do_analyze()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
