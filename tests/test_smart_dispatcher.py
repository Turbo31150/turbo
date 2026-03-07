"""Tests for src/smart_dispatcher.py — Adaptive routing from benchmark data.

Covers: NodeStats (success_rate, score), SmartDispatcher (_get_best_node,
_should_retry, _retry_on_fallback, get_routing_report, get_cowork_scripts),
dispatch_batch, _maybe_refresh_stats.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.smart_dispatcher import NodeStats, SmartDispatcher


# ===========================================================================
# NodeStats
# ===========================================================================

class TestNodeStats:
    def test_defaults(self):
        ns = NodeStats(node="M1")
        assert ns.total_calls == 0
        assert ns.success_count == 0
        assert ns.avg_latency_ms == 0
        assert ns.avg_quality == 0
        assert ns.weight == 1.0

    def test_success_rate_no_calls(self):
        ns = NodeStats(node="M1", total_calls=0)
        assert ns.success_rate == 0.0

    def test_success_rate(self):
        ns = NodeStats(node="M1", total_calls=100, success_count=90)
        assert ns.success_rate == 0.9

    def test_score_perfect(self):
        ns = NodeStats(node="M1", total_calls=100, success_count=100,
                       avg_latency_ms=500, avg_quality=1.0, weight=1.0,
                       last_failure_ago_s=1000)
        s = ns.score
        # sr=1.0*0.4 + speed~0.98*0.25 + quality=1.0*0.25 + weight=1.0*0.1 = ~0.995
        assert s > 0.9

    def test_score_with_recent_failure_penalty(self):
        ns = NodeStats(node="M1", total_calls=100, success_count=100,
                       avg_latency_ms=500, avg_quality=1.0, weight=1.0,
                       last_failure_ago_s=60)  # recent failure
        s = ns.score
        # Same as above but -0.2 penalty
        assert s < 0.85

    def test_score_slow_node(self):
        ns = NodeStats(node="M3", total_calls=50, success_count=45,
                       avg_latency_ms=25000, avg_quality=0.7, weight=1.2)
        s = ns.score
        # speed = max(0, 1 - 25000/30000) = 0.167
        assert s < 0.7

    def test_score_fast_high_quality(self):
        ns = NodeStats(node="OL1", total_calls=200, success_count=190,
                       avg_latency_ms=200, avg_quality=0.85, weight=1.3)
        s = ns.score
        assert s > 0.8

    def test_score_zero_latency(self):
        ns = NodeStats(node="M1", total_calls=10, success_count=10,
                       avg_latency_ms=0, avg_quality=0.8, weight=1.0)
        s = ns.score
        assert s > 0


# ===========================================================================
# SmartDispatcher — init
# ===========================================================================

class TestSmartDispatcherInit:
    def test_init(self):
        with patch("src.smart_dispatcher.PatternAgentRegistry"):
            d = SmartDispatcher(db_path=":memory:")
        assert d._stats_cache == {}
        assert d._cache_age == 0.0
        assert d._cache_ttl == 60.0


# ===========================================================================
# SmartDispatcher — _should_retry
# ===========================================================================

class TestShouldRetry:
    def setup_method(self):
        with patch("src.smart_dispatcher.PatternAgentRegistry"):
            self.d = SmartDispatcher(db_path=":memory:")

    def test_empty_content_retries(self):
        result = MagicMock()
        result.content = ""
        assert self.d._should_retry("code", result) is True

    def test_short_content_retries(self):
        result = MagicMock()
        result.content = "short"
        assert self.d._should_retry("code", result) is True

    def test_long_content_no_retry(self):
        result = MagicMock()
        result.content = "x" * 100
        assert self.d._should_retry("code", result) is False


# ===========================================================================
# SmartDispatcher — _get_best_node
# ===========================================================================

class TestGetBestNode:
    def setup_method(self):
        with patch("src.smart_dispatcher.PatternAgentRegistry"):
            self.d = SmartDispatcher(db_path=":memory:")

    def test_no_stats(self):
        agent = MagicMock()
        agent.primary_node = "M1"
        assert self.d._get_best_node("code", agent) is None

    def test_few_calls_ignored(self):
        self.d._stats_cache = {
            "code": {
                "M1": NodeStats("M1", total_calls=2, success_count=2, avg_quality=1.0),
            }
        }
        agent = MagicMock()
        agent.primary_node = "OL1"
        assert self.d._get_best_node("code", agent) is None

    def test_picks_best_when_significantly_better(self):
        self.d._stats_cache = {
            "code": {
                "M1": NodeStats("M1", total_calls=50, success_count=50,
                                avg_quality=0.9, avg_latency_ms=500, weight=1.8),
                "OL1": NodeStats("OL1", total_calls=30, success_count=20,
                                 avg_quality=0.5, avg_latency_ms=200, weight=1.3),
            }
        }
        agent = MagicMock()
        agent.primary_node = "OL1"
        best = self.d._get_best_node("code", agent)
        assert best == "M1"

    def test_no_override_when_similar(self):
        self.d._stats_cache = {
            "code": {
                "M1": NodeStats("M1", total_calls=50, success_count=48,
                                avg_quality=0.85, avg_latency_ms=600, weight=1.8),
                "OL1": NodeStats("OL1", total_calls=30, success_count=28,
                                 avg_quality=0.82, avg_latency_ms=300, weight=1.3),
            }
        }
        agent = MagicMock()
        agent.primary_node = "M1"
        # M1 already good enough — no override
        best = self.d._get_best_node("code", agent)
        assert best is None


# ===========================================================================
# SmartDispatcher — _retry_on_fallback
# ===========================================================================

class TestRetryOnFallback:
    def setup_method(self):
        with patch("src.smart_dispatcher.PatternAgentRegistry"):
            self.d = SmartDispatcher(db_path=":memory:")

    @pytest.mark.asyncio
    async def test_retry_success(self):
        agent = MagicMock()
        agent.primary_node = "M1"
        original = MagicMock()
        original.node = "M1"
        original.success = False

        success_result = MagicMock()
        success_result.success = True
        success_result.metadata = None
        self.d.registry.dispatch = AsyncMock(return_value=success_result)

        result = await self.d._retry_on_fallback("code", "prompt", agent, original)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_retry_all_fail(self):
        agent = MagicMock()
        agent.primary_node = "M1"
        original = MagicMock()
        original.node = "M1"
        original.success = False

        fail_result = MagicMock()
        fail_result.success = False
        self.d.registry.dispatch = AsyncMock(return_value=fail_result)

        result = await self.d._retry_on_fallback("code", "prompt", agent, original)
        # Returns original since all retries failed
        assert result is original

    @pytest.mark.asyncio
    async def test_filters_failed_node(self):
        agent = MagicMock()
        agent.primary_node = "OL1"
        original = MagicMock()
        original.node = "OL1"
        original.success = False

        success_result = MagicMock()
        success_result.success = True
        success_result.metadata = None

        calls = []
        async def capture_dispatch(pat, prompt):
            calls.append(agent.primary_node)
            return success_result

        self.d.registry.dispatch = capture_dispatch
        await self.d._retry_on_fallback("simple", "hi", agent, original)
        # OL1 should not be in fallback calls since it was the failed node
        assert "OL1" not in calls


# ===========================================================================
# SmartDispatcher — _maybe_refresh_stats
# ===========================================================================

class TestMaybeRefreshStats:
    def test_skips_when_fresh(self):
        with patch("src.smart_dispatcher.PatternAgentRegistry"):
            d = SmartDispatcher(db_path=":memory:")
        import time
        d._cache_age = time.time()  # just refreshed
        with patch("src.smart_dispatcher.sqlite3") as mock_sql:
            d._maybe_refresh_stats()
        mock_sql.connect.assert_not_called()

    def test_refreshes_when_stale(self):
        with patch("src.smart_dispatcher.PatternAgentRegistry"):
            d = SmartDispatcher(db_path=":memory:")
        d._cache_age = 0  # very stale
        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, k: {
            "classified_type": "code", "node": "M1",
            "total": 50, "ok": 45, "avg_ms": 600, "avg_q": 0.85
        }[k]

        mock_db = MagicMock()
        mock_cur = MagicMock()
        mock_cur.execute.return_value.fetchall.return_value = []
        mock_db.cursor.return_value = mock_cur
        with patch("src.smart_dispatcher.sqlite3") as mock_sql:
            mock_sql.connect.return_value = mock_db
            d._maybe_refresh_stats()
        mock_sql.connect.assert_called_once()

    def test_db_error_no_crash(self):
        import sqlite3 as _sqlite3
        with patch("src.smart_dispatcher.PatternAgentRegistry"):
            d = SmartDispatcher(db_path=":memory:")
        d._cache_age = 0
        with patch("src.smart_dispatcher.sqlite3") as mock_sql:
            mock_sql.Error = _sqlite3.Error
            mock_sql.connect.side_effect = _sqlite3.OperationalError("DB gone")
            d._maybe_refresh_stats()  # should not raise


# ===========================================================================
# SmartDispatcher — get_cowork_scripts
# ===========================================================================

class TestGetCoworkScripts:
    def setup_method(self):
        with patch("src.smart_dispatcher.PatternAgentRegistry"):
            self.d = SmartDispatcher(db_path=":memory:")

    def test_unknown_pattern(self):
        scripts = self.d.get_cowork_scripts("nonexistent_pattern_xyz")
        assert scripts == []

    def test_known_pattern_db_error(self):
        import sqlite3 as _sqlite3
        with patch("src.smart_dispatcher.sqlite3") as mock_sql:
            mock_sql.Error = _sqlite3.Error
            mock_sql.connect.side_effect = _sqlite3.OperationalError("DB error")
            scripts = self.d.get_cowork_scripts("code")
        assert scripts == []

    def test_known_pattern_empty_result(self):
        mock_db = MagicMock()
        mock_db.execute.return_value.fetchall.return_value = []
        with patch("src.smart_dispatcher.sqlite3") as mock_sql:
            mock_sql.connect.return_value = mock_db
            scripts = self.d.get_cowork_scripts("code")
        assert scripts == []


# ===========================================================================
# SmartDispatcher — get_routing_report
# ===========================================================================

class TestGetRoutingReport:
    def test_empty_cache(self):
        with patch("src.smart_dispatcher.PatternAgentRegistry"):
            d = SmartDispatcher(db_path=":memory:")
        d._stats_cache = {}
        import time
        d._cache_age = time.time()
        report = d.get_routing_report()
        assert report == {}

    def test_with_data(self):
        with patch("src.smart_dispatcher.PatternAgentRegistry") as MockReg:
            d = SmartDispatcher(db_path=":memory:")
        import time
        d._cache_age = time.time()

        mock_agent = MagicMock()
        mock_agent.primary_node = "M1"
        d.registry.agents = {"code": mock_agent}

        d._stats_cache = {
            "code": {
                "M1": NodeStats("M1", total_calls=50, success_count=48,
                                avg_quality=0.9, avg_latency_ms=500, weight=1.8),
            }
        }
        report = d.get_routing_report()
        assert "code" in report
        assert report["code"]["default_node"] == "M1"
        assert "M1" in report["code"]["nodes"]


# ===========================================================================
# SmartDispatcher — _feed_back (feedback loops)
# ===========================================================================

class TestFeedBack:
    def test_feed_back_calls_orchestrator(self):
        mock_orch = MagicMock()
        result = MagicMock()
        result.node = "M1"
        result.latency_ms = 500
        result.quality_score = 0.85
        result.success = True

        with patch.dict(sys.modules, {
            "src.orchestrator_v2": MagicMock(orchestrator_v2=mock_orch),
            "src.adaptive_router": MagicMock(get_router=MagicMock(return_value=MagicMock())),
            "src.event_stream": MagicMock(get_stream=MagicMock(return_value=MagicMock())),
        }):
            from src.smart_dispatcher import SmartDispatcher
            SmartDispatcher._feed_back("code", result)

        mock_orch.record_call.assert_called_once()

    def test_feed_back_graceful_on_missing_modules(self):
        result = MagicMock()
        result.node = "OL1"
        result.latency_ms = 200
        result.quality_score = 0.7
        result.success = True

        with patch.dict(sys.modules, {
            "src.orchestrator_v2": None,
            "src.adaptive_router": None,
            "src.event_stream": None,
        }):
            from src.smart_dispatcher import SmartDispatcher
            SmartDispatcher._feed_back("simple", result)  # should not raise
