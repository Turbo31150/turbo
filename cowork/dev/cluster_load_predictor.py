#!/usr/bin/env python3
"""cluster_load_predictor.py — Prediction de charge cluster.

Analyse historique, detecte patterns horaires, predit charge,
recommande pre-chargement modeles.

Usage:
    python dev/cluster_load_predictor.py --once
    python dev/cluster_load_predictor.py --predict
    python dev/cluster_load_predictor.py --history
    python dev/cluster_load_predictor.py --alerts
"""
import argparse
import json
import os
import sqlite3
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
from _paths import ETOILE_DB
DB_PATH = DEV / "data" / "load_predictor.db"


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS predictions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, hour INTEGER, predicted_load TEXT,
        recommendations TEXT)""")
    db.execute("""CREATE TABLE IF NOT EXISTS load_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, hour INTEGER, weekday INTEGER,
        request_count INTEGER, avg_latency REAL)""")
    db.commit()
    return db


def get_historical_load():
    """Get request history from etoile.db."""
    if not ETOILE_DB.exists():
        return []
    try:
        conn = sqlite3.connect(str(ETOILE_DB))
        has_table = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='tool_metrics'"
        ).fetchone()[0]
        if not has_table:
            conn.close()
            return []
        rows = conn.execute("""
            SELECT CAST(strftime('%H', timestamp, 'unixepoch', 'localtime') AS INTEGER) as hour,
                   COUNT(*) as cnt,
                   AVG(CASE WHEN latency_ms > 0 THEN latency_ms ELSE NULL END) as avg_lat
            FROM tool_metrics
            WHERE timestamp > ?
            GROUP BY hour ORDER BY hour
        """, (time.time() - 7 * 86400,)).fetchall()
        conn.close()
        return [{"hour": r[0], "count": r[1], "avg_latency": r[2]} for r in rows]
    except Exception:
        return []


def predict_load():
    """Predict load for next hours."""
    history = get_historical_load()
    if not history:
        return {"predictions": [], "message": "No historical data"}

    hourly_avg = defaultdict(list)
    for h in history:
        hourly_avg[h["hour"]].append(h["count"])

    now = datetime.now()
    predictions = []
    for offset in range(1, 7):
        target_hour = (now.hour + offset) % 24
        counts = hourly_avg.get(target_hour, [0])
        avg_load = sum(counts) / max(len(counts), 1)
        predictions.append({
            "hour": target_hour,
            "offset_hours": offset,
            "predicted_requests": round(avg_load, 1),
            "load_level": "high" if avg_load > 50 else ("medium" if avg_load > 20 else "low"),
        })

    return predictions


def generate_recommendations(predictions):
    """Generate model pre-loading recommendations."""
    recs = []
    for pred in predictions:
        if pred["load_level"] == "high":
            recs.append({
                "hour": pred["hour"],
                "action": "pre-load qwen3-8b + deepseek-r1-0528-qwen3-8b",
                "reason": f"High load expected ({pred['predicted_requests']} requests)",
            })
        elif pred["load_level"] == "low" and pred["hour"] in range(1, 6):
            recs.append({
                "hour": pred["hour"],
                "action": "unload unused models, run maintenance",
                "reason": "Low load period — good for maintenance",
            })
    return recs


def do_predict():
    """Full prediction cycle."""
    db = init_db()
    predictions = predict_load()
    recs = generate_recommendations(predictions) if isinstance(predictions, list) else []

    report = {
        "ts": datetime.now().isoformat(),
        "predictions": predictions if isinstance(predictions, list) else [],
        "recommendations": recs,
    }

    now = datetime.now()
    db.execute(
        "INSERT INTO predictions (ts, hour, predicted_load, recommendations) VALUES (?,?,?,?)",
        (time.time(), now.hour, json.dumps(predictions), json.dumps(recs))
    )
    db.commit()
    db.close()
    return report


def main():
    parser = argparse.ArgumentParser(description="Cluster Load Predictor")
    parser.add_argument("--once", "--predict", action="store_true", help="Predict load")
    parser.add_argument("--history", action="store_true", help="Historical data")
    parser.add_argument("--alerts", action="store_true", help="High load alerts")
    args = parser.parse_args()

    result = do_predict()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
