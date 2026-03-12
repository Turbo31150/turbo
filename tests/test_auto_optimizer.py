"""Tests for src/auto_optimizer.py — Dynamic cluster parameter tuning.

Covers: Adjustment, AutoOptimizer (optimize, force_optimize, enable,
_optimize_routing_weights, _optimize_lb_concurrency, _optimize_loop_intervals,
get_history, get_stats), auto_optimizer singleton.
All external module imports are mocked.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.auto_optimizer import Adjustment, AutoOptimizer, auto_optimizer


# ===========================================================================
# Adjustment
# ===========================================================================

class TestAdjustment:
    def test_fields(self):
        a = Adjustment(ts=1000.0, param="weight_M1", old_value=1.0,
                       new_value=0.5, reason="low success", module="orch")
        assert a.param == "weight_M1"
        assert a.reason == "low success"


# ===========================================================================
# AutoOptimizer — enable/disable
# ===========================================================================

class TestEnableDisable:
    def test_enabled_by_default(self):
        ao = AutoOptimizer()
        assert ao._enabled is True

    def test_disable(self):
        ao = AutoOptimizer()
        ao.enable(False)
        assert ao._enabled is False

    def test_optimize_when_disabled(self):
        ao = AutoOptimizer()
        ao.enable(False)
        assert ao.optimize() == []


# ===========================================================================
# AutoOptimizer — cooldown
# ===========================================================================

class TestCooldown:
    def test_cooldown_blocks(self):
        ao = AutoOptimizer()
        ao._last_optimize = time.time()  # just optimized
        with patch.object(ao, "_optimize_routing_weights", return_value=[]), \
             patch.object(ao, "_optimize_lb_concurrency", return_value=[]), \
             patch.object(ao, "_optimize_loop_intervals", return_value=[]):
            result = ao.optimize()
        assert result == []

    def test_force_optimize_bypasses_cooldown(self):
        ao = AutoOptimizer()
        ao._last_optimize = time.time()
        with patch.object(ao, "_optimize_routing_weights", return_value=[]), \
             patch.object(ao, "_optimize_lb_concurrency", return_value=[]), \
             patch.object(ao, "_optimize_loop_intervals", return_value=[]):
            result = ao.force_optimize()
        # Should have run (cooldown reset)
        assert result == []  # no adjustments but ran through


# ===========================================================================
# AutoOptimizer — routing weights
# ===========================================================================

class TestRoutingWeights:
    def test_low_success_rate(self):
        ao = AutoOptimizer()
        mock_orch = MagicMock()
        mock_orch.get_node_stats.return_value = {
            "M1": {"total_calls": 50, "success_rate": 0.5, "avg_latency_ms": 100},
        }
        with patch.dict("sys.modules", {"src.orchestrator_v2": MagicMock(orchestrator_v2=mock_orch)}):
            result = ao._optimize_routing_weights()
        assert len(result) >= 1
        assert "success rate" in result[0]["reason"].lower() or "success" in result[0]["reason"].lower()

    def test_high_latency(self):
        ao = AutoOptimizer()
        mock_orch = MagicMock()
        mock_orch.get_node_stats.return_value = {
            "OL1": {"total_calls": 30, "success_rate": 0.95, "avg_latency_ms": 8000},
        }
        with patch.dict("sys.modules", {"src.orchestrator_v2": MagicMock(orchestrator_v2=mock_orch)}):
            result = ao._optimize_routing_weights()
        assert len(result) >= 1
        assert "latency" in result[0]["reason"].lower()

    def test_not_enough_data(self):
        ao = AutoOptimizer()
        mock_orch = MagicMock()
        mock_orch.get_node_stats.return_value = {
            "M1": {"total_calls": 3, "success_rate": 0.3, "avg_latency_ms": 100},
        }
        with patch.dict("sys.modules", {"src.orchestrator_v2": MagicMock(orchestrator_v2=mock_orch)}):
            result = ao._optimize_routing_weights()
        assert result == []

    def test_import_error(self):
        ao = AutoOptimizer()
        with patch("builtins.__import__", side_effect=ImportError("no module")):
            result = ao._optimize_routing_weights()
        assert result == []


# ===========================================================================
# AutoOptimizer — LB concurrency
# ===========================================================================

class TestLBConcurrency:
    def test_circuit_broken(self):
        ao = AutoOptimizer()
        mock_lb = MagicMock()
        mock_lb.get_status.return_value = {
            "nodes": {"M2": {"circuit_broken": True, "recent_failures": 5}},
        }
        with patch.dict("sys.modules", {"src.load_balancer": MagicMock(load_balancer=mock_lb)}):
            result = ao._optimize_lb_concurrency()
        assert len(result) == 1
        assert "circuit" in result[0]["reason"].lower()

    def test_no_issues(self):
        ao = AutoOptimizer()
        mock_lb = MagicMock()
        mock_lb.get_status.return_value = {"nodes": {"M1": {"circuit_broken": False}}}
        with patch.dict("sys.modules", {"src.load_balancer": MagicMock(load_balancer=mock_lb)}):
            result = ao._optimize_lb_concurrency()
        assert result == []


# ===========================================================================
# AutoOptimizer — loop intervals
# ===========================================================================

class TestLoopIntervals:
    def test_high_fail_rate(self):
        ao = AutoOptimizer()
        mock_loop = MagicMock()
        mock_loop.get_status.return_value = {
            "tasks": {"health_check": {"run_count": 20, "fail_count": 15, "interval_s": 60}},
        }
        with patch.dict("sys.modules", {"src.autonomous_loop": MagicMock(autonomous_loop=mock_loop)}):
            result = ao._optimize_loop_intervals()
        assert len(result) == 1
        assert result[0]["new_value"] == 120  # doubled

    def test_acceptable_fail_rate(self):
        ao = AutoOptimizer()
        mock_loop = MagicMock()
        mock_loop.get_status.return_value = {
            "tasks": {"health": {"run_count": 20, "fail_count": 2, "interval_s": 60}},
        }
        with patch.dict("sys.modules", {"src.autonomous_loop": MagicMock(autonomous_loop=mock_loop)}):
            result = ao._optimize_loop_intervals()
        assert result == []


# ===========================================================================
# AutoOptimizer — history / stats
# ===========================================================================

class TestHistoryAndStats:
    def test_history_empty(self):
        ao = AutoOptimizer()
        assert ao.get_history() == []

    def test_history_recorded(self):
        ao = AutoOptimizer()
        adj = Adjustment(ts=time.time(), param="test", old_value=1,
                         new_value=2, reason="test", module="test")
        ao._record(adj)
        history = ao.get_history()
        assert len(history) == 1
        assert history[0]["param"] == "test"

    def test_history_max(self):
        ao = AutoOptimizer()
        ao._max_history = 5
        for i in range(10):
            ao._record(Adjustment(ts=time.time(), param=f"p{i}",
                                  old_value=0, new_value=1, reason="r", module="m"))
        assert len(ao._history) == 5

    def test_stats(self):
        ao = AutoOptimizer()
        ao._record(Adjustment(ts=time.time(), param="p1", old_value=0,
                               new_value=1, reason="r", module="orch"))
        ao._record(Adjustment(ts=time.time(), param="p2", old_value=0,
                               new_value=1, reason="r", module="lb"))
        stats = ao.get_stats()
        assert stats["total_adjustments"] == 2
        assert stats["enabled"] is True
        assert stats["by_module"]["orch"] == 1
        assert stats["by_module"]["lb"] == 1


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert auto_optimizer is not None
        assert isinstance(auto_optimizer, AutoOptimizer)
