#!/usr/bin/env python3
"""adaptive_load_balancer.py — Dynamic load balancing across cluster nodes.

Tracks concurrent requests per node and adjusts routing weights based on:
- Current load (pending requests)
- Node capacity (max parallel requests)
- Recent performance (latency trend)
- Reliability score

CLI:
    --once         : Show current load distribution
    --dispatch TYPE PROMPT : Route via load balancer
    --simulate N   : Simulate N concurrent dispatches
    --json         : JSON output

Stdlib-only (json, argparse, sqlite3, time, urllib).
"""

import argparse
import json
import sqlite3
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data"
GAPS_DB = DATA_DIR / "cowork_gaps.db"
from _paths import ETOILE_DB

# Node capacity limits
NODE_CAPACITY = {
    "M1":  {"max_parallel": 3, "weight": 1.8},
    "OL1": {"max_parallel": 3, "weight": 1.3},  # OLLAMA_NUM_PARALLEL=3
    "M2":  {"max_parallel": 1, "weight": 1.0},
    "M3":  {"max_parallel": 1, "weight": 0.8},
}

NODES = {
    "M1":  {"url": "http://127.0.0.1:1234/api/v1/chat", "model": "qwen3-8b",
            "ollama": False, "prefix": "/nothink\n", "timeout": 30},
    "OL1": {"url": "http://127.0.0.1:11434/api/chat", "model": "qwen3:1.7b",
            "ollama": True, "timeout": 20},
    "M2":  {"url": "http://192.168.1.26:1234/api/v1/chat", "model": "deepseek-r1-0528-qwen3-8b",
            "ollama": False, "max_tokens": 2048, "timeout": 60},
    "M3":  {"url": "http://192.168.1.113:1234/api/v1/chat", "model": "deepseek-r1-0528-qwen3-8b",
            "ollama": False, "max_tokens": 2048, "timeout": 60},
}


def get_db(path):
    conn = sqlite3.connect(str(path), timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


def init_load_table(db):
    """Create load tracking table."""
    db.execute("""CREATE TABLE IF NOT EXISTS node_load (
        node TEXT PRIMARY KEY,
        current_load INTEGER DEFAULT 0,
        total_dispatched INTEGER DEFAULT 0,
        total_completed INTEGER DEFAULT 0,
        avg_response_ms REAL DEFAULT 0,
        last_dispatch TEXT,
        updated_at TEXT
    )""")
    db.commit()


def get_load_state(db):
    """Get current load for all nodes."""
    init_load_table(db)
    loads = {}
    for node in NODE_CAPACITY:
        row = db.execute(
            "SELECT * FROM node_load WHERE node=?", (node,)
        ).fetchone()
        if row:
            loads[node] = dict(row)
        else:
            loads[node] = {"node": node, "current_load": 0, "total_dispatched": 0,
                           "total_completed": 0, "avg_response_ms": 0}
    return loads


def get_reliability(db):
    """Get reliability scores if available."""
    scores = {}
    try:
        rows = db.execute("SELECT node, composite FROM node_reliability").fetchall()
        for r in rows:
            scores[r["node"]] = r["composite"]
    except Exception:
        pass
    return scores


def select_best_node(db, task_type=None):
    """Select the best node based on weighted scoring."""
    loads = get_load_state(db)
    reliability = get_reliability(db)

    candidates = []
    for node, cap in NODE_CAPACITY.items():
        load = loads.get(node, {}).get("current_load", 0)
        max_p = cap["max_parallel"]

        # Skip overloaded nodes
        if load >= max_p:
            continue

        # Compute score
        load_ratio = 1.0 - (load / max_p)  # 1.0 = empty, 0.0 = full
        weight = cap["weight"]
        rel = reliability.get(node, 50) / 100

        # Weighted score: 40% load availability + 30% reliability + 30% weight
        score = load_ratio * 0.4 + rel * 0.3 + (weight / 2.0) * 0.3

        candidates.append({
            "node": node, "score": round(score, 3),
            "load": load, "max": max_p, "reliability": round(rel * 100, 1),
        })

    if not candidates:
        # Everything overloaded, pick least loaded
        least = min(loads.items(), key=lambda x: x[1].get("current_load", 999))
        return least[0], {"fallback": True}

    candidates.sort(key=lambda x: -x["score"])
    return candidates[0]["node"], candidates[0]


def record_dispatch_start(db, node):
    """Record start of a dispatch (increment load)."""
    init_load_table(db)
    now = datetime.now().isoformat()
    db.execute("""
        INSERT INTO node_load (node, current_load, total_dispatched, last_dispatch, updated_at)
        VALUES (?, 1, 1, ?, ?)
        ON CONFLICT(node) DO UPDATE SET
            current_load = current_load + 1,
            total_dispatched = total_dispatched + 1,
            last_dispatch = ?,
            updated_at = ?
    """, (node, now, now, now, now))
    db.commit()


def record_dispatch_end(db, node, latency_ms):
    """Record end of a dispatch (decrement load)."""
    init_load_table(db)
    now = datetime.now().isoformat()

    # Get current avg for EMA update
    row = db.execute("SELECT avg_response_ms FROM node_load WHERE node=?", (node,)).fetchone()
    old_avg = row["avg_response_ms"] if row else latency_ms
    alpha = 0.3
    new_avg = old_avg * (1 - alpha) + latency_ms * alpha

    db.execute("""
        UPDATE node_load SET
            current_load = MAX(current_load - 1, 0),
            total_completed = total_completed + 1,
            avg_response_ms = ?,
            updated_at = ?
        WHERE node = ?
    """, (new_avg, now, node))
    db.commit()


def dispatch_balanced(task_type, prompt):
    """Dispatch with load balancing."""
    db = get_db(GAPS_DB)
    node, info = select_best_node(db, task_type)

    record_dispatch_start(db, node)
    start = time.time()

    try:
        cfg = NODES[node]
        if cfg.get("ollama"):
            body = json.dumps({
                "model": cfg["model"],
                "messages": [{"role": "user", "content": prompt}],
                "stream": False, "think": False,
            }).encode()
        else:
            prefix = cfg.get("prefix", "")
            max_tokens = cfg.get("max_tokens", 1024)
            body = json.dumps({
                "model": cfg["model"],
                "input": f"{prefix}{prompt}",
                "temperature": 0.2, "max_output_tokens": max_tokens,
                "stream": False, "store": False,
            }).encode()

        req = urllib.request.Request(cfg["url"], data=body,
                                     headers={"Content-Type": "application/json"})
        resp = urllib.request.urlopen(req, timeout=cfg.get("timeout", 30))
        data = json.loads(resp.read())
        elapsed = int((time.time() - start) * 1000)

        if cfg.get("ollama"):
            text = data.get("message", {}).get("content", "")
        else:
            text = ""
            for item in reversed(data.get("output", [])):
                if item.get("type") == "message":
                    content = item.get("content", [])
                    if content and isinstance(content, list):
                        text = content[0].get("text", "")
                    elif isinstance(content, str):
                        text = content
                    break

        record_dispatch_end(db, node, elapsed)
        db.close()
        return {"success": True, "node": node, "text": text, "latency_ms": elapsed, "routing_info": info}

    except Exception as e:
        elapsed = int((time.time() - start) * 1000)
        record_dispatch_end(db, node, elapsed)
        db.close()
        return {"success": False, "node": node, "error": str(e)[:200], "latency_ms": elapsed}


def show_load(db):
    """Display current load distribution."""
    loads = get_load_state(db)
    reliability = get_reliability(db)

    print("=== Load Distribution ===")
    for node in ["M1", "OL1", "M2", "M3"]:
        load = loads.get(node, {})
        cap = NODE_CAPACITY.get(node, {})
        cur = load.get("current_load", 0)
        mx = cap.get("max_parallel", 1)
        total = load.get("total_dispatched", 0)
        avg = load.get("avg_response_ms", 0)
        rel = reliability.get(node, 0)

        bar_len = int(cur / mx * 10) if mx > 0 else 0
        bar = "#" * bar_len + "." * (10 - bar_len)

        print(f"  {node:4} [{bar}] {cur}/{mx} ({total} total, avg={avg:.0f}ms, rel={rel:.0f})")


def main():
    parser = argparse.ArgumentParser(description="Adaptive Load Balancer")
    parser.add_argument("--once", action="store_true", help="Show load")
    parser.add_argument("--dispatch", nargs=2, metavar=("TYPE", "PROMPT"))
    parser.add_argument("--simulate", type=int, help="Simulate N dispatches")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    if not any([args.once, args.dispatch, args.simulate]):
        parser.print_help()
        sys.exit(1)

    if args.once:
        db = get_db(GAPS_DB)
        show_load(db)
        db.close()
        return

    if args.dispatch:
        task_type, prompt = args.dispatch
        result = dispatch_balanced(task_type, prompt)
        if args.json:
            print(json.dumps(result, indent=2, default=str))
        else:
            if result["success"]:
                print(f"[{result['node']}] {result['text'][:500]}")
            else:
                print(f"FAIL [{result['node']}]: {result.get('error', '')}")
        return

    if args.simulate:
        print(f"=== Simulating {args.simulate} dispatches ===")
        db = get_db(GAPS_DB)
        selections = {}
        for i in range(args.simulate):
            node, info = select_best_node(db, "simple")
            selections[node] = selections.get(node, 0) + 1
            record_dispatch_start(db, node)
            # Simulate completion after count
            if i % 3 == 2:
                for n in NODE_CAPACITY:
                    record_dispatch_end(db, n, 500)

        print("  Distribution:")
        for node, count in sorted(selections.items(), key=lambda x: -x[1]):
            pct = count / args.simulate * 100
            print(f"    {node:4} {count:3} ({pct:.0f}%)")

        # Reset loads
        for n in NODE_CAPACITY:
            db.execute("UPDATE node_load SET current_load = 0 WHERE node = ?", (n,))
        db.commit()
        db.close()


if __name__ == "__main__":
    main()
