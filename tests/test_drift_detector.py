"""Tests for src/drift_detector.py — Continuous model quality surveillance.

Covers: ModelMetricWindow (add, recent, count), DriftDetector (record,
compute_baselines, _check_drift, get_model_health, get_all_health,
get_alerts, get_degraded_models, suggest_rerouting, get_report).
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Prevent _load_state from reading real disk file
with patch("src.drift_detector.DriftDetector._load_state"):
    from src.drift_detector import ModelMetricWindow, DriftDetector


# ===========================================================================
# ModelMetricWindow
# ===========================================================================

class TestModelMetricWindow:
    def test_empty(self):
        w = ModelMetricWindow()
        assert w.count == 0
        assert w.recent() == []

    def test_add_and_count(self):
        w = ModelMetricWindow()
        now = time.time()
        w.add(100, now)
        w.add(200, now)
        assert w.count == 2

    def test_recent_filter(self):
        w = ModelMetricWindow()
        old = time.time() - 7200  # 2 hours ago
        now = time.time()
        w.add(100, old)
        w.add(200, now)
        recent = w.recent(3600)  # last hour
        assert len(recent) == 1
        assert recent[0] == 200

    def test_maxlen(self):
        w = ModelMetricWindow()
        for i in range(600):
            w.add(float(i), time.time())
        assert w.count == 500  # maxlen=500


# ===========================================================================
# DriftDetector — record
# ===========================================================================

class TestRecord:
    def test_basic_record(self):
        with patch.object(DriftDetector, "_load_state"):
            dd = DriftDetector()
        dd.record("M1", 500, True, quality=0.9, tokens=100)
        health = dd.get_model_health("M1")
        assert "latency_ms" in health["metrics"]
        assert "success" in health["metrics"]

    def test_record_failure(self):
        with patch.object(DriftDetector, "_load_state"):
            dd = DriftDetector()
        dd.record("M1", 1000, False)
        health = dd.get_model_health("M1")
        assert health["metrics"]["success"]["mean"] == 0.0

    def test_skips_zero_quality(self):
        with patch.object(DriftDetector, "_load_state"):
            dd = DriftDetector()
        dd.record("M1", 500, True, quality=0.0)
        health = dd.get_model_health("M1")
        assert "quality" not in health["metrics"]


# ===========================================================================
# DriftDetector — compute_baselines
# ===========================================================================

class TestComputeBaselines:
    def test_compute(self):
        with patch.object(DriftDetector, "_load_state"):
            dd = DriftDetector()
        now = time.time()
        for i in range(20):
            dd._windows["M1"]["latency_ms"].add(500 + i, now)
        dd.compute_baselines()
        assert "M1" in dd._baselines
        assert "latency_ms" in dd._baselines["M1"]
        mean, std = dd._baselines["M1"]["latency_ms"]
        assert 500 <= mean <= 520

    def test_too_few_samples(self):
        with patch.object(DriftDetector, "_load_state"):
            dd = DriftDetector()
        dd._windows["M1"]["latency_ms"].add(500, time.time())
        dd.compute_baselines()
        assert dd._baselines.get("M1", {}).get("latency_ms") is None


# ===========================================================================
# DriftDetector — _check_drift & alerts
# ===========================================================================

class TestCheckDrift:
    def test_no_baseline_no_alert(self):
        with patch.object(DriftDetector, "_load_state"):
            dd = DriftDetector()
        dd.record("M1", 500, True)
        assert dd.get_alerts() == []

    def test_drift_alert_generated(self):
        with patch.object(DriftDetector, "_load_state"):
            dd = DriftDetector()
        # Set baseline: latency 500ms ± 10ms
        dd._baselines["M1"] = {"latency_ms": (500, 10)}
        # Record 15 values way above baseline (>2.5σ)
        now = time.time()
        for _ in range(15):
            dd._windows["M1"]["latency_ms"].add(600, now)
        dd._check_drift("M1")
        alerts = dd.get_alerts()
        assert len(alerts) >= 1
        assert alerts[0]["model"] == "M1"
        assert alerts[0]["direction"] == "degraded"

    def test_improvement_alert(self):
        with patch.object(DriftDetector, "_load_state"):
            dd = DriftDetector()
        dd._baselines["M1"] = {"latency_ms": (500, 10)}
        now = time.time()
        for _ in range(15):
            dd._windows["M1"]["latency_ms"].add(400, now)
        dd._check_drift("M1")
        alerts = dd.get_alerts()
        assert len(alerts) >= 1
        assert alerts[0]["direction"] == "improved"


# ===========================================================================
# DriftDetector — get_model_health / get_all_health
# ===========================================================================

class TestHealth:
    def test_unknown_model(self):
        with patch.object(DriftDetector, "_load_state"):
            dd = DriftDetector()
        health = dd.get_model_health("unknown")
        assert health["model"] == "unknown"
        assert health["metrics"] == {}

    def test_with_data(self):
        with patch.object(DriftDetector, "_load_state"):
            dd = DriftDetector()
        now = time.time()
        dd._windows["M1"]["latency_ms"].add(500, now)
        dd._windows["M1"]["latency_ms"].add(600, now)
        health = dd.get_model_health("M1")
        assert health["metrics"]["latency_ms"]["mean"] == 550
        assert health["metrics"]["latency_ms"]["count"] == 2

    def test_get_all_health(self):
        with patch.object(DriftDetector, "_load_state"):
            dd = DriftDetector()
        dd._windows["M1"]["latency_ms"].add(500, time.time())
        dd._windows["OL1"]["latency_ms"].add(200, time.time())
        all_health = dd.get_all_health()
        assert "M1" in all_health
        assert "OL1" in all_health


# ===========================================================================
# DriftDetector — get_degraded_models / suggest_rerouting
# ===========================================================================

class TestDegradedAndRerouting:
    def test_no_degraded(self):
        with patch.object(DriftDetector, "_load_state"):
            dd = DriftDetector()
        assert dd.get_degraded_models() == []

    def test_degraded_model(self):
        with patch.object(DriftDetector, "_load_state"):
            dd = DriftDetector()
        dd._alerts = [{"model": "M2", "direction": "degraded", "timestamp": time.time()}]
        assert "M2" in dd.get_degraded_models()

    def test_old_alert_not_degraded(self):
        with patch.object(DriftDetector, "_load_state"):
            dd = DriftDetector()
        dd._alerts = [{"model": "M2", "direction": "degraded", "timestamp": time.time() - 900}]
        assert dd.get_degraded_models() == []

    def test_suggest_rerouting(self):
        with patch.object(DriftDetector, "_load_state"):
            dd = DriftDetector()
        dd._alerts = [{"model": "M2", "direction": "degraded", "timestamp": time.time()}]
        result = dd.suggest_rerouting("code", ["M1", "M2", "OL1"])
        assert result == ["M1", "OL1", "M2"]

    def test_suggest_rerouting_no_degraded(self):
        with patch.object(DriftDetector, "_load_state"):
            dd = DriftDetector()
        result = dd.suggest_rerouting("code", ["M1", "M2"])
        assert result == ["M1", "M2"]


# ===========================================================================
# DriftDetector — get_report
# ===========================================================================

class TestReport:
    def test_report_structure(self):
        with patch.object(DriftDetector, "_load_state"):
            dd = DriftDetector()
        report = dd.get_report()
        assert "models" in report
        assert "alerts" in report
        assert "degraded" in report
        assert "baseline_models" in report
        assert "timestamp" in report
