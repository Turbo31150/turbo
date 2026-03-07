"""Tests for src/agent_monitor.py — Real-time agent monitoring.

Covers: RollingMetric (add, _prune, count/avg/max/min/rate_per_sec),
AgentMetrics, NodeMetrics, Alert, AgentMonitor (record_dispatch, get_dashboard,
get_agent_detail, load_from_db), get_monitor singleton.
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

from src.agent_monitor import (
    RollingMetric, AgentMetrics, NodeMetrics, Alert, AgentMonitor, get_monitor,
)


# ===========================================================================
# RollingMetric
# ===========================================================================

class TestRollingMetric:
    def test_empty(self):
        rm = RollingMetric()
        assert rm.count == 0
        assert rm.avg == 0
        assert rm.max == 0
        assert rm.min == 0
        assert rm.rate_per_sec == 0

    def test_add_and_count(self):
        rm = RollingMetric(window_s=300)
        now = time.time()
        rm.add(100, now)
        rm.add(200, now + 1)
        rm.add(300, now + 2)
        assert rm.count == 3

    def test_avg(self):
        rm = RollingMetric(window_s=300)
        now = time.time()
        rm.add(100, now)
        rm.add(200, now)
        rm.add(300, now)
        assert rm.avg == 200.0

    def test_max(self):
        rm = RollingMetric(window_s=300)
        now = time.time()
        rm.add(50, now)
        rm.add(300, now)
        rm.add(100, now)
        assert rm.max == 300

    def test_min(self):
        rm = RollingMetric(window_s=300)
        now = time.time()
        rm.add(50, now)
        rm.add(300, now)
        rm.add(100, now)
        assert rm.min == 50

    def test_rate_per_sec(self):
        rm = RollingMetric(window_s=300)
        now = time.time()
        rm.add(1, now)
        rm.add(1, now + 10)
        # 2 entries over 10 seconds span
        assert rm.rate_per_sec == pytest.approx(0.2, abs=0.05)

    def test_rate_single_entry(self):
        rm = RollingMetric(window_s=300)
        rm.add(1, time.time())
        assert rm.rate_per_sec == 0  # need at least 2

    def test_prune_old_entries(self):
        rm = RollingMetric(window_s=10)
        old = time.time() - 20  # 20s ago, outside 10s window
        rm.add(100, old)
        rm.add(200, time.time())
        assert rm.count == 1  # old entry pruned


# ===========================================================================
# Dataclasses
# ===========================================================================

class TestDataclasses:
    def test_agent_metrics_defaults(self):
        am = AgentMetrics(pattern="code")
        assert am.total_dispatches == 0
        assert am.total_ok == 0
        assert am.last_node == ""

    def test_node_metrics_defaults(self):
        nm = NodeMetrics(name="M1")
        assert nm.active_count == 0
        assert nm.total_dispatches == 0

    def test_alert_defaults(self):
        a = Alert(severity="warning", message="test")
        assert a.timestamp > 0
        assert a.pattern == ""
        assert a.node == ""


# ===========================================================================
# AgentMonitor — record_dispatch
# ===========================================================================

class TestRecordDispatch:
    def test_basic_record(self):
        mon = AgentMonitor()
        mon.record_dispatch("code", "M1", "speed", 500, True, 0.9)
        assert "code" in mon._agent_metrics
        assert mon._agent_metrics["code"].total_dispatches == 1
        assert mon._agent_metrics["code"].total_ok == 1
        assert "M1" in mon._node_metrics
        assert mon._node_metrics["M1"].total_dispatches == 1

    def test_failed_dispatch(self):
        mon = AgentMonitor()
        mon.record_dispatch("code", "M2", "speed", 1000, False)
        assert mon._agent_metrics["code"].total_ok == 0

    def test_multiple_dispatches(self):
        mon = AgentMonitor()
        mon.record_dispatch("code", "M1", "speed", 500, True)
        mon.record_dispatch("code", "M1", "speed", 600, True)
        mon.record_dispatch("math", "OL1", "speed", 200, True)
        assert mon._agent_metrics["code"].total_dispatches == 2
        assert mon._agent_metrics["math"].total_dispatches == 1
        assert mon._node_metrics["M1"].total_dispatches == 2

    def test_alert_low_success(self):
        mon = AgentMonitor()
        # 5 failures to trigger critical alert (avg < 0.5)
        for _ in range(5):
            mon.record_dispatch("bad", "M1", "speed", 100, False)
        alerts = [a for a in mon._alerts if a.pattern == "bad" and a.severity == "critical"]
        assert len(alerts) >= 1

    def test_alert_high_latency(self):
        mon = AgentMonitor()
        # 3 dispatches with >60s latency
        for _ in range(3):
            mon.record_dispatch("slow", "M1", "speed", 70000, True)
        alerts = [a for a in mon._alerts if a.pattern == "slow" and a.severity == "warning"]
        assert len(alerts) >= 1

    def test_alert_node_down(self):
        mon = AgentMonitor()
        # 5 failures on same node
        for _ in range(5):
            mon.record_dispatch("code", "M2", "speed", 100, False)
        alerts = [a for a in mon._alerts if a.node == "M2" and "down" in a.message]
        assert len(alerts) >= 1

    def test_updates_last_fields(self):
        mon = AgentMonitor()
        mon.record_dispatch("code", "M1", "speed", 500, True)
        mon.record_dispatch("code", "OL1", "quality", 300, True)
        assert mon._agent_metrics["code"].last_node == "OL1"
        assert mon._agent_metrics["code"].last_strategy == "quality"


# ===========================================================================
# AgentMonitor — get_dashboard
# ===========================================================================

class TestGetDashboard:
    def test_empty_dashboard(self):
        mon = AgentMonitor()
        dash = mon.get_dashboard()
        assert dash["total_dispatches"] == 0
        assert dash["success_rate"] == "0%"
        assert dash["agents"] == {}
        assert dash["nodes"] == {}
        assert dash["alerts"] == []
        assert dash["uptime_s"] >= 0

    def test_dashboard_with_data(self):
        mon = AgentMonitor()
        mon.record_dispatch("code", "M1", "speed", 500, True, 0.9)
        mon.record_dispatch("math", "OL1", "speed", 200, True, 0.8)
        dash = mon.get_dashboard()
        assert dash["total_dispatches"] == 2
        assert "code" in dash["agents"]
        assert "math" in dash["agents"]
        assert "M1" in dash["nodes"]
        assert "OL1" in dash["nodes"]

    def test_dashboard_agent_fields(self):
        mon = AgentMonitor()
        mon.record_dispatch("code", "M1", "speed", 500, True, 0.9)
        dash = mon.get_dashboard()
        agent = dash["agents"]["code"]
        assert agent["dispatches"] == 1
        assert agent["ok"] == 1
        assert agent["last_node"] == "M1"
        assert "avg_ms" in agent
        assert "rps" in agent


# ===========================================================================
# AgentMonitor — get_agent_detail
# ===========================================================================

class TestGetAgentDetail:
    def test_missing_agent(self):
        mon = AgentMonitor()
        detail = mon.get_agent_detail("nonexistent")
        assert "error" in detail

    def test_existing_agent(self):
        mon = AgentMonitor()
        mon.record_dispatch("code", "M1", "speed", 500, True, 0.9)
        detail = mon.get_agent_detail("code")
        assert detail["pattern"] == "code"
        assert detail["total_dispatches"] == 1
        assert detail["total_ok"] == 1
        assert "latency" in detail
        assert "quality" in detail
        assert detail["last_node"] == "M1"


# ===========================================================================
# AgentMonitor — load_from_db
# ===========================================================================

class TestLoadFromDb:
    def test_db_error_graceful(self):
        mon = AgentMonitor()
        mon.load_from_db(db_path="/nonexistent/path/db.sqlite")
        # Should not raise, just log warning
        assert mon._agent_metrics == {}

    def test_load_with_mock_db(self):
        mon = AgentMonitor()
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchall.return_value = [
            {"classified_type": "code", "node": "M1", "strategy": "speed",
             "latency_ms": 500, "success": 1, "quality_score": 0.9},
            {"classified_type": "math", "node": "OL1", "strategy": "speed",
             "latency_ms": 200, "success": 1, "quality_score": 0.8},
        ]
        with patch("src.agent_monitor.sqlite3.connect", return_value=mock_conn):
            mon.load_from_db()
        assert "code" in mon._agent_metrics
        assert "math" in mon._agent_metrics


# ===========================================================================
# get_monitor singleton
# ===========================================================================

class TestGetMonitor:
    def test_returns_instance(self):
        import src.agent_monitor as mod
        mod._monitor = None
        with patch.object(AgentMonitor, "load_from_db"):
            mon = get_monitor()
        assert isinstance(mon, AgentMonitor)

    def test_same_instance(self):
        import src.agent_monitor as mod
        mod._monitor = None
        with patch.object(AgentMonitor, "load_from_db"):
            m1 = get_monitor()
            m2 = get_monitor()
        assert m1 is m2
