"""Tests for src/orchestrator_v2.py — Unified coordinator.

Covers: NodeStats, SessionBudget, ROUTING_MATRIX, OrchestratorV2
(record_call, weighted_score, fallback_chain, budget, node_stats,
health_check, get_alerts).
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

from src.orchestrator_v2 import (
    NodeStats, SessionBudget, ROUTING_MATRIX, OrchestratorV2,
)


# ===========================================================================
# NodeStats
# ===========================================================================

class TestNodeStats:
    def test_defaults(self):
        ns = NodeStats()
        assert ns.total_calls == 0
        assert ns.success_count == 0
        assert ns.total_latency_ms == 0.0
        assert ns.total_tokens == 0

    def test_success_rate_no_calls(self):
        ns = NodeStats()
        assert ns.success_rate == 1.0

    def test_success_rate(self):
        ns = NodeStats(total_calls=10, success_count=8)
        assert ns.success_rate == 0.8

    def test_avg_latency_no_calls(self):
        ns = NodeStats()
        assert ns.avg_latency_ms == 100.0

    def test_avg_latency(self):
        ns = NodeStats(total_calls=4, total_latency_ms=800.0)
        assert ns.avg_latency_ms == 200.0

    def test_avg_latency_norm_low(self):
        ns = NodeStats(total_calls=1, total_latency_ms=100.0)
        assert ns.avg_latency_norm == 0.2  # 100/500

    def test_avg_latency_norm_capped(self):
        ns = NodeStats(total_calls=1, total_latency_ms=1000.0)
        assert ns.avg_latency_norm == 1.0  # capped at 1.0


# ===========================================================================
# SessionBudget
# ===========================================================================

class TestSessionBudget:
    def test_defaults(self):
        sb = SessionBudget()
        assert sb.total_tokens == 0
        assert sb.total_calls == 0

    def test_record(self):
        sb = SessionBudget()
        sb.record("M1", tokens=100)
        sb.record("M1", tokens=200)
        sb.record("OL1", tokens=50)
        assert sb.total_tokens == 350
        assert sb.total_calls == 3
        assert sb.tokens_by_node["M1"] == 300
        assert sb.calls_by_node["M1"] == 2

    def test_record_zero_tokens(self):
        sb = SessionBudget()
        sb.record("M1")
        assert sb.total_calls == 1
        assert sb.total_tokens == 0


# ===========================================================================
# ROUTING_MATRIX
# ===========================================================================

class TestRoutingMatrix:
    def test_not_empty(self):
        assert len(ROUTING_MATRIX) >= 5

    def test_required_task_types(self):
        for key in ("code", "voice", "trading", "simple"):
            assert key in ROUTING_MATRIX, f"Missing task type: {key}"

    def test_entries_are_tuples(self):
        for task_type, entries in ROUTING_MATRIX.items():
            assert isinstance(entries, list)
            for node, weight in entries:
                assert isinstance(node, str)
                assert isinstance(weight, (int, float))
                assert weight > 0


# ===========================================================================
# OrchestratorV2 — init
# ===========================================================================

class TestOrchestratorV2Init:
    def test_init(self):
        orch = OrchestratorV2()
        assert orch._node_stats == {}
        assert orch._session_budget.total_tokens == 0


# ===========================================================================
# OrchestratorV2 — record_call
# ===========================================================================

class TestRecordCall:
    def test_record_success(self):
        orch = OrchestratorV2()
        with patch("src.orchestrator_v2.observability_matrix"), \
             patch("src.orchestrator_v2.drift_detector"), \
             patch("src.orchestrator_v2.auto_tune"):
            orch.record_call("M1", latency_ms=150, success=True, tokens=100)
        stats = orch._node_stats["M1"]
        assert stats.total_calls == 1
        assert stats.success_count == 1
        assert stats.total_latency_ms == 150
        assert stats.total_tokens == 100
        assert orch._session_budget.total_tokens == 100

    def test_record_failure(self):
        orch = OrchestratorV2()
        with patch("src.orchestrator_v2.observability_matrix"), \
             patch("src.orchestrator_v2.drift_detector"), \
             patch("src.orchestrator_v2.auto_tune"):
            orch.record_call("M2", latency_ms=5000, success=False)
        stats = orch._node_stats["M2"]
        assert stats.success_count == 0
        assert stats.last_failure_ts > 0

    def test_record_multiple_nodes(self):
        orch = OrchestratorV2()
        with patch("src.orchestrator_v2.observability_matrix"), \
             patch("src.orchestrator_v2.drift_detector"), \
             patch("src.orchestrator_v2.auto_tune"):
            orch.record_call("M1", latency_ms=100, success=True, tokens=50)
            orch.record_call("OL1", latency_ms=200, success=True, tokens=30)
        assert len(orch._node_stats) == 2

    def test_record_handles_subsystem_errors(self):
        orch = OrchestratorV2()
        with patch("src.orchestrator_v2.observability_matrix") as obs:
            obs.record_node_call.side_effect = RuntimeError("obs broken")
            with patch("src.orchestrator_v2.drift_detector") as dd:
                dd.record.side_effect = RuntimeError("drift broken")
                with patch("src.orchestrator_v2.auto_tune") as at:
                    at.begin_request.side_effect = RuntimeError("tune broken")
                    orch.record_call("M1", latency_ms=100, success=True)
        # Should not raise, stats still recorded
        assert orch._node_stats["M1"].total_calls == 1


# ===========================================================================
# OrchestratorV2 — weighted_score
# ===========================================================================

class TestWeightedScore:
    def test_default_score(self):
        orch = OrchestratorV2()
        with patch("src.orchestrator_v2.auto_tune") as at:
            mock_load = MagicMock()
            mock_load.active_requests = 0
            mock_load.max_concurrent = 4
            at.get_node_load.return_value = mock_load
            score = orch.weighted_score("M1", "code")
        # With defaults: weight=1.8, load_factor=0, success=1.0, latency_norm=0.2
        # score = 1.8 * 1.0 * 1.0 * (1/0.2) = 9.0
        assert score > 0

    def test_unknown_node_default_weight(self):
        orch = OrchestratorV2()
        with patch("src.orchestrator_v2.auto_tune") as at:
            mock_load = MagicMock()
            mock_load.active_requests = 0
            mock_load.max_concurrent = 1
            at.get_node_load.return_value = mock_load
            score = orch.weighted_score("UNKNOWN", "code")
        assert score > 0  # uses weight=1.0


# ===========================================================================
# OrchestratorV2 — budget
# ===========================================================================

class TestBudget:
    def test_get_budget_report(self):
        orch = OrchestratorV2()
        with patch("src.orchestrator_v2.observability_matrix"), \
             patch("src.orchestrator_v2.drift_detector"), \
             patch("src.orchestrator_v2.auto_tune"):
            orch.record_call("M1", latency_ms=100, success=True, tokens=500)
        report = orch.get_budget_report()
        assert report["total_tokens"] == 500
        assert report["total_calls"] == 1
        assert "tokens_by_node" in report
        assert "session_duration_s" in report

    def test_reset_budget(self):
        orch = OrchestratorV2()
        orch._session_budget.record("M1", 1000)
        orch.reset_budget()
        assert orch._session_budget.total_tokens == 0
        assert orch._session_budget.total_calls == 0


# ===========================================================================
# OrchestratorV2 — get_node_stats
# ===========================================================================

class TestGetNodeStats:
    def test_empty(self):
        orch = OrchestratorV2()
        assert orch.get_node_stats() == {}

    def test_with_data(self):
        orch = OrchestratorV2()
        with patch("src.orchestrator_v2.observability_matrix"), \
             patch("src.orchestrator_v2.drift_detector"), \
             patch("src.orchestrator_v2.auto_tune"):
            orch.record_call("M1", latency_ms=150, success=True, tokens=100)
        stats = orch.get_node_stats()
        assert "M1" in stats
        assert stats["M1"]["total_calls"] == 1
        assert stats["M1"]["success_rate"] == 1.0
        assert stats["M1"]["avg_latency_ms"] == 150.0


# ===========================================================================
# OrchestratorV2 — health_check
# ===========================================================================

class TestHealthCheck:
    def test_perfect_health(self):
        orch = OrchestratorV2()
        with patch("src.orchestrator_v2.observability_matrix") as obs, \
             patch("src.orchestrator_v2.drift_detector") as dd, \
             patch("src.orchestrator_v2.auto_tune") as at:
            obs.get_alerts.return_value = []
            dd.get_degraded_models.return_value = []
            dd.get_alerts.return_value = []
            at.get_status.return_value = {"resource_snapshot": {"cpu_percent": 20, "memory_percent": 30}}
            score = orch.health_check()
        assert score == 100

    def test_degraded_health(self):
        orch = OrchestratorV2()
        with patch("src.orchestrator_v2.observability_matrix") as obs, \
             patch("src.orchestrator_v2.drift_detector") as dd, \
             patch("src.orchestrator_v2.auto_tune") as at:
            obs.get_alerts.return_value = [{"msg": "alert1"}, {"msg": "alert2"}]
            dd.get_degraded_models.return_value = ["M2"]
            dd.get_alerts.return_value = []
            at.get_status.return_value = {"resource_snapshot": {"cpu_percent": 80, "memory_percent": 50}}
            score = orch.health_check()
        assert score < 100

    def test_health_handles_exceptions(self):
        orch = OrchestratorV2()
        with patch("src.orchestrator_v2.observability_matrix") as obs, \
             patch("src.orchestrator_v2.drift_detector") as dd, \
             patch("src.orchestrator_v2.auto_tune") as at:
            obs.get_alerts.side_effect = RuntimeError("obs down")
            dd.get_degraded_models.side_effect = RuntimeError("drift down")
            at.get_status.side_effect = RuntimeError("tune down")
            score = orch.health_check()
        assert score == 50  # all fallback to 50


# ===========================================================================
# OrchestratorV2 — get_alerts
# ===========================================================================

class TestGetAlerts:
    def test_empty_alerts(self):
        orch = OrchestratorV2()
        with patch("src.orchestrator_v2.observability_matrix") as obs, \
             patch("src.orchestrator_v2.drift_detector") as dd:
            obs.get_alerts.return_value = []
            dd.get_alerts.return_value = []
            alerts = orch.get_alerts()
        assert alerts == []

    def test_mixed_alerts(self):
        orch = OrchestratorV2()
        with patch("src.orchestrator_v2.observability_matrix") as obs, \
             patch("src.orchestrator_v2.drift_detector") as dd:
            obs.get_alerts.return_value = [{"msg": "obs_alert"}]
            dd.get_alerts.return_value = [{"msg": "drift_alert"}]
            alerts = orch.get_alerts()
        assert len(alerts) == 2
        sources = {a["source"] for a in alerts}
        assert "observability" in sources
        assert "drift" in sources

    def test_handles_errors(self):
        orch = OrchestratorV2()
        with patch("src.orchestrator_v2.observability_matrix") as obs, \
             patch("src.orchestrator_v2.drift_detector") as dd:
            obs.get_alerts.side_effect = RuntimeError("broken")
            dd.get_alerts.return_value = [{"msg": "ok"}]
            alerts = orch.get_alerts()
        assert len(alerts) == 1


# ===========================================================================
# OrchestratorV2 — fallback_chain
# ===========================================================================

class TestFallbackChain:
    def test_code_chain(self):
        orch = OrchestratorV2()
        with patch("src.orchestrator_v2.drift_detector") as dd, \
             patch("src.orchestrator_v2.auto_tune") as at:
            dd.get_degraded_models.return_value = []
            mock_load = MagicMock()
            mock_load.active_requests = 0
            mock_load.max_concurrent = 4
            at.get_node_load.return_value = mock_load
            chain = orch.fallback_chain("code")
        assert isinstance(chain, list)
        assert len(chain) > 0

    def test_exclude_nodes(self):
        orch = OrchestratorV2()
        with patch("src.orchestrator_v2.drift_detector") as dd, \
             patch("src.orchestrator_v2.auto_tune") as at:
            dd.get_degraded_models.return_value = []
            mock_load = MagicMock()
            mock_load.active_requests = 0
            mock_load.max_concurrent = 4
            at.get_node_load.return_value = mock_load
            chain = orch.fallback_chain("code", exclude={"M1"})
        assert "M1" not in chain

    def test_unknown_task_type(self):
        orch = OrchestratorV2()
        with patch("src.orchestrator_v2.drift_detector") as dd, \
             patch("src.orchestrator_v2.auto_tune") as at:
            dd.get_degraded_models.return_value = []
            mock_load = MagicMock()
            mock_load.active_requests = 0
            mock_load.max_concurrent = 4
            at.get_node_load.return_value = mock_load
            chain = orch.fallback_chain("nonexistent_type")
        assert isinstance(chain, list)
