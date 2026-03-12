"""Tests for src/self_improve_engine.py — Autonomous cluster self-improvement."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.self_improve_engine import (
    SelfImproveEngine,
    NodeMetrics,
    ImprovementAction,
    self_improve_engine,
)


# ===========================================================================
# NodeMetrics
# ===========================================================================

class TestNodeMetrics:
    def test_success_rate_no_calls(self):
        m = NodeMetrics(node="M1")
        assert m.success_rate == 0.0

    def test_success_rate(self):
        m = NodeMetrics(node="M1", total_calls=100, success_count=85)
        assert m.success_rate == 0.85

    def test_is_degraded_low_quality(self):
        m = NodeMetrics(node="M3", total_calls=20, success_count=18,
                        avg_quality=0.3)
        assert m.is_degraded is True

    def test_is_degraded_low_success(self):
        m = NodeMetrics(node="M3", total_calls=20, success_count=8,
                        avg_quality=0.7)
        assert m.is_degraded is True

    def test_not_degraded(self):
        m = NodeMetrics(node="M1", total_calls=50, success_count=48,
                        avg_quality=0.85)
        assert m.is_degraded is False

    def test_not_degraded_few_calls(self):
        m = NodeMetrics(node="M1", total_calls=2, success_count=0,
                        avg_quality=0.1)
        assert m.is_degraded is False  # not enough data


# ===========================================================================
# SelfImproveEngine — collect_metrics
# ===========================================================================

class TestCollectMetrics:
    def test_returns_empty_on_db_error(self):
        import sqlite3 as _sqlite3
        engine = SelfImproveEngine(db_path=":memory:")
        with patch("src.self_improve_engine.sqlite3") as mock_sql:
            mock_sql.Error = _sqlite3.Error
            mock_sql.connect.side_effect = _sqlite3.OperationalError("DB gone")
            result = engine._collect_metrics()
        assert result == {}

    def test_collects_from_db(self):
        engine = SelfImproveEngine(db_path=":memory:")

        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, k: {
            "node": "M1", "total": 50, "ok": 45,
            "avg_lat": 500, "avg_q": 0.85,
        }[k]

        mock_db = MagicMock()
        mock_cur = MagicMock()
        # First execute returns node metrics, second returns pattern metrics
        mock_db.execute = MagicMock(side_effect=[
            MagicMock(fetchall=MagicMock(return_value=[mock_row])),
            MagicMock(fetchall=MagicMock(return_value=[])),
        ])
        mock_db.row_factory = None

        with patch("src.self_improve_engine.sqlite3") as mock_sql:
            mock_sql.Row = None
            mock_sql.connect.return_value = mock_db
            result = engine._collect_metrics()

        assert "M1" in result
        assert result["M1"].total_calls == 50


# ===========================================================================
# SelfImproveEngine — run_cycle
# ===========================================================================

class TestRunCycle:
    @pytest.mark.asyncio
    async def test_no_data_returns_early(self):
        engine = SelfImproveEngine(db_path=":memory:")
        with patch.object(engine, "_collect_metrics", return_value={}):
            report = await engine.run_cycle()
        assert report["status"] == "no_data"

    @pytest.mark.asyncio
    async def test_full_cycle_with_metrics(self):
        engine = SelfImproveEngine(db_path=":memory:")
        metrics = {
            "M1": NodeMetrics("M1", total_calls=50, success_count=48,
                              avg_quality=0.9, avg_latency_ms=400),
        }
        with patch.object(engine, "_collect_metrics", return_value=metrics):
            with patch.object(engine, "_handle_degraded_nodes", return_value=[]):
                with patch.object(engine, "_adjust_weights", return_value=[]):
                    with patch.object(engine, "_optimize_strategies", return_value=[]):
                        with patch.object(engine, "_evolve_patterns", return_value=[]):
                            with patch.object(engine, "_persist_actions"):
                                report = await engine.run_cycle()

        assert report["nodes_analyzed"] == 1
        assert report["actions_taken"] == 0
        assert "M1" in report["node_health"]

    @pytest.mark.asyncio
    async def test_cycle_with_actions(self):
        engine = SelfImproveEngine(db_path=":memory:")
        metrics = {
            "M3": NodeMetrics("M3", total_calls=20, success_count=8,
                              avg_quality=0.3, avg_latency_ms=15000),
        }
        action = ImprovementAction(
            action_type="node_disable", target="M3",
            description="Circuit opened: quality=0.30", confidence=0.8,
        )
        with patch.object(engine, "_collect_metrics", return_value=metrics):
            with patch.object(engine, "_handle_degraded_nodes", return_value=[action]):
                with patch.object(engine, "_adjust_weights", return_value=[]):
                    with patch.object(engine, "_optimize_strategies", return_value=[]):
                        with patch.object(engine, "_evolve_patterns", return_value=[]):
                            with patch.object(engine, "_persist_actions"):
                                with patch.object(engine, "_notify"):
                                    report = await engine.run_cycle()

        assert report["actions_taken"] == 1
        assert report["actions"][0]["type"] == "node_disable"


# ===========================================================================
# SelfImproveEngine — adjust_weights
# ===========================================================================

class TestAdjustWeights:
    def test_increases_weight_for_good_node(self):
        engine = SelfImproveEngine(db_path=":memory:")
        metrics = {
            "M1": NodeMetrics("M1", total_calls=50, success_count=48,
                              avg_quality=0.9),
        }
        mock_health = MagicMock()
        mock_health.base_weight = 1.5
        mock_router = MagicMock()
        mock_router.health = {"M1": mock_health}

        with patch.dict(sys.modules, {
            "src.adaptive_router": MagicMock(get_router=MagicMock(return_value=mock_router)),
        }):
            actions = engine._adjust_weights(metrics)

        assert len(actions) == 1
        assert mock_health.base_weight == 1.6  # +0.1

    def test_decreases_weight_for_bad_node(self):
        engine = SelfImproveEngine(db_path=":memory:")
        metrics = {
            "M3": NodeMetrics("M3", total_calls=20, success_count=12,
                              avg_quality=0.4),
        }
        mock_health = MagicMock()
        mock_health.base_weight = 1.2
        mock_router = MagicMock()
        mock_router.health = {"M3": mock_health}

        with patch.dict(sys.modules, {
            "src.adaptive_router": MagicMock(get_router=MagicMock(return_value=mock_router)),
        }):
            actions = engine._adjust_weights(metrics)

        assert len(actions) == 1
        assert mock_health.base_weight == pytest.approx(1.1, abs=0.01)


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_singleton_exists(self):
        assert self_improve_engine is not None
        assert isinstance(self_improve_engine, SelfImproveEngine)

    def test_get_status(self):
        status = self_improve_engine.get_status()
        assert "cycles" in status
        assert "total_actions" in status
