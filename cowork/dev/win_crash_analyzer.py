#!/usr/bin/env python3
"""win_crash_analyzer.py — #213 Analyze Windows BSOD/crashes via event logs.
Usage:
    python dev/win_crash_analyzer.py --scan
    python dev/win_crash_analyzer.py --recent
    python dev/win_crash_analyzer.py --patterns
    python dev/win_crash_analyzer.py --prevent
    python dev/win_crash_analyzer.py --once
"""
import argparse, json, sqlite3, time, subprocess, os, re
from datetime import datetime, timedelta
from pathlib import Path
from collections import Counter

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "crash_analyzer.db"

# Critical Event IDs
CRASH_EVENTS = {
    41: {"name": "Kernel-Power", "severity": "critical", "desc": "Unexpected shutdown/reboot"},
    1001: {"name": "Windows Error Reporting", "severity": "high", "desc": "Application crash report"},
    6008: {"name": "EventLog", "severity": "high", "desc": "Unexpected shutdown detected"},
    1000: {"name": "Application Error", "severity": "medium", "desc": "Application crash"},
    1002: {"name": "Application Hang", "severity": "medium", "desc": "Application not responding"},
    7031: {"name": "Service Control Manager", "severity": "high", "desc": "Service terminated unexpectedly"},
    7034: {"name": "Service Control Manager", "severity": "high", "desc": "Service terminated unexpectedly"},
    161: {"name": "volmgr", "severity": "critical", "desc": "Dump file creation failed"},
}

# Common fix recommendations
FIX_RECOMMENDATIONS = {
    41: ["Check power supply stability", "Update BIOS/UEFI", "Check for overheating", "Run sfc /scannow"],
    1001: ["Update the crashing application", "Check for driver conflicts", "Verify system files"],
    6008: ["Check power supply", "Check for scheduled tasks causing shutdown", "Review thermal logs"],
    1000: ["Update the application", "Reinstall if persistent", "Check compatibility"],
    1002: ["Check disk performance", "Increase available RAM", "Update application"],
    7031: ["Check service dependencies", "Update related drivers", "Check disk health"],
    7034: ["Review service configuration", "Check for resource exhaustion"],
    161: ["Free disk space for crash dumps", "Check disk health with chkdsk"],
}


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("""CREATE TABLE IF NOT EXISTS crashes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id INTEGER,
        event_name TEXT,
        severity TEXT,
        source TEXT,
        message TEXT,
        event_time TEXT,
        scan_time TEXT DEFAULT (datetime('now','localtime'))
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS patterns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pattern_type TEXT,
        description TEXT,
        frequency INTEGER,
        last_seen TEXT,
        recommendation TEXT,
        ts TEXT DEFAULT (datetime('now','localtime'))
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS scans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        events_found INTEGER,
        new_events INTEGER,
        critical_count INTEGER,
        ts TEXT DEFAULT (datetime('now','localtime'))
    )""")
    db.commit()
    return db


def _query_event_log(event_ids, count=50):
    """Query Windows Event Log for crash events."""
    events = []
    # Build XPath query for multiple event IDs
    id_filters = " or ".join(f"EventID={eid}" for eid in event_ids)
    xpath = f"*[System[({id_filters})]]"

    for log_name in ["System", "Application"]:
        try:
            cmd = [
                "wevtutil", "qe", log_name,
                f"/q:{xpath}",
                f"/c:{count}",
                "/f:text",
                "/rd:true"  # reverse direction (newest first)
            ]
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            if result.returncode == 0 and result.stdout.strip():
                events.extend(_parse_wevtutil_text(result.stdout, log_name))
        except subprocess.TimeoutExpired:
            pass
        except FileNotFoundError:
            # wevtutil not available
            pass
        except Exception:
            pass

    return events


def _parse_wevtutil_text(text, log_name):
    """Parse wevtutil text output into structured events."""
    events = []
    current = {}

    for line in text.split("\n"):
        line = line.strip()
        if not line:
            if current:
                current["log"] = log_name
                events.append(current)
                current = {}
            continue

        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip().lower()
            value = value.strip()

            if "event id" in key or key == "id":
                try:
                    current["event_id"] = int(re.search(r'\d+', value).group())
                except (AttributeError, ValueError):
                    pass
            elif "date" in key or "time" in key:
                if "event_time" not in current:
                    current["event_time"] = value
            elif "source" in key or "provider" in key:
                current["source"] = value
            elif "description" in key or "message" in key:
                current["message"] = value[:500]

    if current:
        current["log"] = log_name
        events.append(current)

    return events


def scan_crashes(db):
    """Scan event logs for crash events."""
    event_ids = list(CRASH_EVENTS.keys())
    events = _query_event_log(event_ids)

    new_count = 0
    critical = 0

    for ev in events:
        eid = ev.get("event_id", 0)
        event_info = CRASH_EVENTS.get(eid, {"name": "Unknown", "severity": "low", "desc": ""})

        # Check if already recorded (by event_id + event_time)
        existing = db.execute(
            "SELECT id FROM crashes WHERE event_id=? AND event_time=?",
            (eid, ev.get("event_time", ""))
        ).fetchone()

        if not existing:
            db.execute(
                "INSERT INTO crashes (event_id, event_name, severity, source, message, event_time) VALUES (?,?,?,?,?,?)",
                (eid, event_info["name"], event_info["severity"],
                 ev.get("source", ""), ev.get("message", event_info["desc"]),
                 ev.get("event_time", ""))
            )
            new_count += 1

        if event_info["severity"] == "critical":
            critical += 1

    db.execute(
        "INSERT INTO scans (events_found, new_events, critical_count) VALUES (?,?,?)",
        (len(events), new_count, critical)
    )
    db.commit()

    return {
        "scanned": True,
        "events_found": len(events),
        "new_events": new_count,
        "critical": critical,
        "event_ids_checked": event_ids
    }


def get_recent(db, limit=20):
    """Get recent crash events."""
    rows = db.execute(
        "SELECT event_id, event_name, severity, source, message, event_time FROM crashes ORDER BY id DESC LIMIT ?",
        (limit,)
    ).fetchall()
    return {
        "recent_crashes": [
            {"event_id": r[0], "name": r[1], "severity": r[2],
             "source": r[3], "message": r[4][:200], "time": r[5]}
            for r in rows
        ],
        "total_recorded": db.execute("SELECT COUNT(*) FROM crashes").fetchone()[0]
    }


def analyze_patterns(db):
    """Detect crash patterns."""
    # Frequency by event type
    freq = db.execute(
        "SELECT event_id, event_name, severity, COUNT(*) as cnt FROM crashes GROUP BY event_id ORDER BY cnt DESC"
    ).fetchall()

    patterns = []
    for eid, ename, sev, cnt in freq:
        last = db.execute(
            "SELECT event_time FROM crashes WHERE event_id=? ORDER BY id DESC LIMIT 1", (eid,)
        ).fetchone()

        recs = FIX_RECOMMENDATIONS.get(eid, ["No specific recommendation"])
        pattern = {
            "event_id": eid,
            "name": ename,
            "severity": sev,
            "occurrences": cnt,
            "last_seen": last[0] if last else "unknown",
            "recommendations": recs
        }
        patterns.append(pattern)

        db.execute("""INSERT OR REPLACE INTO patterns
            (pattern_type, description, frequency, last_seen, recommendation)
            VALUES (?,?,?,?,?)""",
            (f"event_{eid}", f"{ename}: {CRASH_EVENTS.get(eid, {}).get('desc', '')}",
             cnt, last[0] if last else "", json.dumps(recs))
        )

    db.commit()

    # Weekly trend
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    recent_count = db.execute(
        "SELECT COUNT(*) FROM crashes WHERE scan_time >= ?", (week_ago,)
    ).fetchone()[0]

    return {
        "patterns": patterns,
        "total_events": db.execute("SELECT COUNT(*) FROM crashes").fetchone()[0],
        "last_7_days": recent_count,
        "most_common": patterns[0] if patterns else None
    }


def get_prevention(db):
    """Prevention recommendations."""
    patterns = db.execute(
        "SELECT pattern_type, frequency, recommendation FROM patterns ORDER BY frequency DESC LIMIT 10"
    ).fetchall()

    recs = []
    for p in patterns:
        try:
            rec_list = json.loads(p[2])
        except (json.JSONDecodeError, TypeError):
            rec_list = [p[2]]
        recs.append({
            "pattern": p[0],
            "frequency": p[1],
            "recommendations": rec_list
        })

    general = [
        "Run 'sfc /scannow' to verify system file integrity",
        "Run 'DISM /Online /Cleanup-Image /RestoreHealth' for component store repair",
        "Keep drivers updated, especially GPU and chipset",
        "Monitor temperatures with GPU/CPU monitoring tools",
        "Ensure stable power supply and no overclocking instabilities",
        "Check disk health with 'chkdsk /f'"
    ]

    return {
        "targeted_recommendations": recs,
        "general_recommendations": general,
        "health_commands": [
            "sfc /scannow",
            "DISM /Online /Cleanup-Image /RestoreHealth",
            "chkdsk C: /f",
            "wmic diskdrive get status"
        ]
    }


def do_status(db):
    total = db.execute("SELECT COUNT(*) FROM crashes").fetchone()[0]
    critical = db.execute("SELECT COUNT(*) FROM crashes WHERE severity='critical'").fetchone()[0]
    scans = db.execute("SELECT COUNT(*) FROM scans").fetchone()[0]
    last_scan = db.execute("SELECT ts FROM scans ORDER BY id DESC LIMIT 1").fetchone()
    return {
        "script": "win_crash_analyzer.py",
        "id": 213,
        "db": str(DB_PATH),
        "total_crashes": total,
        "critical_events": critical,
        "total_scans": scans,
        "last_scan": last_scan[0] if last_scan else None,
        "monitored_event_ids": list(CRASH_EVENTS.keys()),
        "ts": datetime.now().isoformat()
    }


def main():
    parser = argparse.ArgumentParser(description="Windows Crash Analyzer — BSOD/crash detection and analysis")
    parser.add_argument("--scan", action="store_true", help="Scan event logs for crashes")
    parser.add_argument("--recent", action="store_true", help="Show recent crashes")
    parser.add_argument("--patterns", action="store_true", help="Analyze crash patterns")
    parser.add_argument("--prevent", action="store_true", help="Prevention recommendations")
    parser.add_argument("--once", action="store_true", help="Quick status")
    args = parser.parse_args()

    db = init_db()

    if args.scan:
        result = scan_crashes(db)
    elif args.recent:
        result = get_recent(db)
    elif args.patterns:
        result = analyze_patterns(db)
    elif args.prevent:
        result = get_prevention(db)
    else:
        result = do_status(db)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    db.close()


if __name__ == "__main__":
    main()
