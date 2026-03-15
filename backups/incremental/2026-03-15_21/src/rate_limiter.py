"""Rate Limiter — Token-bucket per-node request throttling.

Prevents cluster node overload by enforcing configurable
requests-per-second limits with burst tolerance.
"""

from __future__ import annotations

import time
import threading
from dataclasses import dataclass, field


@dataclass
class _Bucket:
    """Token bucket for a single node."""
    capacity: float
    refill_rate: float  # tokens per second
    tokens: float = 0.0
    last_refill: float = field(default_factory=time.monotonic)
    total_allowed: int = 0
    total_denied: int = 0

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now

    def try_acquire(self, tokens: float = 1.0) -> bool:
        self._refill()
        if self.tokens >= tokens:
            self.tokens -= tokens
            self.total_allowed += 1
            return True
        self.total_denied += 1
        return False

    def wait_time(self, tokens: float = 1.0) -> float:
        self._refill()
        if self.tokens >= tokens:
            return 0.0
        return (tokens - self.tokens) / self.refill_rate


class RateLimiter:
    """Per-node token-bucket rate limiter."""

    def __init__(
        self,
        default_rps: float = 10.0,
        default_burst: float = 20.0,
    ):
        self._default_rps = default_rps
        self._default_burst = default_burst
        self._buckets: dict[str, _Bucket] = {}
        self._lock = threading.Lock()
        self._config: dict[str, tuple[float, float]] = {}  # node -> (rps, burst)

    def configure_node(self, node: str, rps: float, burst: float | None = None) -> None:
        """Set custom rate limit for a specific node."""
        with self._lock:
            self._config[node] = (rps, burst or rps * 2)
            if node in self._buckets:
                b = self._buckets[node]
                b.refill_rate = rps
                b.capacity = burst or rps * 2
                b.tokens = min(b.tokens, b.capacity)

    def _get_bucket(self, node: str) -> _Bucket:
        if node not in self._buckets:
            rps, burst = self._config.get(node, (self._default_rps, self._default_burst))
            self._buckets[node] = _Bucket(capacity=burst, refill_rate=rps, tokens=burst)
        return self._buckets[node]

    def allow(self, node: str, cost: float = 1.0) -> bool:
        """Check if a request to *node* is allowed. Consumes tokens if yes."""
        with self._lock:
            return self._get_bucket(node).try_acquire(cost)

    def wait_time(self, node: str, cost: float = 1.0) -> float:
        """Seconds to wait before *node* can accept *cost* tokens."""
        with self._lock:
            return self._get_bucket(node).wait_time(cost)

    def get_node_stats(self, node: str) -> dict:
        """Stats for a single node bucket."""
        with self._lock:
            b = self._get_bucket(node)
            b._refill()
            return {
                "node": node,
                "tokens_available": round(b.tokens, 2),
                "capacity": b.capacity,
                "refill_rate": b.refill_rate,
                "total_allowed": b.total_allowed,
                "total_denied": b.total_denied,
            }

    def get_all_stats(self) -> dict:
        """Stats for every known node."""
        with self._lock:
            nodes = {}
            total_allowed = 0
            total_denied = 0
            for name, b in self._buckets.items():
                b._refill()
                nodes[name] = {
                    "tokens_available": round(b.tokens, 2),
                    "capacity": b.capacity,
                    "rps": b.refill_rate,
                    "total_allowed": b.total_allowed,
                    "total_denied": b.total_denied,
                }
                total_allowed += b.total_allowed
                total_denied += b.total_denied
            return {
                "nodes": nodes,
                "total_allowed": total_allowed,
                "total_denied": total_denied,
                "default_rps": self._default_rps,
                "default_burst": self._default_burst,
            }

    def reset_node(self, node: str) -> None:
        """Reset a node's bucket to full capacity."""
        with self._lock:
            if node in self._buckets:
                b = self._buckets[node]
                b.tokens = b.capacity
                b.total_allowed = 0
                b.total_denied = 0

    def reset_all(self) -> None:
        """Reset all buckets."""
        with self._lock:
            self._buckets.clear()


# ── Singleton ────────────────────────────────────────────────────────────────
rate_limiter = RateLimiter()
