"""Tests for src/retry_manager.py — Retry with backoff and circuit breaker.

Covers: RetryConfig, CircuitBreaker (state, record_success, record_failure,
is_allowed, reset), RetryManager (get_breaker, configure_breaker, execute,
execute_sync, get_stats, reset_all), retry_manager singleton.
Uses mocked sleep/asyncio.sleep for speed.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from unittest.mock import patch, AsyncMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.retry_manager import RetryConfig, CircuitBreaker, RetryManager, retry_manager


# ===========================================================================
# RetryConfig
# ===========================================================================

class TestRetryConfig:
    def test_defaults(self):
        rc = RetryConfig()
        assert rc.max_retries == 3
        assert rc.base_delay_s == 1.0
        assert rc.backoff_factor == 2.0
        assert rc.jitter is True


# ===========================================================================
# CircuitBreaker
# ===========================================================================

class TestCircuitBreaker:
    def test_initial_state(self):
        cb = CircuitBreaker()
        assert cb.state == "closed"
        assert cb.is_allowed() is True

    def test_record_success_resets(self):
        cb = CircuitBreaker(failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        assert cb._failures == 0
        assert cb.state == "closed"

    def test_record_failure_opens(self):
        cb = CircuitBreaker(failure_threshold=3)
        for _ in range(3):
            cb.record_failure()
        assert cb.state == "open"
        assert cb.is_allowed() is False
        assert cb._total_tripped == 1

    def test_half_open_after_timeout(self):
        cb = CircuitBreaker(failure_threshold=2, reset_timeout_s=0.1)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == "open"
        # Simulate timeout
        cb._last_failure = time.time() - 1
        assert cb.state == "half_open"
        assert cb.is_allowed() is True

    def test_reset(self):
        cb = CircuitBreaker(failure_threshold=2)
        cb.record_failure()
        cb.record_failure()
        cb.reset()
        assert cb.state == "closed"
        assert cb._failures == 0


# ===========================================================================
# RetryManager — breakers
# ===========================================================================

class TestBreakerManagement:
    def test_get_breaker_creates(self):
        rm = RetryManager()
        cb = rm.get_breaker("test")
        assert isinstance(cb, CircuitBreaker)
        assert rm.get_breaker("test") is cb

    def test_configure_breaker(self):
        rm = RetryManager()
        rm.configure_breaker("api", failure_threshold=10, reset_timeout_s=120)
        cb = rm.get_breaker("api")
        assert cb.failure_threshold == 10
        assert cb.reset_timeout_s == 120


# ===========================================================================
# RetryManager — execute (async)
# ===========================================================================

class TestExecuteAsync:
    @pytest.mark.asyncio
    async def test_success_first_try(self):
        rm = RetryManager()
        func = AsyncMock(return_value="ok")
        result = await rm.execute(func, name="test")
        assert result == "ok"
        assert rm._stats["total_successes"] == 1

    @pytest.mark.asyncio
    async def test_retries_then_succeeds(self):
        rm = RetryManager()
        call_count = 0
        async def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("fail")
            return "ok"
        cfg = RetryConfig(max_retries=3, base_delay_s=0.001, jitter=False)
        result = await rm.execute(flaky, name="test", config=cfg)
        assert result == "ok"
        assert call_count == 3
        assert rm._stats["total_retries"] == 2

    @pytest.mark.asyncio
    async def test_all_retries_exhausted(self):
        rm = RetryManager()
        async def always_fail():
            raise ValueError("always fails")
        cfg = RetryConfig(max_retries=2, base_delay_s=0.001, jitter=False)
        with pytest.raises(ValueError, match="always fails"):
            await rm.execute(always_fail, name="test", config=cfg)
        assert rm._stats["total_failures"] == 1

    @pytest.mark.asyncio
    async def test_circuit_breaker_blocks(self):
        rm = RetryManager()
        rm.configure_breaker("test", failure_threshold=1)
        rm.get_breaker("test").record_failure()
        async def func():
            return "ok"
        with pytest.raises(RuntimeError, match="Circuit breaker open"):
            await rm.execute(func, name="test")


# ===========================================================================
# RetryManager — execute_sync
# ===========================================================================

class TestExecuteSync:
    def test_success_first_try(self):
        rm = RetryManager()
        result = rm.execute_sync(lambda: "ok", name="test")
        assert result == "ok"
        assert rm._stats["total_successes"] == 1

    def test_retries_then_succeeds(self):
        rm = RetryManager()
        call_count = 0
        def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("fail")
            return "ok"
        cfg = RetryConfig(max_retries=3, base_delay_s=0.001, jitter=False)
        result = rm.execute_sync(flaky, name="test", config=cfg)
        assert result == "ok"
        assert call_count == 2

    def test_all_retries_exhausted(self):
        rm = RetryManager()
        def always_fail():
            raise ValueError("boom")
        cfg = RetryConfig(max_retries=1, base_delay_s=0.001, jitter=False)
        with pytest.raises(ValueError, match="boom"):
            rm.execute_sync(always_fail, name="test", config=cfg)
        assert rm._stats["total_failures"] == 1

    def test_circuit_breaker_blocks_sync(self):
        rm = RetryManager()
        rm.configure_breaker("test", failure_threshold=1)
        rm.get_breaker("test").record_failure()
        with pytest.raises(RuntimeError, match="Circuit breaker open"):
            rm.execute_sync(lambda: "ok", name="test")


# ===========================================================================
# RetryManager — stats & reset
# ===========================================================================

class TestStatsReset:
    def test_stats(self):
        rm = RetryManager()
        rm.configure_breaker("api", failure_threshold=3)
        rm.get_breaker("api").record_failure()
        stats = rm.get_stats()
        assert "breakers" in stats
        assert stats["breakers"]["api"]["failures"] == 1

    def test_reset_all(self):
        rm = RetryManager()
        rm.configure_breaker("api")
        rm.get_breaker("api").record_failure()
        rm._stats["total_retries"] = 10
        rm.reset_all()
        assert rm.get_breaker("api").state == "closed"
        assert rm._stats["total_retries"] == 0


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert retry_manager is not None
        assert isinstance(retry_manager, RetryManager)
