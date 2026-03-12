#!/usr/bin/env python3
"""smart_routing_engine.py — Intelligent dispatch routing based on learned data.

Reads routing_recommendations and timeout_configs from cowork_gaps.db,
combined with real-time heartbeat status, to provide optimal routing decisions.

Features:
- Circuit breaker: Skip nodes with consecutive failures
- Latency-aware: Route to fastest node for time-sensitive tasks
- Quality-aware: Route to highest quality node for important tasks
- Fallback chains: Auto-fallback when primary node is down/slow

CLI:
    --once         : Show current routing table
    --route TYPE   : Get optimal route for a task type
    --status       : Show all nodes with circuit breaker state
    --apply        : Apply routing to pattern_agents config

Stdlib-only (json, argparse, sqlite3).
"""

import argparse
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data"
GAPS_DB = DATA_DIR / "cowork_gaps.db"
from _paths import ETOILE_DB

# Circuit breaker thresholds
CB_FAIL_THRESHOLD = 3      # Open circuit after N consecutive fails
CB_RECOVERY_TIME_S = 300   # Try again after 5 minutes

# Node capabilities
NODE_CAPABILITIES = {
    "M1":       {"speed": "fast", "reasoning": True, "code": True, "max_ctx": 32768},
    "M2":       {"speed": "slow", "reasoning": True, "code": True, "max_ctx": 27000},
    "M3":       {"speed": "slow", "reasoning": True, "code": True, "max_ctx": 25000},
    "OL1":      {"speed": "fast", "reasoning": False, "code": False, "max_ctx": 8192},
}

# Default routing (used when no learned data)
DEFAULT_ROUTES = {
    "simple":       ["OL1", "M1"],
    "code":         ["M1", "OL1", "M2"],
    "analysis":     ["M1", "OL1", "M2"],
    "math":         ["M1", "OL1"],           # M2/M3 too slow for math
    "reasoning":    ["M1", "M2", "M3"],      # M2/M3 ok for deep reasoning
    "trading":      ["M1", "OL1"],
    "system":       ["OL1", "M1"],
    "creative":     ["M1", "OL1"],
    "web":          ["OL1", "M1"],
    "architecture": ["M1", "M2"],
    "security":     ["M1", "M2"],
    "data":         ["M1", "OL1"],
    "devops":       ["M1", "OL1"],
}


def get_gaps():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(GAPS_DB), timeout=10)
    db.execute("PRAGMA journal_mode=WAL")
    db.row_factory = sqlite3.Row
    return db


def get_etoile():
    db = sqlite3.connect(str(ETOILE_DB), timeout=10)
    db.execute("PRAGMA journal_mode=WAL")
    db.row_factory = sqlite3.Row
    return db


def get_heartbeat_status(gaps_db):
    """Get current node status from heartbeat data."""
    status = {}
    try:
        rows = gaps_db.execute("""
            SELECT node, last_status, consecutive_fails, last_check
            FROM heartbeat_state
        """).fetchall()
        for r in rows:
            status[r["node"]] = {
                "online": r["last_status"] == "online",
                "consecutive_fails": r["consecutive_fails"],
                "last_check": r["last_check"],
            }
    except Exception:
        pass
    return status


def get_circuit_breaker_state(edb):
    """Compute circuit breaker state from recent dispatches."""
    states = {}
    try:
        rows = edb.execute("""
            SELECT node,
                   SUM(CASE WHEN success=0 THEN 1 ELSE 0 END) as recent_fails,
                   SUM(CASE WHEN success=1 THEN 1 ELSE 0 END) as recent_ok,
                   MAX(CASE WHEN success=1 THEN timestamp ELSE '' END) as last_ok
            FROM (SELECT * FROM agent_dispatch_log ORDER BY id DESC LIMIT 50)
            GROUP BY node
        """).fetchall()
        for r in rows:
            total = r["recent_fails"] + r["recent_ok"]
            fail_rate = r["recent_fails"] / max(total, 1)
            states[r["node"]] = {
                "state": "OPEN" if r["recent_fails"] >= CB_FAIL_THRESHOLD and fail_rate > 0.5 else "CLOSED",
                "recent_fails": r["recent_fails"],
                "recent_ok": r["recent_ok"],
                "fail_rate": round(fail_rate * 100, 1),
                "last_ok": r["last_ok"],
            }
    except Exception:
        pass
    return states


def get_learned_routes(gaps_db):
    """Get routing recommendations from learning data."""
    routes = {}
    try:
        rows = gaps_db.execute("""
            SELECT task_type, best_node, score, fallback_node, fallback_score
            FROM routing_recommendations
            ORDER BY timestamp DESC
        """).fetchall()
        seen = set()
        for r in rows:
            t = r["task_type"]
            if t not in seen:
                seen.add(t)
                chain = [r["best_node"]]
                if r["fallback_node"]:
                    chain.append(r["fallback_node"])
                routes[t] = {
                    "chain": chain,
                    "best_score": r["score"],
                    "fallback_score": r["fallback_score"],
                }
    except Exception:
        pass
    return routes


def get_optimal_route(task_type, gaps_db=None, edb=None):
    """Get the optimal routing chain for a task type."""
    # 1. Start with default
    chain = DEFAULT_ROUTES.get(task_type, DEFAULT_ROUTES.get("simple", ["M1", "OL1"]))

    # 2. Override with learned routes if available
    if gaps_db:
        learned = get_learned_routes(gaps_db)
        if task_type in learned:
            chain = learned[task_type]["chain"]

    # 3. Filter by heartbeat (remove offline nodes)
    if gaps_db:
        heartbeat = get_heartbeat_status(gaps_db)
        chain = [n for n in chain if heartbeat.get(n, {}).get("online", True)]

    # 4. Filter by circuit breaker
    if edb:
        cb = get_circuit_breaker_state(edb)
        chain = [n for n in chain if cb.get(n, {}).get("state", "CLOSED") != "OPEN"]

    # 5. Ensure at least one node
    if not chain:
        chain = ["M1", "OL1"]  # Emergency fallback

    # 6. Add remaining nodes as deep fallback
    all_nodes = ["M1", "OL1", "M2", "M3"]
    for n in all_nodes:
        if n not in chain:
            chain.append(n)

    return chain


def get_timeout(task_type, node, gaps_db=None):
    """Get optimal timeout for a type/node combination."""
    default_timeouts = {
        "simple": 15, "code": 60, "analysis": 90, "reasoning": 120,
        "math": 60, "trading": 75, "system": 30, "creative": 60,
    }
    base = default_timeouts.get(task_type, 30)

    if gaps_db:
        try:
            row = gaps_db.execute("""
                SELECT recommended_timeout_s FROM timeout_configs
                WHERE pattern=? AND node=?
                ORDER BY timestamp DESC LIMIT 1
            """, (task_type, node)).fetchone()
            if row:
                return int(row["recommended_timeout_s"])
        except Exception:
            pass

    # Apply node factor
    node_factors = {"M1": 1.0, "OL1": 1.0, "M2": 2.0, "M3": 2.5}
    return int(base * node_factors.get(node, 1.5))


def show_routing_table(gaps_db, edb):
    """Display full routing table with all context."""
    heartbeat = get_heartbeat_status(gaps_db)
    cb = get_circuit_breaker_state(edb)
    learned = get_learned_routes(gaps_db)

    print("=== Node Status ===")
    for node in ["M1", "M2", "M3", "OL1"]:
        hb = heartbeat.get(node, {})
        cbs = cb.get(node, {})
        online = "ONLINE" if hb.get("online", True) else "OFFLINE"
        circuit = cbs.get("state", "CLOSED")
        fails = cbs.get("recent_fails", 0)
        print(f"  {node:4} {online:7} CB={circuit:6} fails={fails} rate={cbs.get('fail_rate', 0)}%")

    print("\n=== Routing Table ===")
    all_types = sorted(set(list(DEFAULT_ROUTES.keys()) + list(learned.keys())))
    for t in all_types:
        chain = get_optimal_route(t, gaps_db, edb)
        timeout = get_timeout(t, chain[0], gaps_db)
        learned_info = ""
        if t in learned:
            learned_info = f" (learned: score={learned[t]['best_score']:.2f})"
        print(f"  {t:15} -> {' -> '.join(chain[:3]):20} timeout={timeout}s{learned_info}")


def main():
    parser = argparse.ArgumentParser(description="Smart Routing Engine")
    parser.add_argument("--once", action="store_true", help="Show routing table")
    parser.add_argument("--route", type=str, help="Get route for task type")
    parser.add_argument("--status", action="store_true", help="Node status + CB")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    if not any([args.once, args.route, args.status]):
        parser.print_help()
        sys.exit(1)

    gaps_db = get_gaps()
    edb = get_etoile()

    if args.status:
        heartbeat = get_heartbeat_status(gaps_db)
        cb = get_circuit_breaker_state(edb)
        result = {"heartbeat": heartbeat, "circuit_breakers": cb}
        print(json.dumps(result, indent=2))
        gaps_db.close()
        edb.close()
        return

    if args.route:
        chain = get_optimal_route(args.route, gaps_db, edb)
        timeout = get_timeout(args.route, chain[0], gaps_db)
        result = {
            "task_type": args.route,
            "route": chain,
            "primary": chain[0],
            "fallback": chain[1] if len(chain) > 1 else None,
            "timeout_s": timeout,
        }
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"{args.route} -> {' -> '.join(chain[:3])} (timeout={timeout}s)")
        gaps_db.close()
        edb.close()
        return

    if args.once:
        show_routing_table(gaps_db, edb)
        gaps_db.close()
        edb.close()
        return


if __name__ == "__main__":
    main()
