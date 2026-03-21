#!/usr/bin/env python3
"""Sync voice_corrections between etoile.db and data/jarvis.db.

Finds rows present in one database but missing from the other (matched on
wrong+correct+category). Inserts missing rows in both directions.
Outputs JSON report with synced count and direction.
Logs execution to etoile.db cowork_execution_log.
"""

import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path

ETOILE_DB = Path(r"F:\BUREAU\turbo\etoile.db")
JARVIS_DB = Path(r"F:\BUREAU\turbo\data\jarvis.db")


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


def get_corrections(db_path: Path) -> list[tuple]:
    """Return all voice_corrections as list of (wrong, correct, category, hit_count)."""
    con = sqlite3.connect(str(db_path))
    rows = con.execute(
        "SELECT wrong, correct, category, hit_count FROM voice_corrections"
    ).fetchall()
    con.close()
    return rows


def get_keys(rows: list[tuple]) -> set[tuple]:
    """Extract unique keys (wrong, correct, category) from rows."""
    return {(r[0], r[1], r[2]) for r in rows}


def insert_missing(db_path: Path, missing: list[tuple]) -> int:
    """Insert missing rows into voice_corrections. Returns count inserted."""
    if not missing:
        return 0
    con = sqlite3.connect(str(db_path))
    inserted = 0
    for wrong, correct, category, hit_count in missing:
        try:
            con.execute(
                "INSERT INTO voice_corrections (wrong, correct, category, hit_count) VALUES (?,?,?,?)",
                (wrong, correct, category, hit_count))
            inserted += 1
        except sqlite3.IntegrityError:
            pass
    con.commit()
    con.close()
    return inserted


def sync() -> dict:
    """Bidirectional sync of voice_corrections."""
    # Verify both DBs exist
    for p in (ETOILE_DB, JARVIS_DB):
        if not p.exists():
            return {"error": f"Database not found: {p}"}

    etoile_rows = get_corrections(ETOILE_DB)
    jarvis_rows = get_corrections(JARVIS_DB)

    etoile_keys = get_keys(etoile_rows)
    jarvis_keys = get_keys(jarvis_rows)

    # Rows in etoile but not jarvis
    missing_in_jarvis = [r for r in etoile_rows if (r[0], r[1], r[2]) not in jarvis_keys]
    # Rows in jarvis but not etoile
    missing_in_etoile = [r for r in jarvis_rows if (r[0], r[1], r[2]) not in etoile_keys]

    to_jarvis = insert_missing(JARVIS_DB, missing_in_jarvis)
    to_etoile = insert_missing(ETOILE_DB, missing_in_etoile)

    # Final counts
    final_etoile = len(get_corrections(ETOILE_DB))
    final_jarvis = len(get_corrections(JARVIS_DB))

    return {
        "before": {
            "etoile_count": len(etoile_rows),
            "jarvis_count": len(jarvis_rows),
        },
        "synced": {
            "etoile_to_jarvis": to_jarvis,
            "jarvis_to_etoile": to_etoile,
            "total_synced": to_jarvis + to_etoile,
        },
        "after": {
            "etoile_count": final_etoile,
            "jarvis_count": final_jarvis,
        },
        "status": "in_sync" if final_etoile == final_jarvis else "mismatch",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.parse_args()

    t0 = time.time()
    try:
        result = sync()
        output = json.dumps(result, indent=2, ensure_ascii=False)
        print(output)
        duration = (time.time() - t0) * 1000
        success = "error" not in result
        log_run(ETOILE_DB, "db_syncer.py", 0 if success else 1, duration, success, output[:500])
        if not success:
            sys.exit(1)
    except Exception as exc:
        duration = (time.time() - t0) * 1000
        err = str(exc)
        log_run(ETOILE_DB, "db_syncer.py", 1, duration, False, stderr_preview=err)
        print(json.dumps({"error": err}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
