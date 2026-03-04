"""Retry Policy — Configurable retry strategies with backoff and jitter."""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from enum import Enum
from threading import Lock
from typing import Any, Callable


class BackoffType(Enum):
    FIXED = "fixed"
    LINEAR = "linear"
    EXPONENTIAL = "exponential"


@dataclass
class RetryPolicy:
    name: str
    max_attempts: int = 3
    backoff: BackoffType = BackoffType.EXPONENTIAL
    base_delay: float = 1.0
    max_delay: float = 30.0
    jitter: bool = True
    retryable_exceptions: tuple = (Exception,)

    def get_delay(self, attempt: int) -> float:
        if self.backoff == BackoffType.FIXED:
            delay = self.base_delay
        elif self.backoff == BackoffType.LINEAR:
            delay = self.base_delay * attempt
        else:  # EXPONENTIAL
            delay = self.base_delay * (2 ** (attempt - 1))
        delay = min(delay, self.max_delay)
        if self.jitter:
            delay = delay * (0.5 + random.random() * 0.5)
        return delay


@dataclass
class RetryResult:
    success: bool
    result: Any = None
    attempts: int = 0
    total_time: float = 0.0
    last_error: str = ""


class RetryPolicyManager:
    """Manages retry policies and executes operations with retry logic."""

    def __init__(self):
        self._policies: dict[str, RetryPolicy] = {}
        self._history: list[dict] = []
        self._max_history = 500
        self._lock = Lock()
        self._register_defaults()

    def _register_defaults(self):
        self.register("default", max_attempts=3, backoff=BackoffType.EXPONENTIAL)
        self.register("aggressive", max_attempts=5, backoff=BackoffType.EXPONENTIAL, base_delay=0.5)
        self.register("gentle", max_attempts=2, backoff=BackoffType.FIXED, base_delay=2.0)

    def register(self, name: str, max_attempts: int = 3,
                 backoff: BackoffType = BackoffType.EXPONENTIAL,
                 base_delay: float = 1.0, max_delay: float = 30.0,
                 jitter: bool = True) -> RetryPolicy:
        policy = RetryPolicy(
            name=name, max_attempts=max_attempts, backoff=backoff,
            base_delay=base_delay, max_delay=max_delay, jitter=jitter,
        )
        with self._lock:
            self._policies[name] = policy
        return policy

    def get(self, name: str) -> RetryPolicy | None:
        return self._policies.get(name)

    def remove(self, name: str) -> bool:
        with self._lock:
            return self._policies.pop(name, None) is not None

    def list_policies(self) -> list[dict]:
        with self._lock:
            return [
                {
                    "name": p.name, "max_attempts": p.max_attempts,
                    "backoff": p.backoff.value, "base_delay": p.base_delay,
                    "max_delay": p.max_delay, "jitter": p.jitter,
                }
                for p in self._policies.values()
            ]

    def execute(self, fn: Callable, policy_name: str = "default",
                *args, **kwargs) -> RetryResult:
        """Execute function with retry policy (synchronous, no actual sleep for tests)."""
        policy = self._policies.get(policy_name)
        if not policy:
            policy = self._policies.get("default", RetryPolicy(name="fallback"))

        t0 = time.time()
        last_error = ""
        for attempt in range(1, policy.max_attempts + 1):
            try:
                result = fn(*args, **kwargs)
                rr = RetryResult(success=True, result=result, attempts=attempt,
                                 total_time=time.time() - t0)
                self._record(policy.name, rr)
                return rr
            except policy.retryable_exceptions as exc:
                last_error = str(exc)
                if attempt < policy.max_attempts:
                    delay = policy.get_delay(attempt)
                    time.sleep(delay)

        rr = RetryResult(success=False, attempts=policy.max_attempts,
                         total_time=time.time() - t0, last_error=last_error)
        self._record(policy.name, rr)
        return rr

    def execute_no_wait(self, fn: Callable, policy_name: str = "default",
                        *args, **kwargs) -> RetryResult:
        """Execute with retry but no sleep between attempts (for testing)."""
        policy = self._policies.get(policy_name)
        if not policy:
            policy = self._policies.get("default", RetryPolicy(name="fallback"))

        t0 = time.time()
        last_error = ""
        for attempt in range(1, policy.max_attempts + 1):
            try:
                result = fn(*args, **kwargs)
                rr = RetryResult(success=True, result=result, attempts=attempt,
                                 total_time=time.time() - t0)
                self._record(policy.name, rr)
                return rr
            except Exception as exc:
                last_error = str(exc)

        rr = RetryResult(success=False, attempts=policy.max_attempts,
                         total_time=time.time() - t0, last_error=last_error)
        self._record(policy.name, rr)
        return rr

    def _record(self, policy_name: str, result: RetryResult) -> None:
        with self._lock:
            self._history.append({
                "policy": policy_name, "success": result.success,
                "attempts": result.attempts, "total_time": round(result.total_time, 4),
                "error": result.last_error, "timestamp": time.time(),
            })
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]

    def get_history(self, limit: int = 50) -> list[dict]:
        with self._lock:
            return self._history[-limit:]

    def get_stats(self) -> dict:
        with self._lock:
            total = len(self._history)
            success = sum(1 for r in self._history if r["success"])
            failed = total - success
            return {
                "total_policies": len(self._policies),
                "total_executions": total,
                "successful": success,
                "failed": failed,
                "success_rate": round(success / total * 100, 1) if total else 0,
            }


retry_manager = RetryPolicyManager()
