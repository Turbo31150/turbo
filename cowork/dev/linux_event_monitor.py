#!/usr/bin/env python3
"""win_event_monitor.py — Moniteur evenements Windows.

Parse Event Log, detecte erreurs critiques.

Usage:
    python dev/win_event_monitor.py --once
    python dev/win_event_monitor.py --errors
    python dev/win_event_monitor.py --security
    python dev/win_event_monitor.py --report
"""
import argparse
import json
import os
import sqlite3
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "event_monitor.db"


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, log_name TEXT, level TEXT,
        source TEXT, event_id INTEGER, message TEXT)""")
    db.execute("""CREATE TABLE IF NOT EXISTS scans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, errors INTEGER, warnings INTEGER,
        critical INTEGER, report TEXT)""")
    db.commit()
    return db


def query_event_log(log_name, level="Error", max_events=50):
    """Query Windows Event Log via wevtutil."""
    events = []
    try:
        # Query last 24h
        result = subprocess.run(
            ["wevtutil", "qe", log_name, "/q:*[System[Level<=2]]",
             "/c:" + str(max_events), "/f:text", "/rd:true"],
            capture_output=True, text=True, timeout=15
        )

        current = {}
        for line in result.stdout.split("\n"):
            line = line.strip()
            if line.startswith("Event["):
                if current:
                    events.append(current)
                current = {}
            elif ":" in line:
                key, _, val = line.partition(":")
                key = key.strip().lower().replace(" ", "_")
                val = val.strip()
                if key in ("source", "event_id", "level", "date"):
                    current[key] = val
                elif key == "description":
                    current["message"] = val[:200]
        if current:
            events.append(current)

    except Exception:
        pass

    # Fallback: PowerShell
    if not events:
        try:
            ps_cmd = f"Get-EventLog -LogName {log_name} -EntryType Error -Newest 20 | Select-Object TimeGenerated,Source,EventID,Message | ConvertTo-Json"
            result = subprocess.run(
                ["bash", "-Command", ps_cmd],
                capture_output=True, text=True, timeout=15
            )
            data = json.loads(result.stdout)
            if isinstance(data, dict):
                data = [data]
            for item in data:
                events.append({
                    "source": item.get("Source", ""),
                    "event_id": str(item.get("EventID", "")),
                    "message": str(item.get("Message", ""))[:200],
                    "level": "Error",
                })
        except Exception:
            pass

    return events


def do_scan():
    """Full event log scan."""
    db = init_db()

    all_events = []
    for log in ["System", "Application"]:
        events = query_event_log(log)
        for e in events:
            e["log"] = log
            all_events.append(e)

    # Categorize
    errors = [e for e in all_events if e.get("level", "").lower() in ("error", "2")]
    warnings = [e for e in all_events if e.get("level", "").lower() in ("warning", "3")]
    critical = [e for e in all_events if e.get("level", "").lower() in ("critical", "1")]

    # Detect patterns
    patterns = {}
    for e in all_events:
        source = e.get("source", "unknown")
        patterns[source] = patterns.get(source, 0) + 1

    frequent_sources = sorted(patterns.items(), key=lambda x: x[1], reverse=True)[:5]

    # Store
    for e in all_events[:50]:
        db.execute(
            "INSERT INTO events (ts, log_name, level, source, event_id, message) VALUES (?,?,?,?,?,?)",
            (time.time(), e.get("log", ""), e.get("level", ""),
             e.get("source", ""), int(e.get("event_id", 0) or 0), e.get("message", "")[:200])
        )

    report = {
        "ts": datetime.now().isoformat(),
        "total_events": len(all_events),
        "errors": len(errors),
        "warnings": len(warnings),
        "critical": len(critical),
        "frequent_sources": [{"source": s, "count": c} for s, c in frequent_sources],
        "recent_errors": [{
            "source": e.get("source", ""), "id": e.get("event_id", ""),
            "message": e.get("message", "")[:100], "log": e.get("log", ""),
        } for e in errors[:10]],
    }

    db.execute(
        "INSERT INTO scans (ts, errors, warnings, critical, report) VALUES (?,?,?,?,?)",
        (time.time(), len(errors), len(warnings), len(critical), json.dumps(report))
    )
    db.commit()
    db.close()
    return report


def main():
    parser = argparse.ArgumentParser(description="Windows Event Monitor")
    parser.add_argument("--once", "--errors", action="store_true", help="Scan events")
    parser.add_argument("--security", action="store_true", help="Security events")
    parser.add_argument("--report", action="store_true", help="Report")
    parser.add_argument("--watch", action="store_true", help="Watch mode")
    args = parser.parse_args()

    result = do_scan()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
