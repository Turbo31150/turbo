"""Tests for src/circuit_breaker.py — Circuit Breaker pattern implementation.

Covers:
- CircuitState enum values
- CircuitStats dataclass defaults
- CircuitBreaker state transitions (CLOSED -> OPEN -> HALF_OPEN -> CLOSED)
- Failure threshold triggering
- Recovery timeout and half-open testing
- Force reset behavior
- get_status() output structure
- ClusterCircuitBreakers manager (get/create, available nodes, reset)
- retry_with_backoff (success, fallback, exhaustion)
- Global cluster_breakers instance
"""

import asyncio
import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.circuit_breaker import (
    CircuitBreaker,
    CircuitState,
    CircuitStats,
    ClusterCircuitBreakers,
    cluster_breakers,
    retry_with_backoff,
)


# ── CircuitState Enum ────────────────────────────────────────────────────


class TestCircuitState:
    def test_closed_value(self):
        assert CircuitState.CLOSED.value == "closed"

    def test_open_value(self):
        assert CircuitState.OPEN.value == "open"

    def test_half_open_value(self):
        assert CircuitState.HALF_OPEN.value == "half_open"

    def test_enum_members_count(self):
        assert len(CircuitState) == 3


# ── CircuitStats Dataclass ───────────────────────────────────────────────


class TestCircuitStats:
    def test_defaults(self):
        stats = CircuitStats()
        assert stats.total_calls == 0
        assert stats.total_failures == 0
        assert stats.consecutive_failures == 0
        assert stats.last_failure_time == 0
        assert stats.last_success_time == 0
        assert stats.time_opened == 0
        assert stats.times_tripped == 0

    def test_custom_values(self):
        stats = CircuitStats(total_calls=10, total_failures=3, consecutive_failures=2)
        assert stats.total_calls == 10
        assert stats.total_failures == 3
        assert stats.consecutive_failures == 2


# ── CircuitBreaker — Basic ───────────────────────────────────────────────


class TestCircuitBreakerBasic:
    def test_initial_state_is_closed(self):
        cb = CircuitBreaker("M1")
        assert cb.state == CircuitState.CLOSED

    def test_constructor_defaults(self):
        cb = CircuitBreaker("M1")
        assert cb.node_name == "M1"
        assert cb.failure_threshold == 3
        assert cb.recovery_timeout == 60.0
        assert cb.half_open_max == 1

    def test_constructor_custom_params(self):
        cb = CircuitBreaker("M2", failure_threshold=5, recovery_timeout=30.0, half_open_max=2)
        assert cb.failure_threshold == 5
        assert cb.recovery_timeout == 30.0
        assert cb.half_open_max == 2

    def test_can_execute_when_closed(self):
        cb = CircuitBreaker("M1")
        assert cb.can_execute() is True

    def test_record_success_increments_total_calls(self):
        cb = CircuitBreaker("M1")
        cb.record_success()
        assert cb._stats.total_calls == 1
        assert cb._stats.consecutive_failures == 0

    def test_record_failure_increments_counters(self):
        cb = CircuitBreaker("M1")
        cb.record_failure()
        assert cb._stats.total_calls == 1
        assert cb._stats.total_failures == 1
        assert cb._stats.consecutive_failures == 1


# ── CircuitBreaker — State Transitions ───────────────────────────────────


class TestCircuitBreakerTransitions:
    def test_closed_to_open_on_threshold(self):
        cb = CircuitBreaker("M1", failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.CLOSED
        cb.record_failure()  # threshold reached
        assert cb.state == CircuitState.OPEN

    def test_success_resets_consecutive_failures(self):
        cb = CircuitBreaker("M1", failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()  # resets consecutive
        cb.record_failure()
        assert cb.state == CircuitState.CLOSED  # only 1 consecutive now

    def test_open_blocks_execution(self):
        cb = CircuitBreaker("M1", failure_threshold=2)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert cb.can_execute() is False

    @patch("src.circuit_breaker.time.monotonic")
    def test_open_to_half_open_after_recovery_timeout(self, mock_time):
        cb = CircuitBreaker("M1", failure_threshold=2, recovery_timeout=10.0)
        # Two failures at t=100
        mock_time.return_value = 100.0
        cb.record_failure()
        cb.record_failure()
        assert cb._state == CircuitState.OPEN
        # Check state at t=111 (after 10s recovery)
        mock_time.return_value = 111.0
        assert cb.state == CircuitState.HALF_OPEN

    @patch("src.circuit_breaker.time.monotonic")
    def test_half_open_allows_one_request(self, mock_time):
        cb = CircuitBreaker("M1", failure_threshold=2, recovery_timeout=5.0, half_open_max=1)
        mock_time.return_value = 100.0
        cb.record_failure()
        cb.record_failure()
        # Move past recovery
        mock_time.return_value = 106.0
        assert cb.state == CircuitState.HALF_OPEN
        assert cb.can_execute() is True
        # Second call in half_open should be blocked
        assert cb.can_execute() is False

    @patch("src.circuit_breaker.time.monotonic")
    def test_half_open_to_closed_on_success(self, mock_time):
        cb = CircuitBreaker("M1", failure_threshold=2, recovery_timeout=5.0)
        mock_time.return_value = 100.0
        cb.record_failure()
        cb.record_failure()
        mock_time.return_value = 106.0
        assert cb.state == CircuitState.HALF_OPEN
        cb.can_execute()  # consume the half-open slot
        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    @patch("src.circuit_breaker.time.monotonic")
    def test_half_open_to_open_on_failure(self, mock_time):
        cb = CircuitBreaker("M1", failure_threshold=2, recovery_timeout=5.0)
        mock_time.return_value = 100.0
        cb.record_failure()
        cb.record_failure()
        mock_time.return_value = 106.0
        assert cb.state == CircuitState.HALF_OPEN
        cb.can_execute()
        mock_time.return_value = 107.0
        cb.record_failure()
        assert cb._state == CircuitState.OPEN
        assert cb._stats.times_tripped == 2  # tripped twice

    def test_times_tripped_increments(self):
        cb = CircuitBreaker("M1", failure_threshold=1)
        cb.record_failure()
        assert cb._stats.times_tripped == 1


# ── CircuitBreaker — Reset ───────────────────────────────────────────────


class TestCircuitBreakerReset:
    def test_force_reset_from_open(self):
        cb = CircuitBreaker("M1", failure_threshold=2)
        cb.record_failure()
        cb.record_failure()
        assert cb._state == CircuitState.OPEN
        cb.reset()
        assert cb.state == CircuitState.CLOSED
        assert cb._stats.consecutive_failures == 0
        assert cb._half_open_calls == 0
        assert cb.can_execute() is True

    def test_reset_preserves_total_stats(self):
        cb = CircuitBreaker("M1", failure_threshold=2)
        cb.record_failure()
        cb.record_failure()
        cb.reset()
        # total_calls and total_failures are NOT reset
        assert cb._stats.total_calls == 2
        assert cb._stats.total_failures == 2


# ── CircuitBreaker — get_status ──────────────────────────────────────────


class TestCircuitBreakerStatus:
    def test_status_keys(self):
        cb = CircuitBreaker("M1")
        status = cb.get_status()
        expected_keys = {
            "node", "state", "consecutive_failures", "total_failures",
            "total_calls", "times_tripped", "failure_rate", "recovery_in",
        }
        assert set(status.keys()) == expected_keys

    def test_status_values_initial(self):
        cb = CircuitBreaker("TestNode")
        status = cb.get_status()
        assert status["node"] == "TestNode"
        assert status["state"] == "closed"
        assert status["consecutive_failures"] == 0
        assert status["total_failures"] == 0
        assert status["total_calls"] == 0
        assert status["times_tripped"] == 0
        assert status["failure_rate"] == "0.0%"

    def test_status_failure_rate_after_failures(self):
        cb = CircuitBreaker("M1", failure_threshold=10)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        status = cb.get_status()
        # 2 failures out of 3 calls = 66.7%
        assert status["failure_rate"] == "66.7%"

    @patch("src.circuit_breaker.time.monotonic")
    def test_status_recovery_in_when_open(self, mock_time):
        cb = CircuitBreaker("M1", failure_threshold=2, recovery_timeout=60.0)
        mock_time.return_value = 1000.0
        cb.record_failure()
        cb.record_failure()
        mock_time.return_value = 1020.0  # 20s elapsed
        status = cb.get_status()
        assert status["state"] == "open"
        # recovery_in should be ~40s (60 - 20)
        assert 39.0 <= status["recovery_in"] <= 41.0


# ── ClusterCircuitBreakers ───────────────────────────────────────────────


class TestClusterCircuitBreakers:
    def test_get_breaker_creates_new(self):
        cluster = ClusterCircuitBreakers()
        cb = cluster.get_breaker("M1")
        assert isinstance(cb, CircuitBreaker)
        assert cb.node_name == "M1"

    def test_get_breaker_returns_same_instance(self):
        cluster = ClusterCircuitBreakers()
        cb1 = cluster.get_breaker("M1")
        cb2 = cluster.get_breaker("M1")
        assert cb1 is cb2

    def test_inherits_config(self):
        cluster = ClusterCircuitBreakers(failure_threshold=5, recovery_timeout=120.0)
        cb = cluster.get_breaker("M1")
        assert cb.failure_threshold == 5
        assert cb.recovery_timeout == 120.0

    def test_can_execute_delegates(self):
        cluster = ClusterCircuitBreakers(failure_threshold=2)
        assert cluster.can_execute("M1") is True
        cluster.record_failure("M1")
        cluster.record_failure("M1")
        assert cluster.can_execute("M1") is False

    def test_record_success_delegates(self):
        cluster = ClusterCircuitBreakers(failure_threshold=3)
        cluster.record_failure("M1")
        cluster.record_failure("M1")
        cluster.record_success("M1")
        cb = cluster.get_breaker("M1")
        assert cb._stats.consecutive_failures == 0

    def test_get_available_nodes(self):
        cluster = ClusterCircuitBreakers(failure_threshold=1)
        cluster.record_failure("M2")  # M2 now OPEN
        available = cluster.get_available_nodes(["M1", "M2", "M3"])
        assert "M1" in available
        assert "M2" not in available
        assert "M3" in available

    def test_get_best_available(self):
        cluster = ClusterCircuitBreakers(failure_threshold=1)
        cluster.record_failure("M1")  # M1 now OPEN
        best = cluster.get_best_available(["M1", "M2", "M3"])
        assert best == "M2"

    def test_get_best_available_none_when_all_down(self):
        cluster = ClusterCircuitBreakers(failure_threshold=1)
        cluster.record_failure("M1")
        cluster.record_failure("M2")
        best = cluster.get_best_available(["M1", "M2"])
        assert best is None

    def test_get_all_status(self):
        cluster = ClusterCircuitBreakers()
        cluster.get_breaker("M1")
        cluster.get_breaker("M2")
        statuses = cluster.get_all_status()
        assert len(statuses) == 2
        nodes = {s["node"] for s in statuses}
        assert nodes == {"M1", "M2"}

    def test_reset_all(self):
        cluster = ClusterCircuitBreakers(failure_threshold=1)
        cluster.record_failure("M1")
        cluster.record_failure("M2")
        assert cluster.can_execute("M1") is False
        assert cluster.can_execute("M2") is False
        cluster.reset_all()
        assert cluster.can_execute("M1") is True
        assert cluster.can_execute("M2") is True

    def test_reset_node(self):
        cluster = ClusterCircuitBreakers(failure_threshold=1)
        cluster.record_failure("M1")
        cluster.record_failure("M2")
        cluster.reset_node("M1")
        assert cluster.can_execute("M1") is True
        assert cluster.can_execute("M2") is False

    def test_reset_node_nonexistent_is_noop(self):
        cluster = ClusterCircuitBreakers()
        cluster.reset_node("NONEXISTENT")  # should not raise


# ── retry_with_backoff ───────────────────────────────────────────────────


class TestRetryWithBackoff:
    @pytest.mark.asyncio
    async def test_success_on_first_try(self):
        func = AsyncMock(return_value="ok")
        breakers = ClusterCircuitBreakers()
        result = await retry_with_backoff(func, ["M1"], breakers, max_retries=3)
        assert result == "ok"
        func.assert_awaited_once_with("M1")

    @pytest.mark.asyncio
    async def test_retries_then_succeeds(self):
        func = AsyncMock(side_effect=[Exception("fail"), "ok"])
        breakers = ClusterCircuitBreakers()
        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await retry_with_backoff(
                func, ["M1"], breakers, max_retries=3, base_delay=0.01
            )
        assert result == "ok"
        assert func.await_count == 2

    @pytest.mark.asyncio
    async def test_falls_back_to_next_node(self):
        call_log = []

        async def mock_func(node, **kw):
            call_log.append(node)
            if node == "M1":
                raise Exception("M1 down")
            return f"{node} ok"

        breakers = ClusterCircuitBreakers()
        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await retry_with_backoff(
                mock_func, ["M1", "M2"], breakers, max_retries=1
            )
        assert result == "M2 ok"
        assert "M1" in call_log
        assert "M2" in call_log

    @pytest.mark.asyncio
    async def test_all_nodes_exhausted_raises(self):
        func = AsyncMock(side_effect=Exception("all down"))
        breakers = ClusterCircuitBreakers()
        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(RuntimeError, match="All nodes exhausted"):
                await retry_with_backoff(
                    func, ["M1", "M2"], breakers, max_retries=1
                )

    @pytest.mark.asyncio
    async def test_all_tripped_forces_half_open(self):
        """When all breakers are OPEN, retry_with_backoff tries the first candidate anyway."""
        func = AsyncMock(return_value="recovered")
        breakers = ClusterCircuitBreakers(failure_threshold=1)
        breakers.record_failure("M1")
        breakers.record_failure("M2")
        # Both OPEN, but function forces first node
        result = await retry_with_backoff(func, ["M1", "M2"], breakers, max_retries=1)
        assert result == "recovered"
        func.assert_awaited_once_with("M1")

    @pytest.mark.asyncio
    async def test_records_failure_in_breakers(self):
        func = AsyncMock(side_effect=Exception("err"))
        breakers = ClusterCircuitBreakers(failure_threshold=10)
        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(RuntimeError):
                await retry_with_backoff(func, ["M1"], breakers, max_retries=3)
        cb = breakers.get_breaker("M1")
        assert cb._stats.total_failures == 3

    @pytest.mark.asyncio
    async def test_records_success_in_breakers(self):
        func = AsyncMock(return_value="ok")
        breakers = ClusterCircuitBreakers()
        await retry_with_backoff(func, ["M1"], breakers, max_retries=1)
        cb = breakers.get_breaker("M1")
        assert cb._stats.total_calls == 1
        assert cb._stats.total_failures == 0


# ── Global Instance ──────────────────────────────────────────────────────


class TestGlobalInstance:
    def test_cluster_breakers_exists(self):
        assert isinstance(cluster_breakers, ClusterCircuitBreakers)

    def test_cluster_breakers_defaults(self):
        assert cluster_breakers.failure_threshold == 3
        assert cluster_breakers.recovery_timeout == 60.0
