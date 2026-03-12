#!/usr/bin/env python3
"""jarvis_response_cache.py (#199) — Response cache with SHA256 hashing.

SHA256 hash of prompt -> cached response in SQLite.
TTL 5 minutes. LRU eviction at max 500 entries. Hit/miss stats.

Usage:
    python dev/jarvis_response_cache.py --once
    python dev/jarvis_response_cache.py --get "What is Python?"
    python dev/jarvis_response_cache.py --put "What is Python?" "Python is a programming language"
    python dev/jarvis_response_cache.py --stats
    python dev/jarvis_response_cache.py --invalidate
"""
import argparse
import hashlib
import json
import sqlite3
import time
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "response_cache.db"

CACHE_TTL = 300  # 5 minutes
MAX_ENTRIES = 500


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS cache (
        key_hash TEXT PRIMARY KEY,
        prompt TEXT NOT NULL,
        response TEXT NOT NULL,
        model TEXT DEFAULT '',
        created_at REAL,
        last_accessed REAL,
        access_count INTEGER DEFAULT 1,
        ttl REAL DEFAULT 300,
        size_bytes INTEGER DEFAULT 0
    )""")
    # Recreate cache_stats if schema changed (migration-safe)
    try:
        db.execute("SELECT total_hits, total_misses, total_evictions, total_invalidations, total_puts FROM cache_stats LIMIT 1")
    except sqlite3.OperationalError:
        db.execute("DROP TABLE IF EXISTS cache_stats")
    db.execute("""CREATE TABLE IF NOT EXISTS cache_stats (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        total_hits INTEGER DEFAULT 0,
        total_misses INTEGER DEFAULT 0,
        total_evictions INTEGER DEFAULT 0,
        total_invalidations INTEGER DEFAULT 0,
        total_puts INTEGER DEFAULT 0
    )""")
    # Init stats row
    db.execute(
        "INSERT OR IGNORE INTO cache_stats (id, total_hits, total_misses) VALUES (1, 0, 0)"
    )
    db.commit()
    return db


def make_key(prompt):
    """Generate SHA256 hash key from prompt."""
    normalized = prompt.strip().lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def cleanup_expired(db):
    """Remove expired entries (TTL-based)."""
    now = time.time()
    deleted = db.execute(
        "DELETE FROM cache WHERE (created_at + ttl) < ?", (now,)
    ).rowcount
    if deleted > 0:
        db.commit()
    return deleted


def enforce_lru(db):
    """Evict oldest entries if over MAX_ENTRIES."""
    count = db.execute("SELECT COUNT(*) FROM cache").fetchone()[0]
    if count <= MAX_ENTRIES:
        return 0

    excess = count - MAX_ENTRIES
    # Delete least recently accessed
    db.execute("""
        DELETE FROM cache WHERE key_hash IN (
            SELECT key_hash FROM cache ORDER BY last_accessed ASC LIMIT ?
        )
    """, (excess,))
    db.execute(
        "UPDATE cache_stats SET total_evictions=total_evictions+? WHERE id=1", (excess,)
    )
    db.commit()
    return excess


def cache_get(db, prompt):
    """Get a cached response by prompt."""
    cleanup_expired(db)
    key = make_key(prompt)
    now = time.time()

    row = db.execute(
        "SELECT response, model, created_at, access_count FROM cache WHERE key_hash=? AND (created_at + ttl) > ?",
        (key, now)
    ).fetchone()

    if row:
        # Cache HIT
        db.execute(
            "UPDATE cache SET last_accessed=?, access_count=access_count+1 WHERE key_hash=?",
            (now, key)
        )
        db.execute("UPDATE cache_stats SET total_hits=total_hits+1 WHERE id=1")
        db.commit()

        age = round(now - row[2], 1)
        return {
            "status": "hit",
            "prompt": prompt[:100],
            "response": row[0],
            "model": row[1],
            "age_seconds": age,
            "access_count": row[3] + 1,
            "key_hash": key[:16]
        }
    else:
        # Cache MISS
        db.execute("UPDATE cache_stats SET total_misses=total_misses+1 WHERE id=1")
        db.commit()

        return {
            "status": "miss",
            "prompt": prompt[:100],
            "key_hash": key[:16]
        }


def cache_put(db, prompt, response, model=""):
    """Store a response in cache."""
    cleanup_expired(db)
    enforce_lru(db)

    key = make_key(prompt)
    now = time.time()
    size = len(response.encode("utf-8"))

    db.execute("""
        INSERT OR REPLACE INTO cache
        (key_hash, prompt, response, model, created_at, last_accessed, access_count, ttl, size_bytes)
        VALUES (?,?,?,?,?,?,1,?,?)
    """, (key, prompt[:1000], response, model, now, now, CACHE_TTL, size))

    db.execute("UPDATE cache_stats SET total_puts=total_puts+1 WHERE id=1")
    db.commit()

    return {
        "status": "ok",
        "key_hash": key[:16],
        "prompt": prompt[:100],
        "response_size": size,
        "ttl": CACHE_TTL,
        "expires_at": datetime.fromtimestamp(now + CACHE_TTL).isoformat()
    }


def get_stats(db):
    """Get cache statistics."""
    cleanup_expired(db)

    row = db.execute(
        "SELECT total_hits, total_misses, total_evictions, total_invalidations, total_puts FROM cache_stats WHERE id=1"
    ).fetchone()
    hits, misses, evictions, invalidations, puts = row

    total_requests = hits + misses
    hit_rate = round(hits / total_requests * 100, 1) if total_requests > 0 else 0

    entry_count = db.execute("SELECT COUNT(*) FROM cache").fetchone()[0]
    total_size = db.execute("SELECT COALESCE(SUM(size_bytes), 0) FROM cache").fetchone()[0]
    avg_accesses = db.execute("SELECT COALESCE(AVG(access_count), 0) FROM cache").fetchone()[0]

    # Top accessed entries
    top = db.execute(
        "SELECT prompt, access_count, model FROM cache ORDER BY access_count DESC LIMIT 5"
    ).fetchall()
    top_entries = [{"prompt": t[0][:80], "accesses": t[1], "model": t[2]} for t in top]

    return {
        "status": "ok",
        "hits": hits,
        "misses": misses,
        "hit_rate_pct": hit_rate,
        "total_requests": total_requests,
        "entries": entry_count,
        "max_entries": MAX_ENTRIES,
        "total_size_bytes": total_size,
        "total_size_kb": round(total_size / 1024, 1),
        "evictions": evictions,
        "invalidations": invalidations,
        "puts": puts,
        "ttl_seconds": CACHE_TTL,
        "avg_access_count": round(avg_accesses, 1),
        "top_entries": top_entries
    }


def invalidate_cache(db, pattern=None):
    """Invalidate cache entries. If pattern given, only matching; else all."""
    if pattern:
        deleted = db.execute(
            "DELETE FROM cache WHERE prompt LIKE ?", (f"%{pattern}%",)
        ).rowcount
    else:
        deleted = db.execute("DELETE FROM cache").rowcount

    db.execute(
        "UPDATE cache_stats SET total_invalidations=total_invalidations+? WHERE id=1",
        (deleted,)
    )
    db.commit()

    return {
        "status": "ok",
        "invalidated": deleted,
        "pattern": pattern or "ALL",
        "remaining": db.execute("SELECT COUNT(*) FROM cache").fetchone()[0]
    }


def once(db):
    """Run once: show stats, do demo put/get."""
    # Demo: put a test entry
    cache_put(db, "test_prompt_once", "This is a cached test response", "demo")

    # Try to get it back
    get_result = cache_get(db, "test_prompt_once")

    stats = get_stats(db)

    return {
        "status": "ok", "mode": "once",
        "demo_get": get_result,
        "cache_stats": stats
    }


def main():
    parser = argparse.ArgumentParser(description="Response Cache (#199) — SHA256 prompt caching")
    parser.add_argument("--get", type=str, help="Get cached response for prompt")
    parser.add_argument("--put", nargs=2, metavar=("PROMPT", "RESPONSE"), help="Store prompt/response pair")
    parser.add_argument("--stats", action="store_true", help="Show cache statistics")
    parser.add_argument("--invalidate", type=str, nargs="?", const="",
                        help="Invalidate cache (optional pattern)")
    parser.add_argument("--once", action="store_true", help="Run once with demo")
    args = parser.parse_args()

    db = init_db()

    if args.get:
        result = cache_get(db, args.get)
    elif args.put:
        result = cache_put(db, args.put[0], args.put[1])
    elif args.stats:
        result = get_stats(db)
    elif args.invalidate is not None:
        result = invalidate_cache(db, args.invalidate if args.invalidate else None)
    elif args.once:
        result = once(db)
    else:
        parser.print_help()
        return

    print(json.dumps(result, indent=2, default=str))
    db.close()


if __name__ == "__main__":
    main()
