#!/usr/bin/env python3
"""ia_task_planner.py — Planificateur de taches IA autonome.

Decompose un objectif en sous-taches via le cluster,
les ordonne et les execute sequentiellement.

Usage:
    python dev/ia_task_planner.py --once
    python dev/ia_task_planner.py --plan "Ameliorer la latence du cluster"
    python dev/ia_task_planner.py --execute
    python dev/ia_task_planner.py --status
    python dev/ia_task_planner.py --history
"""
import argparse
import json
import os
import sqlite3
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "task_planner.db"
M1_URL = "http://127.0.0.1:1234/api/v1/chat"
OL1_URL = "http://127.0.0.1:11434/api/chat"


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS goals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, goal TEXT, plan TEXT,
        status TEXT DEFAULT 'pending', result TEXT)""")
    db.execute("""CREATE TABLE IF NOT EXISTS steps (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        goal_id INTEGER, step_num INTEGER, description TEXT,
        command TEXT, status TEXT DEFAULT 'pending', output TEXT,
        FOREIGN KEY(goal_id) REFERENCES goals(id))""")
    db.commit()
    return db


def query_m1(prompt, timeout=30):
    """Query M1 for plan generation."""
    try:
        data = json.dumps({
            "model": "qwen3-8b",
            "input": f"/nothink\n{prompt}",
            "temperature": 0.3, "max_output_tokens": 1024,
            "stream": False, "store": False,
        }).encode()
        req = urllib.request.Request(M1_URL, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            result = json.loads(r.read().decode())
            for item in reversed(result.get("output", [])):
                if item.get("type") == "message":
                    for c in item.get("content", []):
                        if c.get("type") == "output_text":
                            return c.get("text", "")
            return ""
    except Exception:
        pass
    # Fallback OL1
    try:
        data = json.dumps({
            "model": "qwen3:1.7b",
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
        }).encode()
        req = urllib.request.Request(OL1_URL, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode()).get("message", {}).get("content", "")
    except Exception:
        return ""


def create_plan(goal):
    """Generate a plan for a goal using the cluster."""
    prompt = f"""Tu es un planificateur de taches pour JARVIS (assistant IA Windows).
Objectif: {goal}

Genere un plan d'action en JSON avec exactement ce format:
{{"steps": [{{"num": 1, "description": "...", "command": "python dev/SCRIPT.py --once"}}]}}

Les commandes doivent etre des scripts Python existants dans dev/ ou des commandes systeme simples.
Maximum 5 etapes. Reponds UNIQUEMENT en JSON."""

    response = query_m1(prompt)
    if not response:
        return None

    try:
        start = response.find("{")
        end = response.rfind("}") + 1
        if start >= 0 and end > start:
            plan = json.loads(response[start:end])
            return plan.get("steps", [])
    except Exception:
        pass
    return None


def do_plan(goal):
    """Create and store a plan."""
    db = init_db()
    steps = create_plan(goal)

    if not steps:
        db.close()
        return {"error": "Failed to generate plan"}

    cursor = db.execute(
        "INSERT INTO goals (ts, goal, plan, status) VALUES (?,?,?,?)",
        (time.time(), goal, json.dumps(steps), "planned")
    )
    goal_id = cursor.lastrowid

    for step in steps:
        db.execute(
            "INSERT INTO steps (goal_id, step_num, description, command) VALUES (?,?,?,?)",
            (goal_id, step.get("num", 0), step.get("description", ""), step.get("command", ""))
        )

    db.commit()
    db.close()
    return {"goal_id": goal_id, "goal": goal, "steps": steps}


def do_execute():
    """Execute pending goals."""
    db = init_db()
    goals = db.execute("SELECT id, goal FROM goals WHERE status='planned' LIMIT 1").fetchall()

    if not goals:
        db.close()
        return {"message": "No pending goals"}

    goal_id, goal = goals[0]
    db.execute("UPDATE goals SET status='running' WHERE id=?", (goal_id,))
    db.commit()

    steps = db.execute(
        "SELECT id, step_num, description, command FROM steps WHERE goal_id=? ORDER BY step_num",
        (goal_id,)
    ).fetchall()

    results = []
    all_ok = True
    for step_id, num, desc, command in steps:
        if not command:
            continue
        try:
            proc = subprocess.run(
                command, shell=True,
                capture_output=True, text=True, timeout=60,
                cwd=str(DEV.parent)
            )
            ok = proc.returncode == 0
            output = (proc.stdout + proc.stderr)[:500]
        except Exception as e:
            ok = False
            output = str(e)

        db.execute(
            "UPDATE steps SET status=?, output=? WHERE id=?",
            ("done" if ok else "failed", output, step_id)
        )
        results.append({"step": num, "desc": desc, "ok": ok, "output": output[:200]})
        if not ok:
            all_ok = False
            break

    db.execute(
        "UPDATE goals SET status=?, result=? WHERE id=?",
        ("completed" if all_ok else "failed", json.dumps(results), goal_id)
    )
    db.commit()
    db.close()
    return {"goal_id": goal_id, "goal": goal, "success": all_ok, "steps": results}


def get_status():
    """Get current goals status."""
    db = init_db()
    goals = db.execute("SELECT id, goal, status, ts FROM goals ORDER BY ts DESC LIMIT 10").fetchall()
    db.close()
    return [{"id": g[0], "goal": g[1], "status": g[2],
             "ts": datetime.fromtimestamp(g[3]).isoformat() if g[3] else None} for g in goals]


def main():
    parser = argparse.ArgumentParser(description="IA Task Planner — Autonomous goal decomposition")
    parser.add_argument("--once", action="store_true", help="Execute pending goals")
    parser.add_argument("--plan", metavar="GOAL", help="Create a plan for goal")
    parser.add_argument("--execute", action="store_true", help="Execute pending plans")
    parser.add_argument("--status", action="store_true", help="Show goals status")
    parser.add_argument("--history", action="store_true", help="Show history")
    args = parser.parse_args()

    if args.plan:
        result = do_plan(args.plan)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.execute or args.once:
        result = do_execute()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.status or args.history:
        result = get_status()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        result = get_status()
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
