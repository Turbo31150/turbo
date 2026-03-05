#!/usr/bin/env python3
"""jarvis_pattern_miner.py — Behavioral pattern mining (#248).

Scans all dev/data/*.db, extracts recurring patterns (same action at same time,
correlations between events), detects anomalies (unusual activity).

Usage:
    python dev/jarvis_pattern_miner.py --once
    python dev/jarvis_pattern_miner.py --mine
    python dev/jarvis_pattern_miner.py --patterns
    python dev/jarvis_pattern_miner.py --anomalies
    python dev/jarvis_pattern_miner.py --export
"""
import argparse
import glob
import json
import os
import sqlite3
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "pattern_miner.db"
DATA_DIR = DEV / "data"


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("""CREATE TABLE IF NOT EXISTS patterns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        source_db TEXT NOT NULL,
        pattern_type TEXT NOT NULL,
        pattern_desc TEXT NOT NULL,
        frequency INTEGER DEFAULT 1,
        confidence REAL DEFAULT 0.0,
        details TEXT
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS anomalies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        source_db TEXT NOT NULL,
        anomaly_type TEXT NOT NULL,
        description TEXT NOT NULL,
        severity TEXT DEFAULT 'low',
        details TEXT
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS scan_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        databases_scanned INTEGER,
        patterns_found INTEGER,
        anomalies_found INTEGER,
        duration_ms REAL
    )""")
    db.commit()
    return db


def scan_database(db_path):
    """Scan a single database for patterns."""
    info = {"path": str(db_path), "tables": [], "total_rows": 0, "timestamps": []}
    try:
        conn = sqlite3.connect(str(db_path))
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()

        for (table_name,) in tables:
            try:
                row_count = conn.execute(f"SELECT COUNT(*) FROM [{table_name}]").fetchone()[0]
                info["tables"].append({"name": table_name, "rows": row_count})
                info["total_rows"] += row_count

                # Try to find timestamp columns
                cols = conn.execute(f"PRAGMA table_info([{table_name}])").fetchall()
                ts_cols = [c[1] for c in cols if c[1].lower() in ("ts", "timestamp", "created_at", "updated_at", "date")]
                for tc in ts_cols:
                    try:
                        timestamps = conn.execute(
                            f"SELECT [{tc}] FROM [{table_name}] WHERE [{tc}] IS NOT NULL ORDER BY [{tc}] DESC LIMIT 100"
                        ).fetchall()
                        info["timestamps"].extend([t[0] for t in timestamps if t[0]])
                    except Exception:
                        pass
            except Exception:
                pass
        conn.close()
    except Exception as e:
        info["error"] = str(e)
    return info


def extract_time_patterns(timestamps):
    """Extract time-based patterns from timestamps."""
    patterns = []
    hour_counts = Counter()
    weekday_counts = Counter()

    for ts in timestamps:
        try:
            if "T" in str(ts):
                dt = datetime.fromisoformat(str(ts).replace("Z", ""))
            else:
                dt = datetime.strptime(str(ts)[:19], "%Y-%m-%d %H:%M:%S")
            hour_counts[dt.hour] += 1
            weekday_counts[dt.weekday()] += 1
        except (ValueError, TypeError):
            continue

    # Peak hours
    if hour_counts:
        peak_hour = hour_counts.most_common(1)[0]
        if peak_hour[1] >= 3:
            patterns.append({
                "type": "peak_hour",
                "desc": f"Peak activity at hour {peak_hour[0]}:00 ({peak_hour[1]} events)",
                "frequency": peak_hour[1],
                "confidence": min(peak_hour[1] / max(sum(hour_counts.values()), 1), 1.0),
            })

    # Peak weekday
    if weekday_counts:
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        peak_day = weekday_counts.most_common(1)[0]
        if peak_day[1] >= 3:
            patterns.append({
                "type": "peak_weekday",
                "desc": f"Peak activity on {days[peak_day[0]]} ({peak_day[1]} events)",
                "frequency": peak_day[1],
                "confidence": min(peak_day[1] / max(sum(weekday_counts.values()), 1), 1.0),
            })

    # Activity gaps (hours with no activity)
    if len(hour_counts) >= 5:
        active_hours = set(hour_counts.keys())
        inactive_hours = set(range(24)) - active_hours
        if len(inactive_hours) <= 10:
            patterns.append({
                "type": "inactive_hours",
                "desc": f"No activity during hours: {sorted(inactive_hours)}",
                "frequency": len(inactive_hours),
                "confidence": 0.7,
            })

    return patterns


def detect_anomalies(db_info_list):
    """Detect anomalies across databases."""
    anomalies = []

    for info in db_info_list:
        if "error" in info:
            anomalies.append({
                "source": os.path.basename(info["path"]),
                "type": "db_error",
                "desc": f"Database error: {info['error']}",
                "severity": "medium",
            })
            continue

        # Empty tables
        for table in info.get("tables", []):
            if table["rows"] == 0:
                anomalies.append({
                    "source": os.path.basename(info["path"]),
                    "type": "empty_table",
                    "desc": f"Table '{table['name']}' is empty",
                    "severity": "low",
                })

        # Very large tables
        for table in info.get("tables", []):
            if table["rows"] > 10000:
                anomalies.append({
                    "source": os.path.basename(info["path"]),
                    "type": "large_table",
                    "desc": f"Table '{table['name']}' has {table['rows']} rows (may need cleanup)",
                    "severity": "low",
                })

        # Stale data (no recent timestamps)
        ts_list = info.get("timestamps", [])
        if ts_list:
            try:
                latest = max(ts_list)
                if "T" in str(latest):
                    latest_dt = datetime.fromisoformat(str(latest).replace("Z", ""))
                else:
                    latest_dt = datetime.strptime(str(latest)[:19], "%Y-%m-%d %H:%M:%S")
                age_hours = (datetime.now() - latest_dt).total_seconds() / 3600
                if age_hours > 168:  # More than 7 days
                    anomalies.append({
                        "source": os.path.basename(info["path"]),
                        "type": "stale_data",
                        "desc": f"No activity for {int(age_hours / 24)} days (last: {latest})",
                        "severity": "medium",
                    })
            except (ValueError, TypeError):
                pass

    return anomalies


def do_mine():
    """Full mining scan of all databases."""
    db = init_db()
    start = time.time()
    now = datetime.now()

    # Find all .db files in data directory
    db_files = sorted(DATA_DIR.glob("*.db"))
    # Exclude pattern_miner.db itself
    db_files = [f for f in db_files if f.name != "pattern_miner.db"]

    all_info = []
    all_patterns = []
    all_anomalies = []

    for db_file in db_files:
        info = scan_database(db_file)
        all_info.append(info)

        # Extract patterns from timestamps
        if info.get("timestamps"):
            patterns = extract_time_patterns(info["timestamps"])
            for p in patterns:
                p["source"] = db_file.name
                all_patterns.append(p)

    # Detect anomalies
    all_anomalies = detect_anomalies(all_info)

    # Store patterns
    for p in all_patterns:
        db.execute(
            "INSERT INTO patterns (ts, source_db, pattern_type, pattern_desc, frequency, confidence, details) VALUES (?,?,?,?,?,?,?)",
            (now.isoformat(), p.get("source", "?"), p["type"], p["desc"],
             p.get("frequency", 1), round(p.get("confidence", 0), 3), json.dumps(p)),
        )

    # Store anomalies
    for a in all_anomalies:
        db.execute(
            "INSERT INTO anomalies (ts, source_db, anomaly_type, description, severity, details) VALUES (?,?,?,?,?,?)",
            (now.isoformat(), a.get("source", "?"), a["type"], a["desc"],
             a.get("severity", "low"), json.dumps(a)),
        )

    duration = (time.time() - start) * 1000
    db.execute(
        "INSERT INTO scan_log (ts, databases_scanned, patterns_found, anomalies_found, duration_ms) VALUES (?,?,?,?,?)",
        (now.isoformat(), len(db_files), len(all_patterns), len(all_anomalies), round(duration, 1)),
    )
    db.commit()

    result = {
        "ts": now.isoformat(),
        "action": "mine",
        "databases_scanned": len(db_files),
        "total_rows_across_dbs": sum(i.get("total_rows", 0) for i in all_info),
        "patterns_found": len(all_patterns),
        "anomalies_found": len(all_anomalies),
        "duration_ms": round(duration, 1),
        "databases": [
            {"name": os.path.basename(i["path"]), "tables": len(i.get("tables", [])),
             "rows": i.get("total_rows", 0)}
            for i in all_info
        ],
    }
    db.close()
    return result


def do_patterns():
    """Show discovered patterns."""
    db = init_db()
    rows = db.execute(
        "SELECT source_db, pattern_type, pattern_desc, frequency, confidence FROM patterns ORDER BY confidence DESC LIMIT 30"
    ).fetchall()

    result = {
        "ts": datetime.now().isoformat(),
        "action": "patterns",
        "total": len(rows),
        "patterns": [
            {"source": r[0], "type": r[1], "desc": r[2], "frequency": r[3], "confidence": round(r[4], 3)}
            for r in rows
        ],
    }
    db.close()
    return result


def do_anomalies():
    """Show detected anomalies."""
    db = init_db()
    rows = db.execute(
        "SELECT source_db, anomaly_type, description, severity FROM anomalies ORDER BY id DESC LIMIT 30"
    ).fetchall()

    severity_counts = db.execute(
        "SELECT severity, COUNT(*) FROM anomalies GROUP BY severity"
    ).fetchall()

    result = {
        "ts": datetime.now().isoformat(),
        "action": "anomalies",
        "total": len(rows),
        "by_severity": {r[0]: r[1] for r in severity_counts},
        "anomalies": [
            {"source": r[0], "type": r[1], "desc": r[2], "severity": r[3]}
            for r in rows
        ],
    }
    db.close()
    return result


def do_export():
    """Export all mined data."""
    db = init_db()
    patterns = db.execute("SELECT * FROM patterns").fetchall()
    anomalies = db.execute("SELECT * FROM anomalies").fetchall()
    scans = db.execute("SELECT * FROM scan_log ORDER BY id DESC LIMIT 10").fetchall()

    result = {
        "ts": datetime.now().isoformat(),
        "action": "export",
        "patterns_count": len(patterns),
        "anomalies_count": len(anomalies),
        "scans_count": len(scans),
        "last_scan": {
            "ts": scans[0][1] if scans else None,
            "dbs": scans[0][2] if scans else 0,
            "patterns": scans[0][3] if scans else 0,
            "anomalies": scans[0][4] if scans else 0,
        } if scans else None,
    }
    db.close()
    return result


def do_status():
    db = init_db()
    result = {
        "ts": datetime.now().isoformat(),
        "script": "jarvis_pattern_miner.py",
        "script_id": 248,
        "db": str(DB_PATH),
        "data_dir": str(DATA_DIR),
        "db_files_available": len(list(DATA_DIR.glob("*.db"))),
        "total_patterns": db.execute("SELECT COUNT(*) FROM patterns").fetchone()[0],
        "total_anomalies": db.execute("SELECT COUNT(*) FROM anomalies").fetchone()[0],
        "total_scans": db.execute("SELECT COUNT(*) FROM scan_log").fetchone()[0],
        "status": "ok",
    }
    db.close()
    return result


def main():
    parser = argparse.ArgumentParser(description="jarvis_pattern_miner.py — Behavioral pattern mining (#248)")
    parser.add_argument("--mine", action="store_true", help="Full mining scan of all databases")
    parser.add_argument("--patterns", action="store_true", help="Show discovered patterns")
    parser.add_argument("--anomalies", action="store_true", help="Show detected anomalies")
    parser.add_argument("--export", action="store_true", help="Export all mined data")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    args = parser.parse_args()

    if args.mine:
        result = do_mine()
    elif args.patterns:
        result = do_patterns()
    elif args.anomalies:
        result = do_anomalies()
    elif args.export:
        result = do_export()
    else:
        result = do_status()

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
