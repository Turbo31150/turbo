"""Retry Manager — Intelligent retry with exponential backoff and circuit breaker.

Provides decorators and functions for retrying failed operations
with configurable backoff, jitter, and circuit breaker pattern.
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
import functools
from dataclasses import dataclass, field
from typing import Any, Callable, TypeVar, Coroutine

logger = logging.getLogger("jarvis.retry_manager")

F = TypeVar("F", bound=Callable)


@dataclass
class RetryConfig:
    max_retries: int = 3
    base_delay_s: float = 1.0
    max_delay_s: float = 30.0
    backoff_factor: float = 2.0
    jitter: bool = True
    retryable_exceptions: tuple = (Exception,)


@dataclass
class CircuitBreaker:
    """Tracks failures and opens circuit when threshold is exceeded."""
    failure_threshold: int = 5
    reset_timeout_s: float = 60.0
    _failures: int = 0
    _last_failure: float = 0.0
    _state: str = "closed"  # closed, open, half_open
    _total_tripped: int = 0

    @property
    def state(self) -> str:
        if self._state == "open":
            if time.time() - self._last_failure >= self.reset_timeout_s:
                self._state = "half_open"
        return self._state

    def record_success(self) -> None:
        self._failures = 0
        self._state = "closed"

    def record_failure(self) -> None:
        self._failures += 1
        self._last_failure = time.time()
        if self._failures >= self.failure_threshold:
            self._state = "open"
            self._total_tripped += 1

    def is_allowed(self) -> bool:
        s = self.state
        return s in ("closed", "half_open")

    def reset(self) -> None:
        self._failures = 0
        self._state = "closed"


class RetryManager:
    """Centralized retry management with circuit breakers."""

    def __init__(self, default_config: RetryConfig | None = None):
        self._default_config = default_config or RetryConfig()
        self._breakers: dict[str, CircuitBreaker] = {}
        self._stats = {"total_retries": 0, "total_successes": 0, "total_failures": 0}

    def get_breaker(self, name: str) -> CircuitBreaker:
        if name not in self._breakers:
            self._breakers[name] = CircuitBreaker()
        return self._breakers[name]

    def configure_breaker(
        self, name: str, failure_threshold: int = 5, reset_timeout_s: float = 60.0
    ) -> None:
        self._breakers[name] = CircuitBreaker(
            failure_threshold=failure_threshold, reset_timeout_s=reset_timeout_s
        )

    async def execute(
        self,
        func: Callable[..., Coroutine],
        *args: Any,
        name: str = "default",
        config: RetryConfig | None = None,
        **kwargs: Any,
    ) -> Any:
        """Execute an async function with retry logic."""
        cfg = config or self._default_config
        breaker = self.get_breaker(name)

        if not breaker.is_allowed():
            raise RuntimeError(f"Circuit breaker open for '{name}'")

        last_exc: Exception | None = None
        for attempt in range(cfg.max_retries + 1):
            try:
                result = await func(*args, **kwargs)
                breaker.record_success()
                self._stats["total_successes"] += 1
                return result
            except cfg.retryable_exceptions as e:
                last_exc = e
                breaker.record_failure()
                if attempt < cfg.max_retries:
                    delay = min(
                        cfg.base_delay_s * (cfg.backoff_factor ** attempt),
                        cfg.max_delay_s,
                    )
                    if cfg.jitter:
                        delay *= (0.5 + random.random())
                    self._stats["total_retries"] += 1
                    logger.debug("Retry %d/%d for %s after %.1fs: %s",
                                 attempt + 1, cfg.max_retries, name, delay, e)
                    await asyncio.sleep(delay)
                    if not breaker.is_allowed():
                        break

        self._stats["total_failures"] += 1
        raise last_exc or RuntimeError(f"All retries exhausted for '{name}'")

    def execute_sync(
        self,
        func: Callable,
        *args: Any,
        name: str = "default",
        config: RetryConfig | None = None,
        **kwargs: Any,
    ) -> Any:
        """Execute a sync function with retry logic."""
        cfg = config or self._default_config
        breaker = self.get_breaker(name)

        if not breaker.is_allowed():
            raise RuntimeError(f"Circuit breaker open for '{name}'")

        last_exc: Exception | None = None
        for attempt in range(cfg.max_retries + 1):
            try:
                result = func(*args, **kwargs)
                breaker.record_success()
                self._stats["total_successes"] += 1
                return result
            except cfg.retryable_exceptions as e:
                last_exc = e
                breaker.record_failure()
                if attempt < cfg.max_retries:
                    delay = min(
                        cfg.base_delay_s * (cfg.backoff_factor ** attempt),
                        cfg.max_delay_s,
                    )
                    if cfg.jitter:
                        delay *= (0.5 + random.random())
                    self._stats["total_retries"] += 1
                    time.sleep(delay)
                    if not breaker.is_allowed():
                        break

        self._stats["total_failures"] += 1
        raise last_exc or RuntimeError(f"All retries exhausted for '{name}'")

    def get_stats(self) -> dict:
        breakers = {}
        for name, cb in self._breakers.items():
            breakers[name] = {
                "state": cb.state,
                "failures": cb._failures,
                "total_tripped": cb._total_tripped,
            }
        return {
            **self._stats,
            "breakers": breakers,
        }

    def reset_all(self) -> None:
        for cb in self._breakers.values():
            cb.reset()
        self._stats = {"total_retries": 0, "total_successes": 0, "total_failures": 0}


# ── Singleton ────────────────────────────────────────────────────────────────
retry_manager = RetryManager()
