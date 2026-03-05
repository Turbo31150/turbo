#!/usr/bin/env python3
"""config_drift_detector.py

Detects configuration drift in the COWORK system.

Tracks:
  1. Script count   - number of *.py files in SCRIPT_DIR
  2. Script hashes  - MD5 of each script file (detect modifications)
  3. DB schema      - table names and column counts in etoile.db
  4. Pattern count  - rows in agent_patterns and cowork_script_mapping
  5. Node config    - distinct nodes in agent_dispatch_log
  6. Scheduler      - count and names in cowork_schedules

CLI:
  --once      Scan for drift (snapshot + compare to previous)
  --snapshot  Save current state without comparing
  --compare   Compare current state to last snapshot
  --stats     Show drift history counts

Stdlib-only: sqlite3, json, argparse, hashlib, pathlib.
"""

import argparse
import hashlib
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Ensure Unicode output on Windows
# ---------------------------------------------------------------------------
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data"
ETOILE_DB = Path(r"F:/BUREAU/turbo/etoile.db")
GAPS_DB = DATA_DIR / "cowork_gaps.db"


# ---------------------------------------------------------------------------
# Database setup
# ---------------------------------------------------------------------------
def _init_db() -> sqlite3.Connection:
    """Open cowork_gaps.db and ensure our tables exist."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(GAPS_DB))
    conn.execute("PRAGMA journal_mode=WAL")

    # Migrate: drop old-schema tables that lack required columns
    for tbl, required_col in [
        ("config_snapshots", "snapshot_json"),
        ("config_drifts", "target"),
    ]:
        cols = [
            row[1]
            for row in conn.execute(f"PRAGMA table_info([{tbl}])").fetchall()
        ]
        if cols and required_col not in cols:
            conn.execute(f"ALTER TABLE [{tbl}] RENAME TO [{tbl}_old]")

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS config_snapshots (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp       TEXT    NOT NULL,
            snapshot_json   TEXT    NOT NULL
        );
        CREATE TABLE IF NOT EXISTS config_drifts (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp       TEXT    NOT NULL,
            drift_type      TEXT    NOT NULL,
            target          TEXT    NOT NULL,
            expected        TEXT,
            actual          TEXT,
            severity        TEXT    NOT NULL DEFAULT 'warning'
        );
    """)
    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# State collectors
# ---------------------------------------------------------------------------
def _md5_file(path: Path) -> str:
    """Return hex MD5 digest of a file."""
    h = hashlib.md5()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
    except OSError:
        return "ERROR"
    return h.hexdigest()


def _collect_scripts() -> dict:
    """Return {filename: md5_hash} for every *.py in SCRIPT_DIR."""
    scripts: dict[str, str] = {}
    for p in sorted(SCRIPT_DIR.glob("*.py")):
        scripts[p.name] = _md5_file(p)
    return scripts


def _collect_etoile_schema() -> dict:
    """Return {table_name: column_count} from etoile.db."""
    schema: dict[str, int] = {}
    if not ETOILE_DB.exists():
        return schema
    try:
        conn = sqlite3.connect(str(ETOILE_DB))
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = [row[0] for row in cur.fetchall()]
        for tbl in tables:
            info = conn.execute(f"PRAGMA table_info([{tbl}])").fetchall()
            schema[tbl] = len(info)
        conn.close()
    except sqlite3.Error:
        pass
    return schema


def _query_etoile_count(table: str) -> int:
    """Return row count for a table in etoile.db, or -1 if missing."""
    if not ETOILE_DB.exists():
        return -1
    try:
        conn = sqlite3.connect(str(ETOILE_DB))
        cur = conn.execute(f"SELECT COUNT(*) FROM [{table}]")
        count = cur.fetchone()[0]
        conn.close()
        return count
    except sqlite3.Error:
        return -1


def _collect_nodes() -> list:
    """Return sorted list of distinct nodes from agent_dispatch_log."""
    if not ETOILE_DB.exists():
        return []
    try:
        conn = sqlite3.connect(str(ETOILE_DB))
        cur = conn.execute(
            "SELECT DISTINCT node FROM agent_dispatch_log "
            "WHERE node IS NOT NULL ORDER BY node"
        )
        nodes = [row[0] for row in cur.fetchall()]
        conn.close()
        return nodes
    except sqlite3.Error:
        return []


def _collect_schedules() -> dict:
    """Return {task_name: enabled} from cowork_schedules in cowork_gaps.db."""
    schedules: dict[str, int] = {}
    if not GAPS_DB.exists():
        return schedules
    try:
        conn = sqlite3.connect(str(GAPS_DB))
        cur = conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name='cowork_schedules'"
        )
        if not cur.fetchone():
            conn.close()
            return schedules
        cur = conn.execute(
            "SELECT task_name, enabled FROM cowork_schedules ORDER BY task_name"
        )
        for row in cur.fetchall():
            schedules[row[0]] = row[1]
        conn.close()
    except sqlite3.Error:
        pass
    return schedules


def collect_state() -> dict:
    """Collect full current state snapshot."""
    scripts = _collect_scripts()
    return {
        "script_count": len(scripts),
        "script_hashes": scripts,
        "db_schema": _collect_etoile_schema(),
        "pattern_count": {
            "agent_patterns": _query_etoile_count("agent_patterns"),
            "cowork_script_mapping": _query_etoile_count("cowork_script_mapping"),
        },
        "nodes": _collect_nodes(),
        "schedules": _collect_schedules(),
    }


# ---------------------------------------------------------------------------
# Snapshot management
# ---------------------------------------------------------------------------
def save_snapshot(conn: sqlite3.Connection, state: dict) -> int:
    """Save a state snapshot and return its id."""
    now = datetime.now().isoformat(timespec="seconds")
    cur = conn.execute(
        "INSERT INTO config_snapshots (timestamp, snapshot_json) VALUES (?, ?)",
        (now, json.dumps(state, ensure_ascii=False)),
    )
    conn.commit()
    return cur.lastrowid


def get_last_snapshot(conn: sqlite3.Connection) -> tuple | None:
    """Return (id, timestamp, state_dict) of the most recent snapshot, or None."""
    cur = conn.execute(
        "SELECT id, timestamp, snapshot_json "
        "FROM config_snapshots ORDER BY id DESC LIMIT 1"
    )
    row = cur.fetchone()
    if row is None:
        return None
    return (row[0], row[1], json.loads(row[2]))


# ---------------------------------------------------------------------------
# Drift detection
# ---------------------------------------------------------------------------
def detect_drifts(prev: dict, curr: dict) -> list[dict]:
    """Compare two state dicts and return a list of drift records."""
    drifts: list[dict] = []
    now = datetime.now().isoformat(timespec="seconds")

    # 1. Script count
    if prev["script_count"] != curr["script_count"]:
        drifts.append({
            "timestamp": now,
            "drift_type": "script_count",
            "target": "SCRIPT_DIR",
            "expected": str(prev["script_count"]),
            "actual": str(curr["script_count"]),
            "severity": "warning",
        })

    # 2. New / removed / modified scripts
    prev_scripts = prev.get("script_hashes", {})
    curr_scripts = curr.get("script_hashes", {})

    for name in sorted(set(curr_scripts) - set(prev_scripts)):
        drifts.append({
            "timestamp": now,
            "drift_type": "script_added",
            "target": name,
            "expected": None,
            "actual": curr_scripts[name],
            "severity": "info",
        })
    for name in sorted(set(prev_scripts) - set(curr_scripts)):
        drifts.append({
            "timestamp": now,
            "drift_type": "script_removed",
            "target": name,
            "expected": prev_scripts[name],
            "actual": None,
            "severity": "warning",
        })
    for name in sorted(set(prev_scripts) & set(curr_scripts)):
        if prev_scripts[name] != curr_scripts[name]:
            drifts.append({
                "timestamp": now,
                "drift_type": "script_modified",
                "target": name,
                "expected": prev_scripts[name],
                "actual": curr_scripts[name],
                "severity": "info",
            })

    # 3. Schema changes
    prev_schema = prev.get("db_schema", {})
    curr_schema = curr.get("db_schema", {})

    for tbl in sorted(set(curr_schema) - set(prev_schema)):
        drifts.append({
            "timestamp": now,
            "drift_type": "table_added",
            "target": tbl,
            "expected": None,
            "actual": str(curr_schema[tbl]),
            "severity": "warning",
        })
    for tbl in sorted(set(prev_schema) - set(curr_schema)):
        drifts.append({
            "timestamp": now,
            "drift_type": "table_removed",
            "target": tbl,
            "expected": str(prev_schema[tbl]),
            "actual": None,
            "severity": "critical",
        })
    for tbl in sorted(set(prev_schema) & set(curr_schema)):
        if prev_schema[tbl] != curr_schema[tbl]:
            drifts.append({
                "timestamp": now,
                "drift_type": "columns_changed",
                "target": tbl,
                "expected": str(prev_schema[tbl]),
                "actual": str(curr_schema[tbl]),
                "severity": "warning",
            })

    # 4. Pattern counts
    for key in ("agent_patterns", "cowork_script_mapping"):
        pv = prev.get("pattern_count", {}).get(key, -1)
        cv = curr.get("pattern_count", {}).get(key, -1)
        if pv != cv:
            drifts.append({
                "timestamp": now,
                "drift_type": "pattern_count",
                "target": key,
                "expected": str(pv),
                "actual": str(cv),
                "severity": "info",
            })

    # 5. Node configuration
    prev_nodes = set(prev.get("nodes", []))
    curr_nodes = set(curr.get("nodes", []))
    for node in sorted(curr_nodes - prev_nodes):
        drifts.append({
            "timestamp": now,
            "drift_type": "node_added",
            "target": node,
            "expected": None,
            "actual": node,
            "severity": "info",
        })
    for node in sorted(prev_nodes - curr_nodes):
        drifts.append({
            "timestamp": now,
            "drift_type": "node_removed",
            "target": node,
            "expected": node,
            "actual": None,
            "severity": "warning",
        })

    # 6. Scheduler tasks
    prev_sched = prev.get("schedules", {})
    curr_sched = curr.get("schedules", {})
    for task in sorted(set(curr_sched) - set(prev_sched)):
        drifts.append({
            "timestamp": now,
            "drift_type": "schedule_added",
            "target": task,
            "expected": None,
            "actual": str(curr_sched[task]),
            "severity": "info",
        })
    for task in sorted(set(prev_sched) - set(curr_sched)):
        drifts.append({
            "timestamp": now,
            "drift_type": "schedule_removed",
            "target": task,
            "expected": str(prev_sched[task]),
            "actual": None,
            "severity": "warning",
        })

    return drifts


def store_drifts(conn: sqlite3.Connection, drifts: list[dict]) -> None:
    """Persist drift records to the database."""
    for d in drifts:
        conn.execute(
            "INSERT INTO config_drifts "
            "(timestamp, drift_type, target, expected, actual, severity) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (d["timestamp"], d["drift_type"], d["target"],
             d["expected"], d["actual"], d["severity"]),
        )
    conn.commit()


# ---------------------------------------------------------------------------
# CLI actions
# ---------------------------------------------------------------------------
def action_snapshot(conn: sqlite3.Connection) -> None:
    """Save current state without comparing."""
    state = collect_state()
    sid = save_snapshot(conn, state)
    result = {
        "action": "snapshot",
        "snapshot_id": sid,
        "script_count": state["script_count"],
        "tables": len(state["db_schema"]),
        "nodes": state["nodes"],
        "schedules_count": len(state["schedules"]),
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))


def action_compare(conn: sqlite3.Connection) -> None:
    """Compare current state to last snapshot (no new snapshot saved)."""
    prev = get_last_snapshot(conn)
    if prev is None:
        print(json.dumps(
            {"error": "No previous snapshot found. Run --snapshot first."},
            indent=2,
        ))
        return

    curr = collect_state()
    drifts = detect_drifts(prev[2], curr)
    if drifts:
        store_drifts(conn, drifts)

    result = {
        "action": "compare",
        "baseline_id": prev[0],
        "baseline_timestamp": prev[1],
        "drifts_found": len(drifts),
        "drifts": drifts,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))


def action_once(conn: sqlite3.Connection) -> None:
    """Take snapshot, compare to previous, output JSON with drifts."""
    prev = get_last_snapshot(conn)
    curr = collect_state()
    sid = save_snapshot(conn, curr)

    summary = {
        "script_count": curr["script_count"],
        "tables": len(curr["db_schema"]),
        "nodes": curr["nodes"],
        "schedules_count": len(curr["schedules"]),
        "agent_patterns": curr["pattern_count"]["agent_patterns"],
        "cowork_script_mapping": curr["pattern_count"]["cowork_script_mapping"],
    }

    if prev is None:
        result = {
            "action": "once",
            "snapshot_id": sid,
            "baseline": None,
            "drifts_found": 0,
            "drifts": [],
            "summary": summary,
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    drifts = detect_drifts(prev[2], curr)
    if drifts:
        store_drifts(conn, drifts)

    result = {
        "action": "once",
        "snapshot_id": sid,
        "baseline_id": prev[0],
        "baseline_timestamp": prev[1],
        "drifts_found": len(drifts),
        "drifts": drifts,
        "summary": summary,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))


def action_stats(conn: sqlite3.Connection) -> None:
    """Show drift history counts."""
    cur = conn.execute(
        "SELECT drift_type, severity, COUNT(*) "
        "FROM config_drifts GROUP BY drift_type, severity ORDER BY drift_type"
    )
    rows = cur.fetchall()

    total = conn.execute("SELECT COUNT(*) FROM config_drifts").fetchone()[0]
    snapshots = conn.execute("SELECT COUNT(*) FROM config_snapshots").fetchone()[0]

    by_type: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    for dtype, sev, cnt in rows:
        by_type[dtype] = by_type.get(dtype, 0) + cnt
        by_severity[sev] = by_severity.get(sev, 0) + cnt

    # Recent drifts (last 10)
    recent_cur = conn.execute(
        "SELECT timestamp, drift_type, target, severity "
        "FROM config_drifts ORDER BY id DESC LIMIT 10"
    )
    recent = [
        {"timestamp": r[0], "drift_type": r[1], "target": r[2], "severity": r[3]}
        for r in recent_cur.fetchall()
    ]

    result = {
        "action": "stats",
        "total_snapshots": snapshots,
        "total_drifts": total,
        "by_type": by_type,
        "by_severity": by_severity,
        "recent": recent,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="COWORK configuration drift detector"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--once", action="store_true",
                       help="Scan for drift (snapshot + compare)")
    group.add_argument("--snapshot", action="store_true",
                       help="Save current state without comparing")
    group.add_argument("--compare", action="store_true",
                       help="Compare current state to last snapshot")
    group.add_argument("--stats", action="store_true",
                       help="Show drift history counts")

    args = parser.parse_args()
    conn = _init_db()

    try:
        if args.once:
            action_once(conn)
        elif args.snapshot:
            action_snapshot(conn)
        elif args.compare:
            action_compare(conn)
        elif args.stats:
            action_stats(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
