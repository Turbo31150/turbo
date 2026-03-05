"""JARVIS Smart Retry - Intelligent retry with fallback chain.

Retries cluster requests with exponential backoff, automatic fallback,
circuit breaker integration, and event bus notifications.

Usage:
    from src.smart_retry import retry_with_fallback, retry_stats
    result = await retry_with_fallback(fn=call_node, nodes=["M1","ollama","gemini"])
"""

from __future__ import annotations

import asyncio
import functools
import logging
import random
import time
from typing import Any, Callable, Awaitable, TypeVar

logger = logging.getLogger("jarvis.smart_retry")
T = TypeVar("T")


class RetryExhausted(Exception):
    def __init__(self, message: str, attempts: list[dict]):
        super().__init__(message)
        self.attempts = attempts


class SmartRetryStats:
    def __init__(self):
        self.total_calls = 0
        self.total_retries = 0
        self.total_fallbacks = 0
        self.total_successes = 0
        self.total_exhausted = 0
        self._recent_failures: list[dict] = []

    def record_success(self, node: str, attempt: int, latency_ms: float) -> None:
        self.total_calls += 1
        self.total_successes += 1
        if attempt > 1:
            self.total_retries += attempt - 1

    def record_fallback(self, from_node: str, to_node: str) -> None:
        self.total_fallbacks += 1

    def record_exhausted(self, nodes: list[str], error: str) -> None:
        self.total_calls += 1
        self.total_exhausted += 1
        self._recent_failures.append({"nodes": nodes, "error": error[:200], "ts": time.time()})
        if len(self._recent_failures) > 50:
            self._recent_failures = self._recent_failures[-50:]

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_calls": self.total_calls,
            "total_retries": self.total_retries,
            "total_fallbacks": self.total_fallbacks,
            "total_successes": self.total_successes,
            "total_exhausted": self.total_exhausted,
            "success_rate": round(self.total_successes / max(self.total_calls, 1) * 100, 1),
            "recent_failures": len(self._recent_failures)
        }


retry_stats = SmartRetryStats()

_circuit_failures: dict[str, list[float]] = {}
_circuit_threshold = 5
_circuit_window_s = 300.0
_circuit_cooldown_s = 60.0
_circuit_opened_at: dict[str, float] = {}


def _is_circuit_open(node: str) -> bool:
    if node not in _circuit_opened_at:
        return False
    elapsed = time.time() - _circuit_opened_at[node]
    if elapsed > _circuit_cooldown_s:
        del _circuit_opened_at[node]
        return False
    return True


def _record_circuit_failure(node: str) -> None:
    now = time.time()
    failures = _circuit_failures.setdefault(node, [])
    failures.append(now)
    failures[:] = [t for t in failures if now - t < _circuit_window_s]
    if len(failures) >= _circuit_threshold:
        _circuit_opened_at[node] = now
        logger.warning(f"Circuit OPENED for {node} ({len(failures)} failures)")


def _record_circuit_success(node: str) -> None:
    _circuit_failures.pop(node, None)
    _circuit_opened_at.pop(node, None)


async def retry_with_fallback(
    fn: Callable[..., Awaitable[T]],
    nodes: list[str],
    args: tuple = (),
    kwargs: dict | None = None,
    max_retries_per_node: int = 2,
    base_delay_s: float = 1.0,
    max_delay_s: float = 30.0,
    timeout_s: float = 120.0,
    node_kwarg: str = "node",
) -> T:
    """Try fn across multiple nodes with exponential backoff and fallback."""
    kwargs = kwargs or {}
    attempts: list[dict] = []
    start = time.time()

    for node_idx, node in enumerate(nodes):
        if _is_circuit_open(node):
            attempts.append({"node": node, "skipped": "circuit_open"})
            continue

        for attempt in range(1, max_retries_per_node + 1):
            elapsed = time.time() - start
            if elapsed > timeout_s:
                raise RetryExhausted(f"Timeout {timeout_s}s after {len(attempts)} attempts", attempts)

            try:
                attempt_start = time.time()
                kwargs[node_kwarg] = node
                result = await asyncio.wait_for(
                    fn(*args, **kwargs),
                    timeout=min(timeout_s - elapsed, 60)
                )
                latency_ms = (time.time() - attempt_start) * 1000
                retry_stats.record_success(node, attempt, latency_ms)
                _record_circuit_success(node)
                if attempt > 1 or node_idx > 0:
                    logger.info(f"OK on {node} (attempt {attempt}, fallback #{node_idx}) {latency_ms:.0f}ms")
                return result

            except asyncio.TimeoutError:
                attempts.append({"node": node, "attempt": attempt, "error": "timeout", "ts": time.time()})
                _record_circuit_failure(node)
            except Exception as e:
                attempts.append({"node": node, "attempt": attempt, "error": str(e)[:200], "ts": time.time()})
                _record_circuit_failure(node)

            if attempt < max_retries_per_node:
                delay = min(base_delay_s * (2 ** (attempt - 1)) + random.uniform(0, 1), max_delay_s)
                await asyncio.sleep(delay)

        if node_idx < len(nodes) - 1:
            retry_stats.record_fallback(node, nodes[node_idx + 1])
            logger.info(f"Fallback: {node} -> {nodes[node_idx + 1]}")

    retry_stats.record_exhausted(nodes, f"{len(attempts)} attempts failed")
    try:
        from src.event_bus import event_bus
        asyncio.create_task(event_bus.emit("cluster.all_nodes_failed", {
            "nodes": nodes, "attempts": len(attempts), "ts": time.time()
        }))
    except Exception:
        pass

    raise RetryExhausted(f"All {len(nodes)} nodes exhausted ({len(attempts)} attempts)", attempts)


def smart_retry(max_retries: int = 3, fallback_nodes: list[str] | None = None,
                base_delay_s: float = 1.0, timeout_s: float = 120.0):
    """Decorator for smart retry with fallback chain."""
    def decorator(fn):
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            nodes = list(fallback_nodes or ["M1", "ollama", "gemini"])
            if "node" in kwargs:
                specified = kwargs.pop("node")
                if specified in nodes:
                    nodes.remove(specified)
                nodes.insert(0, specified)
            return await retry_with_fallback(
                fn=fn, nodes=nodes, args=args, kwargs=kwargs,
                max_retries_per_node=max_retries,
                base_delay_s=base_delay_s, timeout_s=timeout_s
            )
        return wrapper
    return decorator

