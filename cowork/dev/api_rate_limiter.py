#!/usr/bin/env python3
"""api_rate_limiter.py

Rate limiting for cluster API calls using a token bucket algorithm.

Fonctionnalites :
* Token bucket par noeud (M1, M2, M3, OL1) avec capacite et refill configurables
* Enregistre chaque requete dans SQLite (cowork_gaps.db)
* Alerte quand un noeud approche sa limite (>80% utilise)
* Fournit des statistiques de consommation par noeud et par minute

CLI :
    --once      : affiche l'etat courant des buckets et alertes JSON
    --stats     : statistiques detaillees par noeud
    --reset     : reinitialise les compteurs de tous les noeuds

Stdlib-only (sqlite3, json, argparse, time, threading).
"""

import argparse
import json
import os
import sqlite3
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data"
DB_PATH = DATA_DIR / "cowork_gaps.db"

# Node definitions: name -> {endpoint, bucket_capacity, refill_rate_per_sec}
NODES = {
    "M1": {
        "endpoint": "http://127.0.0.1:1234",
        "bucket_capacity": 60,       # max 60 tokens (requests)
        "refill_rate": 1.0,          # 1 token/sec = 60/min
        "alert_threshold": 0.80,     # alert at 80% usage
    },
    "M2": {
        "endpoint": "http://192.168.1.26:1234",
        "bucket_capacity": 30,
        "refill_rate": 0.5,
        "alert_threshold": 0.80,
    },
    "M3": {
        "endpoint": "http://192.168.1.113:1234",
        "bucket_capacity": 20,
        "refill_rate": 0.33,
        "alert_threshold": 0.80,
    },
    "OL1": {
        "endpoint": "http://127.0.0.1:11434",
        "bucket_capacity": 90,
        "refill_rate": 1.5,
        "alert_threshold": 0.80,
    },
}

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
def init_db(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS rate_limit_buckets (
            node TEXT PRIMARY KEY,
            tokens_remaining REAL NOT NULL,
            last_refill_ts REAL NOT NULL,
            bucket_capacity INTEGER NOT NULL,
            refill_rate REAL NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS rate_limit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            node TEXT NOT NULL,
            action TEXT NOT NULL,
            tokens_before REAL,
            tokens_after REAL,
            allowed INTEGER NOT NULL DEFAULT 1
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS rate_limit_alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            node TEXT NOT NULL,
            message TEXT NOT NULL,
            usage_pct REAL NOT NULL
        )
    """)
    conn.commit()


def get_db() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn

# ---------------------------------------------------------------------------
# Token Bucket Logic
# ---------------------------------------------------------------------------
def ensure_bucket(conn: sqlite3.Connection, node: str):
    """Create bucket row if it doesn't exist."""
    row = conn.execute(
        "SELECT * FROM rate_limit_buckets WHERE node = ?", (node,)
    ).fetchone()
    if row is None:
        cfg = NODES[node]
        conn.execute("""
            INSERT INTO rate_limit_buckets (node, tokens_remaining, last_refill_ts,
                                            bucket_capacity, refill_rate)
            VALUES (?, ?, ?, ?, ?)
        """, (node, cfg["bucket_capacity"], time.time(),
              cfg["bucket_capacity"], cfg["refill_rate"]))
        conn.commit()


def refill_bucket(conn: sqlite3.Connection, node: str) -> dict:
    """Refill tokens based on elapsed time. Returns current state."""
    ensure_bucket(conn, node)
    row = conn.execute(
        "SELECT * FROM rate_limit_buckets WHERE node = ?", (node,)
    ).fetchone()

    now = time.time()
    elapsed = now - row["last_refill_ts"]
    new_tokens = row["tokens_remaining"] + elapsed * row["refill_rate"]
    capacity = row["bucket_capacity"]
    new_tokens = min(new_tokens, capacity)

    conn.execute("""
        UPDATE rate_limit_buckets
        SET tokens_remaining = ?, last_refill_ts = ?
        WHERE node = ?
    """, (new_tokens, now, node))
    conn.commit()

    return {
        "node": node,
        "tokens_remaining": round(new_tokens, 2),
        "bucket_capacity": capacity,
        "refill_rate": row["refill_rate"],
        "usage_pct": round((1.0 - new_tokens / capacity) * 100, 1),
    }


def consume_token(conn: sqlite3.Connection, node: str) -> dict:
    """Try to consume one token. Returns result with allowed flag."""
    state = refill_bucket(conn, node)
    tokens = state["tokens_remaining"]

    if tokens >= 1.0:
        new_tokens = tokens - 1.0
        allowed = True
    else:
        new_tokens = tokens
        allowed = False

    conn.execute("""
        UPDATE rate_limit_buckets SET tokens_remaining = ? WHERE node = ?
    """, (new_tokens, node))

    conn.execute("""
        INSERT INTO rate_limit_log (timestamp, node, action, tokens_before, tokens_after, allowed)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (datetime.now().isoformat(), node, "consume", tokens, new_tokens, int(allowed)))
    conn.commit()

    state["tokens_remaining"] = round(new_tokens, 2)
    state["allowed"] = allowed
    state["usage_pct"] = round((1.0 - new_tokens / state["bucket_capacity"]) * 100, 1)
    return state


def check_alerts(conn: sqlite3.Connection, node: str, state: dict) -> list[str]:
    """Check if node is approaching its rate limit."""
    alerts = []
    cfg = NODES.get(node, {})
    threshold = cfg.get("alert_threshold", 0.80)
    usage = state["usage_pct"] / 100.0

    if usage >= 0.95:
        msg = f"CRITICAL: {node} at {state['usage_pct']}% capacity — {state['tokens_remaining']} tokens left"
        alerts.append(msg)
    elif usage >= threshold:
        msg = f"WARNING: {node} at {state['usage_pct']}% capacity — approaching limit"
        alerts.append(msg)

    for alert_msg in alerts:
        conn.execute("""
            INSERT INTO rate_limit_alerts (timestamp, node, message, usage_pct)
            VALUES (?, ?, ?, ?)
        """, (datetime.now().isoformat(), node, alert_msg, state["usage_pct"]))
    conn.commit()

    return alerts

# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------
def action_once() -> dict:
    """Show current bucket states and any alerts."""
    conn = get_db()
    result = {
        "timestamp": datetime.now().isoformat(),
        "action": "status",
        "nodes": {},
        "alerts": [],
    }

    for node in NODES:
        state = refill_bucket(conn, node)
        alerts = check_alerts(conn, node, state)
        state["alerts"] = alerts
        result["nodes"][node] = state
        result["alerts"].extend(alerts)

    # Requests in last minute per node
    one_min_ago = (datetime.now() - timedelta(minutes=1)).isoformat()
    for node in NODES:
        row = conn.execute("""
            SELECT COUNT(*) as cnt FROM rate_limit_log
            WHERE node = ? AND timestamp > ? AND action = 'consume'
        """, (node, one_min_ago)).fetchone()
        result["nodes"][node]["requests_last_minute"] = row["cnt"]

    conn.close()
    return result


def action_stats() -> dict:
    """Show detailed rate limiting statistics."""
    conn = get_db()
    result = {
        "timestamp": datetime.now().isoformat(),
        "action": "stats",
        "per_node": {},
        "recent_alerts": [],
    }

    for node in NODES:
        ensure_bucket(conn, node)
        # Total requests
        total = conn.execute("""
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN allowed=1 THEN 1 ELSE 0 END) as allowed,
                   SUM(CASE WHEN allowed=0 THEN 1 ELSE 0 END) as denied
            FROM rate_limit_log WHERE node = ?
        """, (node,)).fetchone()

        # Requests per hour (last 24h, grouped by hour)
        hourly = conn.execute("""
            SELECT substr(timestamp, 1, 13) as hour, COUNT(*) as cnt
            FROM rate_limit_log
            WHERE node = ? AND timestamp > ?
            GROUP BY hour ORDER BY hour DESC LIMIT 24
        """, (node, (datetime.now() - timedelta(hours=24)).isoformat())).fetchall()

        state = refill_bucket(conn, node)

        result["per_node"][node] = {
            "current_state": state,
            "total_requests": total["total"],
            "total_allowed": total["allowed"] or 0,
            "total_denied": total["denied"] or 0,
            "deny_rate_pct": round(
                (total["denied"] or 0) / max(total["total"], 1) * 100, 2
            ),
            "hourly_breakdown": [dict(h) for h in hourly],
        }

    # Recent alerts
    alerts = conn.execute("""
        SELECT * FROM rate_limit_alerts ORDER BY timestamp DESC LIMIT 20
    """).fetchall()
    result["recent_alerts"] = [dict(a) for a in alerts]

    conn.close()
    return result


def action_reset() -> dict:
    """Reset all buckets to full capacity."""
    conn = get_db()
    now = time.time()

    for node, cfg in NODES.items():
        conn.execute("""
            INSERT OR REPLACE INTO rate_limit_buckets
            (node, tokens_remaining, last_refill_ts, bucket_capacity, refill_rate)
            VALUES (?, ?, ?, ?, ?)
        """, (node, cfg["bucket_capacity"], now,
              cfg["bucket_capacity"], cfg["refill_rate"]))

    conn.execute("DELETE FROM rate_limit_log")
    conn.execute("DELETE FROM rate_limit_alerts")
    conn.commit()
    conn.close()

    return {
        "timestamp": datetime.now().isoformat(),
        "action": "reset",
        "message": "All buckets reset to full capacity, logs and alerts cleared",
        "nodes_reset": list(NODES.keys()),
    }

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Rate limiting for cluster API calls using token bucket algorithm."
    )
    parser.add_argument("--once", action="store_true",
                        help="Show current bucket states and alerts as JSON")
    parser.add_argument("--stats", action="store_true",
                        help="Show detailed rate limiting statistics")
    parser.add_argument("--reset", action="store_true",
                        help="Reset all rate limit counters to full capacity")
    args = parser.parse_args()

    if not any([args.once, args.stats, args.reset]):
        parser.print_help()
        sys.exit(1)

    if args.reset:
        result = action_reset()
    elif args.stats:
        result = action_stats()
    elif args.once:
        result = action_once()
    else:
        parser.print_help()
        sys.exit(1)

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
