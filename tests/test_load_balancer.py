"""Tests for src/load_balancer.py — Weighted round-robin load balancer.

Covers: LoadBalancer (pick, release, report, get_status, reset),
load_balancer singleton.
Orchestrator imports are mocked.
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

from src.load_balancer import LoadBalancer, load_balancer


# ===========================================================================
# LoadBalancer — pick (fallback when orchestrator unavailable)
# ===========================================================================

class TestPick:
    def test_returns_node(self):
        lb = LoadBalancer()
        with patch.dict("sys.modules", {"src.orchestrator_v2": None}):
            node = lb.pick("code")
        assert node in ("M1", "OL1")

    def test_exclude_with_orchestrator(self):
        lb = LoadBalancer()
        mock_orch = MagicMock()
        mock_matrix = {"code": [("M1", 1.8), ("OL1", 1.3)]}
        mock_orch.weighted_score.return_value = 1.0
        with patch.dict("sys.modules", {
            "src.orchestrator_v2": MagicMock(
                orchestrator_v2=mock_orch, ROUTING_MATRIX=mock_matrix)
        }):
            node = lb.pick("code", exclude={"M1"})
        assert node == "OL1"

    def test_returns_m1_when_all_excluded(self):
        lb = LoadBalancer()
        with patch.dict("sys.modules", {"src.orchestrator_v2": None}):
            node = lb.pick("code", exclude={"M1", "OL1"})
        # Falls back to M1 (empty candidates → return "M1")
        assert node == "M1"

    def test_increments_active(self):
        lb = LoadBalancer()
        with patch.dict("sys.modules", {"src.orchestrator_v2": None}):
            node = lb.pick("code")
        status = lb.get_status()
        assert status["nodes"][node]["active_requests"] == 1


# ===========================================================================
# LoadBalancer — release
# ===========================================================================

class TestRelease:
    def test_release(self):
        lb = LoadBalancer()
        with patch.dict("sys.modules", {"src.orchestrator_v2": None}):
            node = lb.pick("code")
        lb.release(node)
        status = lb.get_status()
        assert status["nodes"][node]["active_requests"] == 0

    def test_release_below_zero(self):
        lb = LoadBalancer()
        lb.release("M1")
        status = lb.get_status()
        assert status["nodes"]["M1"]["active_requests"] == 0


# ===========================================================================
# LoadBalancer — report
# ===========================================================================

class TestReport:
    def test_report_success(self):
        lb = LoadBalancer()
        with patch.dict("sys.modules", {"src.orchestrator_v2": None}):
            node = lb.pick("code")
        lb.report(node, 100.0, True, 50)
        status = lb.get_status()
        assert status["nodes"][node]["active_requests"] == 0
        assert status["nodes"][node]["recent_failures"] == 0

    def test_report_failure(self):
        lb = LoadBalancer()
        with patch.dict("sys.modules", {"src.orchestrator_v2": None}):
            node = lb.pick("code")
        lb.report(node, 100.0, False)
        status = lb.get_status()
        assert status["nodes"][node]["recent_failures"] == 1

    def test_circuit_breaker(self):
        lb = LoadBalancer()
        lb._failure_threshold = 3
        for _ in range(3):
            lb.report("M1", 100.0, False)
        status = lb.get_status()
        assert status["nodes"]["M1"]["circuit_broken"] is True


# ===========================================================================
# LoadBalancer — get_status
# ===========================================================================

class TestGetStatus:
    def test_empty(self):
        lb = LoadBalancer()
        status = lb.get_status()
        assert status["max_concurrent"] == 3
        assert status["failure_threshold"] == 5
        assert status["nodes"] == {}


# ===========================================================================
# LoadBalancer — reset
# ===========================================================================

class TestReset:
    def test_reset(self):
        lb = LoadBalancer()
        lb.report("M1", 100.0, False)
        lb.reset()
        status = lb.get_status()
        assert status["nodes"] == {}


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert load_balancer is not None
        assert isinstance(load_balancer, LoadBalancer)
