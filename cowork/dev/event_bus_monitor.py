#!/usr/bin/env python3
"""event_bus_monitor.py — Surveille le event_bus JARVIS en continu.

Log les events critiques, detecte les boucles infinies,
et alerte si le debit d'events est anormal.

Usage:
    python dev/event_bus_monitor.py --once
    python dev/event_bus_monitor.py --loop --interval 30
    python dev/event_bus_monitor.py --report
"""
import argparse
from _paths import ETOILE_DB
import json
import os
import sqlite3
import time
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "event_bus_monitor.db"
WS_URL = "http://127.0.0.1:9742"
TELEGRAM_PROXY = "http://127.0.0.1:18800"

# Thresholds
MAX_EVENTS_PER_MIN = 100  # Alert if more events per minute
MAX_SAME_EVENT_PER_MIN = 50  # Alert if same event fires too often (loop detection)
CRITICAL_EVENTS = [
    "autonomous.task_failed",
    "brain.skill_created",
    "proactive.executed",
    "improve.cycle_done",
    "autodev.command_created",
]


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS checks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, total_events INTEGER, unique_events INTEGER,
        loops_detected INTEGER, alerts TEXT, top_events TEXT)""")
    db.execute("""CREATE TABLE IF NOT EXISTS event_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, event_name TEXT, count INTEGER)""")
    db.commit()
    return db


def get_event_stats():
    """Get event_bus stats from WS REST API."""
    try:
        req = urllib.request.Request(f"{WS_URL}/api/event_bus/stats")
        with urllib.request.urlopen(req, timeout=5) as r:
            return json.loads(r.read().decode())
    except Exception:
        pass

    # Fallback: try to read from etoile.db event_log if it exists
    etoile = Path(str(ETOILE_DB))
    if etoile.exists():
        try:
            conn = sqlite3.connect(str(etoile))
            has_table = conn.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='event_log'"
            ).fetchone()[0]
            if has_table:
                rows = conn.execute("""
                    SELECT event_name, COUNT(*) as cnt, MAX(timestamp) as last_ts
                    FROM event_log
                    WHERE timestamp > ?
                    GROUP BY event_name
                    ORDER BY cnt DESC LIMIT 50
                """, (time.time() - 300,)).fetchall()  # Last 5 minutes
                conn.close()
                events = {}
                for r in rows:
                    events[r[0]] = {"count": r[1], "last_ts": r[2]}
                return {"events": events, "source": "etoile_db"}
            conn.close()
        except Exception:
            pass

    return {"error": "no_event_data_available"}


def get_autonomous_events():
    """Get autonomous loop task events."""
    try:
        req = urllib.request.Request(f"{WS_URL}/api/autonomous/status")
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read().decode())
            tasks = data.get("tasks", {})
            events = {}
            for name, info in tasks.items():
                run_count = info.get("run_count", 0)
                fail_count = info.get("fail_count", 0)
                if run_count > 0:
                    events[f"task.{name}"] = {
                        "runs": run_count,
                        "fails": fail_count,
                        "rate": round(fail_count / max(run_count, 1), 3),
                    }
            return events
    except Exception:
        return {}


def send_telegram_alert(message):
    """Send alert via Telegram proxy."""
    try:
        data = json.dumps({"text": message}).encode()
        req = urllib.request.Request(
            f"{TELEGRAM_PROXY}/chat",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass


def do_check():
    """Run a single event bus check."""
    db = init_db()
    now = time.time()
    alerts = []

    # Get event stats
    stats = get_event_stats()
    auto_events = get_autonomous_events()

    total_events = 0
    unique_events = 0
    loops_detected = 0
    top_events = []

    if "events" in stats:
        events = stats["events"]
        unique_events = len(events)

        for name, info in events.items():
            count = info.get("count", 0)
            total_events += count
            top_events.append({"name": name, "count": count})

            # Log event
            db.execute(
                "INSERT INTO event_log (ts, event_name, count) VALUES (?,?,?)",
                (now, name, count)
            )

            # Loop detection: same event fired too many times
            if count > MAX_SAME_EVENT_PER_MIN:
                loops_detected += 1
                alerts.append(f"LOOP DETECTED: '{name}' fired {count} times in 5min")

        # Total throughput check
        if total_events > MAX_EVENTS_PER_MIN * 5:  # 5-min window
            alerts.append(f"HIGH EVENT RATE: {total_events} events in 5min (threshold: {MAX_EVENTS_PER_MIN * 5})")

        top_events.sort(key=lambda x: x["count"], reverse=True)
        top_events = top_events[:10]

    elif "error" in stats:
        alerts.append(f"Event bus unavailable: {stats.get('error', 'unknown')}")

    # Check autonomous task failure rates
    for name, info in auto_events.items():
        if info.get("rate", 0) > 0.5 and info.get("runs", 0) > 5:
            alerts.append(f"HIGH FAIL RATE: {name} — {info['fails']}/{info['runs']} ({info['rate']*100:.0f}%)")

    # Store check result
    db.execute(
        "INSERT INTO checks (ts, total_events, unique_events, loops_detected, alerts, top_events) VALUES (?,?,?,?,?,?)",
        (now, total_events, unique_events, loops_detected,
         json.dumps(alerts), json.dumps(top_events))
    )
    db.commit()
    db.close()

    # Alert if critical
    if loops_detected > 0 or len(alerts) >= 3:
        msg = f"[EVENT BUS MONITOR] {loops_detected} loops, {len(alerts)} alerts\n" + "\n".join(alerts[:5])
        send_telegram_alert(msg)

    return {
        "ts": datetime.now().isoformat(),
        "total_events": total_events,
        "unique_events": unique_events,
        "loops_detected": loops_detected,
        "alerts": alerts,
        "top_events": top_events[:5],
        "auto_events": auto_events,
    }


def get_report():
    """Get monitoring report."""
    db = init_db()
    rows = db.execute("SELECT * FROM checks ORDER BY ts DESC LIMIT 20").fetchall()
    db.close()
    report = []
    for r in rows:
        report.append({
            "ts": datetime.fromtimestamp(r[1]).isoformat() if r[1] else None,
            "total_events": r[2], "unique_events": r[3],
            "loops": r[4],
            "alerts": json.loads(r[5]) if r[5] else [],
        })
    return report


def main():
    parser = argparse.ArgumentParser(description="Event Bus Monitor — Detect loops & anomalies")
    parser.add_argument("--once", action="store_true", help="Single check")
    parser.add_argument("--loop", action="store_true", help="Continuous monitoring")
    parser.add_argument("--interval", type=int, default=30, help="Loop interval (seconds)")
    parser.add_argument("--report", action="store_true", help="Historical report")
    args = parser.parse_args()

    if args.report:
        report = get_report()
        print(json.dumps(report, ensure_ascii=False, indent=2))
    elif args.loop:
        print(f"[EVENT_BUS_MONITOR] Starting continuous monitoring (interval={args.interval}s)")
        while True:
            try:
                result = do_check()
                status = "OK" if result["loops_detected"] == 0 else f"WARN ({result['loops_detected']} loops)"
                print(f"[{result['ts']}] {status} — {result['total_events']} events, {result['unique_events']} unique")
                if result["alerts"]:
                    for a in result["alerts"][:3]:
                        print(f"  ALERT: {a}")
            except Exception as e:
                print(f"[ERROR] Check failed: {e}")
            time.sleep(args.interval)
    else:
        result = do_check()
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()