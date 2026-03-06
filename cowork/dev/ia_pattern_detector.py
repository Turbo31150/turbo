#!/usr/bin/env python3
"""ia_pattern_detector.py — Detecte les patterns d'utilisation JARVIS.

Analyse etoile.db (user_patterns, queries), clustering temporel,
prediction prochaine commande, suggestions automatisation.

Usage:
    python dev/ia_pattern_detector.py --once
    python dev/ia_pattern_detector.py --detect
    python dev/ia_pattern_detector.py --predict
    python dev/ia_pattern_detector.py --report
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
from _paths import ETOILE_DB
from _paths import JARVIS_DB
DB_PATH = DEV / "data" / "pattern_detector.db"


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS detections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, patterns_found INTEGER, sequences_found INTEGER,
        predictions TEXT, report TEXT)""")
    db.commit()
    return db


def get_user_patterns():
    """Get user_patterns from etoile.db."""
    if not ETOILE_DB.exists():
        return []
    try:
        conn = sqlite3.connect(str(ETOILE_DB))
        has_table = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='user_patterns'"
        ).fetchone()[0]
        if not has_table:
            conn.close()
            return []
        rows = conn.execute(
            "SELECT action, hour, weekday, context, timestamp FROM user_patterns ORDER BY timestamp DESC LIMIT 1000"
        ).fetchall()
        conn.close()
        return [{"action": r[0], "hour": r[1], "weekday": r[2],
                 "context": r[3], "ts": r[4]} for r in rows]
    except Exception:
        return []


def detect_temporal_patterns(patterns):
    """Detect patterns by hour and weekday."""
    hourly = defaultdict(Counter)
    daily = defaultdict(Counter)

    for p in patterns:
        action = p["action"]
        if p["hour"] is not None:
            hourly[p["hour"]][action] += 1
        if p["weekday"] is not None:
            daily[p["weekday"]][action] += 1

    temporal = []
    for hour in sorted(hourly.keys()):
        top = hourly[hour].most_common(3)
        if top and top[0][1] >= 2:
            temporal.append({
                "type": "hourly",
                "hour": hour,
                "top_actions": [{"action": a, "count": c} for a, c in top],
                "total": sum(hourly[hour].values()),
            })

    days = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
    for wd in sorted(daily.keys()):
        top = daily[wd].most_common(3)
        if top and top[0][1] >= 2:
            temporal.append({
                "type": "daily",
                "weekday": wd,
                "day_name": days[wd] if wd < len(days) else str(wd),
                "top_actions": [{"action": a, "count": c} for a, c in top],
            })

    return temporal


def detect_sequences(patterns, min_sequence=2):
    """Detect repeated action sequences."""
    if len(patterns) < min_sequence:
        return []

    # Sort by timestamp
    sorted_p = sorted(patterns, key=lambda x: x.get("ts", 0))
    actions = [p["action"] for p in sorted_p]

    # Find 2-grams and 3-grams
    sequences = Counter()
    for i in range(len(actions) - 1):
        seq2 = f"{actions[i]} → {actions[i+1]}"
        sequences[seq2] += 1
        if i < len(actions) - 2:
            seq3 = f"{actions[i]} → {actions[i+1]} → {actions[i+2]}"
            sequences[seq3] += 1

    return [{"sequence": seq, "count": cnt}
            for seq, cnt in sequences.most_common(10) if cnt >= min_sequence]


def predict_next(patterns):
    """Predict next likely actions based on current time."""
    now = datetime.now()
    hour = now.hour
    weekday = now.weekday()

    # Score actions by temporal proximity
    scores = Counter()
    for p in patterns:
        action = p["action"]
        weight = 1.0
        if p["hour"] == hour:
            weight += 3.0
        elif p["hour"] is not None and abs(p["hour"] - hour) <= 1:
            weight += 1.0
        if p["weekday"] == weekday:
            weight += 2.0
        scores[action] += weight

    total = sum(scores.values())
    predictions = []
    for action, score in scores.most_common(5):
        predictions.append({
            "action": action,
            "score": round(score, 2),
            "confidence": round(score / max(total, 1), 3),
        })

    return predictions


def do_detect():
    """Full pattern detection cycle."""
    db = init_db()
    patterns = get_user_patterns()

    temporal = detect_temporal_patterns(patterns)
    sequences = detect_sequences(patterns)
    predictions = predict_next(patterns)

    report = {
        "ts": datetime.now().isoformat(),
        "total_patterns": len(patterns),
        "temporal_patterns": temporal[:15],
        "sequences": sequences[:10],
        "predictions": predictions,
    }

    db.execute(
        "INSERT INTO detections (ts, patterns_found, sequences_found, predictions, report) VALUES (?,?,?,?,?)",
        (time.time(), len(temporal), len(sequences), json.dumps(predictions), json.dumps(report))
    )
    db.commit()
    db.close()
    return report


def main():
    parser = argparse.ArgumentParser(description="IA Pattern Detector — Find usage patterns")
    parser.add_argument("--once", "--detect", action="store_true", help="Full detection")
    parser.add_argument("--predict", action="store_true", help="Predict next actions")
    parser.add_argument("--report", action="store_true", help="History")
    args = parser.parse_args()

    if args.predict:
        patterns = get_user_patterns()
        result = predict_next(patterns)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        result = do_detect()
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
