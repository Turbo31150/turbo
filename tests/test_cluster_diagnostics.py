"""Tests for src/cluster_diagnostics.py — Deep diagnostic with recommendations.

Covers: ClusterDiagnostics (run_diagnostic, _check_orchestrator,
_check_load_balancer, _check_autonomous_loop, _check_alerts,
_check_data_stores, _check_event_bus, get_last_report, get_history,
get_quick_status), grading, cluster_diagnostics singleton.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.cluster_diagnostics import ClusterDiagnostics, cluster_diagnostics


# ===========================================================================
# ClusterDiagnostics — init
# ===========================================================================

class TestInit:
    def test_defaults(self):
        cd = ClusterDiagnostics()
        assert cd._last_report == {}
        assert cd._report_history == []
        assert cd._max_history == 50


# ===========================================================================
# ClusterDiagnostics — _check_orchestrator
# ===========================================================================

class TestCheckOrchestrator:
    def test_success(self):
        cd = ClusterDiagnostics()
        mock_orch = MagicMock()
        mock_orch.health_check.return_value = 85
        mock_orch.get_node_stats.return_value = {"M1": {"success_rate": 0.95, "total_calls": 100}}
        mock_orch.get_budget_report.return_value = {"total_tokens": 10000}
        mock_orch.get_alerts.return_value = []
        with patch.dict("sys.modules", {"src.orchestrator_v2": MagicMock(orchestrator_v2=mock_orch)}):
            result = cd._check_orchestrator()
        assert result["score"] == 85
        assert result["problems"] == []

    def test_critical_health(self):
        cd = ClusterDiagnostics()
        mock_orch = MagicMock()
        mock_orch.health_check.return_value = 30
        mock_orch.get_node_stats.return_value = {}
        mock_orch.get_budget_report.return_value = {"total_tokens": 0}
        mock_orch.get_alerts.return_value = []
        with patch.dict("sys.modules", {"src.orchestrator_v2": MagicMock(orchestrator_v2=mock_orch)}):
            result = cd._check_orchestrator()
        assert result["score"] == 30
        assert len(result["problems"]) >= 1

    def test_import_error(self):
        cd = ClusterDiagnostics()
        with patch("builtins.__import__", side_effect=ImportError("no module")):
            result = cd._check_orchestrator()
        assert result["score"] == 0
        assert len(result["problems"]) >= 1


# ===========================================================================
# ClusterDiagnostics — _check_load_balancer
# ===========================================================================

class TestCheckLoadBalancer:
    def test_healthy(self):
        cd = ClusterDiagnostics()
        mock_lb = MagicMock()
        mock_lb.get_status.return_value = {
            "nodes": {"M1": {"circuit_broken": False, "active_requests": 0}},
            "max_concurrent": 3,
        }
        with patch.dict("sys.modules", {"src.load_balancer": MagicMock(load_balancer=mock_lb)}):
            result = cd._check_load_balancer()
        assert result["score"] == 100
        assert result["circuit_broken"] == []

    def test_circuit_broken(self):
        cd = ClusterDiagnostics()
        mock_lb = MagicMock()
        mock_lb.get_status.return_value = {
            "nodes": {"M2": {"circuit_broken": True, "active_requests": 0}},
            "max_concurrent": 3,
        }
        with patch.dict("sys.modules", {"src.load_balancer": MagicMock(load_balancer=mock_lb)}):
            result = cd._check_load_balancer()
        assert result["score"] == 70  # 100 - 30
        assert "M2" in result["circuit_broken"]

    def test_import_error(self):
        cd = ClusterDiagnostics()
        with patch("builtins.__import__", side_effect=ImportError("no")):
            result = cd._check_load_balancer()
        assert result["score"] == 50


# ===========================================================================
# ClusterDiagnostics — _check_autonomous_loop
# ===========================================================================

class TestCheckAutonomousLoop:
    def test_running_healthy(self):
        cd = ClusterDiagnostics()
        mock_loop = MagicMock()
        mock_loop.get_status.return_value = {
            "running": True,
            "tasks": {"audit": {"run_count": 10, "fail_count": 0}},
            "event_count": 42,
        }
        with patch.dict("sys.modules", {"src.autonomous_loop": MagicMock(autonomous_loop=mock_loop)}):
            result = cd._check_autonomous_loop()
        assert result["score"] == 100

    def test_not_running(self):
        cd = ClusterDiagnostics()
        mock_loop = MagicMock()
        mock_loop.get_status.return_value = {"running": False}
        with patch.dict("sys.modules", {"src.autonomous_loop": MagicMock(autonomous_loop=mock_loop)}):
            result = cd._check_autonomous_loop()
        assert result["score"] == 0
        assert "NOT running" in result["problems"][0]

    def test_high_failure_tasks(self):
        cd = ClusterDiagnostics()
        mock_loop = MagicMock()
        mock_loop.get_status.return_value = {
            "running": True,
            "tasks": {"bad_task": {"run_count": 10, "fail_count": 5}},
        }
        with patch.dict("sys.modules", {"src.autonomous_loop": MagicMock(autonomous_loop=mock_loop)}):
            result = cd._check_autonomous_loop()
        assert result["score"] < 100
        assert len(result["problems"]) >= 1


# ===========================================================================
# ClusterDiagnostics — _check_alerts
# ===========================================================================

class TestCheckAlerts:
    def test_no_alerts(self):
        cd = ClusterDiagnostics()
        mock_am = MagicMock()
        mock_am.get_active.return_value = []
        with patch.dict("sys.modules", {"src.alert_manager": MagicMock(alert_manager=mock_am)}):
            result = cd._check_alerts()
        assert result["score"] == 100

    def test_critical_alerts(self):
        cd = ClusterDiagnostics()
        mock_am = MagicMock()
        mock_am.get_active.return_value = [
            {"level": "critical", "message": "Node M2 offline"},
        ]
        with patch.dict("sys.modules", {"src.alert_manager": MagicMock(alert_manager=mock_am)}):
            result = cd._check_alerts()
        assert result["score"] == 75  # 100 - 25
        assert result["critical_count"] == 1


# ===========================================================================
# ClusterDiagnostics — _check_data_stores
# ===========================================================================

class TestCheckDataStores:
    def test_import_error_graceful(self):
        cd = ClusterDiagnostics()
        with patch("builtins.__import__", side_effect=ImportError("no")):
            result = cd._check_data_stores()
        assert result["score"] == 100  # default score


# ===========================================================================
# ClusterDiagnostics — _check_event_bus
# ===========================================================================

class TestCheckEventBus:
    def test_healthy(self):
        cd = ClusterDiagnostics()
        mock_bus = MagicMock()
        mock_bus.get_stats.return_value = {
            "total_subscriptions": 5, "total_events_emitted": 100,
        }
        with patch.dict("sys.modules", {"src.event_bus": MagicMock(event_bus=mock_bus)}):
            result = cd._check_event_bus()
        assert result["score"] == 100

    def test_no_subscribers(self):
        cd = ClusterDiagnostics()
        mock_bus = MagicMock()
        mock_bus.get_stats.return_value = {
            "total_subscriptions": 0, "total_events_emitted": 0,
        }
        with patch.dict("sys.modules", {"src.event_bus": MagicMock(event_bus=mock_bus)}):
            result = cd._check_event_bus()
        assert result["score"] == 70


# ===========================================================================
# ClusterDiagnostics — run_diagnostic
# ===========================================================================

class TestRunDiagnostic:
    def _mock_checks(self, cd, score=80):
        section = {"score": score, "problems": [], "recommendations": []}
        for method in ("_check_orchestrator", "_check_load_balancer",
                       "_check_autonomous_loop", "_check_alerts",
                       "_check_data_stores", "_check_event_bus"):
            setattr(cd, method, lambda s=section: dict(s))

    def test_grade_a(self):
        cd = ClusterDiagnostics()
        self._mock_checks(cd, 95)
        report = cd.run_diagnostic()
        assert report["grade"] == "A"
        assert report["scores"]["overall"] == 95

    def test_grade_b(self):
        cd = ClusterDiagnostics()
        self._mock_checks(cd, 80)
        report = cd.run_diagnostic()
        assert report["grade"] == "B"

    def test_grade_c(self):
        cd = ClusterDiagnostics()
        self._mock_checks(cd, 65)
        report = cd.run_diagnostic()
        assert report["grade"] == "C"

    def test_grade_d(self):
        cd = ClusterDiagnostics()
        self._mock_checks(cd, 45)
        report = cd.run_diagnostic()
        assert report["grade"] == "D"

    def test_grade_f(self):
        cd = ClusterDiagnostics()
        self._mock_checks(cd, 30)
        report = cd.run_diagnostic()
        assert report["grade"] == "F"

    def test_stores_last_report(self):
        cd = ClusterDiagnostics()
        self._mock_checks(cd, 90)
        cd.run_diagnostic()
        assert cd._last_report["grade"] == "A"

    def test_appends_history(self):
        cd = ClusterDiagnostics()
        self._mock_checks(cd, 90)
        cd.run_diagnostic()
        cd.run_diagnostic()
        assert len(cd._report_history) == 2

    def test_history_max_limit(self):
        cd = ClusterDiagnostics()
        cd._max_history = 3
        self._mock_checks(cd, 90)
        for _ in range(5):
            cd.run_diagnostic()
        assert len(cd._report_history) == 3

    def test_collects_problems(self):
        cd = ClusterDiagnostics()
        cd._check_orchestrator = lambda: {"score": 30, "problems": ["Node down"], "recommendations": ["Fix it"]}
        cd._check_load_balancer = lambda: {"score": 100, "problems": [], "recommendations": []}
        cd._check_autonomous_loop = lambda: {"score": 100, "problems": [], "recommendations": []}
        cd._check_alerts = lambda: {"score": 100, "problems": [], "recommendations": []}
        cd._check_data_stores = lambda: {"score": 100, "problems": [], "recommendations": []}
        cd._check_event_bus = lambda: {"score": 100, "problems": [], "recommendations": []}
        report = cd.run_diagnostic()
        assert "Node down" in report["problems"]
        assert "Fix it" in report["recommendations"]


# ===========================================================================
# ClusterDiagnostics — query methods
# ===========================================================================

class TestQueryMethods:
    def test_get_last_report_empty(self):
        cd = ClusterDiagnostics()
        assert cd.get_last_report() == {}

    def test_get_history_empty(self):
        cd = ClusterDiagnostics()
        assert cd.get_history() == []

    def test_get_history_limit(self):
        cd = ClusterDiagnostics()
        cd._report_history = [{"grade": "A"}] * 10
        assert len(cd.get_history(limit=3)) == 3

    def test_get_quick_status_no_modules(self):
        cd = ClusterDiagnostics()
        with patch("builtins.__import__", side_effect=ImportError("no")):
            status = cd.get_quick_status()
        assert status["health_score"] == 0
        assert status["active_alerts"] == 0
        assert status["loop_running"] is False
        assert status["last_diagnostic"] == "N/A"


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert cluster_diagnostics is not None
        assert isinstance(cluster_diagnostics, ClusterDiagnostics)
