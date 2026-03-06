#!/usr/bin/env python3
"""JARVIS Brain — Context-aware memory and reasoning engine.

Maintains conversation context, learns user patterns, predicts needs,
and provides intelligent suggestions based on historical data.
"""
import argparse
import json
import sqlite3
import time
import hashlib
from pathlib import Path

DB_PATH = Path(__file__).parent / "brain.db"
from _paths import TURBO_DIR as TURBO

def init_db():
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS context (
        id INTEGER PRIMARY KEY, ts REAL, category TEXT, key TEXT UNIQUE,
        value TEXT, confidence REAL DEFAULT 1.0, access_count INTEGER DEFAULT 0,
        last_accessed REAL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS patterns (
        id INTEGER PRIMARY KEY, ts REAL, pattern_type TEXT, description TEXT,
        frequency INTEGER DEFAULT 1, last_seen REAL, data TEXT)""")
    db.execute("""CREATE TABLE IF NOT EXISTS predictions (
        id INTEGER PRIMARY KEY, ts REAL, prediction TEXT, basis TEXT,
        confidence REAL, verified INTEGER DEFAULT 0, correct INTEGER DEFAULT 0)""")
    db.execute("""CREATE TABLE IF NOT EXISTS sessions (
        id INTEGER PRIMARY KEY, start_ts REAL, end_ts REAL,
        commands_count INTEGER, topics TEXT, mood TEXT)""")
    db.commit()
    return db

def learn_from_history(db):
    """Analyze etoile.db and jarvis.db for patterns."""
    patterns_found = 0
    # Analyze etoile.db for usage patterns
    edb_path = TURBO / "data" / "etoile.db"
    if edb_path.exists():
        try:
            edb = sqlite3.connect(str(edb_path))
            # Get most used commands
            try:
                rows = edb.execute(
                    "SELECT name, COUNT(*) as cnt FROM command_history GROUP BY name ORDER BY cnt DESC LIMIT 20"
                ).fetchall()
                for name, cnt in rows:
                    db.execute(
                        "INSERT OR REPLACE INTO patterns (ts, pattern_type, description, frequency, last_seen, data) VALUES (?,?,?,?,?,?)",
                        (time.time(), "command_usage", f"Commande frequente: {name}", cnt, time.time(), json.dumps({"command": name, "count": cnt})))
                    patterns_found += 1
            except sqlite3.OperationalError:
                pass
            # Get active hours
            try:
                rows = edb.execute(
                    "SELECT strftime('%H', datetime(timestamp, 'unixepoch')) as hour, COUNT(*) FROM command_history GROUP BY hour ORDER BY COUNT(*) DESC LIMIT 5"
                ).fetchall()
                for hour, cnt in rows:
                    db.execute(
                        "INSERT OR REPLACE INTO context (ts, category, key, value, confidence, last_accessed) VALUES (?,?,?,?,?,?)",
                        (time.time(), "user_schedule", f"active_hour_{hour}", str(cnt), min(1.0, cnt/50), time.time()))
            except sqlite3.OperationalError:
                pass
            edb.close()
        except Exception as e:
            print(f"  etoile.db: {e}")

    # Analyze jarvis.db for conversation patterns
    jdb_path = TURBO / "data" / "jarvis.db"
    if jdb_path.exists():
        try:
            jdb = sqlite3.connect(str(jdb_path))
            try:
                rows = jdb.execute(
                    "SELECT COUNT(*) FROM conversations WHERE timestamp > ?",
                    (time.time() - 86400,)).fetchone()
                if rows:
                    db.execute(
                        "INSERT OR REPLACE INTO context (ts, category, key, value, confidence, last_accessed) VALUES (?,?,?,?,?,?)",
                        (time.time(), "activity", "conversations_24h", str(rows[0]), 1.0, time.time()))
            except sqlite3.OperationalError:
                pass
            jdb.close()
        except Exception:
            pass
    db.commit()
    return patterns_found

def predict_next_actions(db):
    """Based on patterns, predict what user might need."""
    predictions = []
    now = time.time()
    hour = int(time.strftime('%H'))

    # Morning predictions (6-9)
    if 6 <= hour <= 9:
        predictions.append(("Rapport matinal cluster + trading", "morning_routine", 0.8))
        predictions.append(("Check emails et Telegram", "morning_routine", 0.7))
    # Work hours (9-18)
    elif 9 <= hour <= 18:
        predictions.append(("Session code intensive — precharger M1 et M2", "work_pattern", 0.6))
    # Evening (18-23)
    elif 18 <= hour <= 23:
        predictions.append(("Backup quotidien et rapport", "evening_routine", 0.5))

    # Check if cluster needs attention
    patterns = db.execute(
        "SELECT description, frequency FROM patterns WHERE pattern_type='cluster_issue' AND last_seen > ? ORDER BY frequency DESC LIMIT 3",
        (now - 3600,)).fetchall()
    for desc, freq in patterns:
        predictions.append((f"Cluster attention: {desc}", "cluster_pattern", min(0.9, freq/10)))

    for pred, basis, conf in predictions:
        db.execute("INSERT INTO predictions (ts, prediction, basis, confidence) VALUES (?,?,?,?)",
                   (now, pred, basis, conf))
    db.commit()
    return predictions

def store_context(db, category, key, value, confidence=1.0):
    """Store a context fact."""
    db.execute(
        "INSERT OR REPLACE INTO context (ts, category, key, value, confidence, last_accessed) VALUES (?,?,?,?,?,?)",
        (time.time(), category, key, str(value), confidence, time.time()))
    db.commit()

def get_context_summary(db):
    """Get a summary of current context."""
    categories = db.execute(
        "SELECT category, COUNT(*), AVG(confidence) FROM context GROUP BY category"
    ).fetchall()
    patterns = db.execute("SELECT COUNT(*) FROM patterns").fetchone()[0]
    predictions = db.execute(
        "SELECT COUNT(*) FROM predictions WHERE ts > ?", (time.time() - 3600,)
    ).fetchone()[0]
    return {
        "categories": {c: {"count": n, "avg_confidence": round(a, 2)} for c, n, a in categories},
        "total_patterns": patterns,
        "recent_predictions": predictions,
    }

def main():
    parser = argparse.ArgumentParser(description="JARVIS Brain — Context & Reasoning")
    parser.add_argument("--learn", action="store_true", help="Learn from databases")
    parser.add_argument("--predict", action="store_true", help="Generate predictions")
    parser.add_argument("--summary", action="store_true", help="Context summary")
    parser.add_argument("--store", nargs=3, metavar=("CAT", "KEY", "VALUE"), help="Store context")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--interval", type=int, default=1800)
    args = parser.parse_args()

    db = init_db()

    if args.store:
        store_context(db, *args.store)
        print(f"Stored: {args.store[0]}/{args.store[1]} = {args.store[2]}")
        return

    if args.summary or args.once:
        summary = get_context_summary(db)
        print("=== JARVIS Brain Summary ===")
        for cat, info in summary["categories"].items():
            print(f"  [{cat}] {info['count']} facts (confidence {info['avg_confidence']})")
        print(f"  Patterns: {summary['total_patterns']}")
        print(f"  Recent predictions: {summary['recent_predictions']}")

    if args.learn or args.once:
        n = learn_from_history(db)
        print(f"Learned {n} patterns from databases")

    if args.predict or args.once:
        preds = predict_next_actions(db)
        if preds:
            print("\n=== Predictions ===")
            for pred, basis, conf in preds:
                print(f"  [{conf:.0%}] {pred} (basis: {basis})")

    if args.loop:
        while True:
            try:
                learn_from_history(db)
                preds = predict_next_actions(db)
                ts = time.strftime('%H:%M')
                print(f"[{ts}] Brain: {len(preds)} predictions")
                time.sleep(args.interval)
            except KeyboardInterrupt:
                break

if __name__ == "__main__":
    main()
