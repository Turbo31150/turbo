"""Comprehensive tests for src/adaptive_router.py — Adaptive Router with circuit breakers.

Tests cover:
- CircuitState enum values
- CircuitBreaker: state transitions, record_success, record_failure, allow_request, cooldown
- NodeHealth: success_rate, effective_weight, update_latency (EMA), capacity limits
- PatternAffinity dataclass
- AdaptiveRouter: pick_node, pick_nodes, acquire, release, record, get_status,
  get_recommendations, _init_nodes, _load_history
- Edge cases: all nodes down, extreme latency, cooldown expiry, capacity saturated
- Singleton get_router

All external dependencies (DB, imports) are mocked.
"""

from __future__ import annotations

import sqlite3
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

# Project root on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))


# ---------------------------------------------------------------------------
# Mock NODES from src.pattern_agents before importing adaptive_router
# ---------------------------------------------------------------------------

FAKE_NODES = {
    "M1": {"url": "http://127.0.0.1:1234/api/v1/chat", "weight": 1.8},
    "M2": {"url": "http://192.168.1.26:1234/api/v1/chat", "weight": 1.5},
    "M3": {"url": "http://192.168.1.113:1234/api/v1/chat", "weight": 1.2},
    "OL1": {"url": "http://127.0.0.1:11434/api/chat", "weight": 1.3},
}

_saved_pattern_agents = sys.modules.get("src.pattern_agents")
_mock_pattern_agents = MagicMock()
_mock_pattern_agents.NODES = FAKE_NODES
sys.modules["src.pattern_agents"] = _mock_pattern_agents

from src.adaptive_router import (
    AdaptiveRouter,
    CircuitBreaker,
    CircuitState,
    NodeHealth,
    PatternAffinity,
    get_router,
)

# Restore after import
if _saved_pattern_agents is not None:
    sys.modules["src.pattern_agents"] = _saved_pattern_agents
else:
    del sys.modules["src.pattern_agents"]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def cb():
    """Fresh CircuitBreaker for node M1."""
    return CircuitBreaker(node="M1", failure_threshold=3, success_threshold=2, cooldown_s=10.0)


@pytest.fixture
def health():
    """Fresh NodeHealth for testing."""
    return NodeHealth(node="M1", base_weight=1.8, max_concurrent=6)


@pytest.fixture
def router():
    """AdaptiveRouter with mocked DB and pattern_agents."""
    with patch("src.adaptive_router.AdaptiveRouter._load_history"):
        with patch("src.adaptive_router.AdaptiveRouter._init_nodes") as mock_init:
            r = AdaptiveRouter(db_path=":memory:")
            # Manually set up nodes like _init_nodes would
            for name, cfg in FAKE_NODES.items():
                r.circuits[name] = CircuitBreaker(node=name)
                r.health[name] = NodeHealth(
                    node=name,
                    base_weight=cfg.get("weight", 1.0),
                    max_concurrent=AdaptiveRouter.NODE_LIMITS.get(name, 3),
                )
            return r


# ===========================================================================
# CircuitState
# ===========================================================================

class TestCircuitState:
    def test_values(self):
        assert CircuitState.CLOSED.value == "closed"
        assert CircuitState.OPEN.value == "open"
        assert CircuitState.HALF_OPEN.value == "half_open"

    def test_members(self):
        assert len(CircuitState) == 3


# ===========================================================================
# CircuitBreaker
# ===========================================================================

class TestCircuitBreaker:

    def test_initial_state_closed(self, cb):
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0
        assert cb.success_count == 0

    def test_allow_request_closed(self, cb):
        assert cb.allow_request() is True

    def test_record_success_resets_failures(self, cb):
        cb.failure_count = 2
        cb.record_success()
        assert cb.failure_count == 0
        assert cb.success_count == 1
        assert cb.last_success_ts > 0

    def test_record_failure_increments(self, cb):
        cb.record_failure()
        assert cb.failure_count == 1
        assert cb.success_count == 0
        assert cb.last_failure_ts > 0

    def test_trips_to_open_after_threshold(self, cb):
        """Circuit trips to OPEN after failure_threshold consecutive failures."""
        for _ in range(cb.failure_threshold):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_does_not_trip_before_threshold(self, cb):
        for _ in range(cb.failure_threshold - 1):
            cb.record_failure()
        assert cb.state == CircuitState.CLOSED

    def test_open_rejects_requests(self, cb):
        for _ in range(cb.failure_threshold):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert cb.allow_request() is False

    def test_open_to_half_open_after_cooldown(self, cb):
        for _ in range(cb.failure_threshold):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN
        # Simulate cooldown elapsed
        cb.last_failure_ts = time.time() - cb.cooldown_s - 1
        assert cb.allow_request() is True
        assert cb.state == CircuitState.HALF_OPEN

    def test_half_open_allows_requests(self, cb):
        cb.state = CircuitState.HALF_OPEN
        assert cb.allow_request() is True

    def test_half_open_to_closed_after_successes(self, cb):
        cb.state = CircuitState.HALF_OPEN
        cb.success_count = 0
        for _ in range(cb.success_threshold):
            cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_half_open_to_open_on_failure(self, cb):
        cb.state = CircuitState.HALF_OPEN
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_success_in_closed_stays_closed(self, cb):
        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_failure_resets_success_count(self, cb):
        cb.record_success()
        cb.record_success()
        assert cb.success_count == 2
        cb.record_failure()
        assert cb.success_count == 0

    def test_open_does_not_transition_before_cooldown(self, cb):
        for _ in range(cb.failure_threshold):
            cb.record_failure()
        cb.last_failure_ts = time.time() - 1  # Only 1 second ago, cooldown is 10s
        assert cb.allow_request() is False
        assert cb.state == CircuitState.OPEN

    def test_cooldown_boundary_exact(self, cb):
        """Cooldown at exactly the boundary should transition."""
        for _ in range(cb.failure_threshold):
            cb.record_failure()
        cb.last_failure_ts = time.time() - cb.cooldown_s  # Exactly at boundary
        assert cb.allow_request() is True
        assert cb.state == CircuitState.HALF_OPEN

    def test_multiple_trip_cycles(self, cb):
        """Test CLOSED -> OPEN -> HALF_OPEN -> OPEN -> HALF_OPEN -> CLOSED cycle."""
        # Trip to OPEN
        for _ in range(cb.failure_threshold):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN

        # Cooldown -> HALF_OPEN
        cb.last_failure_ts = time.time() - cb.cooldown_s - 1
        cb.allow_request()
        assert cb.state == CircuitState.HALF_OPEN

        # Fail again -> back to OPEN
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

        # Cooldown again -> HALF_OPEN
        cb.last_failure_ts = time.time() - cb.cooldown_s - 1
        cb.allow_request()
        assert cb.state == CircuitState.HALF_OPEN

        # Succeed enough -> CLOSED
        for _ in range(cb.success_threshold):
            cb.record_success()
        assert cb.state == CircuitState.CLOSED


# ===========================================================================
# NodeHealth
# ===========================================================================

class TestNodeHealth:

    def test_initial_success_rate(self, health):
        """No calls yet -> success_rate = 0."""
        assert health.success_rate == 0.0

    def test_success_rate_calculation(self, health):
        health.total_calls = 10
        health.total_success = 7
        assert health.success_rate == pytest.approx(0.7)

    def test_success_rate_all_success(self, health):
        health.total_calls = 100
        health.total_success = 100
        assert health.success_rate == 1.0

    def test_success_rate_zero_calls_no_division_by_zero(self, health):
        health.total_calls = 0
        health.total_success = 0
        # max(1, 0) = 1 -> 0/1 = 0
        assert health.success_rate == 0.0

    def test_effective_weight_healthy(self, health):
        health.total_calls = 100
        health.total_success = 100
        health.ema_latency_ms = 1000  # 1s
        health.active_requests = 0
        # sr = 1.0
        # latency_factor = max(0.1, 1.0 - 1000/60000) = 1 - 0.01667 = ~0.983
        # capacity_factor = max(0.1, 1.0 - 0/6) = 1.0
        w = health.effective_weight
        expected = 1.8 * 1.0 * (1.0 - 1000 / 60000) * 1.0
        assert w == pytest.approx(expected, rel=1e-3)

    def test_effective_weight_high_latency(self, health):
        """Very high latency penalizes weight."""
        health.total_calls = 10
        health.total_success = 10
        health.ema_latency_ms = 59000  # Nearly 60s
        health.active_requests = 0
        w = health.effective_weight
        # latency_factor = max(0.1, 1.0 - 59000/60000) = max(0.1, 0.0167) = 0.1
        # clamped to 0.1
        assert w == pytest.approx(1.8 * 1.0 * 0.1 * 1.0, abs=0.05)

    def test_effective_weight_extreme_latency(self, health):
        """Latency > 60s is clamped to 0.1 factor."""
        health.total_calls = 10
        health.total_success = 10
        health.ema_latency_ms = 120000  # 120s!
        w = health.effective_weight
        # latency_factor = max(0.1, 1.0 - 120000/60000) = max(0.1, -1.0) = 0.1
        assert w == pytest.approx(1.8 * 1.0 * 0.1 * 1.0, rel=0.01)

    def test_effective_weight_near_capacity(self, health):
        """Node near capacity gets penalized."""
        health.total_calls = 10
        health.total_success = 10
        health.ema_latency_ms = 0
        health.active_requests = 5  # 5/6 capacity
        w = health.effective_weight
        # capacity_factor = max(0.1, 1 - 5/6) = max(0.1, 0.1667) = 0.1667
        cap_factor = max(0.1, 1.0 - 5 / 6)
        assert w == pytest.approx(1.8 * 1.0 * 1.0 * cap_factor, rel=0.01)

    def test_effective_weight_at_capacity(self, health):
        """At max capacity, capacity_factor clamped to 0.1."""
        health.total_calls = 10
        health.total_success = 10
        health.ema_latency_ms = 0
        health.active_requests = 6
        w = health.effective_weight
        assert w == pytest.approx(1.8 * 1.0 * 1.0 * 0.1, rel=0.01)

    def test_effective_weight_zero_success(self, health):
        """Zero success rate -> effective weight near 0."""
        health.total_calls = 10
        health.total_success = 0
        w = health.effective_weight
        assert w == pytest.approx(0.0)

    def test_update_latency_first_call(self, health):
        """First call sets EMA directly."""
        health.ema_latency_ms = 0
        health.update_latency(500)
        assert health.ema_latency_ms == 500

    def test_update_latency_ema(self, health):
        """Subsequent calls use EMA formula."""
        health.ema_latency_ms = 0
        health.update_latency(1000)
        assert health.ema_latency_ms == 1000
        health.update_latency(2000)
        # EMA = 0.3 * 2000 + 0.7 * 1000 = 600 + 700 = 1300
        assert health.ema_latency_ms == pytest.approx(1300)

    def test_update_latency_converges(self, health):
        """After many identical updates, EMA converges to the value."""
        health.ema_latency_ms = 0
        for _ in range(100):
            health.update_latency(500)
        assert health.ema_latency_ms == pytest.approx(500, abs=1)

    def test_update_latency_zero(self, health):
        """Updating with 0ms latency."""
        health.update_latency(1000)
        health.update_latency(0)
        # EMA = 0.3 * 0 + 0.7 * 1000 = 700
        assert health.ema_latency_ms == pytest.approx(700)


# ===========================================================================
# PatternAffinity
# ===========================================================================

class TestPatternAffinity:

    def test_default_values(self):
        pa = PatternAffinity(pattern="code", node="M1")
        assert pa.score == 0.0
        assert pa.calls == 0
        assert pa.successes == 0
        assert pa.avg_quality == 0.0
        assert pa.avg_latency_ms == 0.0

    def test_custom_values(self):
        pa = PatternAffinity(
            pattern="debug", node="M2",
            score=0.85, calls=100, successes=90,
            avg_quality=0.9, avg_latency_ms=2500.0,
        )
        assert pa.pattern == "debug"
        assert pa.node == "M2"
        assert pa.score == 0.85


# ===========================================================================
# AdaptiveRouter
# ===========================================================================

class TestAdaptiveRouterInit:

    def test_init_creates_nodes(self, router):
        assert set(router.circuits.keys()) == {"M1", "M2", "M3", "OL1"}
        assert set(router.health.keys()) == {"M1", "M2", "M3", "OL1"}

    def test_init_weights_match_config(self, router):
        assert router.health["M1"].base_weight == 1.8
        assert router.health["M2"].base_weight == 1.5
        assert router.health["M3"].base_weight == 1.2
        assert router.health["OL1"].base_weight == 1.3

    def test_init_max_concurrent(self, router):
        assert router.health["M1"].max_concurrent == 11
        assert router.health["M2"].max_concurrent == 3
        assert router.health["M3"].max_concurrent == 2
        assert router.health["OL1"].max_concurrent == 3

    def test_all_circuits_closed_initially(self, router):
        for name, cb in router.circuits.items():
            assert cb.state == CircuitState.CLOSED, f"{name} should start CLOSED"


class TestAdaptiveRouterLoadHistory:

    def test_load_history_populates_health(self):
        """_load_history reads dispatch_log and seeds health + affinity."""
        db = sqlite3.connect(":memory:")
        db.execute("""
            CREATE TABLE agent_dispatch_log (
                node TEXT, classified_type TEXT, success INTEGER,
                latency_ms REAL, quality_score REAL
            )
        """)
        db.executemany(
            "INSERT INTO agent_dispatch_log VALUES (?, ?, ?, ?, ?)",
            [
                ("M1", "code", 1, 800, 0.9),
                ("M1", "code", 1, 1200, 0.8),
                ("M1", "code", 0, 5000, 0.2),
                ("M2", "debug", 1, 3000, 0.7),
            ],
        )
        db.commit()
        db_path = ":memory:"

        # We need to use the actual file since connect(":memory:") creates separate DBs
        # So we use a temp file approach
        import tempfile, os
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp_path = tmp.name
        tmp.close()

        db2 = sqlite3.connect(tmp_path)
        db2.execute("""
            CREATE TABLE agent_dispatch_log (
                node TEXT, classified_type TEXT, success INTEGER,
                latency_ms REAL, quality_score REAL
            )
        """)
        db2.executemany(
            "INSERT INTO agent_dispatch_log VALUES (?, ?, ?, ?, ?)",
            [
                ("M1", "code", 1, 800, 0.9),
                ("M1", "code", 1, 1200, 0.8),
                ("M1", "code", 0, 5000, 0.2),
                ("M2", "debug", 1, 3000, 0.7),
            ],
        )
        db2.commit()
        db2.close()

        try:
            with patch("src.adaptive_router.AdaptiveRouter._init_nodes") as mock_init:
                r = AdaptiveRouter.__new__(AdaptiveRouter)
                r.db_path = tmp_path
                r.circuits = {}
                r.health = {}
                from collections import defaultdict
                r.affinity = defaultdict(dict)

                # Manually set up nodes
                for name, cfg in FAKE_NODES.items():
                    r.circuits[name] = CircuitBreaker(node=name)
                    r.health[name] = NodeHealth(
                        node=name,
                        base_weight=cfg.get("weight", 1.0),
                        max_concurrent=AdaptiveRouter.NODE_LIMITS.get(name, 3),
                    )

                r._load_history()

                # M1 should have 3 calls (all code pattern)
                assert r.health["M1"].total_calls == 3
                assert r.health["M1"].total_success == 2
                assert r.health["M1"].ema_latency_ms > 0

                # M2 should have 1 call (debug pattern)
                assert r.health["M2"].total_calls == 1
                assert r.health["M2"].total_success == 1

                # Affinity should have entries
                assert "code" in r.affinity
                assert "M1" in r.affinity["code"]
                assert r.affinity["code"]["M1"].calls == 3
                assert "debug" in r.affinity
                assert "M2" in r.affinity["debug"]
        finally:
            os.unlink(tmp_path)

    def test_load_history_handles_missing_db(self):
        """_load_history should not crash on missing DB."""
        with patch("src.adaptive_router.AdaptiveRouter._init_nodes"):
            r = AdaptiveRouter.__new__(AdaptiveRouter)
            r.db_path = "/nonexistent/path/nope.db"
            r.circuits = {}
            r.health = {}
            from collections import defaultdict
            r.affinity = defaultdict(dict)
            # Should not raise
            r._load_history()

    def test_load_history_handles_missing_table(self):
        """_load_history should not crash if table does not exist."""
        import tempfile, os
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp_path = tmp.name
        tmp.close()
        # Create empty DB (no tables)
        conn = sqlite3.connect(tmp_path)
        conn.close()

        try:
            with patch("src.adaptive_router.AdaptiveRouter._init_nodes"):
                r = AdaptiveRouter.__new__(AdaptiveRouter)
                r.db_path = tmp_path
                r.circuits = {}
                r.health = {}
                from collections import defaultdict
                r.affinity = defaultdict(dict)
                r._load_history()  # Should not raise
        finally:
            # Ensure no lingering connections before unlinking on Windows
            import gc
            gc.collect()
            try:
                os.unlink(tmp_path)
            except PermissionError:
                pass  # Windows file locking — temp file will be cleaned later


class TestPickNode:

    def test_picks_preferred_when_all_equal(self, router):
        """When all nodes are equal, preferred gets a bonus."""
        node = router.pick_node("code", preferred="M1")
        assert node == "M1"

    def test_picks_highest_weight_default(self, router):
        """M1 has highest base_weight (1.8), should be preferred."""
        # Set all nodes to have some calls so success_rate > 0
        for h in router.health.values():
            h.total_calls = 10
            h.total_success = 10
        node = router.pick_node("unknown_pattern", preferred="M1")
        assert node == "M1"

    def test_skips_open_circuit(self, router):
        """Node with open circuit should be skipped."""
        for h in router.health.values():
            h.total_calls = 10
            h.total_success = 10
        # Trip M1 circuit
        router.circuits["M1"].state = CircuitState.OPEN
        router.circuits["M1"].last_failure_ts = time.time()  # Recent failure
        node = router.pick_node("code", preferred="M1")
        assert node != "M1"

    def test_skips_node_at_capacity(self, router):
        """Node at max_concurrent should be skipped."""
        for h in router.health.values():
            h.total_calls = 10
            h.total_success = 10
        router.health["M1"].active_requests = router.health["M1"].max_concurrent
        node = router.pick_node("code", preferred="M1")
        assert node != "M1"

    def test_fallback_when_all_nodes_down(self, router):
        """When all circuits are open, fallback to preferred."""
        for name, cb in router.circuits.items():
            cb.state = CircuitState.OPEN
            cb.last_failure_ts = time.time()  # Recent failure, won't transition
        node = router.pick_node("code", preferred="M1")
        assert node == "M1"

    def test_fallback_preferred_custom(self, router):
        """When all nodes are down, returns the custom preferred node."""
        for name, cb in router.circuits.items():
            cb.state = CircuitState.OPEN
            cb.last_failure_ts = time.time()
        node = router.pick_node("code", preferred="OL1")
        assert node == "OL1"

    def test_affinity_influences_choice(self, router):
        """Node with high affinity for a pattern should be chosen."""
        for h in router.health.values():
            h.total_calls = 10
            h.total_success = 10
        # Give OL1 very high affinity for pattern "quick"
        router.affinity["quick"]["OL1"] = PatternAffinity(
            pattern="quick", node="OL1", score=1.0, calls=100, successes=100,
        )
        # Give M1 low affinity
        router.affinity["quick"]["M1"] = PatternAffinity(
            pattern="quick", node="M1", score=0.1, calls=100, successes=10,
        )
        node = router.pick_node("quick", preferred="M2")
        # OL1 should win due to high affinity score
        assert node == "OL1"

    def test_all_at_capacity_falls_back(self, router):
        """All nodes at capacity -> fallback to preferred."""
        for h in router.health.values():
            h.active_requests = h.max_concurrent
        node = router.pick_node("code", preferred="M3")
        assert node == "M3"


class TestPickNodes:

    def test_returns_up_to_count(self, router):
        for h in router.health.values():
            h.total_calls = 10
            h.total_success = 10
        nodes = router.pick_nodes("code", count=3)
        assert len(nodes) <= 3
        assert len(nodes) >= 1

    def test_returns_all_when_count_exceeds_available(self, router):
        for h in router.health.values():
            h.total_calls = 10
            h.total_success = 10
        nodes = router.pick_nodes("code", count=10)
        assert len(nodes) == 4  # M1, M2, M3, OL1

    def test_excludes_open_circuits(self, router):
        for h in router.health.values():
            h.total_calls = 10
            h.total_success = 10
        router.circuits["M1"].state = CircuitState.OPEN
        router.circuits["M1"].last_failure_ts = time.time()
        nodes = router.pick_nodes("code", count=10)
        assert "M1" not in nodes

    def test_returns_empty_when_all_down(self, router):
        for cb in router.circuits.values():
            cb.state = CircuitState.OPEN
            cb.last_failure_ts = time.time()
        nodes = router.pick_nodes("code", count=3)
        assert nodes == []

    def test_ordered_by_score(self, router):
        for h in router.health.values():
            h.total_calls = 10
            h.total_success = 10
        nodes = router.pick_nodes("code", count=4, preferred="M1")
        # M1 has highest weight (1.8) + preferred bonus -> should be first
        assert nodes[0] == "M1"


class TestAcquireRelease:

    def test_acquire_increments(self, router):
        assert router.health["M1"].active_requests == 0
        router.acquire("M1")
        assert router.health["M1"].active_requests == 1
        router.acquire("M1")
        assert router.health["M1"].active_requests == 2

    def test_release_decrements(self, router):
        router.acquire("M1")
        router.acquire("M1")
        router.release("M1")
        assert router.health["M1"].active_requests == 1

    def test_release_does_not_go_below_zero(self, router):
        router.release("M1")  # Already at 0
        assert router.health["M1"].active_requests == 0

    def test_acquire_unknown_node_no_crash(self, router):
        """Acquiring unknown node should not crash."""
        router.acquire("UNKNOWN")  # no-op

    def test_release_unknown_node_no_crash(self, router):
        """Releasing unknown node should not crash."""
        router.release("UNKNOWN")  # no-op


class TestRecord:

    def test_record_success_updates_health(self, router):
        router.record("M1", pattern="code", success=True, latency_ms=500, quality=0.9)
        assert router.health["M1"].total_calls == 1
        assert router.health["M1"].total_success == 1
        assert router.health["M1"].ema_latency_ms == 500

    def test_record_failure_updates_health(self, router):
        router.record("M1", pattern="code", success=False, latency_ms=5000, quality=0.0)
        assert router.health["M1"].total_calls == 1
        assert router.health["M1"].total_success == 0

    def test_record_updates_circuit_breaker(self, router):
        # 5 failures should trip circuit (default threshold)
        for _ in range(5):
            router.record("M1", success=False, latency_ms=1000)
        assert router.circuits["M1"].state == CircuitState.OPEN

    def test_record_success_resets_circuit(self, router):
        """Success resets failure_count on circuit."""
        router.record("M1", success=False, latency_ms=1000)
        router.record("M1", success=False, latency_ms=1000)
        assert router.circuits["M1"].failure_count == 2
        router.record("M1", success=True, latency_ms=500)
        assert router.circuits["M1"].failure_count == 0

    def test_record_creates_affinity(self, router):
        router.record("M1", pattern="translation", success=True, latency_ms=800, quality=0.95)
        assert "translation" in router.affinity
        assert "M1" in router.affinity["translation"]
        aff = router.affinity["translation"]["M1"]
        assert aff.calls == 1
        assert aff.successes == 1
        assert aff.avg_quality == pytest.approx(0.95)
        assert aff.avg_latency_ms == pytest.approx(800)

    def test_record_updates_existing_affinity(self, router):
        router.record("M1", pattern="code", success=True, latency_ms=1000, quality=0.8)
        router.record("M1", pattern="code", success=True, latency_ms=2000, quality=0.6)
        aff = router.affinity["code"]["M1"]
        assert aff.calls == 2
        assert aff.successes == 2
        assert aff.avg_quality == pytest.approx(0.7)
        assert aff.avg_latency_ms == pytest.approx(1500)

    def test_record_no_pattern_skips_affinity(self, router):
        router.record("M1", pattern="", success=True, latency_ms=500)
        # No affinity entry should be created for empty pattern
        assert "" not in router.affinity

    def test_record_unknown_node_no_crash(self, router):
        """Recording for unknown node should not crash."""
        router.record("UNKNOWN", pattern="code", success=True, latency_ms=100)

    def test_record_affinity_score_formula(self, router):
        """Verify the affinity score formula: sr*0.5 + quality*0.3 + latency_factor*0.2."""
        router.record("M1", pattern="math", success=True, latency_ms=1000, quality=0.8)
        aff = router.affinity["math"]["M1"]
        sr = 1.0  # 1/1
        expected_score = sr * 0.5 + min(1, 0.8) * 0.3 + max(0, 1 - 1000 / 30000) * 0.2
        assert aff.score == pytest.approx(expected_score, rel=1e-3)


class TestGetStatus:

    def test_returns_all_nodes(self, router):
        status = router.get_status()
        assert "nodes" in status
        assert set(status["nodes"].keys()) == {"M1", "M2", "M3", "OL1"}

    def test_node_status_fields(self, router):
        status = router.get_status()
        for name, info in status["nodes"].items():
            assert "circuit" in info
            assert "failure_count" in info
            assert "success_rate" in info
            assert "ema_latency_ms" in info
            assert "active_requests" in info
            assert "max_concurrent" in info
            assert "effective_weight" in info
            assert "total_calls" in info

    def test_total_nodes(self, router):
        status = router.get_status()
        assert status["total_nodes"] == 4

    def test_healthy_nodes_count(self, router):
        status = router.get_status()
        assert status["healthy_nodes"] == 4

    def test_healthy_nodes_decreases_on_open_circuit(self, router):
        router.circuits["M1"].state = CircuitState.OPEN
        router.circuits["M1"].last_failure_ts = time.time()
        status = router.get_status()
        assert status["healthy_nodes"] == 3

    def test_open_circuits_list(self, router):
        router.circuits["M2"].state = CircuitState.OPEN
        router.circuits["M2"].last_failure_ts = time.time()
        status = router.get_status()
        assert "M2" in status["open_circuits"]

    def test_affinities_in_status(self, router):
        router.record("M1", pattern="code", success=True, latency_ms=500, quality=0.9)
        status = router.get_status()
        assert "affinities" in status
        assert "code" in status["affinities"]
        assert "M1" in status["affinities"]["code"]
        assert "score" in status["affinities"]["code"]["M1"]


class TestGetRecommendations:

    def test_no_recommendations_healthy(self, router):
        """Healthy router should produce no recommendations."""
        recs = router.get_recommendations()
        assert recs == []

    def test_circuit_open_recommendation(self, router):
        router.circuits["M1"].state = CircuitState.OPEN
        router.circuits["M1"].failure_count = 5
        router.circuits["M1"].last_failure_ts = time.time()
        recs = router.get_recommendations()
        open_recs = [r for r in recs if r["type"] == "circuit_open"]
        assert len(open_recs) == 1
        assert open_recs[0]["node"] == "M1"
        assert open_recs[0]["severity"] == "high"

    def test_low_success_recommendation(self, router):
        router.health["M2"].total_calls = 20
        router.health["M2"].total_success = 5  # 25% success
        recs = router.get_recommendations()
        low_recs = [r for r in recs if r["type"] == "low_success"]
        assert len(low_recs) == 1
        assert low_recs[0]["node"] == "M2"

    def test_low_success_not_triggered_below_threshold(self, router):
        """Fewer than 10 calls should not trigger low_success."""
        router.health["M2"].total_calls = 5
        router.health["M2"].total_success = 0
        recs = router.get_recommendations()
        low_recs = [r for r in recs if r["type"] == "low_success"]
        assert len(low_recs) == 0

    def test_high_latency_recommendation(self, router):
        router.health["M3"].total_calls = 10
        router.health["M3"].ema_latency_ms = 45000  # 45s
        recs = router.get_recommendations()
        lat_recs = [r for r in recs if r["type"] == "high_latency"]
        assert len(lat_recs) == 1
        assert lat_recs[0]["node"] == "M3"
        assert lat_recs[0]["severity"] == "medium"

    def test_high_latency_not_triggered_below_threshold(self, router):
        """Fewer than 5 calls should not trigger high_latency."""
        router.health["M3"].total_calls = 3
        router.health["M3"].ema_latency_ms = 99999
        recs = router.get_recommendations()
        lat_recs = [r for r in recs if r["type"] == "high_latency"]
        assert len(lat_recs) == 0

    def test_at_capacity_recommendation(self, router):
        router.health["OL1"].active_requests = router.health["OL1"].max_concurrent
        recs = router.get_recommendations()
        cap_recs = [r for r in recs if r["type"] == "at_capacity"]
        assert len(cap_recs) == 1
        assert cap_recs[0]["node"] == "OL1"

    def test_weak_pattern_recommendation(self, router):
        router.affinity["obscure"]["M1"] = PatternAffinity(
            pattern="obscure", node="M1", score=0.15, calls=10, successes=2,
        )
        recs = router.get_recommendations()
        weak_recs = [r for r in recs if r["type"] == "weak_pattern"]
        assert len(weak_recs) == 1
        assert weak_recs[0]["pattern"] == "obscure"

    def test_weak_pattern_not_triggered_few_calls(self, router):
        """Pattern with <= 5 calls should not trigger weak_pattern."""
        router.affinity["rare"]["M1"] = PatternAffinity(
            pattern="rare", node="M1", score=0.1, calls=3, successes=0,
        )
        recs = router.get_recommendations()
        weak_recs = [r for r in recs if r["type"] == "weak_pattern"]
        assert len(weak_recs) == 0

    def test_multiple_recommendations(self, router):
        """Multiple issues produce multiple recommendations."""
        # Open circuit
        router.circuits["M1"].state = CircuitState.OPEN
        router.circuits["M1"].failure_count = 5
        router.circuits["M1"].last_failure_ts = time.time()
        # Low success
        router.health["M2"].total_calls = 20
        router.health["M2"].total_success = 3
        # At capacity
        router.health["OL1"].active_requests = router.health["OL1"].max_concurrent

        recs = router.get_recommendations()
        types = {r["type"] for r in recs}
        assert "circuit_open" in types
        assert "low_success" in types
        assert "at_capacity" in types


# ===========================================================================
# Edge Cases
# ===========================================================================

class TestEdgeCases:

    def test_pick_node_with_no_health_data(self, router):
        """Nodes with zero calls still get default affinity of 0.3."""
        node = router.pick_node("code", preferred="M1")
        # Should not crash; M1 has effective_weight=0 (0 success_rate) but aff_score=0.3
        assert node in {"M1", "M2", "M3", "OL1"}

    def test_ema_latency_extreme_spikes(self, health):
        """Extreme latency spikes are smoothed by EMA."""
        health.update_latency(100)
        health.update_latency(100000)  # Extreme spike
        # EMA = 0.3 * 100000 + 0.7 * 100 = 30000 + 70 = 30070
        assert health.ema_latency_ms == pytest.approx(30070)
        # After several normal readings, it recovers
        for _ in range(20):
            health.update_latency(100)
        assert health.ema_latency_ms < 200  # Should converge back down

    def test_concurrent_acquire_release_stress(self, router):
        """Many acquire/release cycles stay consistent."""
        for _ in range(100):
            router.acquire("M1")
        assert router.health["M1"].active_requests == 100
        for _ in range(100):
            router.release("M1")
        assert router.health["M1"].active_requests == 0
        # Extra releases should stay at 0
        router.release("M1")
        assert router.health["M1"].active_requests == 0

    def test_pick_node_all_at_capacity_and_open(self, router):
        """All nodes at capacity AND open circuits -> returns preferred."""
        for name in router.circuits:
            router.circuits[name].state = CircuitState.OPEN
            router.circuits[name].last_failure_ts = time.time()
        for name in router.health:
            router.health[name].active_requests = router.health[name].max_concurrent
        result = router.pick_node("code", preferred="M3")
        assert result == "M3"

    def test_record_many_patterns(self, router):
        """Recording many different patterns should work."""
        for i in range(50):
            router.record("M1", pattern=f"pattern_{i}", success=True,
                          latency_ms=100 + i * 10, quality=0.5)
        assert len(router.affinity) == 50
        for i in range(50):
            assert f"pattern_{i}" in router.affinity

    def test_cooldown_expiry_allows_half_open(self, router):
        """After cooldown expires, circuit transitions to HALF_OPEN on allow_request."""
        cb = router.circuits["M1"]
        # Trip circuit
        for _ in range(cb.failure_threshold):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN
        # Fast-forward past cooldown
        cb.last_failure_ts = time.time() - cb.cooldown_s - 5
        assert cb.allow_request() is True
        assert cb.state == CircuitState.HALF_OPEN

    def test_pick_nodes_count_zero(self, router):
        """Asking for 0 nodes returns empty list."""
        nodes = router.pick_nodes("code", count=0)
        assert nodes == []

    def test_record_negative_latency_no_crash(self, router):
        """Negative latency should not crash (degenerate input)."""
        router.record("M1", pattern="code", success=True, latency_ms=-100, quality=0.5)
        # No assertion on value -- just verify no crash


# ===========================================================================
# Singleton get_router
# ===========================================================================

class TestGetRouter:

    def test_get_router_returns_instance(self):
        import src.adaptive_router as ar_module
        ar_module._router = None
        with patch.object(AdaptiveRouter, "__init__", return_value=None):
            r = get_router()
            assert r is not None

    def test_get_router_returns_same_instance(self):
        import src.adaptive_router as ar_module
        with patch.object(AdaptiveRouter, "__init__", return_value=None):
            ar_module._router = None
            r1 = get_router()
            r2 = get_router()
            assert r1 is r2

    def test_get_router_resets_with_none(self):
        import src.adaptive_router as ar_module
        with patch.object(AdaptiveRouter, "__init__", return_value=None):
            ar_module._router = None
            r1 = get_router()
            ar_module._router = None
            r2 = get_router()
            # r1 and r2 are different instances since we reset _router
            assert r1 is not r2


# ===========================================================================
# Integration-style: full record + pick cycle
# ===========================================================================

class TestRecordAndPick:

    def test_record_improves_node_selection(self, router):
        """Recording good results for a node on a pattern improves its selection."""
        # Give all nodes some baseline
        for h in router.health.values():
            h.total_calls = 10
            h.total_success = 8

        # Record great results for OL1 on "translation"
        for _ in range(20):
            router.record("OL1", pattern="translation", success=True,
                          latency_ms=200, quality=0.95)
        # Record poor results for M1 on "translation" (failures hurt more)
        for _ in range(20):
            router.record("M1", pattern="translation", success=False,
                          latency_ms=8000, quality=0.1)

        # Use M2 as preferred (neutral) so M1 gets no preferred bonus
        node = router.pick_node("translation", preferred="M2")
        # OL1 should be chosen due to high affinity + M1 degraded by failures
        assert node == "OL1"

    def test_circuit_trip_reroutes(self, router):
        """After a node trips its circuit, traffic goes elsewhere."""
        for h in router.health.values():
            h.total_calls = 10
            h.total_success = 10

        # Trip M1 circuit by recording failures
        for _ in range(5):
            router.record("M1", success=False, latency_ms=10000)

        assert router.circuits["M1"].state == CircuitState.OPEN
        node = router.pick_node("code", preferred="M1")
        assert node != "M1"

    def test_full_lifecycle(self, router):
        """Full lifecycle: pick -> acquire -> record -> release."""
        for h in router.health.values():
            h.total_calls = 10
            h.total_success = 10

        node = router.pick_node("code", preferred="M1")
        router.acquire(node)
        assert router.health[node].active_requests == 1

        router.record(node, pattern="code", success=True, latency_ms=800, quality=0.9)
        assert router.health[node].total_calls == 11
        assert router.health[node].total_success == 11

        router.release(node)
        assert router.health[node].active_requests == 0

        status = router.get_status()
        assert status["nodes"][node]["total_calls"] == 11
