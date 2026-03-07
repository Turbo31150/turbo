"""Tests for src/agent_self_improve.py — Continuous optimization cycle.

Covers: ImprovementAction, ImprovementReport dataclasses,
SelfImprover (_get_current_metrics, _optimize_strategies,
_run_discovery, _learn_from_memory, _update_router, _tune_config,
_generate_recommendations, run_cycle, get_history).
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.agent_self_improve import ImprovementAction, ImprovementReport, SelfImprover


# ===========================================================================
# ImprovementAction
# ===========================================================================

class TestImprovementAction:
    def test_basic(self):
        action = ImprovementAction(
            action_type="strategy_change",
            target="code",
            description="Switch to M1",
            impact="+15% success",
            confidence=0.85,
        )
        assert action.action_type == "strategy_change"
        assert action.confidence == 0.85

    def test_all_types(self):
        for atype in ("strategy_change", "node_swap", "pattern_discovered",
                       "fact_learned", "circuit_update", "config_tune"):
            a = ImprovementAction(atype, "t", "d", "i", 0.5)
            assert a.action_type == atype

    def test_confidence_range(self):
        low = ImprovementAction("t", "t", "d", "i", 0.0)
        high = ImprovementAction("t", "t", "d", "i", 1.0)
        assert low.confidence == 0.0
        assert high.confidence == 1.0


# ===========================================================================
# ImprovementReport
# ===========================================================================

class TestImprovementReport:
    def test_summary(self):
        actions = [
            ImprovementAction("s", "t1", "d1", "i1", 0.9),
            ImprovementAction("s", "t2", "d2", "i2", 0.3),
            ImprovementAction("s", "t3", "d3", "i3", 0.8),
        ]
        report = ImprovementReport(
            cycle_id=1, timestamp="2026-03-07 12:00:00",
            duration_ms=150.0, actions=actions,
            metrics_before={"success_rate": 0.8},
            metrics_after={"success_rate": 0.85},
            recommendations=["Increase M1 usage"],
        )
        summary = report.summary
        assert "Cycle #1" in summary
        assert "3 actions" in summary
        assert "150ms" in summary
        assert "2 high-confidence" in summary

    def test_empty_actions(self):
        report = ImprovementReport(
            cycle_id=2, timestamp="now", duration_ms=50,
            actions=[], metrics_before={}, metrics_after={},
            recommendations=[],
        )
        assert "0 actions" in report.summary
        assert "0 high-confidence" in report.summary


# ===========================================================================
# SelfImprover — init
# ===========================================================================

class TestSelfImproverInit:
    def test_default_path(self):
        improver = SelfImprover()
        assert "etoile.db" in improver.db_path

    def test_custom_path(self):
        improver = SelfImprover(db_path="/tmp/test.db")
        assert improver.db_path == "/tmp/test.db"

    def test_cycle_count_starts_zero(self):
        improver = SelfImprover()
        assert improver._cycle_count == 0


# ===========================================================================
# SelfImprover — _get_current_metrics
# ===========================================================================

class TestGetCurrentMetrics:
    def test_db_error(self):
        improver = SelfImprover(db_path="/nonexistent/path.db")
        metrics = improver._get_current_metrics()
        assert metrics["total_dispatches"] == 0
        assert metrics["success_rate"] == 0

    def test_with_mock_db(self):
        mock_db = MagicMock()
        mock_overall = MagicMock()
        mock_overall.__getitem__ = lambda self, key: {
            "total": 100, "ok": 85, "avg_ms": 1500, "avg_q": 0.8
        }[key]

        mock_nodes_cursor = MagicMock()
        mock_nodes_cursor.fetchall.return_value = []
        mock_patterns_cursor = MagicMock()
        mock_patterns_cursor.fetchall.return_value = []

        call_count = [0]
        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                c = MagicMock()
                c.fetchone.return_value = mock_overall
                return c
            else:
                c = MagicMock()
                c.fetchall.return_value = []
                return c

        mock_db.execute.side_effect = side_effect

        with patch("src.agent_self_improve.sqlite3") as mock_sql:
            mock_sql.connect.return_value = mock_db
            mock_sql.Row = None
            improver = SelfImprover()
            metrics = improver._get_current_metrics()

        assert metrics["total_dispatches"] == 100
        assert metrics["success_rate"] == 0.85


# ===========================================================================
# SelfImprover — _optimize_strategies
# ===========================================================================

class TestOptimizeStrategies:
    def test_no_data(self):
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_db.execute.return_value = mock_cursor

        with patch("src.agent_self_improve.sqlite3") as mock_sql:
            mock_sql.connect.return_value = mock_db
            mock_sql.Row = None
            improver = SelfImprover()
            actions = improver._optimize_strategies()

        assert actions == []

    def test_finds_insight(self):
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {"pattern": "code", "strategy": "fast", "n": 20, "ok": 18, "avg_ms": 500},
            {"pattern": "code", "strategy": "slow", "n": 10, "ok": 3, "avg_ms": 5000},
        ]
        mock_db.execute.return_value = mock_cursor

        with patch("src.agent_self_improve.sqlite3") as mock_sql:
            mock_sql.connect.return_value = mock_db
            mock_sql.Row = None
            improver = SelfImprover()
            actions = improver._optimize_strategies()

        assert len(actions) >= 1
        assert actions[0].action_type == "strategy_insight"
        assert actions[0].target == "code"

    def test_db_error(self):
        with patch("src.agent_self_improve.sqlite3") as mock_sql:
            mock_sql.connect.side_effect = Exception("DB err")
            improver = SelfImprover()
            actions = improver._optimize_strategies()
        assert actions == []


# ===========================================================================
# SelfImprover — _run_discovery
# ===========================================================================

class TestRunDiscovery:
    def test_import_error(self):
        improver = SelfImprover()
        with patch.dict("sys.modules", {"src.pattern_discovery": None}):
            actions = improver._run_discovery()
        assert actions == []

    def test_no_patterns(self):
        mock_disc = MagicMock()
        mock_disc.discover.return_value = []

        with patch("src.pattern_discovery.PatternDiscovery", return_value=mock_disc):
            improver = SelfImprover()
            actions = improver._run_discovery()

        assert actions == []


# ===========================================================================
# SelfImprover — _learn_from_memory
# ===========================================================================

class TestLearnFromMemory:
    def test_import_error(self):
        improver = SelfImprover()
        with patch.dict("sys.modules", {"src.agent_episodic_memory": None}):
            actions = improver._learn_from_memory()
        assert actions == []


# ===========================================================================
# SelfImprover — _update_router
# ===========================================================================

class TestUpdateRouter:
    def test_import_error(self):
        improver = SelfImprover()
        with patch.dict("sys.modules", {"src.adaptive_router": None}):
            actions = improver._update_router()
        assert actions == []

    def test_with_recommendations(self):
        mock_router = MagicMock()
        mock_router.get_recommendations.return_value = [
            {"node": "M2", "message": "High failure rate on M2", "severity": "high"},
        ]

        with patch("src.adaptive_router.get_router", return_value=mock_router):
            improver = SelfImprover()
            actions = improver._update_router()

        assert len(actions) == 1
        assert actions[0].action_type == "router_alert"
        assert actions[0].confidence == 0.8


# ===========================================================================
# SelfImprover — _tune_config
# ===========================================================================

class TestTuneConfig:
    def test_no_slow_patterns(self):
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_db.execute.return_value = mock_cursor

        with patch("src.agent_self_improve.sqlite3") as mock_sql:
            mock_sql.connect.return_value = mock_db
            mock_sql.Row = None
            improver = SelfImprover()
            actions = improver._tune_config()

        assert actions == []

    def test_detects_slow(self):
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {"pattern": "reasoning", "avg_ms": 45000, "n": 5},
        ]
        mock_db.execute.return_value = mock_cursor

        with patch("src.agent_self_improve.sqlite3") as mock_sql:
            mock_sql.connect.return_value = mock_db
            mock_sql.Row = None
            improver = SelfImprover()
            actions = improver._tune_config()

        assert len(actions) == 1
        assert actions[0].action_type == "config_tune"
        assert actions[0].target == "reasoning"

    def test_db_error(self):
        with patch("src.agent_self_improve.sqlite3") as mock_sql:
            mock_sql.connect.side_effect = Exception("err")
            improver = SelfImprover()
            actions = improver._tune_config()
        assert actions == []


# ===========================================================================
# SelfImprover — _generate_recommendations
# ===========================================================================

class TestGenerateRecommendations:
    def test_low_success_rate(self):
        improver = SelfImprover()
        recs = improver._generate_recommendations(
            {"success_rate": 0.5, "avg_latency_ms": 1000, "nodes": {}},
            {}, [],
        )
        assert any("Success rate" in r or "success" in r.lower() for r in recs)

    def test_high_latency(self):
        improver = SelfImprover()
        recs = improver._generate_recommendations(
            {"success_rate": 0.9, "avg_latency_ms": 50000, "nodes": {}},
            {}, [],
        )
        assert any("latency" in r.lower() for r in recs)

    def test_high_confidence_actions(self):
        improver = SelfImprover()
        actions = [
            ImprovementAction("s", "t", "d", "i", 0.9),
            ImprovementAction("s", "t", "d", "i", 0.8),
        ]
        recs = improver._generate_recommendations(
            {"success_rate": 0.9, "avg_latency_ms": 1000, "nodes": {}},
            {}, actions,
        )
        assert any("high-confidence" in r for r in recs)

    def test_bad_node(self):
        improver = SelfImprover()
        recs = improver._generate_recommendations(
            {"success_rate": 0.9, "avg_latency_ms": 1000,
             "nodes": {"M3": {"n": 20, "ok": 4, "avg_ms": 5000}}},
            {}, [],
        )
        assert any("M3" in r for r in recs)

    def test_good_metrics_no_recs(self):
        improver = SelfImprover()
        recs = improver._generate_recommendations(
            {"success_rate": 0.95, "avg_latency_ms": 500,
             "nodes": {"M1": {"n": 100, "ok": 98, "avg_ms": 300}}},
            {}, [],
        )
        assert len(recs) == 0


# ===========================================================================
# SelfImprover — run_cycle
# ===========================================================================

class TestRunCycle:
    @pytest.mark.asyncio
    async def test_full_cycle(self):
        improver = SelfImprover()

        with patch.object(improver, "_get_current_metrics", return_value={
                "total_dispatches": 100, "success_rate": 0.85,
                "avg_latency_ms": 1500, "avg_quality": 0.8, "nodes": {}, "patterns": {}}), \
             patch.object(improver, "_optimize_strategies", return_value=[]), \
             patch.object(improver, "_run_discovery", return_value=[]), \
             patch.object(improver, "_learn_from_memory", return_value=[]), \
             patch.object(improver, "_update_router", return_value=[]), \
             patch.object(improver, "_tune_config", return_value=[]), \
             patch.object(improver, "_save_report"):
            report = await improver.run_cycle()

        assert isinstance(report, ImprovementReport)
        assert report.cycle_id == 1
        assert report.duration_ms > 0
        assert report.metrics_before["success_rate"] == 0.85

    @pytest.mark.asyncio
    async def test_increments_cycle_count(self):
        improver = SelfImprover()
        assert improver._cycle_count == 0

        with patch.object(improver, "_get_current_metrics", return_value={}), \
             patch.object(improver, "_optimize_strategies", return_value=[]), \
             patch.object(improver, "_run_discovery", return_value=[]), \
             patch.object(improver, "_learn_from_memory", return_value=[]), \
             patch.object(improver, "_update_router", return_value=[]), \
             patch.object(improver, "_tune_config", return_value=[]), \
             patch.object(improver, "_save_report"):
            await improver.run_cycle()
            await improver.run_cycle()

        assert improver._cycle_count == 2

    @pytest.mark.asyncio
    async def test_collects_actions(self):
        improver = SelfImprover()
        action1 = ImprovementAction("s", "t1", "d1", "i1", 0.9)
        action2 = ImprovementAction("c", "t2", "d2", "i2", 0.5)

        with patch.object(improver, "_get_current_metrics", return_value={"success_rate": 0.9, "avg_latency_ms": 500, "nodes": {}}), \
             patch.object(improver, "_optimize_strategies", return_value=[action1]), \
             patch.object(improver, "_run_discovery", return_value=[]), \
             patch.object(improver, "_learn_from_memory", return_value=[]), \
             patch.object(improver, "_update_router", return_value=[]), \
             patch.object(improver, "_tune_config", return_value=[action2]), \
             patch.object(improver, "_save_report"):
            report = await improver.run_cycle()

        assert len(report.actions) == 2


# ===========================================================================
# SelfImprover — get_history
# ===========================================================================

class TestGetHistory:
    def test_db_error(self):
        improver = SelfImprover(db_path="/nonexistent.db")
        history = improver.get_history()
        assert history == []

    def test_with_data(self):
        mock_db = MagicMock()
        mock_row = {"id": 1, "cycle_id": 1, "timestamp": "now",
                     "duration_ms": 100, "actions_count": 3}
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [mock_row]
        mock_db.execute.side_effect = [MagicMock(), mock_cursor]

        with patch("src.agent_self_improve.sqlite3") as mock_sql:
            mock_sql.connect.return_value = mock_db
            mock_sql.Row = None
            improver = SelfImprover()
            history = improver.get_history(limit=5)

        # get_history calls dict(r) on each row
        assert isinstance(history, list)

    def test_limit_parameter(self):
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_db.execute.side_effect = [MagicMock(), mock_cursor]

        with patch("src.agent_self_improve.sqlite3") as mock_sql:
            mock_sql.connect.return_value = mock_db
            mock_sql.Row = None
            improver = SelfImprover()
            improver.get_history(limit=3)

        # Verify limit was passed
        call_args = mock_db.execute.call_args_list[-1]
        assert call_args[0][1] == (3,)
