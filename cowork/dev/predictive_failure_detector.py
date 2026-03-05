#!/usr/bin/env python3
"""Predictive Failure Detector — Predict script failures from patterns.

Analyzes error logs from dev/data/*.db SQLite databases, detects recurring
failure patterns (time-based, load-based), and predicts likely next failures
with confidence scores.

Usage:
    python predictive_failure_detector.py --once --predict
    python predictive_failure_detector.py --once --stats
    python predictive_failure_detector.py --once --predict --stats
"""

import argparse
import datetime
import json
import math
import os
import sqlite3
import sys
import time
import glob
import re
from collections import Counter, defaultdict


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "cowork_gaps.db")


def init_db(conn):
    """Initialize SQLite tables for failure tracking and predictions."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS failure_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            source_db TEXT NOT NULL,
            source_table TEXT NOT NULL,
            error_type TEXT,
            error_message TEXT,
            script_name TEXT,
            severity TEXT DEFAULT 'medium'
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS failure_predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            script_name TEXT,
            predicted_failure TEXT,
            confidence REAL,
            reason TEXT,
            window_hours INTEGER DEFAULT 24
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS failure_patterns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            pattern_type TEXT NOT NULL,
            pattern_key TEXT NOT NULL,
            occurrences INTEGER,
            last_seen TEXT,
            avg_interval_hours REAL,
            details TEXT
        )
    """)
    conn.commit()


def scan_databases(verbose=False):
    """Scan all SQLite databases in data/ for error-related records."""
    events = []
    db_pattern = os.path.join(DATA_DIR, "*.db")

    for db_file in glob.glob(db_pattern):
        db_name = os.path.basename(db_file)
        if verbose:
            print(f"  Scanning DB: {db_name}")

        try:
            conn = sqlite3.connect(db_file, timeout=5)
            conn.row_factory = sqlite3.Row

            # Get all tables
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()

            for table_row in tables:
                table = table_row["name"]
                events.extend(_scan_table_for_errors(conn, db_name, table, verbose))

            conn.close()
        except (sqlite3.Error, OSError) as e:
            if verbose:
                print(f"    Error reading {db_name}: {e}")

    return events


def _scan_table_for_errors(conn, db_name, table, verbose=False):
    """Scan a single table for error-like records."""
    events = []

    try:
        # Get column names
        cursor = conn.execute(f"PRAGMA table_info({table})")
        columns = {row["name"].lower() for row in cursor.fetchall()}

        # Look for status/error columns
        error_columns = columns & {"status", "error", "error_message", "result",
                                    "state", "severity", "level"}
        time_columns = columns & {"timestamp", "created_at", "date", "time",
                                   "created", "updated_at", "last_seen"}

        if not error_columns:
            return events

        # Query for error records
        for ecol in error_columns:
            try:
                time_col = next(iter(time_columns)) if time_columns else None
                select_cols = [ecol]
                if time_col:
                    select_cols.append(time_col)

                # Look for name/script columns
                name_cols = columns & {"name", "script_name", "script", "task",
                                        "test_name", "source"}
                if name_cols:
                    select_cols.append(next(iter(name_cols)))

                query = f"SELECT {', '.join(select_cols)} FROM {table} WHERE "
                query += f"{ecol} LIKE '%error%' OR {ecol} LIKE '%fail%' "
                query += f"OR {ecol} = 'failed' OR {ecol} = 'error' "
                query += f"OR {ecol} LIKE '%exception%' OR {ecol} LIKE '%timeout%'"
                query += " LIMIT 500"

                rows = conn.execute(query).fetchall()
                for row in rows:
                    event = {
                        "source_db": db_name,
                        "source_table": table,
                        "error_type": ecol,
                        "error_message": str(row[0])[:200],
                        "timestamp": str(row[1]) if len(row) > 1 and row[1] else "",
                        "script_name": str(row[2]) if len(row) > 2 and row[2] else ""
                    }
                    events.append(event)

            except sqlite3.Error:
                continue

    except sqlite3.Error:
        pass

    return events


def detect_patterns(events, verbose=False):
    """Detect recurring failure patterns from events."""
    patterns = []

    # Pattern 1: Script-based clustering
    script_errors = defaultdict(list)
    for e in events:
        key = e.get("script_name") or e.get("source_table", "unknown")
        script_errors[key].append(e)

    for script, errs in script_errors.items():
        if len(errs) >= 2:
            patterns.append({
                "type": "recurring_script",
                "key": script,
                "occurrences": len(errs),
                "error_types": list(set(e.get("error_message", "")[:50] for e in errs)),
                "last_seen": max((e.get("timestamp", "") for e in errs), default="")
            })

    # Pattern 2: Error type clustering
    error_types = Counter()
    for e in events:
        msg = e.get("error_message", "").lower()
        # Normalize error messages
        if "timeout" in msg:
            error_types["timeout"] += 1
        elif "connection" in msg or "refused" in msg:
            error_types["connection_error"] += 1
        elif "permission" in msg or "access" in msg:
            error_types["permission_error"] += 1
        elif "memory" in msg or "oom" in msg:
            error_types["memory_error"] += 1
        elif "disk" in msg or "space" in msg:
            error_types["disk_error"] += 1
        elif "fail" in msg:
            error_types["general_failure"] += 1
        else:
            error_types["other"] += 1

    for error_type, count in error_types.most_common():
        if count >= 2:
            patterns.append({
                "type": "error_category",
                "key": error_type,
                "occurrences": count,
                "error_types": [error_type],
                "last_seen": ""
            })

    # Pattern 3: Time-based patterns (hourly distribution)
    hourly = Counter()
    for e in events:
        ts = e.get("timestamp", "")
        try:
            if "T" in ts:
                hour = int(ts.split("T")[1][:2])
            elif " " in ts:
                hour = int(ts.split(" ")[1][:2])
            else:
                continue
            hourly[hour] += 1
        except (ValueError, IndexError):
            continue

    if hourly:
        peak_hour = hourly.most_common(1)[0]
        if peak_hour[1] >= 3:
            patterns.append({
                "type": "time_based",
                "key": f"peak_hour_{peak_hour[0]:02d}",
                "occurrences": peak_hour[1],
                "error_types": [f"Most failures at hour {peak_hour[0]:02d}:00"],
                "last_seen": ""
            })

    # Pattern 4: Database-based clustering
    db_errors = Counter(e.get("source_db", "") for e in events)
    for db_name, count in db_errors.most_common():
        if count >= 3:
            patterns.append({
                "type": "db_hotspot",
                "key": db_name,
                "occurrences": count,
                "error_types": [f"Database {db_name} has {count} error records"],
                "last_seen": ""
            })

    return patterns


def predict_failures(patterns, events, verbose=False):
    """Predict likely next failures based on detected patterns."""
    predictions = []
    now = datetime.datetime.now()
    current_hour = now.hour

    for pattern in patterns:
        if pattern["type"] == "recurring_script":
            # Scripts that fail often will likely fail again
            occurrences = pattern["occurrences"]
            # Confidence based on frequency
            confidence = min(0.95, 0.3 + (occurrences * 0.1))

            predictions.append({
                "script_name": pattern["key"],
                "predicted_failure": f"Recurring failure ({occurrences} past events)",
                "confidence": round(confidence, 2),
                "reason": f"Script has failed {occurrences} times. "
                         f"Error types: {', '.join(pattern['error_types'][:3])}",
                "window_hours": 24,
                "severity": "high" if occurrences >= 5 else "medium"
            })

        elif pattern["type"] == "time_based":
            # Predict failures at peak hours
            peak_str = pattern["key"]  # e.g., "peak_hour_14"
            try:
                peak_hour = int(peak_str.split("_")[-1])
            except ValueError:
                continue

            hours_until = (peak_hour - current_hour) % 24
            confidence = min(0.85, 0.4 + (pattern["occurrences"] * 0.08))

            predictions.append({
                "script_name": "multiple",
                "predicted_failure": f"Peak failure window at {peak_hour:02d}:00 "
                                    f"(in ~{hours_until}h)",
                "confidence": round(confidence, 2),
                "reason": f"{pattern['occurrences']} failures historically at this hour",
                "window_hours": hours_until + 1,
                "severity": "medium"
            })

        elif pattern["type"] == "error_category":
            if pattern["key"] in ("timeout", "connection_error", "memory_error"):
                confidence = min(0.80, 0.3 + (pattern["occurrences"] * 0.07))
                predictions.append({
                    "script_name": "system",
                    "predicted_failure": f"{pattern['key']} likely to recur",
                    "confidence": round(confidence, 2),
                    "reason": f"{pattern['occurrences']} occurrences of {pattern['key']}. "
                             "System-level issues tend to be persistent.",
                    "window_hours": 12,
                    "severity": "high" if pattern["key"] == "memory_error" else "medium"
                })

    # Sort by confidence descending
    predictions.sort(key=lambda p: p["confidence"], reverse=True)
    return predictions


def compute_stats(events, patterns):
    """Compute summary statistics from events and patterns."""
    total_events = len(events)

    # Error distribution
    error_dist = Counter()
    for e in events:
        msg = e.get("error_message", "").lower()
        if "timeout" in msg:
            error_dist["timeout"] += 1
        elif "fail" in msg:
            error_dist["failure"] += 1
        elif "error" in msg:
            error_dist["error"] += 1
        else:
            error_dist["other"] += 1

    # Source distribution
    source_dist = Counter(e.get("source_db", "unknown") for e in events)

    # Script distribution
    script_dist = Counter(e.get("script_name", "unknown") for e in events if e.get("script_name"))

    # Time distribution
    hourly_dist = Counter()
    for e in events:
        ts = e.get("timestamp", "")
        try:
            if "T" in ts:
                hour = int(ts.split("T")[1][:2])
            elif " " in ts:
                hour = int(ts.split(" ")[1][:2])
            else:
                continue
            hourly_dist[hour] += 1
        except (ValueError, IndexError):
            continue

    return {
        "total_error_events": total_events,
        "total_patterns": len(patterns),
        "error_distribution": dict(error_dist.most_common()),
        "source_distribution": dict(source_dist.most_common(10)),
        "top_failing_scripts": dict(script_dist.most_common(10)),
        "hourly_distribution": dict(sorted(hourly_dist.items())),
        "most_common_pattern": patterns[0]["key"] if patterns else "none"
    }


def run(args):
    """Main execution logic."""
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    init_db(conn)

    if args.verbose:
        print(f"[failure-detector] Scanning databases in {DATA_DIR}")

    # Scan all databases for error events
    events = scan_databases(verbose=args.verbose)

    if args.verbose:
        print(f"[failure-detector] Found {len(events)} error events")

    # Detect patterns
    patterns = detect_patterns(events, verbose=args.verbose)

    if args.verbose:
        print(f"[failure-detector] Detected {len(patterns)} patterns")

    # Save patterns to DB
    now = datetime.datetime.now().isoformat()
    for p in patterns:
        conn.execute(
            "INSERT INTO failure_patterns (timestamp, pattern_type, pattern_key, occurrences, last_seen, details) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (now, p["type"], p["key"], p["occurrences"],
             p.get("last_seen", ""), json.dumps(p.get("error_types", [])))
        )

    # Build output
    output = {
        "timestamp": now,
        "events_scanned": len(events),
        "patterns_detected": len(patterns)
    }

    # Predictions
    if args.predict:
        predictions = predict_failures(patterns, events, verbose=args.verbose)

        # Save predictions to DB
        for pred in predictions:
            conn.execute(
                "INSERT INTO failure_predictions "
                "(timestamp, script_name, predicted_failure, confidence, reason, window_hours) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (now, pred["script_name"], pred["predicted_failure"],
                 pred["confidence"], pred["reason"], pred["window_hours"])
            )

        output["predictions"] = predictions
        output["high_risk_count"] = sum(1 for p in predictions if p["confidence"] >= 0.6)

        if args.verbose:
            print(f"\n[failure-detector] Predictions ({len(predictions)} total):")
            for p in predictions:
                risk = "HIGH" if p["confidence"] >= 0.6 else "MED" if p["confidence"] >= 0.4 else "LOW"
                print(f"  [{risk}] {p['script_name']}: {p['predicted_failure']} "
                      f"(confidence={p['confidence']})")

    # Statistics
    if args.stats:
        stats = compute_stats(events, patterns)
        output["stats"] = stats

        if args.verbose:
            print(f"\n[failure-detector] Statistics:")
            print(f"  Total error events: {stats['total_error_events']}")
            print(f"  Error distribution: {stats['error_distribution']}")
            print(f"  Top sources: {stats['source_distribution']}")
            if stats['top_failing_scripts']:
                print(f"  Top failing scripts: {stats['top_failing_scripts']}")

    output["patterns"] = [
        {
            "type": p["type"],
            "key": p["key"],
            "occurrences": p["occurrences"]
        }
        for p in patterns
    ]

    conn.commit()
    conn.close()

    print(json.dumps(output, indent=2))
    return output


def main():
    parser = argparse.ArgumentParser(
        description="Predictive Failure Detector — Predict script failures from patterns"
    )
    parser.add_argument("--once", action="store_true",
                        help="Run once and exit")
    parser.add_argument("--predict", action="store_true",
                        help="Generate failure predictions")
    parser.add_argument("--stats", action="store_true",
                        help="Show failure statistics")
    parser.add_argument("--verbose", action="store_true",
                        help="Enable verbose output")
    args = parser.parse_args()

    if args.once:
        run(args)
    else:
        print("[failure-detector] Running in continuous mode (Ctrl+C to stop)")
        while True:
            try:
                run(args)
                time.sleep(300)
            except KeyboardInterrupt:
                print("\n[failure-detector] Stopped")
                break


if __name__ == "__main__":
    main()
