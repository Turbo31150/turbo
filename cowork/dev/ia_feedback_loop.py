#!/usr/bin/env python3
"""ia_feedback_loop.py — Boucle feedback IA.

Collecte resultats, ajuste poids cluster, ameliore routing.

Usage:
    python dev/ia_feedback_loop.py --once
    python dev/ia_feedback_loop.py --collect
    python dev/ia_feedback_loop.py --analyze
    python dev/ia_feedback_loop.py --adjust
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
DB_PATH = DEV / "data" / "feedback_loop.db"
ETOILE_DB = Path("F:/BUREAU/turbo/data/etoile.db")

# Current MAO weights
CURRENT_WEIGHTS = {
    "M1": 1.8, "M2": 1.5,
    "M2": 1.4, "OL1": 1.3, "glm-4.7": 1.2,
    "GEMINI": 1.2, "CLAUDE": 1.2, "M3": 1.0,
}


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, agent TEXT, success_rate REAL,
        avg_latency REAL, total_calls INTEGER,
        current_weight REAL, suggested_weight REAL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS adjustments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, agent TEXT, old_weight REAL,
        new_weight REAL, reason TEXT)""")
    db.commit()
    return db


def collect_agent_stats():
    """Collect success/fail stats per agent from etoile.db."""
    stats = defaultdict(lambda: {"ok": 0, "fail": 0, "total_latency": 0})

    if not ETOILE_DB.exists():
        return stats

    try:
        db = sqlite3.connect(str(ETOILE_DB))
        tables = [t[0] for t in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]

        if "tool_metrics" in tables:
            rows = db.execute(
                "SELECT node, status, latency_ms FROM tool_metrics WHERE ts > ?",
                (time.time() - 86400 * 7,)
            ).fetchall()
            for r in rows:
                node = r[0] or "unknown"
                if r[1] == "ok":
                    stats[node]["ok"] += 1
                else:
                    stats[node]["fail"] += 1
                stats[node]["total_latency"] += (r[2] or 0)

        db.close()
    except Exception:
        pass

    return stats


def calculate_adjustments(stats):
    """Calculate weight adjustments based on performance."""
    adjustments = []

    for agent, weight in CURRENT_WEIGHTS.items():
        # Find matching stats
        agent_stats = None
        for key, val in stats.items():
            if agent.lower() in key.lower() or key.lower() in agent.lower():
                agent_stats = val
                break

        if not agent_stats:
            continue

        total = agent_stats["ok"] + agent_stats["fail"]
        if total < 5:
            continue

        success_rate = agent_stats["ok"] / total
        avg_latency = agent_stats["total_latency"] / total

        # Scoring: success_rate * 0.7 + speed_score * 0.3
        speed_score = max(0, 1 - (avg_latency / 10000))  # Normalize to 0-1 (10s = 0)
        performance = success_rate * 0.7 + speed_score * 0.3

        # Calculate suggested weight (bounded regression toward performance)
        suggested = weight * 0.8 + performance * 2.0 * 0.2
        suggested = max(0.5, min(2.0, round(suggested, 2)))

        delta = abs(suggested - weight)
        reason = ""
        if success_rate < 0.7:
            reason = f"low_success_rate:{success_rate:.0%}"
        elif avg_latency > 5000:
            reason = f"high_latency:{avg_latency:.0f}ms"
        elif delta > 0.1:
            reason = f"performance_adjusted"

        adjustments.append({
            "agent": agent,
            "current_weight": weight,
            "suggested_weight": suggested,
            "success_rate": round(success_rate, 3),
            "avg_latency_ms": round(avg_latency, 1),
            "total_calls": total,
            "delta": round(suggested - weight, 2),
            "reason": reason,
        })

    return adjustments


def do_feedback():
    """Run full feedback loop."""
    db = init_db()
    stats = collect_agent_stats()
    adjustments = calculate_adjustments(stats)

    for adj in adjustments:
        db.execute(
            "INSERT INTO feedback (ts, agent, success_rate, avg_latency, total_calls, current_weight, suggested_weight) VALUES (?,?,?,?,?,?,?)",
            (time.time(), adj["agent"], adj["success_rate"], adj["avg_latency_ms"],
             adj["total_calls"], adj["current_weight"], adj["suggested_weight"])
        )
        if abs(adj["delta"]) > 0.1:
            db.execute(
                "INSERT INTO adjustments (ts, agent, old_weight, new_weight, reason) VALUES (?,?,?,?,?)",
                (time.time(), adj["agent"], adj["current_weight"], adj["suggested_weight"], adj["reason"])
            )

    db.commit()
    db.close()

    significant = [a for a in adjustments if abs(a["delta"]) > 0.1]

    return {
        "ts": datetime.now().isoformat(),
        "agents_analyzed": len(adjustments),
        "significant_adjustments": len(significant),
        "adjustments": adjustments,
    }


def main():
    parser = argparse.ArgumentParser(description="IA Feedback Loop")
    parser.add_argument("--once", "--collect", action="store_true", help="Collect and analyze")
    parser.add_argument("--analyze", action="store_true", help="Analyze stats")
    parser.add_argument("--adjust", action="store_true", help="Show adjustments")
    parser.add_argument("--report", action="store_true", help="Report")
    args = parser.parse_args()

    result = do_feedback()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
