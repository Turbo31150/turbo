"""Tests for src/cache_manager.py — Multi-layer caching with TTL and LRU.

Covers: CacheEntry, CacheManager (get, set, delete, clear, _l1_put, _l2_put,
_l2_get, get_namespaces, get_stats), cache_manager singleton.
Uses tmp_path for L2 disk isolation.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.cache_manager import CacheEntry, CacheManager, cache_manager


# ===========================================================================
# CacheEntry
# ===========================================================================

class TestCacheEntry:
    def test_not_expired(self):
        e = CacheEntry(value="v", created_at=time.time(), ttl_s=9999)
        assert e.expired is False

    def test_expired(self):
        e = CacheEntry(value="v", created_at=time.time() - 100, ttl_s=1)
        assert e.expired is True

    def test_no_ttl_never_expires(self):
        e = CacheEntry(value="v", created_at=time.time() - 99999, ttl_s=0)
        assert e.expired is False


# ===========================================================================
# CacheManager — get/set (L1 only)
# ===========================================================================

class TestGetSetL1:
    def test_set_and_get(self, tmp_path):
        cm = CacheManager(l2_dir=tmp_path / "cache")
        cm.set("key", "value")
        assert cm.get("key") == "value"
        assert cm._stats["l1_hits"] == 1

    def test_get_miss(self, tmp_path):
        cm = CacheManager(l2_dir=tmp_path / "cache")
        assert cm.get("nonexistent") is None
        assert cm._stats["l1_misses"] >= 1

    def test_set_with_namespace(self, tmp_path):
        cm = CacheManager(l2_dir=tmp_path / "cache")
        cm.set("key", "v1", namespace="ns1")
        cm.set("key", "v2", namespace="ns2")
        assert cm.get("key", namespace="ns1") == "v1"
        assert cm.get("key", namespace="ns2") == "v2"

    def test_ttl_expired_returns_none(self, tmp_path):
        cm = CacheManager(l2_dir=tmp_path / "cache")
        cm.set("temp", "val", ttl_s=1)
        # Manually expire L1
        ns = cm._ns("default")
        ns["temp"].created_at = time.time() - 10
        # Also remove L2 file so fallback doesn't find it
        l2_path = cm._l2_path("temp", "default")
        if l2_path.exists():
            l2_path.unlink()
        assert cm.get("temp") is None

    def test_lru_eviction(self, tmp_path):
        cm = CacheManager(l1_max_size=3, l2_dir=tmp_path / "cache")
        cm.set("a", 1)
        cm.set("b", 2)
        cm.set("c", 3)
        cm.set("d", 4)  # evicts "a"
        assert cm.get("a") is None or cm._stats["l1_misses"] >= 1
        assert cm._stats["evictions"] >= 1


# ===========================================================================
# CacheManager — L2 persistence
# ===========================================================================

class TestL2:
    def test_l2_persists(self, tmp_path):
        cm = CacheManager(l2_dir=tmp_path / "cache")
        cm.set("key", "persisted")
        # Clear L1
        cm._l1.clear()
        # Should find in L2
        result = cm.get("key")
        assert result == "persisted"
        assert cm._stats["l2_hits"] >= 1

    def test_l2_miss(self, tmp_path):
        cm = CacheManager(l2_dir=tmp_path / "cache")
        assert cm.get("nope") is None
        assert cm._stats["l2_misses"] >= 1


# ===========================================================================
# CacheManager — delete
# ===========================================================================

class TestDelete:
    def test_delete_existing(self, tmp_path):
        cm = CacheManager(l2_dir=tmp_path / "cache")
        cm.set("key", "val")
        assert cm.delete("key") is True
        assert cm.get("key") is None

    def test_delete_nonexistent(self, tmp_path):
        cm = CacheManager(l2_dir=tmp_path / "cache")
        assert cm.delete("nope") is False


# ===========================================================================
# CacheManager — clear
# ===========================================================================

class TestClear:
    def test_clear_namespace(self, tmp_path):
        cm = CacheManager(l2_dir=tmp_path / "cache")
        cm.set("a", 1, namespace="ns1")
        cm.set("b", 2, namespace="ns2")
        cleared = cm.clear(namespace="ns1")
        assert cleared >= 1
        assert cm.get("a", namespace="ns1") is None
        assert cm.get("b", namespace="ns2") == 2

    def test_clear_all(self, tmp_path):
        cm = CacheManager(l2_dir=tmp_path / "cache")
        cm.set("a", 1, namespace="ns1")
        cm.set("b", 2, namespace="ns2")
        cleared = cm.clear()
        assert cleared >= 2


# ===========================================================================
# CacheManager — namespaces & stats
# ===========================================================================

class TestNamespacesStats:
    def test_get_namespaces(self, tmp_path):
        cm = CacheManager(l2_dir=tmp_path / "cache")
        cm.set("a", 1, namespace="ns1")
        cm.set("b", 2, namespace="ns2")
        ns = cm.get_namespaces()
        assert set(ns) == {"ns1", "ns2"}

    def test_stats(self, tmp_path):
        cm = CacheManager(l2_dir=tmp_path / "cache")
        cm.set("a", 1)
        cm.get("a")
        cm.get("miss")
        stats = cm.get_stats()
        assert stats["sets"] == 1
        assert stats["l1_hits"] >= 1
        assert stats["l1_entries"] >= 1
        assert "hit_rate" in stats

    def test_stats_empty(self, tmp_path):
        cm = CacheManager(l2_dir=tmp_path / "cache")
        stats = cm.get_stats()
        assert stats["l1_entries"] == 0
        assert stats["sets"] == 0


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert cache_manager is not None
        assert isinstance(cache_manager, CacheManager)
