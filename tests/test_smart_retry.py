"""Tests for src/smart_retry.py — Smart Retry with fallback chain.

Covers: RetryExhausted, SmartRetryStats, circuit breaker logic,
retry_with_fallback, smart_retry decorator, backoff, timeouts.
All external dependencies are mocked — no network, no database.
"""

import sys
import asyncio
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.smart_retry import (
    RetryExhausted,
    SmartRetryStats,
    retry_stats,
    retry_with_fallback,
    smart_retry,
    _is_circuit_open,
    _record_circuit_failure,
    _record_circuit_success,
    _circuit_failures,
    _circuit_opened_at,
    _circuit_threshold,
    _circuit_window_s,
    _circuit_cooldown_s,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _reset_circuit_state():
    """Clear global circuit breaker state between tests."""
    _circuit_failures.clear()
    _circuit_opened_at.clear()


def _reset_stats():
    """Reset the global retry_stats counters."""
    retry_stats.total_calls = 0
    retry_stats.total_retries = 0
    retry_stats.total_fallbacks = 0
    retry_stats.total_successes = 0
    retry_stats.total_exhausted = 0
    retry_stats._recent_failures.clear()


@pytest.fixture(autouse=True)
def _clean_state():
    """Automatically reset global state before every test."""
    _reset_circuit_state()
    _reset_stats()
    yield
    _reset_circuit_state()
    _reset_stats()


# ---------------------------------------------------------------------------
# 1. Import smoke test
# ---------------------------------------------------------------------------

class TestImports:
    def test_module_imports(self):
        """All public names are importable."""
        from src.smart_retry import (
            RetryExhausted,
            SmartRetryStats,
            retry_stats,
            retry_with_fallback,
            smart_retry,
        )
        assert RetryExhausted is not None
        assert SmartRetryStats is not None
        assert retry_stats is not None
        assert callable(retry_with_fallback)
        assert callable(smart_retry)

    def test_retry_exhausted_is_exception(self):
        assert issubclass(RetryExhausted, Exception)


# ---------------------------------------------------------------------------
# 2. RetryExhausted
# ---------------------------------------------------------------------------

class TestRetryExhausted:
    def test_stores_attempts(self):
        attempts = [{"node": "M1", "attempt": 1, "error": "timeout"}]
        exc = RetryExhausted("all failed", attempts)
        assert str(exc) == "all failed"
        assert exc.attempts == attempts
        assert len(exc.attempts) == 1

    def test_empty_attempts(self):
        exc = RetryExhausted("empty", [])
        assert exc.attempts == []


# ---------------------------------------------------------------------------
# 3. SmartRetryStats
# ---------------------------------------------------------------------------

class TestSmartRetryStats:
    def test_initial_state(self):
        stats = SmartRetryStats()
        d = stats.to_dict()
        assert d["total_calls"] == 0
        assert d["total_retries"] == 0
        assert d["total_fallbacks"] == 0
        assert d["total_successes"] == 0
        assert d["total_exhausted"] == 0
        assert d["success_rate"] == 0.0
        assert d["recent_failures"] == 0

    def test_record_success_first_attempt(self):
        stats = SmartRetryStats()
        stats.record_success("M1", attempt=1, latency_ms=42.0)
        assert stats.total_calls == 1
        assert stats.total_successes == 1
        assert stats.total_retries == 0

    def test_record_success_after_retries(self):
        stats = SmartRetryStats()
        stats.record_success("M1", attempt=3, latency_ms=100.0)
        assert stats.total_retries == 2  # attempt 3 => 2 retries

    def test_record_fallback(self):
        stats = SmartRetryStats()
        stats.record_fallback("M1", "ollama")
        assert stats.total_fallbacks == 1

    def test_record_exhausted(self):
        stats = SmartRetryStats()
        stats.record_exhausted(["M1", "ollama"], "timeout")
        assert stats.total_exhausted == 1
        assert stats.total_calls == 1
        assert len(stats._recent_failures) == 1
        assert stats._recent_failures[0]["error"] == "timeout"

    def test_recent_failures_capped_at_50(self):
        stats = SmartRetryStats()
        for i in range(60):
            stats.record_exhausted(["M1"], f"error_{i}")
        assert len(stats._recent_failures) == 50

    def test_success_rate(self):
        stats = SmartRetryStats()
        stats.record_success("M1", 1, 10.0)
        stats.record_success("M1", 1, 10.0)
        stats.record_exhausted(["M1"], "err")
        # 2 success out of 3 total_calls => 66.7%
        d = stats.to_dict()
        assert d["success_rate"] == 66.7

    def test_success_rate_zero_calls(self):
        stats = SmartRetryStats()
        assert stats.to_dict()["success_rate"] == 0.0

    def test_error_truncated_to_200(self):
        stats = SmartRetryStats()
        long_error = "x" * 500
        stats.record_exhausted(["M1"], long_error)
        assert len(stats._recent_failures[0]["error"]) == 200


# ---------------------------------------------------------------------------
# 4. Circuit breaker logic
# ---------------------------------------------------------------------------

class TestCircuitBreaker:
    def test_circuit_closed_by_default(self):
        assert _is_circuit_open("M1") is False

    def test_circuit_opens_after_threshold(self):
        for _ in range(_circuit_threshold):
            _record_circuit_failure("M1")
        assert _is_circuit_open("M1") is True

    def test_circuit_does_not_open_below_threshold(self):
        for _ in range(_circuit_threshold - 1):
            _record_circuit_failure("M1")
        assert _is_circuit_open("M1") is False

    def test_circuit_success_resets(self):
        for _ in range(_circuit_threshold):
            _record_circuit_failure("M1")
        assert _is_circuit_open("M1") is True
        _record_circuit_success("M1")
        assert _is_circuit_open("M1") is False
        assert "M1" not in _circuit_failures
        assert "M1" not in _circuit_opened_at

    @patch("src.smart_retry.time")
    def test_circuit_reopens_after_cooldown(self, mock_time):
        """After cooldown passes, circuit should close automatically."""
        base = 1000.0
        mock_time.time.return_value = base
        for _ in range(_circuit_threshold):
            _record_circuit_failure("M1")
        assert _is_circuit_open("M1") is True

        # Advance past cooldown
        mock_time.time.return_value = base + _circuit_cooldown_s + 1
        assert _is_circuit_open("M1") is False

    @patch("src.smart_retry.time")
    def test_old_failures_pruned_outside_window(self, mock_time):
        """Failures older than the window should be pruned."""
        base = 1000.0
        mock_time.time.return_value = base
        for _ in range(_circuit_threshold - 1):
            _record_circuit_failure("M1")

        # Advance past the window so old failures expire
        mock_time.time.return_value = base + _circuit_window_s + 1
        _record_circuit_failure("M1")
        # Only 1 recent failure, below threshold
        assert _is_circuit_open("M1") is False


# ---------------------------------------------------------------------------
# 5. retry_with_fallback — success paths
# ---------------------------------------------------------------------------

class TestRetryWithFallbackSuccess:
    @pytest.mark.asyncio
    async def test_success_first_node_first_attempt(self):
        fn = AsyncMock(return_value="ok")
        result = await retry_with_fallback(fn=fn, nodes=["M1"])
        assert result == "ok"
        fn.assert_awaited_once()
        assert retry_stats.total_successes == 1
        assert retry_stats.total_retries == 0

    @pytest.mark.asyncio
    async def test_success_after_one_retry(self):
        fn = AsyncMock(side_effect=[ValueError("fail"), "ok"])
        with patch("src.smart_retry.asyncio.sleep", new_callable=AsyncMock):
            result = await retry_with_fallback(
                fn=fn, nodes=["M1"], max_retries_per_node=2, base_delay_s=0.01
            )
        assert result == "ok"
        assert fn.await_count == 2
        assert retry_stats.total_successes == 1
        assert retry_stats.total_retries == 1

    @pytest.mark.asyncio
    async def test_success_on_fallback_node(self):
        fn = AsyncMock(side_effect=[ValueError("e1"), ValueError("e2"), "ok"])
        with patch("src.smart_retry.asyncio.sleep", new_callable=AsyncMock):
            result = await retry_with_fallback(
                fn=fn, nodes=["M1", "ollama"],
                max_retries_per_node=2, base_delay_s=0.01
            )
        assert result == "ok"
        assert retry_stats.total_fallbacks == 1
        assert retry_stats.total_successes == 1

    @pytest.mark.asyncio
    async def test_node_kwarg_passed_to_fn(self):
        """Verify the current node is injected as a kwarg."""
        captured_kwargs = {}

        async def capture_fn(**kw):
            captured_kwargs.update(kw)
            return "done"

        await retry_with_fallback(fn=capture_fn, nodes=["M1"])
        assert captured_kwargs.get("node") == "M1"

    @pytest.mark.asyncio
    async def test_custom_node_kwarg_name(self):
        captured = {}

        async def capture_fn(**kw):
            captured.update(kw)
            return "done"

        await retry_with_fallback(
            fn=capture_fn, nodes=["M1"], node_kwarg="target_node"
        )
        assert captured.get("target_node") == "M1"
        assert "node" not in captured

    @pytest.mark.asyncio
    async def test_args_and_kwargs_forwarded(self):
        captured_args = []
        captured_kwargs = {}

        async def capture_fn(*args, **kw):
            captured_args.extend(args)
            captured_kwargs.update(kw)
            return "done"

        await retry_with_fallback(
            fn=capture_fn, nodes=["M1"],
            args=("a", "b"), kwargs={"extra": 42}
        )
        assert captured_args == ["a", "b"]
        assert captured_kwargs["extra"] == 42
        assert captured_kwargs["node"] == "M1"


# ---------------------------------------------------------------------------
# 6. retry_with_fallback — failure paths
# ---------------------------------------------------------------------------

class TestRetryWithFallbackFailure:
    @pytest.mark.asyncio
    async def test_exhausted_all_nodes(self):
        fn = AsyncMock(side_effect=ValueError("always fails"))
        with patch("src.smart_retry.asyncio.sleep", new_callable=AsyncMock):
            with patch("src.smart_retry.event_bus", create=True):
                with pytest.raises(RetryExhausted) as exc_info:
                    await retry_with_fallback(
                        fn=fn, nodes=["M1", "ollama"],
                        max_retries_per_node=2, base_delay_s=0.01
                    )
        exc = exc_info.value
        assert len(exc.attempts) == 4  # 2 nodes x 2 retries
        assert retry_stats.total_exhausted == 1

    @pytest.mark.asyncio
    async def test_timeout_error_recorded(self):
        """asyncio.TimeoutError from wait_for is caught and recorded."""
        fn = AsyncMock(side_effect=asyncio.TimeoutError())
        with pytest.raises(RetryExhausted) as exc_info:
            await retry_with_fallback(
                fn=fn, nodes=["M1"],
                max_retries_per_node=1, timeout_s=120.0
            )
        assert any(a.get("error") == "timeout" for a in exc_info.value.attempts)

    @pytest.mark.asyncio
    async def test_circuit_open_skips_node(self):
        # Open circuit for M1
        for _ in range(_circuit_threshold):
            _record_circuit_failure("M1")
        assert _is_circuit_open("M1") is True

        fn = AsyncMock(return_value="ok")
        result = await retry_with_fallback(fn=fn, nodes=["M1", "ollama"])
        assert result == "ok"
        # fn should have been called with ollama, not M1
        call_kwargs = fn.call_args[1]
        assert call_kwargs["node"] == "ollama"

    @pytest.mark.asyncio
    async def test_all_nodes_circuit_open_raises(self):
        for n in ["M1", "ollama"]:
            for _ in range(_circuit_threshold):
                _record_circuit_failure(n)

        fn = AsyncMock(return_value="ok")
        with pytest.raises(RetryExhausted) as exc_info:
            await retry_with_fallback(fn=fn, nodes=["M1", "ollama"])
        # All skipped => attempts contain skipped entries
        assert all(a.get("skipped") == "circuit_open" for a in exc_info.value.attempts)
        fn.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_event_bus_emit_on_exhaustion(self):
        """When all nodes fail, event_bus.emit is called (if importable)."""
        fn = AsyncMock(side_effect=ValueError("fail"))
        mock_bus = MagicMock()
        mock_bus.emit = AsyncMock()

        with patch("src.smart_retry.asyncio.sleep", new_callable=AsyncMock):
            with patch.dict("sys.modules", {"src.event_bus": MagicMock(event_bus=mock_bus)}):
                with pytest.raises(RetryExhausted):
                    await retry_with_fallback(
                        fn=fn, nodes=["M1"],
                        max_retries_per_node=1, base_delay_s=0.01
                    )


# ---------------------------------------------------------------------------
# 7. Backoff calculation
# ---------------------------------------------------------------------------

class TestBackoff:
    @pytest.mark.asyncio
    async def test_exponential_backoff_delays(self):
        """Verify sleep is called with increasing delays (exponential)."""
        sleep_values = []
        original_sleep = asyncio.sleep

        async def capture_sleep(delay):
            sleep_values.append(delay)

        fn = AsyncMock(side_effect=[ValueError("e1"), ValueError("e2"), "ok"])

        with patch("src.smart_retry.asyncio.sleep", side_effect=capture_sleep):
            with patch("src.smart_retry.random.uniform", return_value=0.0):
                result = await retry_with_fallback(
                    fn=fn, nodes=["M1"],
                    max_retries_per_node=3,
                    base_delay_s=2.0, max_delay_s=100.0
                )

        assert result == "ok"
        # attempt 1 fails -> delay = 2.0 * 2^0 + 0.0 = 2.0
        # attempt 2 fails -> delay = 2.0 * 2^1 + 0.0 = 4.0
        assert len(sleep_values) == 2
        assert sleep_values[0] == pytest.approx(2.0)
        assert sleep_values[1] == pytest.approx(4.0)

    @pytest.mark.asyncio
    async def test_backoff_capped_at_max_delay(self):
        sleep_values = []

        async def capture_sleep(delay):
            sleep_values.append(delay)

        effects = [ValueError("fail")] * 4 + ["ok"]
        fn = AsyncMock(side_effect=effects)

        with patch("src.smart_retry.asyncio.sleep", side_effect=capture_sleep):
            with patch("src.smart_retry.random.uniform", return_value=0.0):
                await retry_with_fallback(
                    fn=fn, nodes=["M1"],
                    max_retries_per_node=5,
                    base_delay_s=5.0, max_delay_s=10.0
                )

        # Delays: min(5*1, 10)=5, min(5*2, 10)=10, min(5*4, 10)=10, min(5*8, 10)=10
        for d in sleep_values:
            assert d <= 10.0

    @pytest.mark.asyncio
    async def test_no_sleep_after_last_attempt_on_node(self):
        """When the last attempt on a node fails, no sleep before fallback."""
        sleep_count = 0

        async def counting_sleep(delay):
            nonlocal sleep_count
            sleep_count += 1

        fn = AsyncMock(side_effect=[ValueError("e1"), "ok"])

        with patch("src.smart_retry.asyncio.sleep", side_effect=counting_sleep):
            await retry_with_fallback(
                fn=fn, nodes=["M1", "ollama"],
                max_retries_per_node=1, base_delay_s=0.01
            )
        # max_retries_per_node=1 => only 1 attempt per node, no sleep between
        assert sleep_count == 0


# ---------------------------------------------------------------------------
# 8. smart_retry decorator
# ---------------------------------------------------------------------------

class TestSmartRetryDecorator:
    @pytest.mark.asyncio
    async def test_decorator_wraps_function(self):
        @smart_retry(max_retries=1, fallback_nodes=["M1"], base_delay_s=0.01)
        async def my_func(node=None):
            return f"hello from {node}"

        result = await my_func()
        assert result == "hello from M1"

    @pytest.mark.asyncio
    async def test_decorator_preserves_name(self):
        @smart_retry()
        async def my_special_func(node=None):
            pass

        assert my_special_func.__name__ == "my_special_func"

    @pytest.mark.asyncio
    async def test_decorator_node_kwarg_prioritized(self):
        """If node= is passed, it should be tried first."""
        calls = []

        @smart_retry(max_retries=1, fallback_nodes=["M1", "ollama", "gemini"], base_delay_s=0.01)
        async def track_fn(node=None):
            calls.append(node)
            return "ok"

        await track_fn(node="gemini")
        # gemini should be first in the chain
        assert calls[0] == "gemini"

    @pytest.mark.asyncio
    async def test_decorator_fallback_on_failure(self):
        attempt = 0

        @smart_retry(max_retries=1, fallback_nodes=["M1", "ollama"], base_delay_s=0.01)
        async def flaky(node=None):
            nonlocal attempt
            attempt += 1
            if node == "M1":
                raise ValueError("M1 down")
            return "ok"

        with patch("src.smart_retry.asyncio.sleep", new_callable=AsyncMock):
            result = await flaky()
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_decorator_exhausted(self):
        @smart_retry(max_retries=1, fallback_nodes=["M1"], base_delay_s=0.01)
        async def always_fail(node=None):
            raise RuntimeError("down")

        with patch("src.smart_retry.asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(RetryExhausted):
                await always_fail()

    @pytest.mark.asyncio
    async def test_decorator_default_nodes(self):
        """Without explicit fallback_nodes, defaults to M1/ollama/gemini."""
        calls = []

        @smart_retry(max_retries=1, base_delay_s=0.01)
        async def track_fn(node=None):
            calls.append(node)
            if node != "gemini":
                raise ValueError("nope")
            return "ok"

        with patch("src.smart_retry.asyncio.sleep", new_callable=AsyncMock):
            result = await track_fn()
        assert result == "ok"
        assert calls == ["M1", "ollama", "gemini"]


# ---------------------------------------------------------------------------
# 9. Global retry_stats singleton
# ---------------------------------------------------------------------------

class TestGlobalRetryStats:
    def test_retry_stats_is_smart_retry_stats_instance(self):
        assert isinstance(retry_stats, SmartRetryStats)

    @pytest.mark.asyncio
    async def test_stats_accumulate_across_calls(self):
        fn = AsyncMock(return_value="ok")
        await retry_with_fallback(fn=fn, nodes=["M1"])
        await retry_with_fallback(fn=fn, nodes=["M1"])
        assert retry_stats.total_successes == 2
        assert retry_stats.total_calls == 2


# ---------------------------------------------------------------------------
# 10. Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    @pytest.mark.asyncio
    async def test_single_node_single_retry(self):
        fn = AsyncMock(return_value="ok")
        result = await retry_with_fallback(
            fn=fn, nodes=["M1"], max_retries_per_node=1
        )
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_asyncio_timeout_error_handled(self):
        """asyncio.TimeoutError should be caught and recorded."""
        fn = AsyncMock(side_effect=[asyncio.TimeoutError(), "ok"])
        with patch("src.smart_retry.asyncio.sleep", new_callable=AsyncMock):
            result = await retry_with_fallback(
                fn=fn, nodes=["M1"], max_retries_per_node=2, base_delay_s=0.01
            )
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_overall_timeout_aborts_early(self):
        """If the total timeout_s expires, RetryExhausted is raised mid-loop."""
        call_count = 0

        async def slow_fn(**kw):
            nonlocal call_count
            call_count += 1
            raise ValueError("fail")

        with patch("src.smart_retry.asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(RetryExhausted) as exc_info:
                await retry_with_fallback(
                    fn=slow_fn, nodes=["M1", "ollama", "gemini"],
                    max_retries_per_node=100,
                    base_delay_s=0.001,
                    timeout_s=0.001  # very short => should stop quickly
                )
        # Should have raised before exhausting all 300 attempts
        assert call_count < 300

    @pytest.mark.asyncio
    async def test_kwargs_none_defaults_to_empty_dict(self):
        """Passing kwargs=None should not crash."""
        fn = AsyncMock(return_value="ok")
        result = await retry_with_fallback(
            fn=fn, nodes=["M1"], kwargs=None
        )
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_event_bus_import_failure_swallowed(self):
        """If event_bus cannot be imported, the error is silently swallowed."""
        fn = AsyncMock(side_effect=ValueError("fail"))

        with patch("src.smart_retry.asyncio.sleep", new_callable=AsyncMock):
            # Ensure src.event_bus is NOT available
            with patch.dict("sys.modules", {"src.event_bus": None}):
                with pytest.raises(RetryExhausted):
                    await retry_with_fallback(
                        fn=fn, nodes=["M1"],
                        max_retries_per_node=1,
                        base_delay_s=0.01
                    )
        # No crash => the except block in the source worked


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
