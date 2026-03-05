"""
resilience.py — Central resilience module for the lienDepart multi-agent orchestrator.

Provides: CircuitBreaker, RetryPolicy, TimeoutManager, AgentFallbackChain,
DeadLetterQueue, and the resilient_call() wrapper function.

No external dependencies — pure Python asyncio.
"""

import asyncio
import json
import logging
import random
import time
from collections import deque
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Coroutine, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DLQ_PATH = Path("F:/BUREAU/lienDepart/data/dlq.json")
DLQ_MAX_SIZE = 100
DLQ_TTL_SECONDS = 86400  # 24 hours

CIRCUIT_FAILURE_THRESHOLD = 5
CIRCUIT_WINDOW_SECONDS = 60
CIRCUIT_HALF_OPEN_DELAY = 30

MODEL_TIMEOUTS: dict[str, float] = {
    "haiku": 15.0,
    "sonnet": 45.0,
    "opus": 120.0,
}

RETRY_MAX_BY_TIER: dict[int, int] = {
    1: 3,
    2: 2,
    3: 1,
    4: 0,
}

RETRY_BASE_DELAY = 1.0
RETRY_FACTOR = 2.0
RETRY_MAX_DELAY = 30.0

FALLBACK_MAP: dict[str, list[str]] = {
    "coder": ["executor"],
    "researcher": ["coder"],
    "data-analyst": ["coder"],
    "trader": ["researcher"],
    "sysadmin": ["executor"],
}


# ---------------------------------------------------------------------------
# 1. CircuitBreaker
# ---------------------------------------------------------------------------

class CircuitState(Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreaker:
    """
    Implements the circuit-breaker pattern with a sliding time window.

    Transitions:
      CLOSED  → OPEN      when failure_threshold failures occur within window_seconds.
      OPEN    → HALF_OPEN after half_open_delay seconds have elapsed.
      HALF_OPEN → CLOSED  on the next recorded success.
      HALF_OPEN → OPEN    on the next recorded failure.
    """

    def __init__(
        self,
        failure_threshold: int = CIRCUIT_FAILURE_THRESHOLD,
        window_seconds: float = CIRCUIT_WINDOW_SECONDS,
        half_open_delay: float = CIRCUIT_HALF_OPEN_DELAY,
    ) -> None:
        self._failure_threshold = failure_threshold
        self._window_seconds = window_seconds
        self._half_open_delay = half_open_delay
        self._state = CircuitState.CLOSED
        self._failure_timestamps: deque[float] = deque()
        self._opened_at: float = 0.0

    def _purge_old_failures(self) -> None:
        """Remove failure timestamps that are outside the sliding window."""
        cutoff = time.monotonic() - self._window_seconds
        while self._failure_timestamps and self._failure_timestamps[0] < cutoff:
            self._failure_timestamps.popleft()

    def can_execute(self) -> bool:
        """Return True if the circuit allows the call to proceed."""
        now = time.monotonic()

        if self._state == CircuitState.CLOSED:
            return True

        if self._state == CircuitState.OPEN:
            if now - self._opened_at >= self._half_open_delay:
                self._state = CircuitState.HALF_OPEN
                logger.info("CircuitBreaker → HALF_OPEN: probing allowed.")
                return True
            return False

        # HALF_OPEN: allow exactly one probe
        return True

    def record_success(self) -> None:
        """Record a successful call; closes the circuit if it was half-open."""
        if self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.CLOSED
            self._failure_timestamps.clear()
            logger.info("CircuitBreaker → CLOSED: probe succeeded.")

    def record_failure(self) -> None:
        """Record a failed call; may trip the circuit open."""
        now = time.monotonic()

        if self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.OPEN
            self._opened_at = now
            logger.warning("CircuitBreaker → OPEN: probe failed.")
            return

        self._failure_timestamps.append(now)
        self._purge_old_failures()

        if len(self._failure_timestamps) >= self._failure_threshold:
            self._state = CircuitState.OPEN
            self._opened_at = now
            logger.warning(
                "CircuitBreaker → OPEN: %d failures in %ss window.",
                self._failure_threshold,
                self._window_seconds,
            )

    def get_state(self) -> str:
        """Return the current circuit state as a string."""
        return self._state.value


# ---------------------------------------------------------------------------
# 2. RetryPolicy
# ---------------------------------------------------------------------------

class RetryPolicy:
    """
    Exponential back-off with jitter.

    Delay formula: min(base * factor^attempt, max_delay) + uniform(0, delay*0.1)
    """

    def __init__(
        self,
        base: float = RETRY_BASE_DELAY,
        factor: float = RETRY_FACTOR,
        max_delay: float = RETRY_MAX_DELAY,
    ) -> None:
        self._base = base
        self._factor = factor
        self._max_delay = max_delay

    def _compute_delay(self, attempt: int) -> float:
        """Return the sleep duration for the given attempt index (0-based)."""
        delay = min(self._base * (self._factor ** attempt), self._max_delay)
        jitter = random.uniform(0, delay * 0.1)
        return delay + jitter

    async def execute(
        self,
        coroutine: Callable[[], Coroutine[Any, Any, Any]],
        max_retries: int,
    ) -> Any:
        """
        Execute the coroutine factory up to max_retries + 1 times.

        Raises the last exception if all attempts fail.
        """
        last_exc: Optional[Exception] = None

        for attempt in range(max_retries + 1):
            try:
                return await coroutine()
            except Exception as exc:
                last_exc = exc
                if attempt < max_retries:
                    delay = self._compute_delay(attempt)
                    logger.warning(
                        "RetryPolicy: attempt %d/%d failed (%s). Retrying in %.2fs.",
                        attempt + 1,
                        max_retries + 1,
                        exc,
                        delay,
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        "RetryPolicy: all %d attempts exhausted. Last error: %s",
                        max_retries + 1,
                        exc,
                    )

        raise last_exc  # type: ignore[misc]


# ---------------------------------------------------------------------------
# 3. TimeoutManager
# ---------------------------------------------------------------------------

class TimeoutManager:
    """Provides per-model timeout values in seconds."""

    def __init__(self, timeouts: Optional[dict[str, float]] = None) -> None:
        self._timeouts: dict[str, float] = timeouts or MODEL_TIMEOUTS

    def get_timeout(self, model: str) -> float:
        """
        Return the timeout in seconds for the given model name.

        Performs a substring match so 'claude-haiku-3' resolves to 'haiku'.
        Falls back to 30s if the model is not recognised.
        """
        model_lower = model.lower()
        for key, value in self._timeouts.items():
            if key in model_lower:
                return value
        logger.warning("TimeoutManager: unknown model '%s', defaulting to 30s.", model)
        return 30.0


# ---------------------------------------------------------------------------
# 4. AgentFallbackChain
# ---------------------------------------------------------------------------

class AgentFallbackChain:
    """Provides ordered fallback agent names for a given agent."""

    def __init__(self, fallback_map: Optional[dict[str, list[str]]] = None) -> None:
        self._map: dict[str, list[str]] = fallback_map or FALLBACK_MAP

    def get_fallbacks(self, agent_name: str) -> list[str]:
        """Return the list of fallback agent names, or an empty list if none defined."""
        return list(self._map.get(agent_name, []))


# ---------------------------------------------------------------------------
# 5. DeadLetterQueue
# ---------------------------------------------------------------------------

class DeadLetterQueue:
    """
    Persistent JSON-backed dead-letter queue stored on disk.

    Thread-safety: protected by an asyncio.Lock for concurrent async access.
    Entries older than DLQ_TTL_SECONDS are purged on every push/pop.
    """

    def __init__(self, path: Path = DLQ_PATH, max_size: int = DLQ_MAX_SIZE) -> None:
        self._path = path
        self._max_size = max_size
        self._lock = asyncio.Lock()
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def _read(self) -> list[dict]:
        """Load entries from disk, returning an empty list on any error."""
        try:
            with self._path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            return data if isinstance(data, list) else []
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def _write(self, entries: list[dict]) -> None:
        """Persist entries to disk atomically via a temp-rename pattern."""
        tmp = self._path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump(entries, fh, ensure_ascii=False, indent=2)
        tmp.replace(self._path)

    def _purge_expired(self, entries: list[dict]) -> list[dict]:
        """Remove entries whose 'queued_at' timestamp is older than DLQ_TTL_SECONDS."""
        cutoff = time.time() - DLQ_TTL_SECONDS
        fresh = [e for e in entries if e.get("queued_at", 0) >= cutoff]
        removed = len(entries) - len(fresh)
        if removed:
            logger.info("DeadLetterQueue: purged %d expired entries.", removed)
        return fresh

    async def push(self, task_info: dict) -> None:
        """Append a task to the queue. Enforces max_size by dropping the oldest entry (FIFO)."""
        async with self._lock:
            entries = self._read()
            entries = self._purge_expired(entries)
            task_info = dict(task_info)
            task_info.setdefault("queued_at", time.time())
            entries.append(task_info)
            if len(entries) > self._max_size:
                dropped = len(entries) - self._max_size
                entries = entries[dropped:]
                logger.warning(
                    "DeadLetterQueue: max_size reached, dropped %d oldest entries.", dropped
                )
            self._write(entries)
            logger.info("DeadLetterQueue: pushed task '%s'.", task_info.get("task_id", "?"))

    async def pop(self) -> Optional[dict]:
        """Remove and return the oldest entry, or None if the queue is empty."""
        async with self._lock:
            entries = self._read()
            entries = self._purge_expired(entries)
            if not entries:
                return None
            entry = entries.pop(0)
            self._write(entries)
            logger.info("DeadLetterQueue: popped task '%s'.", entry.get("task_id", "?"))
            return entry

    async def list_all(self) -> list[dict]:
        """Return all current entries without modifying the queue."""
        async with self._lock:
            entries = self._read()
            return self._purge_expired(entries)

    async def purge_old(self) -> int:
        """Explicitly purge expired entries. Returns the number of entries removed."""
        async with self._lock:
            entries = self._read()
            fresh = self._purge_expired(entries)
            removed = len(entries) - len(fresh)
            if removed:
                self._write(fresh)
            return removed


# ---------------------------------------------------------------------------
# Module-level singletons (shared across the orchestrator)
# ---------------------------------------------------------------------------

_circuit_breakers: dict[str, CircuitBreaker] = {}
_retry_policy = RetryPolicy()
_timeout_manager = TimeoutManager()
_fallback_chain = AgentFallbackChain()
_dlq = DeadLetterQueue()


def get_circuit_breaker(agent_name: str) -> CircuitBreaker:
    """Return (or create) the CircuitBreaker instance for a given agent."""
    if agent_name not in _circuit_breakers:
        _circuit_breakers[agent_name] = CircuitBreaker()
    return _circuit_breakers[agent_name]


# ---------------------------------------------------------------------------
# 6. resilient_call()
# ---------------------------------------------------------------------------

async def resilient_call(
    agent_name: str,
    model: str,
    tier: int,
    coro_factory: Callable[[], Coroutine[Any, Any, Any]],
    fallback_coro_factory: Optional[Callable[[str], Coroutine[Any, Any, Any]]] = None,
) -> Any:
    """
    Execute a coroutine with full resilience: timeout → retry → fallback → dead-letter.

    Parameters
    ----------
    agent_name:
        Name of the originating agent (e.g. 'coder', 'researcher').
    model:
        Model identifier used to resolve the timeout (e.g. 'claude-haiku-3').
    tier:
        Agent tier (1–4) used to resolve the max retry count.
    coro_factory:
        Zero-argument callable that returns a fresh coroutine for each attempt.
    fallback_coro_factory:
        Optional callable accepting a fallback agent name and returning a coroutine.
        When None, no fallback is attempted before dead-lettering.

    Returns
    -------
    Any
        The result of the first successful coroutine execution.

    Raises
    ------
    RuntimeError
        When the circuit is open and the call is rejected without being queued.
    Exception
        The last exception from the final fallback attempt if all paths fail
        (the task is also pushed to the dead-letter queue in that case).
    """
    cb = get_circuit_breaker(agent_name)
    timeout = _timeout_manager.get_timeout(model)
    max_retries = RETRY_MAX_BY_TIER.get(tier, 0)

    # --- Circuit breaker gate ---
    if not cb.can_execute():
        logger.warning(
            "resilient_call: circuit OPEN for agent '%s'. Call rejected.", agent_name
        )
        await _dlq.push(
            {
                "task_id": f"{agent_name}-{time.time()}",
                "agent": agent_name,
                "model": model,
                "tier": tier,
                "reason": "circuit_open",
            }
        )
        raise RuntimeError(
            f"CircuitBreaker is OPEN for agent '{agent_name}'. Task sent to DLQ."
        )

    # --- Primary path: timeout + retry ---
    async def _primary_attempt() -> Any:
        return await asyncio.wait_for(coro_factory(), timeout=timeout)

    try:
        result = await _retry_policy.execute(_primary_attempt, max_retries)
        cb.record_success()
        return result

    except Exception as primary_exc:
        cb.record_failure()
        logger.warning(
            "resilient_call: primary path failed for agent '%s': %s",
            agent_name,
            primary_exc,
        )

    # --- Fallback path ---
    fallbacks = _fallback_chain.get_fallbacks(agent_name)
    if fallbacks and fallback_coro_factory is not None:
        for fallback_agent in fallbacks:
            fallback_cb = get_circuit_breaker(fallback_agent)
            if not fallback_cb.can_execute():
                logger.warning(
                    "resilient_call: fallback agent '%s' circuit is OPEN, skipping.",
                    fallback_agent,
                )
                continue

            logger.info(
                "resilient_call: trying fallback agent '%s' for '%s'.",
                fallback_agent,
                agent_name,
            )

            async def _fallback_attempt(fa: str = fallback_agent) -> Any:
                fallback_timeout = _timeout_manager.get_timeout(model)
                return await asyncio.wait_for(
                    fallback_coro_factory(fa), timeout=fallback_timeout
                )

            try:
                result = await _retry_policy.execute(_fallback_attempt, max(max_retries - 1, 0))
                fallback_cb.record_success()
                logger.info(
                    "resilient_call: fallback agent '%s' succeeded.", fallback_agent
                )
                return result
            except Exception as fallback_exc:
                fallback_cb.record_failure()
                logger.warning(
                    "resilient_call: fallback agent '%s' also failed: %s",
                    fallback_agent,
                    fallback_exc,
                )

    # --- Dead-letter queue ---
    logger.error(
        "resilient_call: all paths exhausted for agent '%s'. Sending to DLQ.", agent_name
    )
    await _dlq.push(
        {
            "task_id": f"{agent_name}-{time.time()}",
            "agent": agent_name,
            "model": model,
            "tier": tier,
            "reason": "all_paths_failed",
        }
    )
    raise RuntimeError(
        f"All resilience paths failed for agent '{agent_name}'. Task sent to DLQ."
    )
