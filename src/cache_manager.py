"""Cache Manager — Multi-layer caching with TTL and LRU eviction.

L1: In-memory dict (fast, limited size)
L2: On-disk JSON (larger, persistent across restarts)
Namespaces isolate cache domains.
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger("jarvis.cache_manager")


@dataclass
class CacheEntry:
    value: Any
    created_at: float
    ttl_s: float
    hits: int = 0

    @property
    def expired(self) -> bool:
        return self.ttl_s > 0 and (time.time() - self.created_at) >= self.ttl_s


class CacheManager:
    """Multi-layer cache with namespaces."""

    def __init__(
        self,
        l1_max_size: int = 500,
        l2_dir: Path | None = None,
        default_ttl_s: float = 300.0,
    ):
        self._l1_max = l1_max_size
        self._l2_dir = l2_dir or Path("data/cache")
        self._default_ttl = default_ttl_s
        self._l1: dict[str, OrderedDict[str, CacheEntry]] = {}
        self._lock = threading.RLock()
        self._stats = {"l1_hits": 0, "l1_misses": 0, "l2_hits": 0, "l2_misses": 0, "sets": 0, "evictions": 0}

    def _ns(self, namespace: str) -> OrderedDict[str, CacheEntry]:
        if namespace not in self._l1:
            self._l1[namespace] = OrderedDict()
        return self._l1[namespace]

    @staticmethod
    def _hash_key(key: str) -> str:
        return hashlib.md5(key.encode()).hexdigest()

    def get(self, key: str, namespace: str = "default") -> Any | None:
        """Get from L1 → L2 fallback. Returns None if miss or expired."""
        with self._lock:
            ns = self._ns(namespace)
            # L1 check
            if key in ns:
                entry = ns[key]
                if entry.expired:
                    del ns[key]
                else:
                    ns.move_to_end(key)
                    entry.hits += 1
                    self._stats["l1_hits"] += 1
                    return entry.value
            self._stats["l1_misses"] += 1

        # L2 check (outside lock for I/O)
        l2_val = self._l2_get(key, namespace)
        if l2_val is not None:
            self._stats["l2_hits"] += 1
            # Promote to L1
            with self._lock:
                self._l1_put(key, l2_val, self._default_ttl, namespace)
            return l2_val
        self._stats["l2_misses"] += 1
        return None

    def set(self, key: str, value: Any, namespace: str = "default", ttl_s: float | None = None) -> None:
        """Store in both L1 and L2."""
        ttl = ttl_s if ttl_s is not None else self._default_ttl
        with self._lock:
            self._l1_put(key, value, ttl, namespace)
        self._l2_put(key, value, namespace)
        self._stats["sets"] += 1

    def delete(self, key: str, namespace: str = "default") -> bool:
        """Delete from both layers."""
        found = False
        with self._lock:
            ns = self._ns(namespace)
            if key in ns:
                del ns[key]
                found = True
        l2_path = self._l2_path(key, namespace)
        if l2_path.exists():
            l2_path.unlink()
            found = True
        return found

    def clear(self, namespace: str | None = None) -> int:
        """Clear a namespace or all. Returns entries cleared."""
        count = 0
        with self._lock:
            if namespace:
                count = len(self._l1.get(namespace, {}))
                self._l1.pop(namespace, None)
            else:
                count = sum(len(ns) for ns in self._l1.values())
                self._l1.clear()
        # L2 clear
        if namespace:
            ns_dir = self._l2_dir / namespace
            if ns_dir.exists():
                for f in ns_dir.glob("*.json"):
                    f.unlink()
                    count += 1
        else:
            if self._l2_dir.exists():
                for f in self._l2_dir.rglob("*.json"):
                    f.unlink()
        return count

    def _l1_put(self, key: str, value: Any, ttl: float, namespace: str) -> None:
        ns = self._ns(namespace)
        ns[key] = CacheEntry(value=value, created_at=time.time(), ttl_s=ttl)
        ns.move_to_end(key)
        while len(ns) > self._l1_max:
            ns.popitem(last=False)
            self._stats["evictions"] += 1

    def _l2_path(self, key: str, namespace: str) -> Path:
        ns_dir = self._l2_dir / namespace
        ns_dir.mkdir(parents=True, exist_ok=True)
        return ns_dir / f"{self._hash_key(key)}.json"

    def _l2_put(self, key: str, value: Any, namespace: str) -> None:
        try:
            path = self._l2_path(key, namespace)
            path.write_text(json.dumps({"key": key, "value": value, "ts": time.time()}), encoding="utf-8")
        except (OSError, TypeError) as e:
            logger.debug("L2 write error for %s: %s", key, e)

    def _l2_get(self, key: str, namespace: str) -> Any | None:
        try:
            path = self._l2_path(key, namespace)
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                if data.get("key") == key:
                    return data.get("value")
        except (OSError, json.JSONDecodeError, KeyError):
            pass
        return None

    def get_namespaces(self) -> list[str]:
        with self._lock:
            return list(self._l1.keys())

    def get_stats(self) -> dict:
        with self._lock:
            total_entries = sum(len(ns) for ns in self._l1.values())
        total_requests = self._stats["l1_hits"] + self._stats["l1_misses"]
        return {
            **self._stats,
            "l1_entries": total_entries,
            "l1_max_size": self._l1_max,
            "namespaces": self.get_namespaces(),
            "hit_rate": round(self._stats["l1_hits"] / max(1, total_requests) * 100, 1),
        }


# ── Singleton ────────────────────────────────────────────────────────────────
cache_manager = CacheManager()
