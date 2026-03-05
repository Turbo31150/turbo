#!/usr/bin/env python3
"""jarvis_pattern_learner.py — Apprentissage de patterns JARVIS.

Detecte et apprend les habitudes utilisateur.

Usage:
    python dev/jarvis_pattern_learner.py --once
    python dev/jarvis_pattern_learner.py --learn
    python dev/jarvis_pattern_learner.py --patterns
    python dev/jarvis_pattern_learner.py --predict
"""
import argparse
import json
import os
import sqlite3
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "pattern_learner.db"
ETOILE_DB = Path("F:/BUREAU/turbo/data/etoile.db")


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS patterns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, pattern_type TEXT, description TEXT,
        frequency INTEGER, confidence REAL)""")
    db.commit()
    return db


def collect_history():
    actions = []
    if not ETOILE_DB.exists():
        return actions
    try:
        db = sqlite3.connect(str(ETOILE_DB))
        for t in [t[0] for t in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]:
            cols = [c[1] for c in db.execute(f"PRAGMA table_info([{t}])").fetchall()]
            if "ts" in cols:
                action_col = next((c for c in cols if c in ("action", "command", "tool", "node")), None)
                if action_col:
                    try:
                        for r in db.execute(f"SELECT ts, [{action_col}] FROM [{t}] WHERE ts > ? ORDER BY ts", (time.time() - 604800,)).fetchall():
                            if r[1]:
                                hour = datetime.fromtimestamp(r[0]).hour if r[0] > 1000000000 else 0
                                weekday = datetime.fromtimestamp(r[0]).weekday() if r[0] > 1000000000 else 0
                                actions.append({"ts": r[0], "action": r[1], "hour": hour, "weekday": weekday})
                    except Exception:
                        pass
        db.close()
    except Exception:
        pass
    return actions


def detect_patterns(actions):
    patterns = []
    if not actions:
        return patterns

    # Hourly patterns
    by_hour = defaultdict(Counter)
    for a in actions:
        by_hour[a["hour"]][a["action"]] += 1

    for hour, counter in sorted(by_hour.items()):
        top = counter.most_common(3)
        for action, count in top:
            if count >= 3:
                patterns.append({
                    "type": "hourly",
                    "description": f"At {hour:02d}h, '{action}' done {count}x this week",
                    "hour": hour,
                    "action": action,
                    "frequency": count,
                    "confidence": min(count / 7, 0.95),
                })

    # Day-of-week patterns
    by_day = defaultdict(Counter)
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    for a in actions:
        by_day[a["weekday"]][a["action"]] += 1

    for day, counter in sorted(by_day.items()):
        top = counter.most_common(2)
        for action, count in top:
            if count >= 3:
                patterns.append({
                    "type": "weekly",
                    "description": f"On {days[day]}, '{action}' done {count}x",
                    "day": days[day],
                    "action": action,
                    "frequency": count,
                    "confidence": min(count / 4, 0.9),
                })

    # Sequence patterns (A -> B)
    sorted_actions = sorted(actions, key=lambda x: x["ts"])
    sequences = Counter()
    for i in range(len(sorted_actions) - 1):
        a, b = sorted_actions[i]["action"], sorted_actions[i + 1]["action"]
        if a != b:
            sequences[(a, b)] += 1

    for (a, b), count in sequences.most_common(5):
        if count >= 3:
            patterns.append({
                "type": "sequence",
                "description": f"'{a}' often followed by '{b}' ({count}x)",
                "from": a, "to": b,
                "frequency": count,
                "confidence": min(count / 5, 0.85),
            })

    return patterns


def do_learn():
    db = init_db()
    actions = collect_history()
    patterns = detect_patterns(actions)

    for p in patterns:
        db.execute("INSERT INTO patterns (ts, pattern_type, description, frequency, confidence) VALUES (?,?,?,?,?)",
                   (time.time(), p["type"], p["description"], p["frequency"], p["confidence"]))
    db.commit()
    db.close()

    return {
        "ts": datetime.now().isoformat(),
        "actions_analyzed": len(actions),
        "patterns_found": len(patterns),
        "by_type": {
            "hourly": sum(1 for p in patterns if p["type"] == "hourly"),
            "weekly": sum(1 for p in patterns if p["type"] == "weekly"),
            "sequence": sum(1 for p in patterns if p["type"] == "sequence"),
        },
        "top_patterns": sorted(patterns, key=lambda x: x["confidence"], reverse=True)[:10],
    }


def main():
    parser = argparse.ArgumentParser(description="JARVIS Pattern Learner")
    parser.add_argument("--once", "--learn", action="store_true", help="Learn patterns")
    parser.add_argument("--patterns", action="store_true", help="Show patterns")
    parser.add_argument("--predict", action="store_true", help="Predict next")
    parser.add_argument("--report", action="store_true", help="Report")
    args = parser.parse_args()
    print(json.dumps(do_learn(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
