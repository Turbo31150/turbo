"""JARVIS Circuit Breaker — Resilient node failure handling.

Implements the circuit breaker pattern for cluster nodes:
- CLOSED: Normal operation, requests pass through
- OPEN: Node blacklisted after N failures, requests fail fast
- HALF_OPEN: After cooldown, allow 1 test request

Prevents cascade failures when a node goes down.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

logger = logging.getLogger("jarvis.circuit_breaker")


class CircuitState(Enum):
    CLOSED = "closed"       # Normal — requests pass through
    OPEN = "open"           # Tripped — requests fail fast
    HALF_OPEN = "half_open" # Testing — allow 1 request


@dataclass
class CircuitStats:
    """Statistics for a single circuit breaker."""
    total_calls: int = 0
    total_failures: int = 0
    consecutive_failures: int = 0
    last_failure_time: float = 0
    last_success_time: float = 0
    time_opened: float = 0
    times_tripped: int = 0


class CircuitBreaker:
    """Circuit breaker for a single node.

    Usage:
        cb = CircuitBreaker("M1", failure_threshold=3, recovery_timeout=60)

        if cb.can_execute():
            try:
                result = await call_node("M1", prompt)
                cb.record_success()
            except Exception:
                cb.record_failure()
                # Use fallback node
        else:
            # Node is blacklisted, use fallback
    """

    def __init__(
        self,
        node_name: str,
        failure_threshold: int = 3,
        recovery_timeout: float = 60.0,
        half_open_max: int = 1,
    ):
        self.node_name = node_name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max = half_open_max

        self._state = CircuitState.CLOSED
        self._stats = CircuitStats()
        self._lock = threading.Lock()
        self._half_open_calls = 0

    @property
    def state(self) -> CircuitState:
        with self._lock:
            if self._state == CircuitState.OPEN:
                # Check if recovery timeout has elapsed
                if time.monotonic() - self._stats.time_opened >= self.recovery_timeout:
                    self._state = CircuitState.HALF_OPEN
                    self._half_open_calls = 0
                    logger.info("Circuit %s: OPEN → HALF_OPEN (testing)", self.node_name)
            return self._state

    def can_execute(self) -> bool:
        """Check if requests should be allowed through."""
        state = self.state
        if state == CircuitState.CLOSED:
            return True
        if state == CircuitState.HALF_OPEN:
            with self._lock:
                if self._half_open_calls < self.half_open_max:
                    self._half_open_calls += 1
                    return True
            return False
        return False  # OPEN

    def record_success(self):
        """Record a successful call."""
        with self._lock:
            self._stats.total_calls += 1
            self._stats.consecutive_failures = 0
            self._stats.last_success_time = time.monotonic()

            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.CLOSED
                logger.info("Circuit %s: HALF_OPEN → CLOSED (recovered)", self.node_name)

    def record_failure(self):
        """Record a failed call."""
        with self._lock:
            self._stats.total_calls += 1
            self._stats.total_failures += 1
            self._stats.consecutive_failures += 1
            self._stats.last_failure_time = time.monotonic()

            if self._state == CircuitState.HALF_OPEN:
                # Failed during test — go back to OPEN
                self._state = CircuitState.OPEN
                self._stats.time_opened = time.monotonic()
                self._stats.times_tripped += 1
                logger.warning("Circuit %s: HALF_OPEN → OPEN (test failed)", self.node_name)

            elif self._stats.consecutive_failures >= self.failure_threshold:
                self._state = CircuitState.OPEN
                self._stats.time_opened = time.monotonic()
                self._stats.times_tripped += 1
                logger.warning(
                    "Circuit %s: CLOSED → OPEN (threshold %d reached, cooldown %ds)",
                    self.node_name, self.failure_threshold, int(self.recovery_timeout),
                )

    def reset(self):
        """Force reset the circuit breaker."""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._stats.consecutive_failures = 0
            self._half_open_calls = 0

    def get_status(self) -> dict:
        """Get circuit breaker status."""
        state = self.state
        with self._lock:
            return {
                "node": self.node_name,
                "state": state.value,
                "consecutive_failures": self._stats.consecutive_failures,
                "total_failures": self._stats.total_failures,
                "total_calls": self._stats.total_calls,
                "times_tripped": self._stats.times_tripped,
                "failure_rate": f"{self._stats.total_failures / max(1, self._stats.total_calls) * 100:.1f}%",
                "recovery_in": max(0, self.recovery_timeout - (time.monotonic() - self._stats.time_opened))
                    if state == CircuitState.OPEN else 0,
            }


class ClusterCircuitBreakers:
    """Manages circuit breakers for all cluster nodes.

    Provides smart fallback routing when nodes are down.
    """

    def __init__(
        self,
        failure_threshold: int = 3,
        recovery_timeout: float = 60.0,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._breakers: dict[str, CircuitBreaker] = {}
        self._lock = threading.Lock()

    def get_breaker(self, node_name: str) -> CircuitBreaker:
        """Get or create a circuit breaker for a node."""
        with self._lock:
            if node_name not in self._breakers:
                self._breakers[node_name] = CircuitBreaker(
                    node_name,
                    self.failure_threshold,
                    self.recovery_timeout,
                )
            return self._breakers[node_name]

    def can_execute(self, node_name: str) -> bool:
        """Check if a node is available."""
        return self.get_breaker(node_name).can_execute()

    def record_success(self, node_name: str):
        """Record a successful call to a node."""
        self.get_breaker(node_name).record_success()

    def record_failure(self, node_name: str):
        """Record a failed call to a node."""
        self.get_breaker(node_name).record_failure()

    def get_available_nodes(self, candidates: list[str]) -> list[str]:
        """Filter a list of candidate nodes to only available ones.

        Args:
            candidates: Ordered list of preferred nodes (best first)

        Returns:
            Filtered list with only available nodes
        """
        return [n for n in candidates if self.can_execute(n)]

    def get_best_available(self, candidates: list[str]) -> str | None:
        """Get the best available node from candidates.

        Returns None if all nodes are down.
        """
        available = self.get_available_nodes(candidates)
        return available[0] if available else None

    def get_all_status(self) -> list[dict]:
        """Get status of all circuit breakers."""
        with self._lock:
            return [cb.get_status() for cb in self._breakers.values()]

    def reset_all(self):
        """Reset all circuit breakers."""
        with self._lock:
            for cb in self._breakers.values():
                cb.reset()

    def reset_node(self, node_name: str):
        """Reset a specific node's circuit breaker."""
        with self._lock:
            if node_name in self._breakers:
                self._breakers[node_name].reset()


# ── Retry with backoff ───────────────────────────────────────────────────

async def retry_with_backoff(
    func: Callable,
    nodes: list[str],
    breakers: ClusterCircuitBreakers,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 16.0,
    **kwargs,
) -> Any:
    """Execute a function with automatic retry and node fallback.

    Tries each available node in order, with exponential backoff.
    Records success/failure in circuit breakers.

    Args:
        func: Async function to call. Signature: func(node, **kwargs)
        nodes: Ordered list of candidate nodes
        breakers: Circuit breaker manager
        max_retries: Max retries per node
        base_delay: Initial delay between retries (seconds)
        max_delay: Maximum delay cap

    Returns:
        Result from the first successful call

    Raises:
        RuntimeError: If all nodes and retries exhausted
    """
    import asyncio

    available = breakers.get_available_nodes(nodes)
    if not available:
        # All nodes tripped — try half-open on first candidate
        available = nodes[:1]
        logger.warning("All nodes tripped, forcing half-open test on %s", available)

    last_error = None
    for node in available:
        delay = base_delay
        for attempt in range(max_retries):
            try:
                result = await func(node, **kwargs)
                breakers.record_success(node)
                return result
            except Exception as exc:
                last_error = exc
                breakers.record_failure(node)
                if attempt < max_retries - 1:
                    logger.debug(
                        "Retry %s attempt %d/%d after %.1fs: %s",
                        node, attempt + 1, max_retries, delay, exc,
                    )
                    await asyncio.sleep(delay)
                    delay = min(delay * 2, max_delay)

    raise RuntimeError(
        f"All nodes exhausted ({', '.join(nodes)}). Last error: {last_error}"
    )


# ── Global instance ──────────────────────────────────────────────────────
cluster_breakers = ClusterCircuitBreakers(
    failure_threshold=3,
    recovery_timeout=60.0,
)
