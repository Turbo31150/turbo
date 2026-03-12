#!/usr/bin/env python3
"""dispatch_cache.py — Intelligent caching for cluster dispatches.

Caches responses from cluster nodes to avoid redundant dispatches:
- LRU cache with configurable TTL
- Hash-based key (prompt fingerprint)
- Per-type TTL (simple=5min, code=30min, etc.)
- Hit/miss stats for optimization
- Auto-eviction of stale entries

CLI:
    --stats        : Show cache statistics
    --clear        : Clear entire cache
    --lookup PROMPT: Check if prompt is cached
    --test         : Run cache tests

Stdlib-only (json, argparse, sqlite3, hashlib, time).
"""

import argparse
import hashlib
import json
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data"
GAPS_DB = DATA_DIR / "cowork_gaps.db"

# TTL per task type (seconds)
TYPE_TTL = {
    "simple":       300,    # 5 min
    "math":         3600,   # 1 hour (math doesn't change)
    "code":         1800,   # 30 min
    "system":       60,     # 1 min (system state changes fast)
    "trading":      120,    # 2 min (market data volatile)
    "creative":     600,    # 10 min
    "analysis":     900,    # 15 min
    "reasoning":    1800,   # 30 min
    "web":          300,    # 5 min
    "data":         600,    # 10 min
    "architecture": 3600,   # 1 hour
    "security":     1800,   # 30 min
}

MAX_CACHE_SIZE = 500   # Max entries
DEFAULT_TTL = 300      # 5 min default


def get_db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(GAPS_DB), timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    conn.execute("""CREATE TABLE IF NOT EXISTS dispatch_cache (
        key TEXT PRIMARY KEY,
        task_type TEXT,
        prompt_hash TEXT,
        prompt_preview TEXT,
        response_text TEXT,
        node TEXT,
        latency_ms INTEGER,
        created_at TEXT,
        expires_at TEXT,
        hit_count INTEGER DEFAULT 0,
        last_hit TEXT
    )""")
    # Check if cache_stats has the right schema
    cols = {r[1] for r in conn.execute("PRAGMA table_info(cache_stats)").fetchall()}
    if cols and "total_hits" not in cols:
        conn.execute("DROP TABLE cache_stats")
    conn.execute("""CREATE TABLE IF NOT EXISTS cache_stats (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        total_hits INTEGER DEFAULT 0,
        total_misses INTEGER DEFAULT 0,
        total_evictions INTEGER DEFAULT 0,
        updated_at TEXT
    )""")
    conn.execute("""
        INSERT OR IGNORE INTO cache_stats (id, total_hits, total_misses, total_evictions, updated_at)
        VALUES (1, 0, 0, 0, ?)
    """, (datetime.now().isoformat(),))
    conn.commit()
    return conn


def prompt_key(prompt, task_type=""):
    """Generate cache key from prompt."""
    normalized = prompt.strip().lower()
    h = hashlib.sha256(f"{task_type}:{normalized}".encode()).hexdigest()[:16]
    return h


def cache_get(db, prompt, task_type=""):
    """Look up cached response. Returns response or None."""
    key = prompt_key(prompt, task_type)
    now = datetime.now().isoformat()

    row = db.execute(
        "SELECT * FROM dispatch_cache WHERE key=? AND expires_at > ?",
        (key, now)
    ).fetchone()

    if row:
        # Hit
        db.execute("""
            UPDATE dispatch_cache SET hit_count = hit_count + 1, last_hit = ?
            WHERE key = ?
        """, (now, key))
        db.execute("""
            UPDATE cache_stats SET total_hits = total_hits + 1, updated_at = ?
            WHERE id = 1
        """, (now,))
        db.commit()
        return {
            "cached": True,
            "text": row["response_text"],
            "node": row["node"],
            "original_latency_ms": row["latency_ms"],
            "hit_count": row["hit_count"] + 1,
            "age_s": int((datetime.fromisoformat(now) -
                          datetime.fromisoformat(row["created_at"])).total_seconds()),
        }

    # Miss
    db.execute("""
        UPDATE cache_stats SET total_misses = total_misses + 1, updated_at = ?
        WHERE id = 1
    """, (now,))
    db.commit()
    return None


def cache_put(db, prompt, task_type, response_text, node, latency_ms):
    """Store a response in cache."""
    key = prompt_key(prompt, task_type)
    ttl = TYPE_TTL.get(task_type, DEFAULT_TTL)
    now = datetime.now()
    expires = datetime.fromtimestamp(now.timestamp() + ttl).isoformat()

    # Evict if at capacity
    count = db.execute("SELECT COUNT(*) FROM dispatch_cache").fetchone()[0]
    if count >= MAX_CACHE_SIZE:
        # Remove oldest unused entries
        db.execute("""
            DELETE FROM dispatch_cache WHERE key IN (
                SELECT key FROM dispatch_cache
                ORDER BY COALESCE(last_hit, created_at) ASC LIMIT 50
            )
        """)
        db.execute("""
            UPDATE cache_stats SET total_evictions = total_evictions + 50, updated_at = ?
            WHERE id = 1
        """, (now.isoformat(),))

    db.execute("""
        INSERT OR REPLACE INTO dispatch_cache
        (key, task_type, prompt_hash, prompt_preview, response_text, node,
         latency_ms, created_at, expires_at, hit_count, last_hit)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, NULL)
    """, (key, task_type, hashlib.sha256(prompt.encode()).hexdigest(),
          prompt[:100], response_text[:5000], node,
          latency_ms, now.isoformat(), expires))
    db.commit()


def cache_evict_expired(db):
    """Remove expired entries."""
    now = datetime.now().isoformat()
    result = db.execute("DELETE FROM dispatch_cache WHERE expires_at <= ?", (now,))
    db.commit()
    return result.rowcount


def show_stats(db):
    """Show cache statistics."""
    row = db.execute("SELECT * FROM cache_stats WHERE id=1").fetchone()
    entries = db.execute("SELECT COUNT(*) FROM dispatch_cache").fetchone()[0]
    expired = cache_evict_expired(db)

    hits = row["total_hits"]
    misses = row["total_misses"]
    total = hits + misses
    hit_rate = hits / max(total, 1) * 100

    print("=== Dispatch Cache ===")
    print(f"  Entries:    {entries}/{MAX_CACHE_SIZE}")
    print(f"  Hits:       {hits}")
    print(f"  Misses:     {misses}")
    print(f"  Hit Rate:   {hit_rate:.1f}%")
    print(f"  Evictions:  {row['total_evictions']}")
    if expired:
        print(f"  Expired:    {expired} (just cleaned)")

    # Per-type breakdown
    types = db.execute("""
        SELECT task_type, COUNT(*) as cnt, SUM(hit_count) as hits
        FROM dispatch_cache GROUP BY task_type ORDER BY hits DESC
    """).fetchall()
    if types:
        print("\n  Per-type:")
        for t in types:
            print(f"    {t['task_type']:15} {t['cnt']} entries  {t['hits']} hits")

    # Top cached
    top = db.execute("""
        SELECT prompt_preview, node, hit_count, task_type
        FROM dispatch_cache ORDER BY hit_count DESC LIMIT 5
    """).fetchall()
    if top:
        print("\n  Most cached:")
        for t in top:
            print(f"    [{t['node']}] {t['task_type']:10} hits={t['hit_count']} \"{t['prompt_preview'][:40]}\"")


def run_test(db):
    """Test cache operations."""
    print("=== Cache Test ===\n")

    # Test put
    cache_put(db, "test prompt 1", "simple", "response 1", "M1", 500)
    print("  PASS cache_put")

    # Test get (hit)
    result = cache_get(db, "test prompt 1", "simple")
    assert result is not None and result["cached"], "Expected cache hit"
    assert result["text"] == "response 1", "Wrong cached text"
    print(f"  PASS cache_get hit (age={result['age_s']}s)")

    # Test get (miss)
    result = cache_get(db, "unknown prompt", "simple")
    assert result is None, "Expected cache miss"
    print("  PASS cache_get miss")

    # Test key uniqueness
    cache_put(db, "test prompt 1", "code", "response code", "OL1", 300)
    result = cache_get(db, "test prompt 1", "code")
    assert result["text"] == "response code", "Type should affect key"
    print("  PASS key uniqueness (same prompt, different type)")

    # Test case insensitivity
    result = cache_get(db, "TEST PROMPT 1", "simple")
    assert result is not None, "Cache should be case-insensitive"
    print("  PASS case insensitive")

    # Test eviction of expired
    evicted = cache_evict_expired(db)
    print(f"  PASS evict_expired ({evicted} removed)")

    # Clean up test entries
    db.execute("DELETE FROM dispatch_cache WHERE prompt_preview LIKE 'test prompt%'")
    db.commit()

    print("\n  All cache tests passed")


def main():
    parser = argparse.ArgumentParser(description="Dispatch Cache")
    parser.add_argument("--stats", action="store_true", help="Show stats")
    parser.add_argument("--clear", action="store_true", help="Clear cache")
    parser.add_argument("--lookup", type=str, help="Lookup prompt")
    parser.add_argument("--type", type=str, default="simple", help="Task type")
    parser.add_argument("--test", action="store_true", help="Run tests")
    args = parser.parse_args()

    if not any([args.stats, args.clear, args.lookup, args.test]):
        parser.print_help()
        sys.exit(1)

    db = get_db()

    if args.stats:
        show_stats(db)
    elif args.clear:
        db.execute("DELETE FROM dispatch_cache")
        db.execute("UPDATE cache_stats SET total_hits=0, total_misses=0, total_evictions=0")
        db.commit()
        print("Cache cleared")
    elif args.lookup:
        result = cache_get(db, args.lookup, args.type)
        if result:
            print(f"HIT: [{result['node']}] age={result['age_s']}s hits={result['hit_count']}")
            print(f"  {result['text'][:200]}")
        else:
            print("MISS")
    elif args.test:
        run_test(db)

    db.close()


if __name__ == "__main__":
    main()
