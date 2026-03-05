#!/usr/bin/env python3
"""quick_answer_cache.py — Cache frequent simple queries to reduce dispatch load.

The 'simple' pattern has 225+ calls. Many are repeated queries.
This script maintains a response cache with TTL to serve common answers
instantly without hitting the cluster.

CLI:
    --once       : analyze cacheable queries
    --hit-rate   : show cache hit rate
    --stats      : show cache statistics

Stdlib-only (sqlite3, json, argparse).
"""

import argparse
import hashlib
import json
import os
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data"
DB_PATH = DATA_DIR / "cowork_gaps.db"
ETOILE_DB = Path(r"F:/BUREAU/turbo/etoile.db")

CACHE_TTL_SECONDS = 300  # 5 minutes
MIN_FREQUENCY = 2  # Must appear 2+ times to be cacheable


def init_db(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS query_cache (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        query_hash TEXT UNIQUE NOT NULL,
        query_text TEXT NOT NULL,
        response_text TEXT,
        pattern TEXT,
        hit_count INTEGER DEFAULT 0,
        created_at TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        node_used TEXT,
        latency_saved_ms REAL DEFAULT 0
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS cache_stats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        total_queries INTEGER,
        cacheable_queries INTEGER,
        unique_queries INTEGER,
        avg_frequency REAL,
        potential_hit_rate REAL,
        estimated_latency_saved_ms REAL
    )""")
    conn.commit()


def get_db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def hash_query(text):
    """Normalize and hash a query for cache lookup."""
    normalized = text.lower().strip()
    # Remove common prefixes
    for prefix in ["jarvis ", "hey jarvis ", "dis-moi ", "montre "]:
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix):]
    return hashlib.md5(normalized.encode()).hexdigest()


def analyze_cacheable():
    """Find queries that could be cached."""
    if not ETOILE_DB.exists():
        return {"error": "etoile.db not found"}

    edb = sqlite3.connect(str(ETOILE_DB))
    edb.row_factory = sqlite3.Row

    # Find repeated queries (simple pattern)
    rows = edb.execute("""
        SELECT request_text, classified_type, node,
               COUNT(*) as frequency,
               AVG(latency_ms) as avg_lat,
               AVG(quality_score) as avg_q
        FROM agent_dispatch_log
        WHERE classified_type IN ('simple', 'system', 'creative')
        AND request_text IS NOT NULL
        GROUP BY request_text
        HAVING frequency >= ?
        ORDER BY frequency DESC
    """, (MIN_FREQUENCY,)).fetchall()

    # All simple queries
    total_simple = edb.execute("""
        SELECT COUNT(*) FROM agent_dispatch_log
        WHERE classified_type = 'simple'
    """).fetchone()[0]

    edb.close()

    cacheable = []
    total_latency_saved = 0
    total_cacheable_calls = 0

    conn = get_db()
    ts = datetime.now().isoformat()

    for r in rows:
        freq = r["frequency"]
        avg_lat = r["avg_lat"] or 0
        latency_saved = avg_lat * (freq - 1)  # First call still hits cluster

        query_h = hash_query(r["request_text"])

        entry = {
            "query": r["request_text"][:100],
            "pattern": r["classified_type"],
            "frequency": freq,
            "avg_latency_ms": round(avg_lat),
            "latency_saved_ms": round(latency_saved),
            "cache_priority": "high" if freq >= 5 else "medium",
        }
        cacheable.append(entry)
        total_cacheable_calls += freq - 1
        total_latency_saved += latency_saved

        # Pre-populate cache entry
        conn.execute("""
            INSERT OR REPLACE INTO query_cache
            (query_hash, query_text, pattern, hit_count, created_at, expires_at, node_used, latency_saved_ms)
            VALUES (?, ?, ?, ?, ?, datetime(?, '+5 minutes'), ?, ?)
        """, (query_h, r["request_text"][:200], r["classified_type"],
              freq, ts, ts, r["node"], latency_saved))

    potential_hit_rate = total_cacheable_calls / max(total_simple, 1) * 100

    conn.execute("""
        INSERT INTO cache_stats
        (timestamp, total_queries, cacheable_queries, unique_queries,
         avg_frequency, potential_hit_rate, estimated_latency_saved_ms)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (ts, total_simple, total_cacheable_calls, len(cacheable),
          sum(c["frequency"] for c in cacheable) / max(len(cacheable), 1),
          potential_hit_rate, total_latency_saved))

    conn.commit()
    conn.close()

    return {
        "timestamp": ts,
        "total_simple_queries": total_simple,
        "cacheable_queries": total_cacheable_calls,
        "unique_cacheable": len(cacheable),
        "potential_hit_rate_pct": round(potential_hit_rate, 1),
        "estimated_latency_saved_ms": round(total_latency_saved),
        "estimated_time_saved_s": round(total_latency_saved / 1000, 1),
        "top_cacheable": cacheable[:20],
    }


def action_hit_rate():
    """Show simulated cache hit rate."""
    conn = get_db()
    stats = conn.execute("""
        SELECT * FROM cache_stats ORDER BY timestamp DESC LIMIT 5
    """).fetchall()
    cache_entries = conn.execute("""
        SELECT query_text, pattern, hit_count, latency_saved_ms
        FROM query_cache ORDER BY hit_count DESC LIMIT 10
    """).fetchall()
    conn.close()
    return {
        "recent_stats": [dict(s) for s in stats],
        "top_cached": [dict(c) for c in cache_entries],
    }


def main():
    parser = argparse.ArgumentParser(description="Quick Answer Cache")
    parser.add_argument("--once", action="store_true", help="Analyze cacheable queries")
    parser.add_argument("--hit-rate", action="store_true", help="Show hit rate")
    parser.add_argument("--stats", action="store_true", help="Show stats")
    args = parser.parse_args()

    if not any([args.once, args.hit_rate, args.stats]):
        parser.print_help()
        sys.exit(1)

    if args.hit_rate or args.stats:
        result = action_hit_rate()
    else:
        result = analyze_cacheable()

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
