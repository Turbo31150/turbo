#!/usr/bin/env python3
"""jarvis_health_aggregator.py — Health aggregator for all dev/data/*.db databases.
Scans all SQLite databases, counts tables/rows, computes a global health score 0-100.
Usage: python dev/jarvis_health_aggregator.py --report --once
"""
import argparse
import json
import os
import sqlite3
import time
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "health_aggregator.db"
DATA_DIR = DEV / "data"


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS checks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL,
        action TEXT,
        report TEXT
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL,
        total_dbs INTEGER,
        total_tables INTEGER,
        total_rows INTEGER,
        total_size_bytes INTEGER,
        score INTEGER,
        details TEXT
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS subsystem_health (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        report_id INTEGER,
        db_name TEXT,
        tables INTEGER,
        rows INTEGER,
        size_bytes INTEGER,
        integrity_ok INTEGER,
        last_modified REAL,
        score INTEGER,
        FOREIGN KEY (report_id) REFERENCES reports(id)
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS trends (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL,
        score INTEGER,
        total_dbs INTEGER,
        total_rows INTEGER
    )""")
    db.commit()
    return db


def _analyze_db(db_path):
    """Analyze a single SQLite database."""
    result = {
        "path": str(db_path),
        "name": db_path.name,
        "size_bytes": 0,
        "tables": 0,
        "rows": 0,
        "table_details": [],
        "integrity_ok": False,
        "last_modified": 0,
        "score": 0
    }
    try:
        result["size_bytes"] = db_path.stat().st_size
        result["last_modified"] = db_path.stat().st_mtime
    except OSError:
        return result

    try:
        conn = sqlite3.connect(str(db_path))
        # Integrity check
        try:
            integrity = conn.execute("PRAGMA integrity_check").fetchone()
            result["integrity_ok"] = integrity[0] == "ok"
        except Exception:
            result["integrity_ok"] = False

        # Get tables
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
        result["tables"] = len(tables)

        total_rows = 0
        for (table_name,) in tables:
            try:
                count = conn.execute(f"SELECT COUNT(*) FROM [{table_name}]").fetchone()[0]
                total_rows += count
                result["table_details"].append({"name": table_name, "rows": count})
            except Exception:
                result["table_details"].append({"name": table_name, "rows": -1})
        result["rows"] = total_rows

        conn.close()

        # Calculate score for this DB
        score = 0
        if result["integrity_ok"]:
            score += 40
        if result["tables"] > 0:
            score += 20
        if result["rows"] > 0:
            score += 20
        # Recency: within last 24h = +20, within 7d = +10
        age_hours = (time.time() - result["last_modified"]) / 3600
        if age_hours < 24:
            score += 20
        elif age_hours < 168:
            score += 10
        result["score"] = min(100, score)

    except Exception as e:
        result["error"] = str(e)

    return result


def do_report():
    """Generate a comprehensive health report of all databases."""
    db = init_db()
    db_files = sorted(DATA_DIR.glob("*.db"))

    analyses = []
    total_tables = 0
    total_rows = 0
    total_size = 0
    scores = []

    for db_file in db_files:
        if db_file.name == "health_aggregator.db":
            continue  # Skip self
        analysis = _analyze_db(db_file)
        analyses.append(analysis)
        total_tables += analysis["tables"]
        total_rows += analysis["rows"]
        total_size += analysis["size_bytes"]
        scores.append(analysis["score"])

    # Global score: weighted average of all DB scores
    global_score = round(sum(scores) / len(scores)) if scores else 0

    # Bonus for diversity
    if len(analyses) >= 10:
        global_score = min(100, global_score + 5)
    if total_rows >= 1000:
        global_score = min(100, global_score + 5)

    # Save report
    cur = db.execute(
        "INSERT INTO reports (ts, total_dbs, total_tables, total_rows, total_size_bytes, score, details) VALUES (?,?,?,?,?,?,?)",
        (time.time(), len(analyses), total_tables, total_rows, total_size, global_score,
         json.dumps([{"name": a["name"], "tables": a["tables"], "rows": a["rows"], "score": a["score"]}
                     for a in analyses]))
    )
    report_id = cur.lastrowid

    # Save per-subsystem
    for a in analyses:
        db.execute(
            "INSERT INTO subsystem_health (report_id, db_name, tables, rows, size_bytes, integrity_ok, last_modified, score) VALUES (?,?,?,?,?,?,?,?)",
            (report_id, a["name"], a["tables"], a["rows"], a["size_bytes"],
             int(a["integrity_ok"]), a["last_modified"], a["score"])
        )

    # Save trend
    db.execute("INSERT INTO trends (ts, score, total_dbs, total_rows) VALUES (?,?,?,?)",
               (time.time(), global_score, len(analyses), total_rows))
    db.commit()

    # Grade
    if global_score >= 90:
        grade = "A"
    elif global_score >= 75:
        grade = "B"
    elif global_score >= 60:
        grade = "C"
    elif global_score >= 40:
        grade = "D"
    else:
        grade = "F"

    result = {
        "ts": datetime.now().isoformat(),
        "action": "report",
        "report_id": report_id,
        "global_score": global_score,
        "grade": grade,
        "total_databases": len(analyses),
        "total_tables": total_tables,
        "total_rows": total_rows,
        "total_size_mb": round(total_size / (1024 * 1024), 2),
        "subsystems": [
            {"name": a["name"], "tables": a["tables"], "rows": a["rows"],
             "size_mb": round(a["size_bytes"] / (1024 * 1024), 2),
             "integrity": a["integrity_ok"], "score": a["score"]}
            for a in sorted(analyses, key=lambda x: x["score"])
        ],
        "healthy_dbs": sum(1 for a in analyses if a["score"] >= 60),
        "unhealthy_dbs": sum(1 for a in analyses if a["score"] < 60)
    }
    db.execute("INSERT INTO checks (ts, action, report) VALUES (?,?,?)",
               (time.time(), "report", json.dumps({"score": global_score, "grade": grade})))
    db.commit()
    db.close()
    return result


def do_score():
    """Quick global health score."""
    db = init_db()
    cur = db.execute("SELECT score, total_dbs, total_rows FROM reports ORDER BY id DESC LIMIT 1")
    row = cur.fetchone()
    if row:
        result = {
            "ts": datetime.now().isoformat(),
            "action": "score",
            "global_score": row[0],
            "total_databases": row[1],
            "total_rows": row[2]
        }
    else:
        # Generate fresh
        db.close()
        report = do_report()
        return {
            "ts": datetime.now().isoformat(),
            "action": "score",
            "global_score": report["global_score"],
            "total_databases": report["total_databases"],
            "total_rows": report["total_rows"]
        }
    db.close()
    return result


def do_subsystems():
    """Show per-subsystem health details."""
    db = init_db()
    cur = db.execute("SELECT id FROM reports ORDER BY id DESC LIMIT 1")
    row = cur.fetchone()
    if not row:
        db.close()
        report = do_report()
        return report

    report_id = row[0]
    cur2 = db.execute(
        "SELECT db_name, tables, rows, size_bytes, integrity_ok, score FROM subsystem_health WHERE report_id=? ORDER BY score",
        (report_id,)
    )
    subsystems = [
        {"name": r[0], "tables": r[1], "rows": r[2],
         "size_mb": round(r[3] / (1024 * 1024), 2),
         "integrity": bool(r[4]), "score": r[5]}
        for r in cur2.fetchall()
    ]

    result = {
        "ts": datetime.now().isoformat(),
        "action": "subsystems",
        "report_id": report_id,
        "subsystems": subsystems,
        "total": len(subsystems),
        "healthy": sum(1 for s in subsystems if s["score"] >= 60),
        "critical": [s["name"] for s in subsystems if s["score"] < 40]
    }
    db.execute("INSERT INTO checks (ts, action, report) VALUES (?,?,?)",
               (time.time(), "subsystems", json.dumps({"total": len(subsystems)})))
    db.commit()
    db.close()
    return result


def do_trends():
    """Show health score trends over time."""
    db = init_db()
    cur = db.execute("SELECT ts, score, total_dbs, total_rows FROM trends ORDER BY ts DESC LIMIT 30")
    data_points = [
        {"ts": datetime.fromtimestamp(r[0]).isoformat(), "score": r[1],
         "databases": r[2], "rows": r[3]}
        for r in cur.fetchall()
    ]

    avg_score = round(sum(d["score"] for d in data_points) / len(data_points), 1) if data_points else 0
    trend_dir = "stable"
    if len(data_points) >= 2:
        if data_points[0]["score"] > data_points[-1]["score"] + 5:
            trend_dir = "improving"
        elif data_points[0]["score"] < data_points[-1]["score"] - 5:
            trend_dir = "declining"

    result = {
        "ts": datetime.now().isoformat(),
        "action": "trends",
        "data_points": data_points[:20],
        "average_score": avg_score,
        "trend_direction": trend_dir,
        "total_measurements": len(data_points)
    }
    db.execute("INSERT INTO checks (ts, action, report) VALUES (?,?,?)",
               (time.time(), "trends", json.dumps({"avg": avg_score, "dir": trend_dir})))
    db.commit()
    db.close()
    return result


def main():
    parser = argparse.ArgumentParser(description="Health aggregator for all dev/data/*.db")
    parser.add_argument("--report", action="store_true", help="Generate full health report")
    parser.add_argument("--score", action="store_true", help="Quick global health score")
    parser.add_argument("--subsystems", action="store_true", help="Per-subsystem health")
    parser.add_argument("--trends", action="store_true", help="Health score trends")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    args = parser.parse_args()

    if args.report:
        print(json.dumps(do_report(), ensure_ascii=False, indent=2))
    elif args.score:
        print(json.dumps(do_score(), ensure_ascii=False, indent=2))
    elif args.subsystems:
        print(json.dumps(do_subsystems(), ensure_ascii=False, indent=2))
    elif args.trends:
        print(json.dumps(do_trends(), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(do_report(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
