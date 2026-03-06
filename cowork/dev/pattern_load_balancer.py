#!/usr/bin/env python3
"""pattern_load_balancer.py — Distribute dispatch load evenly across cluster nodes.

Analyzes current load distribution and generates rebalancing rules to prevent
node overload. M1 handles 73% of all traffic — this script aims to distribute
complex patterns across available nodes.

CLI:
    --once       : analyze and suggest rebalancing
    --apply      : apply rebalancing to routing tables
    --stats      : show load distribution

Stdlib-only (sqlite3, json, argparse).
"""

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data"
DB_PATH = DATA_DIR / "cowork_gaps.db"
from _paths import ETOILE_DB

# Target load distribution (percentage of total traffic)
TARGET_DISTRIBUTION = {
    "M1": 0.45,    # Reduce from 73% to 45%
    "OL1": 0.30,   # Increase from ~16% (best success rate)
    "M2": 0.15,    # Keep moderate
    "M3": 0.10,    # Backup only
}

# Pattern complexity tiers
PATTERN_TIERS = {
    "simple": {"tier": 1, "preferred": ["OL1", "M1"]},
    "creative": {"tier": 1, "preferred": ["OL1", "M1"]},
    "system": {"tier": 1, "preferred": ["M1", "OL1"]},
    "code": {"tier": 2, "preferred": ["M1", "OL1"]},
    "math": {"tier": 2, "preferred": ["M1", "M2"]},
    "devops": {"tier": 2, "preferred": ["M1", "OL1"]},
    "web": {"tier": 2, "preferred": ["OL1", "M1"]},
    "analysis": {"tier": 3, "preferred": ["OL1", "M1", "M2"]},
    "architecture": {"tier": 3, "preferred": ["OL1", "M2", "M1"]},
    "security": {"tier": 3, "preferred": ["OL1", "M1", "M2"]},
    "data": {"tier": 3, "preferred": ["OL1", "M1"]},
    "trading": {"tier": 3, "preferred": ["M1", "M2"]},
    "reasoning": {"tier": 3, "preferred": ["M2", "M1"]},
}


def init_db(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS load_balance_rules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        pattern TEXT NOT NULL,
        from_node TEXT,
        to_node TEXT,
        reason TEXT,
        applied INTEGER DEFAULT 0
    )""")
    conn.commit()


def get_db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def analyze_load():
    """Analyze current load distribution."""
    if not ETOILE_DB.exists():
        return {"error": "etoile.db not found"}

    edb = sqlite3.connect(str(ETOILE_DB))
    edb.row_factory = sqlite3.Row

    # Current distribution
    total_dispatches = edb.execute(
        "SELECT COUNT(*) FROM agent_dispatch_log"
    ).fetchone()[0]

    node_load = edb.execute("""
        SELECT node, COUNT(*) as dispatches,
               SUM(CASE WHEN success=1 THEN 1 ELSE 0 END) as successes,
               AVG(latency_ms) as avg_lat,
               AVG(quality_score) as avg_q
        FROM agent_dispatch_log
        GROUP BY node
        ORDER BY dispatches DESC
    """).fetchall()

    # Per pattern per node
    pattern_node = edb.execute("""
        SELECT classified_type, node, COUNT(*) as cnt,
               AVG(CASE WHEN success=1 THEN 1.0 ELSE 0.0 END) as success_rate
        FROM agent_dispatch_log
        GROUP BY classified_type, node
        ORDER BY classified_type, cnt DESC
    """).fetchall()

    edb.close()

    # Calculate imbalance
    distribution = {}
    for nl in node_load:
        node = nl["node"]
        pct = nl["dispatches"] / max(total_dispatches, 1) * 100
        target_pct = TARGET_DISTRIBUTION.get(node, 0.1) * 100
        distribution[node] = {
            "current_pct": round(pct, 1),
            "target_pct": round(target_pct, 1),
            "delta": round(pct - target_pct, 1),
            "dispatches": nl["dispatches"],
            "success_rate": round((nl["successes"] or 0) / max(nl["dispatches"], 1) * 100, 1),
            "avg_latency_ms": round(nl["avg_lat"] or 0),
            "avg_quality": round(nl["avg_q"] or 0, 3),
        }

    # Generate rebalancing suggestions
    suggestions = []
    overloaded = [(n, d) for n, d in distribution.items() if d["delta"] > 10]
    underloaded = [(n, d) for n, d in distribution.items() if d["delta"] < -10]

    for over_node, over_data in overloaded:
        for under_node, under_data in underloaded:
            # Find patterns to move
            movable = []
            for pn in pattern_node:
                if pn["node"] == over_node:
                    tier_info = PATTERN_TIERS.get(pn["classified_type"], {})
                    if under_node in tier_info.get("preferred", []):
                        movable.append({
                            "pattern": pn["classified_type"],
                            "current_count": pn["cnt"],
                            "current_success": round(pn["success_rate"] * 100, 1)
                        })

            if movable:
                suggestions.append({
                    "from": over_node,
                    "to": under_node,
                    "from_load": over_data["current_pct"],
                    "to_load": under_data["current_pct"],
                    "patterns_to_move": movable[:5],
                    "expected_improvement": f"Reduce {over_node} by ~{len(movable)*2}%"
                })

    return {
        "timestamp": datetime.now().isoformat(),
        "total_dispatches": total_dispatches,
        "distribution": distribution,
        "suggestions": suggestions,
        "pattern_tiers": {k: v["tier"] for k, v in PATTERN_TIERS.items()},
    }


def apply_rebalancing(analysis):
    """Record rebalancing rules."""
    conn = get_db()
    ts = datetime.now().isoformat()
    count = 0

    for sug in analysis.get("suggestions", []):
        for pat in sug.get("patterns_to_move", []):
            conn.execute("""
                INSERT INTO load_balance_rules
                (timestamp, pattern, from_node, to_node, reason, applied)
                VALUES (?, ?, ?, ?, ?, 1)
            """, (ts, pat["pattern"], sug["from"], sug["to"],
                  f"Rebalance: {sug['from']} overloaded at {sug['from_load']}%"))
            count += 1

    conn.commit()
    conn.close()
    return {"rules_created": count}


def main():
    parser = argparse.ArgumentParser(description="Pattern Load Balancer")
    parser.add_argument("--once", action="store_true", help="Analyze load")
    parser.add_argument("--apply", action="store_true", help="Apply rebalancing")
    parser.add_argument("--stats", action="store_true", help="Show stats")
    args = parser.parse_args()

    if not any([args.once, args.apply, args.stats]):
        parser.print_help()
        sys.exit(1)

    analysis = analyze_load()

    if args.apply:
        apply_result = apply_rebalancing(analysis)
        analysis.update(apply_result)

    if args.stats:
        conn = get_db()
        rules = conn.execute("""
            SELECT pattern, from_node, to_node, reason, timestamp
            FROM load_balance_rules ORDER BY timestamp DESC LIMIT 20
        """).fetchall()
        conn.close()
        analysis["recent_rules"] = [dict(r) for r in rules]

    print(json.dumps(analysis, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
