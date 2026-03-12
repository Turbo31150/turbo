"""Tests for src/health_probe.py — Deep health checks with dependency verification.

Covers: HealthStatus, CheckResult, ProbeConfig, HealthProbe (register,
unregister, list_probes, run_check, run_all, overall_status, get_history,
get_stats), health_probe singleton.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.health_probe import (
    HealthStatus, CheckResult, ProbeConfig, HealthProbe, health_probe,
)


# ===========================================================================
# Enums & Dataclasses
# ===========================================================================

class TestDataclasses:
    def test_health_status_values(self):
        assert HealthStatus.HEALTHY.value == "healthy"
        assert HealthStatus.DEGRADED.value == "degraded"
        assert HealthStatus.UNHEALTHY.value == "unhealthy"
        assert HealthStatus.UNKNOWN.value == "unknown"

    def test_check_result(self):
        cr = CheckResult(name="test", status=HealthStatus.HEALTHY)
        assert cr.latency_ms == 0.0
        assert cr.timestamp > 0

    def test_probe_config(self):
        pc = ProbeConfig(name="db", check_fn=lambda: True)
        assert pc.critical is True
        assert pc.timeout_s == 5.0


# ===========================================================================
# HealthProbe — register / unregister
# ===========================================================================

class TestRegister:
    def test_register(self):
        hp = HealthProbe()
        hp.register("db", check_fn=lambda: True)
        probes = hp.list_probes()
        assert len(probes) == 1
        assert probes[0]["name"] == "db"

    def test_unregister(self):
        hp = HealthProbe()
        hp.register("temp", check_fn=lambda: True)
        assert hp.unregister("temp") is True
        assert hp.unregister("temp") is False

    def test_list_probes(self):
        hp = HealthProbe()
        hp.register("a", check_fn=lambda: True, critical=True)
        hp.register("b", check_fn=lambda: True, critical=False)
        probes = hp.list_probes()
        assert len(probes) == 2


# ===========================================================================
# HealthProbe — run_check
# ===========================================================================

class TestRunCheck:
    def test_healthy(self):
        hp = HealthProbe()
        hp.register("ok_check", check_fn=lambda: True)
        result = hp.run_check("ok_check")
        assert result is not None
        assert result.status == HealthStatus.HEALTHY
        assert result.message == "OK"

    def test_healthy_string_ok(self):
        hp = HealthProbe()
        hp.register("ok_str", check_fn=lambda: "ok")
        result = hp.run_check("ok_str")
        assert result.status == HealthStatus.HEALTHY

    def test_degraded_string(self):
        hp = HealthProbe()
        hp.register("warn", check_fn=lambda: "slow response")
        result = hp.run_check("warn")
        assert result.status == HealthStatus.DEGRADED
        assert result.message == "slow response"

    def test_unhealthy_critical(self):
        hp = HealthProbe()
        hp.register("fail", check_fn=lambda: False, critical=True)
        result = hp.run_check("fail")
        assert result.status == HealthStatus.UNHEALTHY

    def test_degraded_non_critical(self):
        hp = HealthProbe()
        hp.register("fail_soft", check_fn=lambda: False, critical=False)
        result = hp.run_check("fail_soft")
        assert result.status == HealthStatus.DEGRADED

    def test_exception_critical(self):
        hp = HealthProbe()
        hp.register("crash", check_fn=lambda: 1/0, critical=True)
        result = hp.run_check("crash")
        assert result.status == HealthStatus.UNHEALTHY
        assert "division by zero" in result.message

    def test_exception_non_critical(self):
        hp = HealthProbe()
        hp.register("crash_soft", check_fn=lambda: 1/0, critical=False)
        result = hp.run_check("crash_soft")
        assert result.status == HealthStatus.DEGRADED

    def test_nonexistent(self):
        hp = HealthProbe()
        result = hp.run_check("nope")
        assert result is None

    def test_stores_last_result(self):
        hp = HealthProbe()
        hp.register("stored", check_fn=lambda: True)
        hp.run_check("stored")
        probes = hp.list_probes()
        assert probes[0]["last_status"] == "healthy"


# ===========================================================================
# HealthProbe — run_all
# ===========================================================================

class TestRunAll:
    def test_run_all(self):
        hp = HealthProbe()
        hp.register("a", check_fn=lambda: True)
        hp.register("b", check_fn=lambda: False, critical=False)
        results = hp.run_all()
        assert len(results) == 2
        statuses = {r.name: r.status for r in results}
        assert statuses["a"] == HealthStatus.HEALTHY
        assert statuses["b"] == HealthStatus.DEGRADED


# ===========================================================================
# HealthProbe — overall_status
# ===========================================================================

class TestOverallStatus:
    def test_unknown_no_probes(self):
        hp = HealthProbe()
        assert hp.overall_status() == HealthStatus.UNKNOWN

    def test_healthy(self):
        hp = HealthProbe()
        hp.register("a", check_fn=lambda: True)
        hp.run_all()
        assert hp.overall_status() == HealthStatus.HEALTHY

    def test_degraded(self):
        hp = HealthProbe()
        hp.register("a", check_fn=lambda: True)
        hp.register("b", check_fn=lambda: "slow", critical=False)
        hp.run_all()
        assert hp.overall_status() == HealthStatus.DEGRADED

    def test_unhealthy(self):
        hp = HealthProbe()
        hp.register("a", check_fn=lambda: True)
        hp.register("b", check_fn=lambda: False, critical=True)
        hp.run_all()
        assert hp.overall_status() == HealthStatus.UNHEALTHY

    def test_unknown_no_results(self):
        hp = HealthProbe()
        hp.register("a", check_fn=lambda: True)
        # No run_all → last_result is None → UNKNOWN
        assert hp.overall_status() == HealthStatus.UNKNOWN


# ===========================================================================
# HealthProbe — history & stats
# ===========================================================================

class TestHistoryStats:
    def test_history_empty(self):
        hp = HealthProbe()
        assert hp.get_history() == []

    def test_history_filtered(self):
        hp = HealthProbe()
        hp.register("a", check_fn=lambda: True)
        hp.register("b", check_fn=lambda: True)
        hp.run_all()
        history = hp.get_history(name="a")
        assert len(history) == 1
        assert history[0]["name"] == "a"

    def test_stats(self):
        hp = HealthProbe()
        hp.register("a", check_fn=lambda: True, critical=True)
        hp.register("b", check_fn=lambda: False, critical=False)
        hp.run_all()
        stats = hp.get_stats()
        assert stats["total_probes"] == 2
        assert stats["critical_probes"] == 1
        assert stats["total_checks"] == 2
        assert stats["healthy"] == 1
        assert stats["degraded"] == 1
        assert stats["avg_latency_ms"] >= 0


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert health_probe is not None
        assert isinstance(health_probe, HealthProbe)
