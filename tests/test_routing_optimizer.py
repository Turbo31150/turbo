"""Tests for src/routing_optimizer.py — Real-time adaptive routing.

Covers: NodeProfile (is_healthy), TaskProfile, RoutingOptimizer (get_node_profile,
get_task_profile, get_optimal_config, get_recommendations, _maybe_refresh, report).
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.routing_optimizer import NodeProfile, TaskProfile, RoutingOptimizer


# ===========================================================================
# NodeProfile
# ===========================================================================

class TestNodeProfile:
    def test_defaults(self):
        np = NodeProfile(name="M1")
        assert np.avg_latency_ms == 0
        assert np.success_rate == 1.0
        assert np.health_score == 1.0
        assert np.concurrent_limit == 3

    def test_is_healthy_true(self):
        np = NodeProfile(name="M1", health_score=0.8, success_rate=0.9)
        assert np.is_healthy is True

    def test_is_healthy_low_health(self):
        np = NodeProfile(name="M1", health_score=0.3, success_rate=0.9)
        assert np.is_healthy is False

    def test_is_healthy_low_success(self):
        np = NodeProfile(name="M1", health_score=0.8, success_rate=0.5)
        assert np.is_healthy is False

    def test_is_healthy_boundary(self):
        # Exactly 0.5 health_score -> not healthy (> 0.5 required)
        np = NodeProfile(name="M1", health_score=0.5, success_rate=0.9)
        assert np.is_healthy is False
        # Exactly 0.7 success_rate -> not healthy (> 0.7 required)
        np2 = NodeProfile(name="M1", health_score=0.8, success_rate=0.7)
        assert np2.is_healthy is False


# ===========================================================================
# TaskProfile
# ===========================================================================

class TestTaskProfile:
    def test_defaults(self):
        tp = TaskProfile(pattern="code", size="medium")
        assert tp.optimal_node == "M1"
        assert tp.optimal_timeout_s == 30
        assert tp.max_tokens == 512
        assert tp.inject_system_prompt is True


# ===========================================================================
# RoutingOptimizer — class constants
# ===========================================================================

class TestConstants:
    def test_default_concurrency(self):
        assert RoutingOptimizer.DEFAULT_CONCURRENCY["M1"] == 4
        assert RoutingOptimizer.DEFAULT_CONCURRENCY["M3"] == 1

    def test_size_tokens(self):
        assert RoutingOptimizer.SIZE_TOKENS["nano"] == 64
        assert RoutingOptimizer.SIZE_TOKENS["xl"] == 2048

    def test_size_system_prompt(self):
        assert RoutingOptimizer.SIZE_SYSTEM_PROMPT["nano"] is False
        assert RoutingOptimizer.SIZE_SYSTEM_PROMPT["large"] is True


# ===========================================================================
# RoutingOptimizer — get_optimal_config (word-count sizing)
# ===========================================================================

class TestGetOptimalConfig:
    def _make_optimizer(self):
        opt = RoutingOptimizer.__new__(RoutingOptimizer)
        opt.db_path = ":memory:"
        opt._node_profiles = {}
        opt._task_profiles = {}
        opt._last_refresh = 0
        opt._refresh_interval = 999999  # prevent auto-refresh hitting real DB
        return opt

    def test_nano(self):
        opt = self._make_optimizer()
        opt._last_refresh = __import__("time").time()  # skip refresh
        config = opt.get_optimal_config("code", "hello")
        assert config["max_tokens"] == 64
        assert config["inject_system_prompt"] is False

    def test_micro(self):
        opt = self._make_optimizer()
        opt._last_refresh = __import__("time").time()
        config = opt.get_optimal_config("code", "write a simple function please")
        assert config["max_tokens"] == 128
        assert config["inject_system_prompt"] is False

    def test_small(self):
        opt = self._make_optimizer()
        opt._last_refresh = __import__("time").time()
        prompt = " ".join(["word"] * 15)
        config = opt.get_optimal_config("code", prompt)
        assert config["max_tokens"] == 256
        assert config["inject_system_prompt"] is True

    def test_medium(self):
        opt = self._make_optimizer()
        opt._last_refresh = __import__("time").time()
        prompt = " ".join(["word"] * 40)
        config = opt.get_optimal_config("code", prompt)
        assert config["max_tokens"] == 512

    def test_large(self):
        opt = self._make_optimizer()
        opt._last_refresh = __import__("time").time()
        prompt = " ".join(["word"] * 80)
        config = opt.get_optimal_config("code", prompt)
        assert config["max_tokens"] == 1024

    def test_xl(self):
        opt = self._make_optimizer()
        opt._last_refresh = __import__("time").time()
        prompt = " ".join(["word"] * 150)
        config = opt.get_optimal_config("code", prompt)
        assert config["max_tokens"] == 2048

    def test_config_structure(self):
        opt = self._make_optimizer()
        opt._last_refresh = __import__("time").time()
        config = opt.get_optimal_config("code", "test")
        assert "node" in config
        assert "timeout_s" in config
        assert "max_tokens" in config
        assert "inject_system_prompt" in config
        assert "concurrent_limit" in config
        assert "health_score" in config


# ===========================================================================
# RoutingOptimizer — get_node_profile / get_task_profile
# ===========================================================================

class TestProfiles:
    def _make_optimizer(self):
        import time
        opt = RoutingOptimizer.__new__(RoutingOptimizer)
        opt.db_path = ":memory:"
        opt._node_profiles = {"M1": NodeProfile(name="M1", avg_latency_ms=500)}
        opt._task_profiles = {"code:small": TaskProfile(pattern="code", size="small", optimal_node="M1")}
        opt._last_refresh = time.time()
        opt._refresh_interval = 999999
        return opt

    def test_get_existing_node(self):
        opt = self._make_optimizer()
        np = opt.get_node_profile("M1")
        assert np.name == "M1"
        assert np.avg_latency_ms == 500

    def test_get_missing_node(self):
        opt = self._make_optimizer()
        np = opt.get_node_profile("M99")
        assert np.name == "M99"
        assert np.avg_latency_ms == 0  # default

    def test_get_existing_task(self):
        opt = self._make_optimizer()
        tp = opt.get_task_profile("code", "small")
        assert tp.pattern == "code"
        assert tp.optimal_node == "M1"

    def test_get_missing_task(self):
        opt = self._make_optimizer()
        tp = opt.get_task_profile("math", "large")
        assert tp.pattern == "math"
        assert tp.max_tokens == 1024


# ===========================================================================
# RoutingOptimizer — get_recommendations
# ===========================================================================

class TestGetRecommendations:
    def _make_optimizer(self):
        import time
        opt = RoutingOptimizer.__new__(RoutingOptimizer)
        opt.db_path = ":memory:"
        opt._node_profiles = {}
        opt._task_profiles = {}
        opt._last_refresh = time.time()
        opt._refresh_interval = 999999
        return opt

    def test_no_profiles_no_recs(self):
        opt = self._make_optimizer()
        assert opt.get_recommendations() == []

    def test_low_success_rate(self):
        opt = self._make_optimizer()
        opt._node_profiles["M2"] = NodeProfile(
            name="M2", success_rate=0.4, total_requests=20,
        )
        recs = opt.get_recommendations()
        assert len(recs) >= 1
        assert recs[0]["type"] == "node_health"
        assert recs[0]["severity"] == "high"

    def test_medium_success_rate(self):
        opt = self._make_optimizer()
        opt._node_profiles["M2"] = NodeProfile(
            name="M2", success_rate=0.6, total_requests=15,
        )
        recs = opt.get_recommendations()
        health_recs = [r for r in recs if r["type"] == "node_health"]
        assert len(health_recs) == 1
        assert health_recs[0]["severity"] == "medium"

    def test_low_requests_ignored(self):
        opt = self._make_optimizer()
        opt._node_profiles["M2"] = NodeProfile(
            name="M2", success_rate=0.3, total_requests=5,
        )
        recs = opt.get_recommendations()
        health_recs = [r for r in recs if r["type"] == "node_health"]
        assert len(health_recs) == 0  # <10 requests

    def test_high_latency(self):
        opt = self._make_optimizer()
        opt._node_profiles["M3"] = NodeProfile(
            name="M3", p95_ms=45000, total_requests=10,
        )
        recs = opt.get_recommendations()
        lat_recs = [r for r in recs if r["type"] == "latency"]
        assert len(lat_recs) == 1

    def test_load_imbalance(self):
        opt = self._make_optimizer()
        opt._node_profiles["M1"] = NodeProfile(name="M1", total_requests=100)
        opt._node_profiles["OL1"] = NodeProfile(name="OL1", total_requests=5)
        recs = opt.get_recommendations()
        lb_recs = [r for r in recs if r["type"] == "load_balance"]
        assert len(lb_recs) == 1

    def test_no_load_imbalance_similar(self):
        opt = self._make_optimizer()
        opt._node_profiles["M1"] = NodeProfile(name="M1", total_requests=50)
        opt._node_profiles["OL1"] = NodeProfile(name="OL1", total_requests=40)
        recs = opt.get_recommendations()
        lb_recs = [r for r in recs if r["type"] == "load_balance"]
        assert len(lb_recs) == 0


# ===========================================================================
# RoutingOptimizer — report
# ===========================================================================

class TestReport:
    def test_report_structure(self):
        import time
        opt = RoutingOptimizer.__new__(RoutingOptimizer)
        opt.db_path = ":memory:"
        opt._node_profiles = {"M1": NodeProfile(name="M1", avg_latency_ms=200, success_rate=0.95, total_requests=50)}
        opt._task_profiles = {"code:small": TaskProfile(pattern="code", size="small")}
        opt._last_refresh = time.time()
        opt._refresh_interval = 999999
        report = opt.report()
        assert "nodes" in report
        assert "recommendations" in report
        assert "task_profiles" in report
        assert "M1" in report["nodes"]
        assert report["nodes"]["M1"]["avg_ms"] == 200

    def test_report_empty(self):
        import time
        opt = RoutingOptimizer.__new__(RoutingOptimizer)
        opt.db_path = ":memory:"
        opt._node_profiles = {}
        opt._task_profiles = {}
        opt._last_refresh = time.time()
        opt._refresh_interval = 999999
        report = opt.report()
        assert report["nodes"] == {}
        assert report["recommendations"] == []
        assert report["task_profiles"] == {}
