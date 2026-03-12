#!/usr/bin/env python3
"""jarvis_command_predictor.py — Predicteur de commandes JARVIS.

Anticipe la prochaine commande via modele Markov.

Usage:
    python dev/jarvis_command_predictor.py --once
    python dev/jarvis_command_predictor.py --predict
    python dev/jarvis_command_predictor.py --history
    python dev/jarvis_command_predictor.py --accuracy
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
DB_PATH = DEV / "data" / "command_predictor.db"
from _paths import ETOILE_DB


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS predictions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, context TEXT, predicted TEXT,
        confidence REAL, actual TEXT)""")
    db.execute("""CREATE TABLE IF NOT EXISTS transitions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        from_cmd TEXT, to_cmd TEXT, count INTEGER,
        UNIQUE(from_cmd, to_cmd))""")
    db.commit()
    return db


def build_transition_matrix():
    transitions = defaultdict(Counter)
    if not ETOILE_DB.exists():
        return transitions
    try:
        db = sqlite3.connect(str(ETOILE_DB))
        for t in [t[0] for t in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]:
            cols = [c[1] for c in db.execute(f"PRAGMA table_info([{t}])").fetchall()]
            cmd_col = next((c for c in cols if c in ("action", "command", "tool")), None)
            if cmd_col and "ts" in cols:
                try:
                    rows = db.execute(f"SELECT [{cmd_col}] FROM [{t}] WHERE [{cmd_col}] IS NOT NULL ORDER BY ts").fetchall()
                    for i in range(len(rows) - 1):
                        a, b = rows[i][0], rows[i + 1][0]
                        if a and b:
                            transitions[a][b] += 1
                except Exception:
                    pass
        db.close()
    except Exception:
        pass
    return transitions


def predict_next(last_command=None, n=3):
    transitions = build_transition_matrix()

    if last_command and last_command in transitions:
        candidates = transitions[last_command].most_common(n)
        total = sum(c for _, c in candidates)
        return [
            {"command": cmd, "count": count, "confidence": round(count / max(total, 1), 3)}
            for cmd, count in candidates
        ]

    # Fallback: most common overall commands
    all_cmds = Counter()
    for frm, tos in transitions.items():
        for to, cnt in tos.items():
            all_cmds[to] += cnt
    return [
        {"command": cmd, "count": count, "confidence": round(count / max(sum(all_cmds.values()), 1), 3)}
        for cmd, count in all_cmds.most_common(n)
    ]


def do_predict():
    db = init_db()
    transitions = build_transition_matrix()

    # Store transitions
    for frm, tos in transitions.items():
        for to, cnt in tos.items():
            db.execute("INSERT OR REPLACE INTO transitions (from_cmd, to_cmd, count) VALUES (?,?,?)",
                       (frm, to, cnt))

    predictions = predict_next()
    total_transitions = sum(sum(v.values()) for v in transitions.values())
    unique_cmds = set()
    for frm, tos in transitions.items():
        unique_cmds.add(frm)
        unique_cmds.update(tos.keys())

    db.commit()
    db.close()

    return {
        "ts": datetime.now().isoformat(),
        "total_transitions": total_transitions,
        "unique_commands": len(unique_cmds),
        "top_predictions": predictions,
        "matrix_size": len(transitions),
    }


def main():
    parser = argparse.ArgumentParser(description="JARVIS Command Predictor")
    parser.add_argument("--once", "--predict", action="store_true", help="Predict")
    parser.add_argument("--history", action="store_true", help="History")
    parser.add_argument("--accuracy", action="store_true", help="Accuracy")
    parser.add_argument("--train", action="store_true", help="Train model")
    args = parser.parse_args()
    print(json.dumps(do_predict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
