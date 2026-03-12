"""Tests for src/rate_limiter.py — Token-bucket rate limiting.

Covers: _Bucket, RateLimiter (configure_node, allow, wait_time,
get_node_stats, get_all_stats, reset_node, reset_all),
rate_limiter singleton.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.rate_limiter import RateLimiter, rate_limiter


# ===========================================================================
# RateLimiter — allow
# ===========================================================================

class TestAllow:
    def test_initial_burst(self):
        rl = RateLimiter(default_rps=10, default_burst=5)
        for _ in range(5):
            assert rl.allow("M1") is True
        # 6th should be denied (burst exhausted)
        assert rl.allow("M1") is False

    def test_different_nodes(self):
        rl = RateLimiter(default_rps=10, default_burst=2)
        assert rl.allow("M1") is True
        assert rl.allow("M1") is True
        assert rl.allow("M1") is False
        # M2 has its own bucket
        assert rl.allow("M2") is True

    def test_cost(self):
        rl = RateLimiter(default_rps=10, default_burst=5)
        assert rl.allow("M1", cost=3) is True
        assert rl.allow("M1", cost=3) is False  # only 2 tokens left


# ===========================================================================
# RateLimiter — wait_time
# ===========================================================================

class TestWaitTime:
    def test_no_wait_when_available(self):
        rl = RateLimiter(default_rps=10, default_burst=5)
        assert rl.wait_time("M1") == 0.0

    def test_wait_when_empty(self):
        rl = RateLimiter(default_rps=10, default_burst=1)
        rl.allow("M1")  # consume the 1 token
        wait = rl.wait_time("M1")
        assert wait > 0


# ===========================================================================
# RateLimiter — configure_node
# ===========================================================================

class TestConfigureNode:
    def test_configure(self):
        rl = RateLimiter(default_rps=10, default_burst=20)
        rl.configure_node("M1", rps=5, burst=10)
        stats = rl.get_node_stats("M1")
        assert stats["refill_rate"] == 5
        assert stats["capacity"] == 10

    def test_configure_updates_existing(self):
        rl = RateLimiter(default_rps=10, default_burst=20)
        rl.allow("M1")  # creates bucket
        rl.configure_node("M1", rps=2, burst=4)
        stats = rl.get_node_stats("M1")
        assert stats["refill_rate"] == 2
        assert stats["capacity"] == 4


# ===========================================================================
# RateLimiter — stats
# ===========================================================================

class TestStats:
    def test_node_stats(self):
        rl = RateLimiter(default_rps=10, default_burst=5)
        rl.allow("M1")
        rl.allow("M1")
        stats = rl.get_node_stats("M1")
        assert stats["total_allowed"] == 2
        assert stats["total_denied"] == 0

    def test_all_stats(self):
        rl = RateLimiter(default_rps=10, default_burst=5)
        rl.allow("M1")
        rl.allow("M2")
        stats = rl.get_all_stats()
        assert stats["total_allowed"] == 2
        assert "M1" in stats["nodes"]
        assert "M2" in stats["nodes"]


# ===========================================================================
# RateLimiter — reset
# ===========================================================================

class TestReset:
    def test_reset_node(self):
        rl = RateLimiter(default_rps=10, default_burst=2)
        rl.allow("M1")
        rl.allow("M1")
        assert rl.allow("M1") is False
        rl.reset_node("M1")
        assert rl.allow("M1") is True
        stats = rl.get_node_stats("M1")
        assert stats["total_allowed"] == 1  # reset counters

    def test_reset_all(self):
        rl = RateLimiter(default_rps=10, default_burst=5)
        rl.allow("M1")
        rl.allow("M2")
        rl.reset_all()
        stats = rl.get_all_stats()
        assert stats["nodes"] == {}


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert rate_limiter is not None
        assert isinstance(rate_limiter, RateLimiter)
