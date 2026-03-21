#!/usr/bin/env python3
"""Pipeline Domino Vivant — Track file modification patterns, auto-generate workflows.

Reads etoile.db memories (category='route_file'), detects hot files (3+ mods),
and generates auto_workflow entries when patterns repeat.

Usage:
    python pipeline_domino_hook.py --once
    python pipeline_domino_hook.py --check FILE
    python pipeline_domino_hook.py --generate
"""
import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone

DB_PATH = os.environ.get(
    "ETOILE_DB", os.path.join(os.path.dirname(__file__), "..", "..", "etoile.db")
)
HOT_THRESHOLD = 3


def get_db():
    if not os.path.exists(DB_PATH):
        print(json.dumps({"error": f"Database not found: {DB_PATH}"}))
        sys.exit(1)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_route_files(conn):
    """Return all route_file memories grouped by file path with counts."""
    cur = conn.execute(
        "SELECT key, value, confidence, created_at, updated_at "
        "FROM memories WHERE category='route_file' ORDER BY updated_at DESC"
    )
    rows = cur.fetchall()
    groups = {}
    for r in rows:
        path = r["key"]
        if path not in groups:
            groups[path] = {"path": path, "count": 0, "last_seen": r["updated_at"],
                            "confidence": r["confidence"]}
        groups[path]["count"] += 1
    return groups


def find_hot_files(groups):
    """Files modified >= HOT_THRESHOLD times are hot."""
    return {p: g for p, g in groups.items() if g["count"] >= HOT_THRESHOLD}


def check_file(conn, filepath):
    """Check if a specific file has a recurring pattern."""
    cur = conn.execute(
        "SELECT key, value, confidence, created_at, updated_at "
        "FROM memories WHERE category='route_file' AND key LIKE ?",
        (f"%{filepath}%",),
    )
    rows = cur.fetchall()
    count = len(rows)
    is_hot = count >= HOT_THRESHOLD
    last_seen = rows[0]["updated_at"] if rows else None
    return {
        "file": filepath,
        "modification_count": count,
        "is_hot": is_hot,
        "threshold": HOT_THRESHOLD,
        "last_seen": last_seen,
        "matches": [dict(r) for r in rows[:10]],
    }


def generate_workflows(conn, hot_files):
    """Insert auto_workflow entries for each hot file into etoile.db."""
    generated = []
    now = datetime.now(timezone.utc).isoformat()
    for path, info in hot_files.items():
        wf_key = f"wf_{os.path.basename(path)}"
        wf_value = json.dumps({
            "source_file": path,
            "trigger": "file_modified",
            "repeat_count": info["count"],
            "last_seen": info["last_seen"],
            "action": "auto_review",
            "generated_at": now,
        })
        try:
            conn.execute(
                "INSERT INTO memories (category, key, value, source, confidence) "
                "VALUES ('auto_workflow', ?, ?, 'pipeline_domino_hook', 0.8) "
                "ON CONFLICT(category, key) DO UPDATE SET value=excluded.value, "
                "updated_at=datetime('now')",
                (wf_key, wf_value),
            )
            generated.append({"key": wf_key, "file": path, "count": info["count"]})
        except sqlite3.Error as e:
            generated.append({"key": wf_key, "file": path, "error": str(e)})
    conn.commit()
    return generated


def cmd_once(conn):
    groups = get_route_files(conn)
    hot = find_hot_files(groups)
    total = len(groups)
    return {
        "mode": "once",
        "total_routes": total,
        "hot_threshold": HOT_THRESHOLD,
        "hot_files": list(hot.values()),
        "hot_count": len(hot),
        "all_files": sorted(groups.values(), key=lambda x: -x["count"])[:20],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def cmd_check(conn, filepath):
    return {"mode": "check", **check_file(conn, filepath)}


def cmd_generate(conn):
    groups = get_route_files(conn)
    hot = find_hot_files(groups)
    if not hot:
        return {"mode": "generate", "hot_files": [], "workflows_generated": [],
                "total_routes": len(groups), "message": "No hot files found"}
    workflows = generate_workflows(conn, hot)
    return {
        "mode": "generate",
        "hot_files": list(hot.values()),
        "workflows_generated": workflows,
        "total_routes": len(groups),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def main():
    parser = argparse.ArgumentParser(description="Pipeline Domino Vivant")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--once", action="store_true", help="Analyze recent patterns")
    group.add_argument("--check", metavar="FILE", help="Check file for recurring pattern")
    group.add_argument("--generate", action="store_true", help="Auto-generate workflows")
    args = parser.parse_args()

    conn = get_db()
    try:
        if args.once:
            result = cmd_once(conn)
        elif args.check:
            result = cmd_check(conn, args.check)
        else:
            result = cmd_generate(conn)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
