#!/usr/bin/env python3
"""jarvis_performance_tracker.py — #208 Track P50/P95/P99 latency per agent.
Usage:
    python dev/jarvis_performance_tracker.py --track '{"agent":"M1","latency_ms":145,"success":true}'
    python dev/jarvis_performance_tracker.py --compare
    python dev/jarvis_performance_tracker.py --regression
    python dev/jarvis_performance_tracker.py --alert
    python dev/jarvis_performance_tracker.py --once
"""
import argparse, json, sqlite3, time, math, os
from datetime import datetime, timedelta
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "performance_tracker.db"

AGENTS = ["M1", "M2", "M3", "OL1"]
REGRESSION_THRESHOLD = 0.20  # 20%


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("""CREATE TABLE IF NOT EXISTS measurements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        agent TEXT NOT NULL,
        latency_ms REAL NOT NULL,
        success INTEGER DEFAULT 1,
        operation TEXT DEFAULT 'query',
        date TEXT NOT NULL,
        ts TEXT DEFAULT (datetime('now','localtime'))
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS daily_stats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        agent TEXT NOT NULL,
        date TEXT NOT NULL,
        p50 REAL,
        p95 REAL,
        p99 REAL,
        mean_ms REAL,
        min_ms REAL,
        max_ms REAL,
        count INTEGER,
        success_rate REAL,
        UNIQUE(agent, date)
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        agent TEXT,
        alert_type TEXT,
        message TEXT,
        severity TEXT DEFAULT 'warning',
        baseline_ms REAL,
        current_ms REAL,
        pct_change REAL,
        ts TEXT DEFAULT (datetime('now','localtime'))
    )""")
    db.execute("CREATE INDEX IF NOT EXISTS idx_meas_agent_date ON measurements(agent, date)")
    db.commit()
    return db


def _percentile(sorted_vals, pct):
    """Calculate percentile from sorted list."""
    if not sorted_vals:
        return 0
    k = (len(sorted_vals) - 1) * (pct / 100.0)
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    d = k - f
    return sorted_vals[f] + d * (sorted_vals[c] - sorted_vals[f])


def track_measurement(db, spec):
    """Record a latency measurement."""
    if isinstance(spec, str):
        spec = json.loads(spec)
    agent = spec.get("agent", "unknown")
    latency = spec.get("latency_ms", 0)
    success = 1 if spec.get("success", True) else 0
    operation = spec.get("operation", "query")
    today = datetime.now().strftime("%Y-%m-%d")

    db.execute(
        "INSERT INTO measurements (agent, latency_ms, success, operation, date) VALUES (?,?,?,?,?)",
        (agent, latency, success, operation, today)
    )
    db.commit()

    # Recalculate daily stats
    _update_daily_stats(db, agent, today)

    return {"recorded": True, "agent": agent, "latency_ms": latency, "date": today}


def _update_daily_stats(db, agent, date):
    """Recalculate daily stats for an agent."""
    rows = db.execute(
        "SELECT latency_ms, success FROM measurements WHERE agent=? AND date=?",
        (agent, date)
    ).fetchall()
    if not rows:
        return

    latencies = sorted([r[0] for r in rows])
    successes = sum(r[1] for r in rows)

    p50 = round(_percentile(latencies, 50), 2)
    p95 = round(_percentile(latencies, 95), 2)
    p99 = round(_percentile(latencies, 99), 2)
    mean_ms = round(sum(latencies) / len(latencies), 2)
    success_rate = round(successes / len(rows) * 100, 1)

    db.execute("""INSERT OR REPLACE INTO daily_stats
        (agent, date, p50, p95, p99, mean_ms, min_ms, max_ms, count, success_rate)
        VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (agent, date, p50, p95, p99, mean_ms, min(latencies), max(latencies), len(rows), success_rate)
    )
    db.commit()


def compare_agents(db):
    """Compare latest stats across agents."""
    today = datetime.now().strftime("%Y-%m-%d")
    rows = db.execute(
        "SELECT agent, p50, p95, p99, mean_ms, count, success_rate FROM daily_stats WHERE date=? ORDER BY p50",
        (today,)
    ).fetchall()

    if not rows:
        # Try yesterday
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        rows = db.execute(
            "SELECT agent, p50, p95, p99, mean_ms, count, success_rate FROM daily_stats WHERE date=? ORDER BY p50",
            (yesterday,)
        ).fetchall()

    comparison = []
    for r in rows:
        comparison.append({
            "agent": r[0], "p50_ms": r[1], "p95_ms": r[2], "p99_ms": r[3],
            "mean_ms": r[4], "requests": r[5], "success_rate": r[6]
        })

    return {"comparison": comparison, "date": today, "agents_tracked": len(comparison)}


def check_regression(db):
    """Check for performance regressions vs 7-day baseline."""
    today = datetime.now().strftime("%Y-%m-%d")
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    regressions = []

    for agent in AGENTS:
        # Current
        current = db.execute(
            "SELECT p50, p95, mean_ms FROM daily_stats WHERE agent=? AND date=?",
            (agent, today)
        ).fetchone()

        # 7-day baseline average
        baseline = db.execute(
            "SELECT AVG(p50), AVG(p95), AVG(mean_ms) FROM daily_stats WHERE agent=? AND date BETWEEN ? AND ? AND date!=?",
            (agent, week_ago, today, today)
        ).fetchone()

        if not current or not baseline or not baseline[0]:
            continue

        for metric, idx, label in [("p50", 0, "P50"), ("p95", 1, "P95"), ("mean", 2, "Mean")]:
            if current[idx] and baseline[idx] and baseline[idx] > 0:
                pct_change = (current[idx] - baseline[idx]) / baseline[idx]
                if pct_change > REGRESSION_THRESHOLD:
                    entry = {
                        "agent": agent,
                        "metric": label,
                        "baseline_ms": round(baseline[idx], 1),
                        "current_ms": round(current[idx], 1),
                        "pct_change": round(pct_change * 100, 1),
                        "severity": "critical" if pct_change > 0.5 else "warning"
                    }
                    regressions.append(entry)
                    db.execute(
                        "INSERT INTO alerts (agent, alert_type, message, severity, baseline_ms, current_ms, pct_change) VALUES (?,?,?,?,?,?,?)",
                        (agent, "regression", f"{label} regression: {entry['baseline_ms']}ms -> {entry['current_ms']}ms (+{entry['pct_change']}%)",
                         entry["severity"], baseline[idx], current[idx], round(pct_change * 100, 1))
                    )

    db.commit()
    return {
        "regressions": regressions,
        "checked_agents": len(AGENTS),
        "threshold": f"{REGRESSION_THRESHOLD*100}%",
        "status": "ALERT" if regressions else "OK"
    }


def get_alerts(db, limit=20):
    """Get recent alerts."""
    rows = db.execute(
        "SELECT agent, alert_type, message, severity, ts FROM alerts ORDER BY id DESC LIMIT ?",
        (limit,)
    ).fetchall()
    return {
        "alerts": [{"agent": r[0], "type": r[1], "message": r[2], "severity": r[3], "ts": r[4]} for r in rows],
        "total": db.execute("SELECT COUNT(*) FROM alerts").fetchone()[0]
    }


def do_status(db):
    total_measurements = db.execute("SELECT COUNT(*) FROM measurements").fetchone()[0]
    today = datetime.now().strftime("%Y-%m-%d")
    today_count = db.execute("SELECT COUNT(*) FROM measurements WHERE date=?", (today,)).fetchone()[0]
    agents_tracked = db.execute("SELECT COUNT(DISTINCT agent) FROM measurements").fetchone()[0]
    recent_alerts = db.execute("SELECT COUNT(*) FROM alerts WHERE DATE(ts)=?", (today,)).fetchone()[0]

    return {
        "script": "jarvis_performance_tracker.py",
        "id": 208,
        "db": str(DB_PATH),
        "total_measurements": total_measurements,
        "today_measurements": today_count,
        "agents_tracked": agents_tracked,
        "today_alerts": recent_alerts,
        "regression_threshold": f"{REGRESSION_THRESHOLD*100}%",
        "ts": datetime.now().isoformat()
    }


def main():
    parser = argparse.ArgumentParser(description="JARVIS Performance Tracker — P50/P95/P99 latency monitoring")
    parser.add_argument("--track", type=str, metavar="JSON", help="Record measurement")
    parser.add_argument("--compare", action="store_true", help="Compare agents today")
    parser.add_argument("--regression", action="store_true", help="Check for regressions")
    parser.add_argument("--alert", action="store_true", help="Show recent alerts")
    parser.add_argument("--once", action="store_true", help="Quick status")
    args = parser.parse_args()

    db = init_db()

    if args.track:
        result = track_measurement(db, args.track)
    elif args.compare:
        result = compare_agents(db)
    elif args.regression:
        result = check_regression(db)
    elif args.alert:
        result = get_alerts(db)
    else:
        result = do_status(db)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    db.close()


if __name__ == "__main__":
    main()
