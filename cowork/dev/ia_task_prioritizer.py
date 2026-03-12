#!/usr/bin/env python3
"""ia_task_prioritizer.py — Prioriseur de taches IA.

Ordonne les taches COWORK par impact/urgence/effort.

Usage:
    python dev/ia_task_prioritizer.py --once
    python dev/ia_task_prioritizer.py --prioritize
    python dev/ia_task_prioritizer.py --queue
    python dev/ia_task_prioritizer.py --stats
"""
import argparse
import json
import os
import re
import sqlite3
import time
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "task_prioritizer.db"
QUEUE_PATH = DEV.parent / "COWORK_QUEUE.md"

# Impact scoring keywords
IMPACT_KEYWORDS = {
    "autonome": 9, "auto": 8, "security": 9, "health": 8,
    "monitor": 7, "optimize": 7, "cluster": 8, "voice": 7,
    "trading": 6, "browser": 6, "predict": 8, "benchmark": 5,
    "cleanup": 4, "report": 3, "log": 3, "cache": 5,
}

URGENCY_KEYWORDS = {
    "guard": 9, "alert": 9, "critical": 10, "health": 8,
    "security": 9, "monitor": 7, "real-time": 8, "watch": 7,
    "daily": 5, "weekly": 3, "monthly": 2, "recurring": 6,
}


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS priorities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, script_name TEXT, impact REAL,
        urgency REAL, effort_inv REAL, score REAL,
        quadrant TEXT)""")
    db.execute("""CREATE TABLE IF NOT EXISTS runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, pending_count INTEGER, prioritized_count INTEGER)""")
    db.commit()
    return db


def parse_pending_tasks():
    """Parse COWORK_QUEUE.md for PENDING tasks."""
    tasks = []
    if not QUEUE_PATH.exists():
        return tasks

    content = QUEUE_PATH.read_text(encoding="utf-8", errors="ignore")

    # Find script sections
    current_num = None
    current_name = None
    current_desc = ""

    for line in content.split("\n"):
        # Match "### 99. win_registry_guard.py"
        m = re.match(r'### (\d+)\.\s+(\S+\.py)', line)
        if m:
            current_num = int(m.group(1))
            current_name = m.group(2)
            current_desc = ""
            continue

        if current_name and line.startswith("- **Fonction**:"):
            current_desc = line.split(":", 1)[1].strip()

        # Check if PENDING in table
        if current_name:
            if f"| {current_num} |" in line and "PENDING" in line:
                tasks.append({
                    "num": current_num,
                    "name": current_name,
                    "description": current_desc[:200],
                })

    return tasks


def score_task(task):
    """Score a task by impact, urgency, and inverse effort."""
    text = (task["name"] + " " + task["description"]).lower()

    # Impact (0-10)
    impact = 3  # Base
    for kw, score in IMPACT_KEYWORDS.items():
        if kw in text:
            impact = max(impact, score)

    # Urgency (0-10)
    urgency = 3
    for kw, score in URGENCY_KEYWORDS.items():
        if kw in text:
            urgency = max(urgency, score)

    # Effort inverse (simpler = higher score)
    # Estimate by name complexity
    name_len = len(task["name"].replace(".py", "").replace("_", ""))
    effort_inv = max(1, 10 - name_len // 3)

    # Composite score
    score = impact * 0.4 + urgency * 0.4 + effort_inv * 0.2

    # Eisenhower quadrant
    if impact >= 7 and urgency >= 7:
        quadrant = "DO_FIRST"
    elif impact >= 7:
        quadrant = "SCHEDULE"
    elif urgency >= 7:
        quadrant = "DELEGATE"
    else:
        quadrant = "CONSIDER"

    return {
        **task,
        "impact": impact,
        "urgency": urgency,
        "effort_inv": effort_inv,
        "score": round(score, 2),
        "quadrant": quadrant,
    }


def do_prioritize():
    """Prioritize all pending tasks."""
    db = init_db()
    tasks = parse_pending_tasks()
    scored = [score_task(t) for t in tasks]
    scored.sort(key=lambda x: x["score"], reverse=True)

    for s in scored:
        db.execute(
            "INSERT INTO priorities (ts, script_name, impact, urgency, effort_inv, score, quadrant) VALUES (?,?,?,?,?,?,?)",
            (time.time(), s["name"], s["impact"], s["urgency"],
             s["effort_inv"], s["score"], s["quadrant"])
        )

    db.execute(
        "INSERT INTO runs (ts, pending_count, prioritized_count) VALUES (?,?,?)",
        (time.time(), len(tasks), len(scored))
    )
    db.commit()
    db.close()

    # Group by quadrant
    by_quadrant = {}
    for s in scored:
        q = s["quadrant"]
        if q not in by_quadrant:
            by_quadrant[q] = []
        by_quadrant[q].append({"name": s["name"], "score": s["score"]})

    return {
        "ts": datetime.now().isoformat(),
        "total_pending": len(tasks),
        "prioritized": len(scored),
        "quadrants": {q: len(items) for q, items in by_quadrant.items()},
        "top_priority": [{"name": s["name"], "score": s["score"], "quadrant": s["quadrant"]} for s in scored[:15]],
        "by_quadrant": by_quadrant,
    }


def main():
    parser = argparse.ArgumentParser(description="IA Task Prioritizer")
    parser.add_argument("--once", "--prioritize", action="store_true", help="Prioritize tasks")
    parser.add_argument("--queue", action="store_true", help="Show queue")
    parser.add_argument("--reorder", action="store_true", help="Reorder queue")
    parser.add_argument("--stats", action="store_true", help="Stats")
    args = parser.parse_args()

    result = do_prioritize()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
