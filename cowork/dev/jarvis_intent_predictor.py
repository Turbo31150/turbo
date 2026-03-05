#!/usr/bin/env python3
"""jarvis_intent_predictor.py — Intent predictor using Markov chains.
Analyzes command history patterns to predict top 3 next likely intents.
Usage: python dev/jarvis_intent_predictor.py --predict --once
"""
import argparse
import json
import math
import os
import random
import sqlite3
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "intent_predictor.db"


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS checks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL,
        action TEXT,
        report TEXT
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS command_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL,
        command TEXT,
        intent TEXT,
        context TEXT
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS transitions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        from_intent TEXT,
        to_intent TEXT,
        count INTEGER DEFAULT 1,
        UNIQUE(from_intent, to_intent)
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS predictions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL,
        last_intent TEXT,
        predicted TEXT,
        actual TEXT,
        correct INTEGER
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS training_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL,
        commands_processed INTEGER,
        transitions_learned INTEGER,
        accuracy REAL
    )""")
    db.commit()

    # Seed with sample command history if empty
    cur = db.execute("SELECT COUNT(*) FROM command_history")
    if cur.fetchone()[0] == 0:
        _seed_history(db)

    return db


def _seed_history(db):
    """Seed with realistic JARVIS command sequences."""
    sequences = [
        ["status_check", "cluster_health", "email_check", "trading_scan", "daily_briefing"],
        ["gpu_status", "thermal_check", "model_load", "code_generate", "test_run"],
        ["status_check", "email_check", "calendar_check", "task_list", "code_generate"],
        ["code_generate", "code_review", "test_run", "bug_fix", "code_generate", "deploy"],
        ["code_review", "bug_fix", "test_run", "deploy", "status_check"],
        ["file_search", "code_generate", "test_run", "code_review", "deploy"],
        ["trading_scan", "risk_check", "portfolio_status", "trading_signal", "trading_execute"],
        ["market_check", "trading_scan", "trading_signal", "risk_check", "trading_execute"],
        ["cluster_health", "gpu_status", "thermal_check", "model_swap", "benchmark"],
        ["disk_check", "cleanup", "backup", "status_check", "audit"],
        ["email_check", "report_generate", "backup", "status_check", "shutdown_prep"],
    ]

    now = time.time()
    for seq_idx, seq in enumerate(sequences):
        for i, intent in enumerate(seq):
            db.execute(
                "INSERT INTO command_history (ts, command, intent, context) VALUES (?,?,?,?)",
                (now - (len(sequences) - seq_idx) * 3600 + i * 60,
                 f"cmd_{intent}", intent, f"sequence_{seq_idx}")
            )
    db.commit()
    _rebuild_transitions(db)


def _rebuild_transitions(db):
    """Rebuild transition matrix from command history."""
    db.execute("DELETE FROM transitions")
    cur = db.execute("SELECT intent FROM command_history ORDER BY ts")
    intents = [r[0] for r in cur.fetchall()]

    trans = defaultdict(lambda: defaultdict(int))
    for i in range(len(intents) - 1):
        trans[intents[i]][intents[i + 1]] += 1

    for from_i, to_map in trans.items():
        for to_i, count in to_map.items():
            db.execute(
                "INSERT OR REPLACE INTO transitions (from_intent, to_intent, count) VALUES (?,?,?)",
                (from_i, to_i, count)
            )
    db.commit()


def do_predict():
    """Predict next likely intents based on Markov chain."""
    db = init_db()

    cur = db.execute("SELECT intent FROM command_history ORDER BY ts DESC LIMIT 1")
    row = cur.fetchone()
    last_intent = row[0] if row else "status_check"

    cur2 = db.execute(
        "SELECT to_intent, count FROM transitions WHERE from_intent=? ORDER BY count DESC",
        (last_intent,)
    )
    transitions = cur2.fetchall()
    total = sum(t[1] for t in transitions) if transitions else 1

    predictions = []
    for to_intent, count in transitions[:5]:
        prob = round(count / total, 4)
        predictions.append({
            "intent": to_intent,
            "probability": prob,
            "confidence": "high" if prob > 0.4 else "medium" if prob > 0.2 else "low",
            "occurrences": count
        })

    if not predictions:
        cur3 = db.execute(
            "SELECT intent, COUNT(*) as cnt FROM command_history GROUP BY intent ORDER BY cnt DESC LIMIT 3"
        )
        for intent, cnt in cur3.fetchall():
            predictions.append({
                "intent": intent,
                "probability": round(cnt / max(total, 1), 4),
                "confidence": "low",
                "occurrences": cnt
            })

    top3 = [p["intent"] for p in predictions[:3]]
    db.execute(
        "INSERT INTO predictions (ts, last_intent, predicted, correct) VALUES (?,?,?,?)",
        (time.time(), last_intent, json.dumps(top3), -1)
    )
    db.commit()

    result = {
        "ts": datetime.now().isoformat(),
        "action": "predict",
        "last_intent": last_intent,
        "top_predictions": predictions[:3],
        "all_candidates": len(transitions),
        "model": "markov_chain_order_1"
    }
    db.execute("INSERT INTO checks (ts, action, report) VALUES (?,?,?)",
               (time.time(), "predict", json.dumps({"last": last_intent, "top3": top3})))
    db.commit()
    db.close()
    return result


def do_history():
    """Show command history and patterns."""
    db = init_db()
    cur = db.execute(
        "SELECT ts, command, intent, context FROM command_history ORDER BY ts DESC LIMIT 30"
    )
    history = [
        {"ts": datetime.fromtimestamp(r[0]).isoformat(), "command": r[1],
         "intent": r[2], "context": r[3]}
        for r in cur.fetchall()
    ]

    cur2 = db.execute(
        "SELECT intent, COUNT(*) FROM command_history GROUP BY intent ORDER BY COUNT(*) DESC LIMIT 15"
    )
    frequency = {r[0]: r[1] for r in cur2.fetchall()}

    cur3 = db.execute(
        "SELECT from_intent, to_intent, count FROM transitions ORDER BY count DESC LIMIT 10"
    )
    top_transitions = [
        {"from": r[0], "to": r[1], "count": r[2]}
        for r in cur3.fetchall()
    ]

    result = {
        "ts": datetime.now().isoformat(),
        "action": "history",
        "total_commands": db.execute("SELECT COUNT(*) FROM command_history").fetchone()[0],
        "recent_commands": history[:10],
        "intent_frequency": frequency,
        "top_transitions": top_transitions
    }
    db.execute("INSERT INTO checks (ts, action, report) VALUES (?,?,?)",
               (time.time(), "history", json.dumps({"total": len(history)})))
    db.commit()
    db.close()
    return result


def do_accuracy():
    """Calculate prediction accuracy."""
    db = init_db()
    validated = db.execute("SELECT COUNT(*) FROM predictions WHERE correct >= 0").fetchone()[0]
    correct = db.execute("SELECT COUNT(*) FROM predictions WHERE correct = 1").fetchone()[0]
    total_preds = db.execute("SELECT COUNT(*) FROM predictions").fetchone()[0]
    accuracy = round(correct / validated, 4) if validated > 0 else 0.0

    total_trans = db.execute("SELECT COUNT(*) FROM transitions").fetchone()[0]
    unique_from = db.execute("SELECT COUNT(DISTINCT from_intent) FROM transitions").fetchone()[0]

    result = {
        "ts": datetime.now().isoformat(),
        "action": "accuracy",
        "total_predictions": total_preds,
        "validated_predictions": validated,
        "correct_predictions": correct,
        "accuracy": accuracy,
        "transition_matrix": {
            "total_transitions": total_trans,
            "unique_source_intents": unique_from
        }
    }
    db.execute("INSERT INTO checks (ts, action, report) VALUES (?,?,?)",
               (time.time(), "accuracy", json.dumps({"accuracy": accuracy})))
    db.commit()
    db.close()
    return result


def do_train():
    """Retrain the Markov chain from all command history."""
    db = init_db()
    start = time.time()

    before_count = db.execute("SELECT COUNT(*) FROM transitions").fetchone()[0]
    _rebuild_transitions(db)
    after_count = db.execute("SELECT COUNT(*) FROM transitions").fetchone()[0]
    total_cmds = db.execute("SELECT COUNT(*) FROM command_history").fetchone()[0]
    elapsed = round(time.time() - start, 3)

    cur = db.execute("SELECT from_intent, to_intent, count FROM transitions")
    from_totals = defaultdict(int)
    all_trans = []
    for r in cur.fetchall():
        from_totals[r[0]] += r[2]
        all_trans.append((r[0], r[1], r[2]))

    entropy = 0
    for from_i, to_i, count in all_trans:
        p = count / from_totals[from_i]
        if p > 0:
            entropy -= p * math.log2(p)
    avg_entropy = entropy / len(from_totals) if from_totals else 0

    db.execute(
        "INSERT INTO training_sessions (ts, commands_processed, transitions_learned, accuracy) VALUES (?,?,?,?)",
        (time.time(), total_cmds, after_count, 0)
    )
    db.commit()

    result = {
        "ts": datetime.now().isoformat(),
        "action": "train",
        "commands_processed": total_cmds,
        "transitions_before": before_count,
        "transitions_after": after_count,
        "avg_entropy": round(avg_entropy, 4),
        "training_time_sec": elapsed,
        "status": "retrained"
    }
    db.execute("INSERT INTO checks (ts, action, report) VALUES (?,?,?)",
               (time.time(), "train", json.dumps(result)))
    db.commit()
    db.close()
    return result


def main():
    parser = argparse.ArgumentParser(description="Intent predictor using Markov chains")
    parser.add_argument("--predict", action="store_true", help="Predict next likely intents")
    parser.add_argument("--history", action="store_true", help="Show command history")
    parser.add_argument("--accuracy", action="store_true", help="Show prediction accuracy")
    parser.add_argument("--train", action="store_true", help="Retrain Markov model")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    args = parser.parse_args()

    if args.predict:
        print(json.dumps(do_predict(), ensure_ascii=False, indent=2))
    elif args.history:
        print(json.dumps(do_history(), ensure_ascii=False, indent=2))
    elif args.accuracy:
        print(json.dumps(do_accuracy(), ensure_ascii=False, indent=2))
    elif args.train:
        print(json.dumps(do_train(), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(do_predict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
