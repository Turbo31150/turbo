#!/usr/bin/env python3
"""jarvis_cron_optimizer.py — Optimiseur crons JARVIS.

Detecte conflits horaires, redistribue la charge.

Usage:
    python dev/jarvis_cron_optimizer.py --once
    python dev/jarvis_cron_optimizer.py --analyze
    python dev/jarvis_cron_optimizer.py --conflicts
    python dev/jarvis_cron_optimizer.py --optimize
"""
import argparse
import json
import os
import re
import sqlite3
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "cron_optimizer.db"
QUEUE_FILE = DEV.parent / "COWORK_QUEUE.md"


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS analyses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, total_crons INTEGER, conflicts INTEGER,
        peak_hour INTEGER, report TEXT)""")
    db.commit()
    return db


def parse_crons():
    crons = []
    if not QUEUE_FILE.exists():
        return crons
    content = QUEUE_FILE.read_text(encoding="utf-8", errors="replace")
    # Parse cron lines like "- **Cron**: daily 01:00" or "recurring 10min"
    current_script = None
    for line in content.split("\n"):
        m = re.match(r"### (\d+)\.\s+(\S+)", line)
        if m:
            current_script = {"num": int(m.group(1)), "name": m.group(2)}
        if "**Cron**" in line and current_script:
            cron_spec = line.split("**Cron**:")[-1].strip()
            crons.append({
                "script": current_script["name"],
                "num": current_script["num"],
                "cron": cron_spec,
            })
    return crons


def analyze_schedule(crons):
    hourly_load = Counter()
    conflicts = []
    by_time = defaultdict(list)

    for c in crons:
        spec = c["cron"].lower()
        if "on-demand" in spec:
            continue

        # Extract hour
        hour = None
        m = re.search(r"(\d{1,2}):(\d{2})", spec)
        if m:
            hour = int(m.group(1))
        elif "daily" in spec and not m:
            hour = 0
        elif "recurring" in spec:
            # Spread across hours
            for h in range(0, 24, 4):
                hourly_load[h] += 1
            continue

        if hour is not None:
            hourly_load[hour] += 1
            by_time[hour].append(c["script"])

    # Detect conflicts (>3 at same hour)
    for hour, scripts in by_time.items():
        if len(scripts) > 3:
            conflicts.append({
                "hour": f"{hour:02d}:00",
                "scripts": scripts,
                "count": len(scripts),
                "severity": "high" if len(scripts) > 5 else "medium",
            })

    peak = hourly_load.most_common(1)
    return {
        "hourly_distribution": dict(sorted(hourly_load.items())),
        "conflicts": conflicts,
        "peak_hour": peak[0][0] if peak else 0,
        "peak_load": peak[0][1] if peak else 0,
    }


def do_analyze():
    db = init_db()
    crons = parse_crons()
    analysis = analyze_schedule(crons)

    recommendations = []
    for c in analysis["conflicts"]:
        recommendations.append(f"Hour {c['hour']}: {c['count']} scripts — consider spreading")

    report = {
        "ts": datetime.now().isoformat(),
        "total_crons": len(crons),
        "scheduled": sum(1 for c in crons if "on-demand" not in c["cron"].lower()),
        "on_demand": sum(1 for c in crons if "on-demand" in c["cron"].lower()),
        "analysis": analysis,
        "recommendations": recommendations,
    }

    db.execute("INSERT INTO analyses (ts, total_crons, conflicts, peak_hour, report) VALUES (?,?,?,?,?)",
               (time.time(), len(crons), len(analysis["conflicts"]),
                analysis["peak_hour"], json.dumps(report)))
    db.commit()
    db.close()
    return report


def main():
    parser = argparse.ArgumentParser(description="JARVIS Cron Optimizer")
    parser.add_argument("--once", "--analyze", action="store_true", help="Analyze crons")
    parser.add_argument("--conflicts", action="store_true", help="Show conflicts")
    parser.add_argument("--spread", action="store_true", help="Spread load")
    parser.add_argument("--optimize", action="store_true", help="Optimize")
    args = parser.parse_args()
    print(json.dumps(do_analyze(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
