#!/usr/bin/env python3
"""prediction_trainer.py — Entraine et maintient le prediction_engine JARVIS.

Analyse les patterns historiques dans etoile.db, nettoie les vieux records,
genere un rapport de prediction accuracy, et injecte des patterns manquants.

Usage:
    python dev/prediction_trainer.py --once
    python dev/prediction_trainer.py --train
    python dev/prediction_trainer.py --report
    python dev/prediction_trainer.py --cleanup --days 90
    python dev/prediction_trainer.py --inject-history
"""
import argparse
import json
import os
import sqlite3
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
from _paths import ETOILE_DB
from _paths import JARVIS_DB
DB_PATH = DEV / "data" / "prediction_trainer.db"


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS training_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, patterns_before INTEGER, patterns_after INTEGER,
        injected INTEGER, cleaned INTEGER, accuracy REAL, report TEXT)""")
    db.commit()
    return db


def count_patterns():
    """Count current patterns in etoile.db."""
    try:
        conn = sqlite3.connect(str(ETOILE_DB))
        count = conn.execute("SELECT COUNT(*) FROM user_patterns").fetchone()[0]
        conn.close()
        return count
    except Exception:
        return 0


def inject_from_voice_history():
    """Inject historical voice command data into user_patterns."""
    if not JARVIS_DB.exists():
        return 0

    injected = 0
    try:
        jarvis = sqlite3.connect(str(JARVIS_DB))
        jarvis.row_factory = sqlite3.Row
        etoile = sqlite3.connect(str(ETOILE_DB))

        # Get voice corrections with high confidence (successful matches)
        rows = jarvis.execute("""
            SELECT corrected_text, confidence, timestamp
            FROM voice_corrections
            WHERE confidence >= 0.7 AND corrected_text IS NOT NULL
            ORDER BY timestamp DESC LIMIT 500
        """).fetchall()

        for row in rows:
            ts = row["timestamp"] if row["timestamp"] else time.time()
            dt = datetime.fromtimestamp(ts)
            action = row["corrected_text"]
            if not action:
                continue

            # Check if already exists
            existing = etoile.execute(
                "SELECT COUNT(*) FROM user_patterns WHERE action=? AND timestamp=?",
                (action, ts)
            ).fetchone()[0]

            if existing == 0:
                etoile.execute(
                    "INSERT INTO user_patterns (action, hour, weekday, context, timestamp) VALUES (?,?,?,?,?)",
                    (action, dt.hour, dt.weekday(),
                     json.dumps({"source": "voice_history", "confidence": row["confidence"]}), ts)
                )
                injected += 1

        etoile.commit()
        etoile.close()
        jarvis.close()
    except Exception as e:
        print(f"[WARN] inject_from_voice_history: {e}")
    return injected


def inject_from_mcp_logs():
    """Inject MCP tool usage patterns."""
    injected = 0
    try:
        etoile = sqlite3.connect(str(ETOILE_DB))

        # Check if tool_metrics table exists
        has_metrics = etoile.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='tool_metrics'"
        ).fetchone()[0]

        if has_metrics:
            rows = etoile.execute("""
                SELECT tool_name, COUNT(*) as cnt, MAX(timestamp) as last_ts
                FROM tool_metrics
                GROUP BY tool_name
                HAVING cnt >= 3
                ORDER BY cnt DESC LIMIT 50
            """).fetchall()

            for row in rows:
                ts = row[2] if row[2] else time.time()
                dt = datetime.fromtimestamp(ts)
                existing = etoile.execute(
                    "SELECT COUNT(*) FROM user_patterns WHERE action=? AND ABS(timestamp-?)<60",
                    (f"mcp:{row[0]}", ts)
                ).fetchone()[0]
                if existing == 0:
                    etoile.execute(
                        "INSERT INTO user_patterns (action, hour, weekday, context, timestamp) VALUES (?,?,?,?,?)",
                        (f"mcp:{row[0]}", dt.hour, dt.weekday(),
                         json.dumps({"source": "mcp_logs", "count": row[1]}), ts)
                    )
                    injected += 1

            etoile.commit()
        etoile.close()
    except Exception as e:
        print(f"[WARN] inject_from_mcp_logs: {e}")
    return injected


def cleanup_old_patterns(max_days=90):
    """Remove patterns older than max_days."""
    cutoff = time.time() - (max_days * 86400)
    try:
        conn = sqlite3.connect(str(ETOILE_DB))
        cursor = conn.execute("DELETE FROM user_patterns WHERE timestamp < ?", (cutoff,))
        cleaned = cursor.rowcount
        conn.commit()
        conn.close()
        return cleaned
    except Exception:
        return 0


def analyze_accuracy():
    """Analyze prediction accuracy based on actual patterns."""
    try:
        conn = sqlite3.connect(str(ETOILE_DB))
        conn.row_factory = sqlite3.Row

        # Get patterns grouped by hour
        hours = conn.execute("""
            SELECT hour, COUNT(DISTINCT action) as unique_actions, COUNT(*) as total
            FROM user_patterns
            GROUP BY hour ORDER BY total DESC
        """).fetchall()

        # Calculate entropy-based predictability
        total_records = conn.execute("SELECT COUNT(*) FROM user_patterns").fetchone()[0]
        if total_records == 0:
            conn.close()
            return {"accuracy": 0, "total": 0, "message": "No data"}

        # For each hour, check if top action is >50% of actions (predictable)
        predictable_hours = 0
        for h in hours:
            top = conn.execute("""
                SELECT action, COUNT(*) as cnt FROM user_patterns
                WHERE hour = ? GROUP BY action ORDER BY cnt DESC LIMIT 1
            """, (h["hour"],)).fetchone()
            if top and h["total"] > 0 and top["cnt"] / h["total"] > 0.3:
                predictable_hours += 1

        accuracy = predictable_hours / max(len(hours), 1)
        conn.close()

        return {
            "accuracy": round(accuracy, 3),
            "total_patterns": total_records,
            "active_hours": len(hours),
            "predictable_hours": predictable_hours,
            "top_hours": [{"hour": h["hour"], "actions": h["unique_actions"], "total": h["total"]} for h in hours[:5]],
        }
    except Exception as e:
        return {"error": str(e)}


def do_train():
    """Full training cycle."""
    db = init_db()
    before = count_patterns()

    # Inject from various sources
    voice_injected = inject_from_voice_history()
    mcp_injected = inject_from_mcp_logs()
    total_injected = voice_injected + mcp_injected

    after = count_patterns()
    accuracy = analyze_accuracy()

    report = {
        "ts": datetime.now().isoformat(),
        "patterns_before": before,
        "patterns_after": after,
        "injected": {"voice": voice_injected, "mcp": mcp_injected, "total": total_injected},
        "accuracy": accuracy,
    }

    db.execute(
        "INSERT INTO training_runs (ts, patterns_before, patterns_after, injected, cleaned, accuracy, report) VALUES (?,?,?,?,?,?,?)",
        (time.time(), before, after, total_injected, 0, accuracy.get("accuracy", 0), json.dumps(report))
    )
    db.commit()
    db.close()
    return report


def main():
    parser = argparse.ArgumentParser(description="Prediction Engine Trainer")
    parser.add_argument("--once", "--train", action="store_true", help="Run training cycle")
    parser.add_argument("--report", action="store_true", help="Accuracy report")
    parser.add_argument("--cleanup", action="store_true", help="Cleanup old patterns")
    parser.add_argument("--days", type=int, default=90, help="Max age for cleanup")
    parser.add_argument("--inject-history", action="store_true", help="Inject from voice/MCP history")
    args = parser.parse_args()

    if args.report:
        result = analyze_accuracy()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.cleanup:
        cleaned = cleanup_old_patterns(args.days)
        print(json.dumps({"cleaned": cleaned, "max_days": args.days}))
    elif args.inject_history:
        voice = inject_from_voice_history()
        mcp = inject_from_mcp_logs()
        print(json.dumps({"voice_injected": voice, "mcp_injected": mcp}))
    else:
        result = do_train()
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
