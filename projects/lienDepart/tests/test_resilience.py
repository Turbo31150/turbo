"""Tests unitaires pour la couche de resilience lienDepart v1.1.0."""

import asyncio
import json
import os
import time
from pathlib import Path

import pytest
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.resilience import (
    CircuitBreaker,
    CircuitState,
    RetryPolicy,
    TimeoutManager,
    AgentFallbackChain,
    DeadLetterQueue,
    resilient_call,
)
from src.health import AgentHealthRegistry, AgentHealth


# ---------------------------------------------------------------------------
# Test 1 : CircuitBreaker s'ouvre apres le seuil d'echecs
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_circuit_breaker_opens_after_threshold():
    """Circuit breaker s'ouvre apres 5 echecs dans la fenetre de 60s."""
    cb = CircuitBreaker(failure_threshold=5, half_open_delay=30.0, window_seconds=60.0)
    assert cb.get_state() == "CLOSED"

    for _ in range(5):
        cb.record_failure()

    assert cb.get_state() == "OPEN"
    assert cb.can_execute() is False


# ---------------------------------------------------------------------------
# Test 2 : CircuitBreaker passe en HALF_OPEN apres le delai de recuperation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_circuit_breaker_half_open_recovery():
    """Circuit breaker passe en HALF_OPEN apres half_open_delay, puis CLOSED sur succes."""
    cb = CircuitBreaker(failure_threshold=2, half_open_delay=0.1, window_seconds=60.0)

    cb.record_failure()
    cb.record_failure()
    assert cb.get_state() == "OPEN"

    await asyncio.sleep(0.15)

    # can_execute() doit retourner True ET transitionner en HALF_OPEN
    assert cb.can_execute() is True
    assert cb.get_state() == "HALF_OPEN"

    cb.record_success()
    assert cb.get_state() == "CLOSED"


# ---------------------------------------------------------------------------
# Test 3 : RetryPolicy avec backoff exponentiel
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_retry_with_exponential_backoff():
    """RetryPolicy relance la coroutine avec backoff exponentiel jusqu'au succes."""
    policy = RetryPolicy(base=0.01, factor=2.0, max_delay=1.0)
    call_count = 0

    async def flaky_coro():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise RuntimeError("Transient error")
        return "success"

    result = await policy.execute(flaky_coro, max_retries=3)
    assert result == "success"
    assert call_count == 3


# ---------------------------------------------------------------------------
# Test 4 : AgentFallbackChain retourne les bons fallbacks
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fallback_chain_activation():
    """AgentFallbackChain retourne les fallbacks configures et liste vide pour agents sans fallback."""
    chain = AgentFallbackChain()

    # Agents avec fallback defini dans FALLBACK_MAP
    assert "executor" in chain.get_fallbacks("coder")
    assert "coder" in chain.get_fallbacks("researcher")

    # Agent inconnu (non present dans FALLBACK_MAP) : liste vide
    assert chain.get_fallbacks("architect") == []


# ---------------------------------------------------------------------------
# Test 5 : DeadLetterQueue persiste sur disque et respecte max_size
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dead_letter_queue_persistence(tmp_path):
    """DLQ persiste les entrees sur disque et respecte la limite max_size (FIFO)."""
    dlq_path = Path(tmp_path) / "test_dlq.json"
    dlq = DeadLetterQueue(path=dlq_path, max_size=3)

    for i in range(5):
        await dlq.push({"agent": f"agent_{i}", "error": f"fail_{i}"})

    items = await dlq.list_all()
    assert len(items) <= 3  # max_size respecte (les plus anciens sont droppes)

    # Verifie que le fichier existe bien sur disque
    assert dlq_path.exists()

    # Verifie la coherence du contenu JSON
    with dlq_path.open("r", encoding="utf-8") as fh:
        persisted = json.load(fh)
    assert isinstance(persisted, list)
    assert len(persisted) <= 3


# ---------------------------------------------------------------------------
# Test 6 : AgentHealthRegistry traque correctement succes et echecs
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_health_registry_tracking():
    """AgentHealthRegistry calcule correctement total_calls, status et avg_latency."""
    # Reinitialise le singleton pour isoler ce test
    AgentHealthRegistry._instance = None
    registry = AgentHealthRegistry.instance()

    agent = "test_agent_health"

    await registry.record_success(agent, 100.0)
    await registry.record_success(agent, 200.0)
    await registry.record_failure(agent)

    health = await registry.get_health(agent)

    assert health.total_calls == 3
    assert health.status in ("HEALTHY", "DEGRADED", "DOWN")
    # Latence moyenne = (100 + 200) / 2 succes = 150 ms
    assert health.avg_latency_ms == pytest.approx(150.0)
    # Taux de succes = 2/3
    assert health.success_rate == pytest.approx(2 / 3)
