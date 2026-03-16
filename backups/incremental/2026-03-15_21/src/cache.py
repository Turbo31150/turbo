"""JARVIS Distributed Cache — LRU cache with TTL for cluster responses.

Reduces cluster latency by caching frequent queries.
Thread-safe, with per-node and per-category tracking.
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any


__all__ = [
    "CacheEntry",
    "ConnectionPool",
    "DistributedCache",
]

logger = logging.getLogger("jarvis.cache")


@dataclass
class CacheEntry:
    """A single cache entry with metadata."""
    key: str
    value: Any
    node: str
    category: str
    created_at: float
    ttl: float
    hits: int = 0

    @property
    def is_expired(self) -> bool:
        return time.monotonic() - self.created_at > self.ttl


class DistributedCache:
    """LRU cache with TTL for cluster query results.

    Features:
    - Per-category TTL (code responses cached longer than web searches)
    - Hit/miss tracking for analytics
    - Thread-safe operations
    - Automatic eviction of expired entries
    """

    # Default TTLs per category (seconds)
    DEFAULT_TTLS = {
        "code": 600,           # 10 min — code responses change slowly
        "analysis": 300,       # 5 min
        "trading": 30,         # 30s — market data changes fast
        "web": 60,             # 1 min — web results
        "voice_correction": 3600,  # 1h — corrections are stable
        "system": 120,         # 2 min
        "consensus": 180,      # 3 min
        "default": 120,        # 2 min fallback
    }

    def __init__(self, max_size: int = 500):
        self.max_size = max_size
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.Lock()
        self._stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "expirations": 0,
        }

    def _make_key(self, prompt: str, node: str = "", model: str = "") -> str:
        """Generate a cache key from query parameters."""
        raw = f"{prompt.strip().lower()}|{node}|{model}"
        return hashlib.md5(raw.encode()).hexdigest()

    def get(self, prompt: str, node: str = "", model: str = "") -> Any | None:
        """Get a cached response. Returns None on miss or expiration."""
        key = self._make_key(prompt, node, model)

        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                self._stats["misses"] += 1
                return None

            if entry.is_expired:
                del self._cache[key]
                self._stats["expirations"] += 1
                self._stats["misses"] += 1
                return None

            # Move to end (most recently used)
            self._cache.move_to_end(key)
            entry.hits += 1
            self._stats["hits"] += 1
            return entry.value

    def put(
        self,
        prompt: str,
        value: Any,
        node: str = "",
        model: str = "",
        category: str = "default",
        ttl: float | None = None,
    ) -> None:
        """Store a response in the cache."""
        key = self._make_key(prompt, node, model)
        effective_ttl = ttl if ttl is not None else self.DEFAULT_TTLS.get(category, self.DEFAULT_TTLS["default"])

        entry = CacheEntry(
            key=key,
            value=value,
            node=node,
            category=category,
            created_at=time.monotonic(),
            ttl=effective_ttl,
        )

        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                self._cache[key] = entry
            else:
                self._cache[key] = entry
                # Evict LRU if over max size
                while len(self._cache) > self.max_size:
                    self._cache.popitem(last=False)
                    self._stats["evictions"] += 1

    def invalidate(self, prompt: str, node: str = "", model: str = "") -> bool:
        """Remove a specific entry from cache."""
        key = self._make_key(prompt, node, model)
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def invalidate_node(self, node: str) -> int:
        """Invalidate all entries from a specific node."""
        count = 0
        with self._lock:
            keys_to_remove = [k for k, v in self._cache.items() if v.node == node]
            for k in keys_to_remove:
                del self._cache[k]
                count += 1
        return count

    def invalidate_category(self, category: str) -> int:
        """Invalidate all entries for a category."""
        count = 0
        with self._lock:
            keys_to_remove = [k for k, v in self._cache.items() if v.category == category]
            for k in keys_to_remove:
                del self._cache[k]
                count += 1
        return count

    def cleanup_expired(self) -> int:
        """Remove all expired entries. Returns count removed."""
        count = 0
        with self._lock:
            keys_to_remove = [k for k, v in self._cache.items() if v.is_expired]
            for k in keys_to_remove:
                del self._cache[k]
                count += 1
                self._stats["expirations"] += 1
        return count

    def clear(self) -> int:
        """Clear entire cache. Returns count removed."""
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            return count

    def get_stats(self) -> dict:
        """Get cache performance statistics."""
        with self._lock:
            total = self._stats["hits"] + self._stats["misses"]
            hit_rate = self._stats["hits"] / max(1, total)

            # Category breakdown
            categories: dict[str, int] = {}
            nodes: dict[str, int] = {}
            for entry in self._cache.values():
                categories[entry.category] = categories.get(entry.category, 0) + 1
                nodes[entry.node] = nodes.get(entry.node, 0) + 1

            return {
                "size": len(self._cache),
                "max_size": self.max_size,
                "hit_rate": f"{hit_rate:.1%}",
                "hits": self._stats["hits"],
                "misses": self._stats["misses"],
                "evictions": self._stats["evictions"],
                "expirations": self._stats["expirations"],
                "by_category": categories,
                "by_node": nodes,
            }


# ── Global cache instance ────────────────────────────────────────────────
cluster_cache = DistributedCache(max_size=500)


# ── Connection Pool Manager ──────────────────────────────────────────────

class ConnectionPool:
    """Persistent httpx connection pool for cluster nodes.

    Avoids TCP handshake overhead for repeated calls to the same node.
    """

    def __init__(self):
        self._pools: dict[str, Any] = {}
        self._lock = threading.Lock()

    async def get_client(self, base_url: str, timeout: float = 120.0):
        """Get or create a persistent httpx client for a base URL."""
        import httpx

        with self._lock:
            if base_url in self._pools:
                client = self._pools[base_url]
                if not client.is_closed:
                    return client
                # Client was closed, remove it
                del self._pools[base_url]

            client = httpx.AsyncClient(
                base_url=base_url,
                timeout=timeout,
                limits=httpx.Limits(
                    max_keepalive_connections=5,
                    max_connections=10,
                    keepalive_expiry=30,
                ),
                http2=False,  # HTTP/2 not needed for local inference
            )
            self._pools[base_url] = client
            return client

    async def close_all(self):
        """Close all connection pools."""
        with self._lock:
            for client in self._pools.values():
                if not client.is_closed:
                    await client.aclose()
            self._pools.clear()

    def get_pool_stats(self) -> dict:
        """Get connection pool statistics."""
        with self._lock:
            return {
                "active_pools": len(self._pools),
                "nodes": list(self._pools.keys()),
            }


# Global connection pool
pool = ConnectionPool()
