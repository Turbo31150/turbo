#!/usr/bin/env python3
"""win_env_auditor.py — Auditeur variables d'environnement.

Detecte doublons PATH, variables obsoletes.

Usage:
    python dev/win_env_auditor.py --once
    python dev/win_env_auditor.py --scan
    python dev/win_env_auditor.py --path
    python dev/win_env_auditor.py --duplicates
"""
import argparse
import json
import os
import sqlite3
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "env_auditor.db"

IMPORTANT_VARS = [
    "PATH", "PYTHONPATH", "JAVA_HOME", "NODE_PATH", "GOPATH",
    "CUDA_HOME", "CUDA_PATH", "OLLAMA_HOST", "OLLAMA_NUM_PARALLEL",
    "TEMP", "TMP", "HOME", "USERPROFILE", "APPDATA",
]


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS audits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, total_vars INTEGER, path_entries INTEGER,
        broken_paths INTEGER, duplicates INTEGER, issues TEXT)""")
    db.commit()
    return db


def analyze_path():
    """Analyze PATH variable."""
    path = os.environ.get("PATH", "")
    entries = [p.strip() for p in path.split(os.pathsep) if p.strip()]

    results = []
    broken = []
    duplicates = []

    seen = {}
    for i, entry in enumerate(entries):
        normalized = entry.lower().replace("/", "\\")
        exists = os.path.isdir(entry)

        result = {
            "index": i,
            "path": entry[:120],
            "exists": exists,
            "duplicate": normalized in seen,
        }
        results.append(result)

        if not exists:
            broken.append(entry[:120])
        if normalized in seen:
            duplicates.append({"path": entry[:120], "first_at": seen[normalized]})
        seen[normalized] = i

    return {
        "total_entries": len(entries),
        "existing": sum(1 for r in results if r["exists"]),
        "broken": broken,
        "duplicates": duplicates,
        "path_length": len(path),
        "entries": results[:30],
    }


def analyze_env_vars():
    """Analyze all environment variables."""
    all_vars = dict(os.environ)
    issues = []

    # Check important vars
    important_status = []
    for var in IMPORTANT_VARS:
        val = all_vars.get(var, "")
        status = {
            "name": var,
            "set": bool(val),
            "value": val[:100] if val else "(not set)",
        }
        if var in ("JAVA_HOME", "CUDA_HOME", "GOPATH") and val:
            if not os.path.exists(val):
                status["issue"] = "path_not_found"
                issues.append(f"{var} points to non-existent path")
        important_status.append(status)

    # Check for suspiciously long values
    long_vars = []
    for name, val in all_vars.items():
        if len(val) > 2000:
            long_vars.append({"name": name, "length": len(val)})

    return {
        "total_variables": len(all_vars),
        "important_vars": important_status,
        "long_values": long_vars,
        "issues": issues,
    }


def do_audit():
    """Full environment audit."""
    db = init_db()
    path_analysis = analyze_path()
    env_analysis = analyze_env_vars()

    all_issues = path_analysis.get("broken", [])[:5] + env_analysis.get("issues", [])

    report = {
        "ts": datetime.now().isoformat(),
        "total_env_vars": env_analysis["total_variables"],
        "path_analysis": {
            "entries": path_analysis["total_entries"],
            "broken": len(path_analysis["broken"]),
            "duplicates": len(path_analysis["duplicates"]),
            "path_length": path_analysis["path_length"],
        },
        "broken_paths": path_analysis["broken"][:10],
        "duplicate_paths": path_analysis["duplicates"][:10],
        "important_vars": env_analysis["important_vars"],
        "issues": all_issues,
    }

    db.execute(
        "INSERT INTO audits (ts, total_vars, path_entries, broken_paths, duplicates, issues) VALUES (?,?,?,?,?,?)",
        (time.time(), env_analysis["total_variables"], path_analysis["total_entries"],
         len(path_analysis["broken"]), len(path_analysis["duplicates"]), json.dumps(all_issues))
    )
    db.commit()
    db.close()
    return report


def main():
    parser = argparse.ArgumentParser(description="Windows Environment Auditor")
    parser.add_argument("--once", "--scan", action="store_true", help="Full audit")
    parser.add_argument("--path", action="store_true", help="PATH analysis")
    parser.add_argument("--duplicates", action="store_true", help="Find duplicates")
    parser.add_argument("--fix", action="store_true", help="Fix issues")
    args = parser.parse_args()

    result = do_audit()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
