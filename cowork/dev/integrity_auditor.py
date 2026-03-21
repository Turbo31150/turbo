#!/usr/bin/env python3
"""Check integrity of ALL .db files in data/ and etoile.db.

Runs PRAGMA integrity_check on each database. Reports: db name, tables count,
total rows count, integrity status. Outputs JSON summary.
Logs execution to etoile.db cowork_execution_log.
"""

import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path

ETOILE_DB = Path(r"F:\BUREAU\turbo\etoile.db")
DATA_DIR = Path(r"F:\BUREAU\turbo\data")
COWORK_DEV_DIR = Path(r"F:\BUREAU\turbo\cowork\dev")


def log_run(db_path: Path, script: str, exit_code: int, duration_ms: float,
            success: bool, stdout_preview: str = "", stderr_preview: str = ""):
    try:
        con = sqlite3.connect(str(db_path))
        con.execute(
            "INSERT INTO cowork_execution_log (script,args,exit_code,duration_ms,success,stdout_preview,stderr_preview)"
            " VALUES (?,?,?,?,?,?,?)",
            (script, "--once", exit_code, duration_ms, int(success),
             stdout_preview[:500], stderr_preview[:500]))
        con.commit()
        con.close()
    except Exception:
        pass


def audit_db(db_path: Path) -> dict:
    """Run integrity check on a single database file."""
    result = {"file": str(db_path), "name": db_path.name, "exists": db_path.exists()}
    if not db_path.exists():
        result["integrity"] = "FILE_NOT_FOUND"
        return result

    try:
        con = sqlite3.connect(str(db_path))
        # Integrity check
        integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
        result["integrity"] = integrity

        # Count tables
        tables = con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
        result["tables_count"] = len(tables)
        result["tables"] = [t[0] for t in tables]

        # Count total rows
        total_rows = 0
        for (tname,) in tables:
            try:
                count = con.execute(f'SELECT COUNT(*) FROM "{tname}"').fetchone()[0]
                total_rows += count
            except Exception:
                pass
        result["total_rows"] = total_rows

        # File size
        result["size_kb"] = round(db_path.stat().st_size / 1024, 1)
        con.close()
    except Exception as exc:
        result["integrity"] = f"ERROR: {exc}"
        result["tables_count"] = 0
        result["total_rows"] = 0

    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.parse_args()

    t0 = time.time()
    try:
        db_files = []
        # etoile.db
        db_files.append(ETOILE_DB)
        # All .db in data/
        if DATA_DIR.exists():
            db_files.extend(sorted(DATA_DIR.glob("*.db")))
        # All .db in cowork/dev/ (some scripts create local dbs)
        if COWORK_DEV_DIR.exists():
            db_files.extend(sorted(COWORK_DEV_DIR.glob("*.db")))

        # Deduplicate
        seen = set()
        unique = []
        for p in db_files:
            rp = p.resolve()
            if rp not in seen:
                seen.add(rp)
                unique.append(p)

        results = [audit_db(db) for db in unique]
        ok_count = sum(1 for r in results if r.get("integrity") == "ok")
        summary = {
            "total_databases": len(results),
            "healthy": ok_count,
            "unhealthy": len(results) - ok_count,
            "total_tables": sum(r.get("tables_count", 0) for r in results),
            "total_rows": sum(r.get("total_rows", 0) for r in results),
            "databases": results,
        }
        output = json.dumps(summary, indent=2, ensure_ascii=False)
        print(output)
        duration = (time.time() - t0) * 1000
        log_run(ETOILE_DB, "integrity_auditor.py", 0, duration, True, output[:500])
    except Exception as exc:
        duration = (time.time() - t0) * 1000
        err = str(exc)
        log_run(ETOILE_DB, "integrity_auditor.py", 1, duration, False, stderr_preview=err)
        print(json.dumps({"error": err}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
