#!/usr/bin/env python3
"""ia_usage_predictor.py — Predit l'utilisation future du cluster.

Patterns horaires, pics de charge, recommandations pre-chargement.

Usage:
    python dev/ia_usage_predictor.py --once
    python dev/ia_usage_predictor.py --predict
    python dev/ia_usage_predictor.py --patterns
    python dev/ia_usage_predictor.py --report
"""
import argparse
import json
import math
import os
import sqlite3
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "usage_predictor.db"
from _paths import ETOILE_DB


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS predictions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, hour INTEGER, weekday INTEGER,
        predicted_load REAL, recommended_models TEXT)""")
    db.execute("""CREATE TABLE IF NOT EXISTS hourly_stats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, hour INTEGER, weekday INTEGER,
        request_count INTEGER, avg_latency REAL)""")
    db.commit()
    return db


def load_usage_history():
    """Load usage history from etoile.db."""
    hourly = defaultdict(lambda: {"count": 0, "total_latency": 0})

    if ETOILE_DB.exists():
        try:
            db = sqlite3.connect(str(ETOILE_DB))
            tables = [t[0] for t in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]

            if "tool_metrics" in tables:
                rows = db.execute(
                    "SELECT ts, latency_ms FROM tool_metrics WHERE ts > ?",
                    (time.time() - 86400 * 14,)
                ).fetchall()
                for r in rows:
                    if r[0]:
                        dt = datetime.fromtimestamp(r[0])
                        key = (dt.hour, dt.weekday())
                        hourly[key]["count"] += 1
                        hourly[key]["total_latency"] += (r[1] or 0)

            db.close()
        except Exception:
            pass

    return hourly


def predict_next_hours(hourly, n=6):
    """Predict load for next N hours."""
    predictions = []
    now = datetime.now()

    for offset in range(n):
        future_hour = (now.hour + offset) % 24
        weekday = (now.weekday() + (now.hour + offset) // 24) % 7
        key = (future_hour, weekday)

        stats = hourly.get(key, {"count": 0, "total_latency": 0})
        load = stats["count"]
        avg_lat = stats["total_latency"] / max(stats["count"], 1)

        # Determine recommended models
        if load > 20:
            models = ["qwen3-8b", "deepseek-r1-0528-qwen3-8b", "qwen3:1.7b"]
            level = "high"
        elif load > 5:
            models = ["qwen3-8b", "qwen3:14b"]
            level = "medium"
        else:
            models = ["qwen3:1.7b"]
            level = "low"

        predictions.append({
            "hour": future_hour, "weekday": weekday,
            "predicted_requests": load,
            "avg_latency_ms": round(avg_lat, 1),
            "load_level": level,
            "recommended_models": models,
        })

    return predictions


def analyze_patterns(hourly):
    """Analyze usage patterns."""
    # Peak hours
    by_hour = defaultdict(int)
    by_weekday = defaultdict(int)

    for (hour, weekday), stats in hourly.items():
        by_hour[hour] += stats["count"]
        by_weekday[weekday] += stats["count"]

    peak_hours = sorted(by_hour.items(), key=lambda x: x[1], reverse=True)[:5]
    peak_days = sorted(by_weekday.items(), key=lambda x: x[1], reverse=True)

    day_names = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]

    return {
        "peak_hours": [{"hour": h, "requests": c} for h, c in peak_hours],
        "busiest_days": [{"day": day_names[d], "requests": c} for d, c in peak_days[:3]],
        "total_data_points": sum(s["count"] for s in hourly.values()),
    }


def do_predict():
    """Run prediction."""
    db = init_db()
    hourly = load_usage_history()
    predictions = predict_next_hours(hourly)
    patterns = analyze_patterns(hourly)

    for pred in predictions:
        db.execute(
            "INSERT INTO predictions (ts, hour, weekday, predicted_load, recommended_models) VALUES (?,?,?,?,?)",
            (time.time(), pred["hour"], pred["weekday"],
             pred["predicted_requests"], json.dumps(pred["recommended_models"]))
        )

    db.commit()
    db.close()

    return {
        "ts": datetime.now().isoformat(),
        "predictions_next_6h": predictions,
        "patterns": patterns,
    }


def main():
    parser = argparse.ArgumentParser(description="IA Usage Predictor")
    parser.add_argument("--once", "--predict", action="store_true", help="Predict usage")
    parser.add_argument("--patterns", action="store_true", help="Show patterns")
    parser.add_argument("--report", action="store_true", help="Report")
    args = parser.parse_args()

    result = do_predict()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
