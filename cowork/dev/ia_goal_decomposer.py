#!/usr/bin/env python3
"""ia_goal_decomposer.py — Decomposeur de buts IA.

Prend un objectif haut-niveau, cree plan d'actions atomiques.

Usage:
    python dev/ia_goal_decomposer.py --once
    python dev/ia_goal_decomposer.py --decompose "GOAL"
    python dev/ia_goal_decomposer.py --plan
    python dev/ia_goal_decomposer.py --status
"""
import argparse
import json
import os
import sqlite3
import time
import urllib.request
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "goal_decomposer.db"
M1_URL = "http://127.0.0.1:1234/api/v1/chat"


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS goals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, goal TEXT, steps_json TEXT,
        total_steps INTEGER, status TEXT DEFAULT 'planned')""")
    db.execute("""CREATE TABLE IF NOT EXISTS steps (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        goal_id INTEGER, step_num INTEGER, description TEXT,
        estimated_min INTEGER, status TEXT DEFAULT 'pending',
        result TEXT)""")
    db.commit()
    return db


def query_m1(prompt, timeout=30):
    """Query M1 for decomposition."""
    try:
        data = json.dumps({
            "model": "qwen3-8b", "input": f"/nothink\n{prompt}",
            "temperature": 0.2, "max_output_tokens": 1024, "stream": False, "store": False,
        }).encode()
        req = urllib.request.Request(M1_URL, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            result = json.loads(r.read().decode())
            for item in reversed(result.get("output", [])):
                if item.get("type") == "message":
                    for c in item.get("content", []):
                        if c.get("type") == "output_text":
                            return c.get("text", "")
    except Exception:
        pass
    return ""


def decompose_goal(goal):
    """Decompose a goal into atomic steps via M1."""
    prompt = f"""Decompose cet objectif en etapes atomiques executables.
Retourne UNIQUEMENT un JSON array avec chaque etape:
[{{"step": 1, "description": "...", "estimated_minutes": N, "dependencies": []}}]

Objectif: {goal}

Regles:
- Maximum 10 etapes
- Chaque etape doit etre executee en <30 minutes
- Inclure les verifications et tests
- Ordonner par dependances"""

    response = query_m1(prompt)

    # Try to extract JSON
    steps = []
    if response:
        try:
            # Find JSON array in response
            start = response.find("[")
            end = response.rfind("]") + 1
            if start >= 0 and end > start:
                steps = json.loads(response[start:end])
        except json.JSONDecodeError:
            pass

    # Fallback: simple decomposition
    if not steps:
        words = goal.split()
        steps = [
            {"step": 1, "description": f"Analyser: {goal}", "estimated_minutes": 10, "dependencies": []},
            {"step": 2, "description": f"Planifier l'implementation", "estimated_minutes": 15, "dependencies": [1]},
            {"step": 3, "description": f"Executer: {goal}", "estimated_minutes": 30, "dependencies": [2]},
            {"step": 4, "description": "Verifier le resultat", "estimated_minutes": 10, "dependencies": [3]},
        ]

    return steps


def do_decompose(goal):
    """Full decomposition."""
    db = init_db()
    steps = decompose_goal(goal)

    # Store goal
    db.execute(
        "INSERT INTO goals (ts, goal, steps_json, total_steps) VALUES (?,?,?,?)",
        (time.time(), goal[:500], json.dumps(steps), len(steps))
    )
    goal_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

    # Store steps
    for s in steps:
        db.execute(
            "INSERT INTO steps (goal_id, step_num, description, estimated_min) VALUES (?,?,?,?)",
            (goal_id, s.get("step", 0), s.get("description", "")[:200],
             s.get("estimated_minutes", 15))
        )

    total_time = sum(s.get("estimated_minutes", 15) for s in steps)

    db.commit()
    db.close()

    return {
        "ts": datetime.now().isoformat(),
        "goal": goal[:100],
        "total_steps": len(steps),
        "estimated_total_min": total_time,
        "steps": steps,
    }


def show_plans():
    """Show recent plans."""
    db = init_db()
    rows = db.execute(
        "SELECT id, ts, goal, total_steps, status FROM goals ORDER BY ts DESC LIMIT 10"
    ).fetchall()
    db.close()
    return [{
        "id": r[0], "ts": datetime.fromtimestamp(r[1]).isoformat(),
        "goal": r[2][:60], "steps": r[3], "status": r[4],
    } for r in rows]


def main():
    parser = argparse.ArgumentParser(description="IA Goal Decomposer")
    parser.add_argument("--once", action="store_true", help="Demo decomposition")
    parser.add_argument("--decompose", metavar="GOAL", help="Decompose a goal")
    parser.add_argument("--plan", action="store_true", help="Show plans")
    parser.add_argument("--status", action="store_true", help="Status")
    args = parser.parse_args()

    if args.decompose:
        result = do_decompose(args.decompose)
    elif args.plan or args.status:
        result = show_plans()
    else:
        result = do_decompose("Optimiser les performances du cluster JARVIS")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
