#!/usr/bin/env python3
"""ia_swarm_coordinator.py — Coordinateur essaim IA.

Distribue une tache complexe en sous-taches paralleles.

Usage:
    python dev/ia_swarm_coordinator.py --once
    python dev/ia_swarm_coordinator.py --dispatch "TASK"
    python dev/ia_swarm_coordinator.py --status
    python dev/ia_swarm_coordinator.py --results
"""
import argparse
import json
import os
import sqlite3
import subprocess
import time
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "swarm_coordinator.db"
AGENTS = {
    "M1": {"url": "http://127.0.0.1:1234/api/v1/chat", "type": "lmstudio", "weight": 1.8},
    "OL1": {"url": "http://127.0.0.1:11434/api/chat", "type": "ollama", "weight": 1.3},
}


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS swarm_tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, task TEXT, subtasks INTEGER,
        completed INTEGER, quality REAL)""")
    db.commit()
    return db


def decompose_task(task):
    aspects = []
    keywords = {
        "code": ["code", "function", "implement", "class", "algorithm"],
        "design": ["design", "architecture", "pattern", "structure"],
        "test": ["test", "verify", "validate", "check"],
        "doc": ["document", "explain", "describe", "readme"],
    }
    task_lower = task.lower()
    for aspect, kws in keywords.items():
        if any(kw in task_lower for kw in kws):
            aspects.append(aspect)
    if not aspects:
        aspects = ["analysis", "solution", "review"]
    return [f"{aspect}: {task}" for aspect in aspects]


def query_agent(name, config, prompt):
    try:
        if config["type"] == "lmstudio":
            body = json.dumps({
                "model": "qwen3-8b", "input": f"/nothink\n{prompt}",
                "temperature": 0.3, "max_output_tokens": 512,
                "stream": False, "store": False,
            })
        else:
            body = json.dumps({
                "model": "qwen3:1.7b",
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
            })

        out = subprocess.run(
            ["curl", "-s", "--max-time", "30", config["url"],
             "-H", "Content-Type: application/json", "-d", body],
            capture_output=True, text=True, timeout=35
        )
        if out.stdout.strip():
            data = json.loads(out.stdout)
            if config["type"] == "lmstudio":
                for item in reversed(data.get("output", [])):
                    if item.get("type") == "message":
                        for c in item.get("content", []):
                            if c.get("type") == "output_text":
                                return c.get("text", "")
            else:
                return data.get("message", {}).get("content", "")
    except Exception:
        pass
    return ""


def do_dispatch(task=None):
    db = init_db()
    if not task:
        task = "Analyze the COWORK system and suggest improvements"

    subtasks = decompose_task(task)
    results = []
    agents = list(AGENTS.items())

    for i, sub in enumerate(subtasks):
        agent_name, agent_config = agents[i % len(agents)]
        response = query_agent(agent_name, agent_config, sub)
        results.append({
            "subtask": sub[:80],
            "agent": agent_name,
            "response_length": len(response),
            "has_response": bool(response.strip()),
        })

    completed = sum(1 for r in results if r["has_response"])

    db.execute("INSERT INTO swarm_tasks (ts, task, subtasks, completed, quality) VALUES (?,?,?,?,?)",
               (time.time(), task[:200], len(subtasks), completed,
                completed / max(len(subtasks), 1)))
    db.commit()
    db.close()

    return {
        "ts": datetime.now().isoformat(),
        "task": task[:100],
        "subtasks": len(subtasks),
        "completed": completed,
        "success_rate": round(completed / max(len(subtasks), 1), 2),
        "results": results,
    }


def main():
    parser = argparse.ArgumentParser(description="IA Swarm Coordinator")
    parser.add_argument("--once", "--status", action="store_true", help="Status")
    parser.add_argument("--dispatch", metavar="TASK", help="Dispatch task")
    parser.add_argument("--results", action="store_true", help="Results")
    parser.add_argument("--optimize", action="store_true", help="Optimize")
    args = parser.parse_args()

    if args.dispatch:
        print(json.dumps(do_dispatch(args.dispatch), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(do_dispatch(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
