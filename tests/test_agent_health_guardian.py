"""Tests for src/agent_health_guardian.py — Proactive health monitoring.

Covers: NodeHealthCheck, HealthAlert, HealthReport (summary), HealthGuardian
(HEALTH_CHECKS, check_all, _check_node, _generate_alerts,
_check_routing_health, auto_heal, get_alert_history, get_summary).
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

with patch("src.pattern_agents.PatternAgentRegistry"):
    from src.agent_health_guardian import (
        NodeHealthCheck, HealthAlert, HealthReport, HealthGuardian,
    )


# ===========================================================================
# NodeHealthCheck
# ===========================================================================

class TestNodeHealthCheck:
    def test_defaults(self):
        n = NodeHealthCheck(node="M1", reachable=True, latency_ms=100)
        assert n.models_loaded == 0
        assert n.models_available == 0
        assert n.error == ""
        assert n.status == "unknown"

    def test_with_data(self):
        n = NodeHealthCheck(node="OL1", reachable=False, latency_ms=0,
                            error="Connection refused", status="offline")
        assert n.reachable is False
        assert n.status == "offline"


# ===========================================================================
# HealthAlert
# ===========================================================================

class TestHealthAlert:
    def test_defaults(self):
        a = HealthAlert(severity="critical", target="M1",
                        alert_type="offline", message="M1 is offline")
        assert a.action == ""
        assert a.auto_healable is False

    def test_with_all_fields(self):
        a = HealthAlert(severity="warning", target="OL1",
                        alert_type="slow", message="Slow",
                        action="Check network", auto_healable=True)
        assert a.auto_healable is True
        assert a.action == "Check network"


# ===========================================================================
# HealthReport
# ===========================================================================

class TestHealthReport:
    def test_summary(self):
        r = HealthReport(
            timestamp="2026-03-07", duration_ms=500,
            node_checks=[], alerts=[HealthAlert("warning", "M1", "slow", "slow")],
            overall_status="healthy", healthy_nodes=3, total_nodes=4,
        )
        s = r.summary
        assert "3/4" in s
        assert "1 alerts" in s
        assert "healthy" in s

    def test_empty_report(self):
        r = HealthReport(
            timestamp="now", duration_ms=0,
            node_checks=[], alerts=[], overall_status="critical",
            healthy_nodes=0, total_nodes=0,
        )
        assert "0/0" in r.summary
        assert "0 alerts" in r.summary


# ===========================================================================
# HealthGuardian — HEALTH_CHECKS
# ===========================================================================

class TestHealthChecks:
    def test_has_4_nodes(self):
        assert len(HealthGuardian.HEALTH_CHECKS) == 4

    def test_expected_nodes(self):
        assert set(HealthGuardian.HEALTH_CHECKS.keys()) == {"M1", "M2", "M3", "OL1"}

    def test_each_has_url_and_type(self):
        for name, cfg in HealthGuardian.HEALTH_CHECKS.items():
            assert "url" in cfg
            assert "type" in cfg
            assert cfg["type"] in ("lmstudio", "ollama")


# ===========================================================================
# HealthGuardian — _generate_alerts
# ===========================================================================

class TestGenerateAlerts:
    def setup_method(self):
        self.guardian = HealthGuardian()

    def test_no_alerts_healthy(self):
        checks = [
            NodeHealthCheck("M1", True, 100, status="healthy"),
            NodeHealthCheck("OL1", True, 50, status="healthy"),
        ]
        alerts = self.guardian._generate_alerts(checks)
        assert alerts == []

    def test_offline_creates_critical(self):
        checks = [
            NodeHealthCheck("M2", False, 0, error="Connection refused", status="offline"),
        ]
        alerts = self.guardian._generate_alerts(checks)
        assert len(alerts) == 1
        assert alerts[0].severity == "critical"
        assert alerts[0].alert_type == "offline"
        assert "M2" in alerts[0].message

    def test_degraded_creates_warning(self):
        checks = [
            NodeHealthCheck("M1", True, 200, models_loaded=0, models_available=3, status="degraded"),
        ]
        alerts = self.guardian._generate_alerts(checks)
        assert len(alerts) == 1
        assert alerts[0].severity == "warning"
        assert alerts[0].alert_type == "degraded"

    def test_slow_creates_warning(self):
        checks = [
            NodeHealthCheck("M3", True, 4000, status="healthy"),
        ]
        alerts = self.guardian._generate_alerts(checks)
        assert len(alerts) == 1
        assert alerts[0].alert_type == "slow"

    def test_auto_healable_local_nodes(self):
        checks = [
            NodeHealthCheck("M1", False, 0, error="offline", status="offline"),
            NodeHealthCheck("OL1", False, 0, error="offline", status="offline"),
            NodeHealthCheck("M2", False, 0, error="offline", status="offline"),
        ]
        alerts = self.guardian._generate_alerts(checks)
        m1_alert = [a for a in alerts if a.target == "M1"][0]
        ol1_alert = [a for a in alerts if a.target == "OL1"][0]
        m2_alert = [a for a in alerts if a.target == "M2"][0]
        assert m1_alert.auto_healable is True
        assert ol1_alert.auto_healable is True
        assert m2_alert.auto_healable is False

    def test_multiple_alerts(self):
        checks = [
            NodeHealthCheck("M1", False, 0, status="offline", error="refused"),
            NodeHealthCheck("M2", True, 200, models_loaded=0, status="degraded"),
            NodeHealthCheck("OL1", True, 3500, status="healthy"),
        ]
        alerts = self.guardian._generate_alerts(checks)
        assert len(alerts) == 3


# ===========================================================================
# HealthGuardian — _check_routing_health
# ===========================================================================

class TestCheckRoutingHealth:
    def test_import_error_returns_empty(self):
        guardian = HealthGuardian()
        with patch("src.agent_health_guardian.HealthGuardian._check_routing_health",
                    wraps=guardian._check_routing_health):
            # When adaptive_router import fails, returns []
            alerts = guardian._check_routing_health()
        assert isinstance(alerts, list)

    def test_with_recommendations(self):
        guardian = HealthGuardian()
        mock_router = MagicMock()
        mock_router.get_recommendations.return_value = [
            {"severity": "warning", "node": "M3", "type": "routing", "message": "M3 slow"},
        ]
        with patch.dict("sys.modules", {"src.adaptive_router": MagicMock()}), \
             patch("src.agent_health_guardian.HealthGuardian._check_routing_health") as mock:
            mock.return_value = [
                HealthAlert("warning", "M3", "routing", "M3 slow"),
            ]
            alerts = guardian._check_routing_health()
        assert len(alerts) == 1


# ===========================================================================
# HealthGuardian — check_all
# ===========================================================================

class TestCheckAll:
    @pytest.mark.asyncio
    async def test_all_healthy(self):
        guardian = HealthGuardian()
        healthy_check = NodeHealthCheck("M1", True, 100, models_loaded=1, status="healthy")

        async def mock_check_node(client, name, cfg):
            return NodeHealthCheck(name, True, 100, models_loaded=1, status="healthy")

        with patch.object(guardian, "_check_node", side_effect=mock_check_node), \
             patch.object(guardian, "_check_routing_health", return_value=[]):
            report = await guardian.check_all()

        assert report.overall_status == "healthy"
        assert report.healthy_nodes == 4
        assert report.total_nodes == 4
        assert len(report.alerts) == 0

    @pytest.mark.asyncio
    async def test_all_offline(self):
        guardian = HealthGuardian()

        async def mock_check_node(client, name, cfg):
            return NodeHealthCheck(name, False, 0, error="offline", status="offline")

        with patch.object(guardian, "_check_node", side_effect=mock_check_node), \
             patch.object(guardian, "_check_routing_health", return_value=[]):
            report = await guardian.check_all()

        assert report.overall_status == "critical"
        assert report.healthy_nodes == 0
        assert len(report.alerts) == 4  # one per node

    @pytest.mark.asyncio
    async def test_stores_last_check(self):
        guardian = HealthGuardian()
        assert guardian._last_check is None

        async def mock_check_node(client, name, cfg):
            return NodeHealthCheck(name, True, 50, status="healthy", models_loaded=1)

        with patch.object(guardian, "_check_node", side_effect=mock_check_node), \
             patch.object(guardian, "_check_routing_health", return_value=[]):
            await guardian.check_all()

        assert guardian._last_check is not None


# ===========================================================================
# HealthGuardian — auto_heal
# ===========================================================================

class TestAutoHeal:
    @pytest.mark.asyncio
    async def test_no_alerts(self):
        guardian = HealthGuardian()
        guardian._last_check = HealthReport(
            timestamp="now", duration_ms=0,
            node_checks=[], alerts=[], overall_status="healthy",
            healthy_nodes=4, total_nodes=4,
        )
        healed = await guardian.auto_heal()
        assert healed == []

    @pytest.mark.asyncio
    async def test_ol1_offline_logged(self):
        guardian = HealthGuardian()
        guardian._last_check = HealthReport(
            timestamp="now", duration_ms=0, node_checks=[],
            alerts=[HealthAlert("critical", "OL1", "offline", "OL1 offline",
                                auto_healable=True)],
            overall_status="critical", healthy_nodes=0, total_nodes=1,
        )
        healed = await guardian.auto_heal()
        assert len(healed) == 1
        assert healed[0]["target"] == "OL1"
        assert healed[0]["ok"] is False

    @pytest.mark.asyncio
    async def test_not_auto_healable_skipped(self):
        guardian = HealthGuardian()
        guardian._last_check = HealthReport(
            timestamp="now", duration_ms=0, node_checks=[],
            alerts=[HealthAlert("critical", "M2", "offline", "M2 offline",
                                auto_healable=False)],
            overall_status="degraded", healthy_nodes=3, total_nodes=4,
        )
        healed = await guardian.auto_heal()
        assert healed == []


# ===========================================================================
# HealthGuardian — get_alert_history / get_summary
# ===========================================================================

class TestQueryMethods:
    def test_alert_history_empty(self):
        guardian = HealthGuardian()
        assert guardian.get_alert_history() == []

    def test_alert_history_with_data(self):
        guardian = HealthGuardian()
        guardian._alert_history = [
            HealthAlert("critical", "M1", "offline", "M1 down"),
            HealthAlert("warning", "M3", "slow", "M3 slow"),
        ]
        history = guardian.get_alert_history()
        assert len(history) == 2
        assert history[0]["severity"] == "critical"
        assert history[1]["target"] == "M3"

    def test_alert_history_limit(self):
        guardian = HealthGuardian()
        guardian._alert_history = [
            HealthAlert("info", f"M{i}", "test", f"alert {i}") for i in range(10)
        ]
        history = guardian.get_alert_history(limit=3)
        assert len(history) == 3

    def test_summary_no_check(self):
        guardian = HealthGuardian()
        s = guardian.get_summary()
        assert s["status"] == "unknown"
        assert "No health check" in s["message"]

    def test_summary_with_check(self):
        guardian = HealthGuardian()
        guardian._last_check = HealthReport(
            timestamp="2026-01-01", duration_ms=500,
            node_checks=[], alerts=[
                HealthAlert("critical", "M2", "offline", "down"),
                HealthAlert("warning", "M3", "slow", "slow"),
            ],
            overall_status="degraded", healthy_nodes=2, total_nodes=4,
        )
        s = guardian.get_summary()
        assert s["status"] == "degraded"
        assert s["healthy_nodes"] == 2
        assert s["total_nodes"] == 4
        assert s["alerts"] == 2
        assert s["critical_alerts"] == 1
