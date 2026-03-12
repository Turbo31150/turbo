#!/usr/bin/env python3
"""task_learner.py — Apprend les patterns d'utilisation Telegram pour prédire les prochaines tâches.

CLI:
  --learn    Analyse l'historique des commandes Telegram et les stocke.
  --predict  Prédit la prochaine tâche selon l'heure/jour.
  --patterns Affiche les patterns fréquents.
  --stats    Statistiques de l'historique.

Toutes les sorties sont du JSON UTF‑8.
"""

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime

# Path to SQLite DB (ensure directory exists)
DB_PATH = os.path.join(os.path.dirname(__file__), "data", "learner.db")

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    # Table storing chaque commande observée
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS commands (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            command TEXT NOT NULL,
            ts TEXT NOT NULL,
            hour INTEGER NOT NULL,
            weekday INTEGER NOT NULL
        )
        """
    )
    conn.commit()
    return conn

def learn(conn):
    """Placeholder learning routine.
    In a real implementation this would parse Telegram logs.
    Here we simply insert a dummy record to prove the pipeline works.
    """
    now = datetime.now()
    cmd = "example_command"
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO commands (command, ts, hour, weekday) VALUES (?,?,?,?)",
        (cmd, now.isoformat(), now.hour, now.weekday()),
    )
    conn.commit()
    return {"status": "learned", "command": cmd, "timestamp": now.isoformat()}

def predict(conn):
    """Predict the most frequent command for the current hour/week day.
    Simple majority vote on matching hour and weekday.
    """
    now = datetime.now()
    cur = conn.cursor()
    cur.execute(
        "SELECT command, COUNT(*) as cnt FROM commands WHERE hour=? AND weekday=? GROUP BY command ORDER BY cnt DESC LIMIT 1",
        (now.hour, now.weekday()),
    )
    row = cur.fetchone()
    if row:
        command, count = row
        confidence = float(count) / max(1, _total_for_time(conn, now.hour, now.weekday()))
        return {"prediction": command, "confidence": round(confidence, 2), "hour": now.hour, "weekday": now.weekday()}
    else:
        return {"prediction": None, "confidence": 0, "hour": now.hour, "weekday": now.weekday()}

def _total_for_time(conn, hour, weekday):
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM commands WHERE hour=? AND weekday=?",
        (hour, weekday),
    )
    return cur.fetchone()[0]

def patterns(conn):
    cur = conn.cursor()
    cur.execute(
        "SELECT command, COUNT(*) as cnt FROM commands GROUP BY command ORDER BY cnt DESC"
    )
    rows = cur.fetchall()
    return [{"command": cmd, "count": cnt} for cmd, cnt in rows]

def stats(conn):
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM commands")
    total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(DISTINCT command) FROM commands")
    distinct = cur.fetchone()[0]
    # commands per hour (average)
    cur.execute("SELECT hour, COUNT(*) FROM commands GROUP BY hour")
    per_hour = {hour: cnt for hour, cnt in cur.fetchall()}
    return {"total_commands": total, "distinct_commands": distinct, "commands_per_hour": per_hour}

def main():
    parser = argparse.ArgumentParser(description="Apprend les patterns d'utilisation Telegram pour prédire les prochaines tâches.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--learn", action="store_true", help="Analyser l'historique et stocker les commandes.")
    group.add_argument("--predict", action="store_true", help="Prédire la prochaine tâche.")
    group.add_argument("--patterns", action="store_true", help="Afficher les patterns fréquents.")
    group.add_argument("--stats", action="store_true", help="Afficher des statistiques de l'historique.")
    args = parser.parse_args()

    conn = init_db()
    if args.learn:
        result = learn(conn)
    elif args.predict:
        result = predict(conn)
    elif args.patterns:
        result = patterns(conn)
    elif args.stats:
        result = stats(conn)
    else:
        result = {"error": "No action specified"}

    print(json.dumps(result, ensure_ascii=False, indent=2))
    conn.close()

if __name__ == "__main__":
    main()
