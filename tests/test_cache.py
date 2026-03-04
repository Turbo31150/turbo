"""Tests for JARVIS cache module."""

import time
import pytest
from src.cache import DistributedCache, ConnectionPool


class TestDistributedCache:
    def test_put_and_get(self):
        cache = DistributedCache(max_size=10)
        cache.put("test prompt", "result", node="M1", category="code")
        assert cache.get("test prompt", node="M1") == "result"

    def test_cache_miss(self):
        cache = DistributedCache(max_size=10)
        assert cache.get("nonexistent") is None

    def test_case_insensitive(self):
        cache = DistributedCache(max_size=10)
        cache.put("Hello World", "result")
        assert cache.get("hello world") == "result"

    def test_ttl_expiration(self):
        cache = DistributedCache(max_size=10)
        cache.put("test", "result", ttl=0.01)  # 10ms TTL
        time.sleep(0.02)
        assert cache.get("test") is None

    def test_lru_eviction(self):
        cache = DistributedCache(max_size=3)
        cache.put("a", "1")
        cache.put("b", "2")
        cache.put("c", "3")
        cache.put("d", "4")  # Should evict "a"
        assert cache.get("a") is None
        assert cache.get("d") == "4"

    def test_invalidate(self):
        cache = DistributedCache(max_size=10)
        cache.put("test", "result")
        assert cache.invalidate("test")
        assert cache.get("test") is None

    def test_invalidate_node(self):
        cache = DistributedCache(max_size=10)
        cache.put("a", "1", node="M1")
        cache.put("b", "2", node="M2")
        count = cache.invalidate_node("M1")
        assert count == 1
        assert cache.get("a", node="M1") is None
        assert cache.get("b", node="M2") == "2"

    def test_invalidate_category(self):
        cache = DistributedCache(max_size=10)
        cache.put("a", "1", category="code")
        cache.put("b", "2", category="trading")
        count = cache.invalidate_category("code")
        assert count == 1

    def test_cleanup_expired(self):
        cache = DistributedCache(max_size=10)
        cache.put("a", "1", ttl=0.01)
        cache.put("b", "2", ttl=3600)
        time.sleep(0.02)
        removed = cache.cleanup_expired()
        assert removed == 1

    def test_stats(self):
        cache = DistributedCache(max_size=10)
        cache.put("a", "1")
        cache.get("a")  # Hit
        cache.get("b")  # Miss
        stats = cache.get_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["size"] == 1

    def test_clear(self):
        cache = DistributedCache(max_size=10)
        cache.put("a", "1")
        cache.put("b", "2")
        count = cache.clear()
        assert count == 2
        assert cache.get("a") is None

    def test_default_ttls(self):
        assert DistributedCache.DEFAULT_TTLS["trading"] < DistributedCache.DEFAULT_TTLS["code"]
        assert DistributedCache.DEFAULT_TTLS["voice_correction"] > DistributedCache.DEFAULT_TTLS["code"]


class TestConnectionPool:
    def test_pool_stats_empty(self):
        pool = ConnectionPool()
        stats = pool.get_pool_stats()
        assert stats["active_pools"] == 0
