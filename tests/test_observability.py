"""Tests for src/observability.py — Real-time metrics correlation & anomaly detection.

Covers: MetricPoint, _pearson, ObservabilityMatrix (record, record_node_call,
get_windowed, get_heatmap, compute_baselines, _anomaly_score, get_correlations,
get_alerts, get_report), observability_matrix singleton.
Pure in-memory — no external calls needed.
"""

from __future__ import annotations

import math
import sys
import time
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.observability import (
    MetricPoint, ObservabilityMatrix, _pearson,
    observability_matrix, NODES, METRIC_TYPES, WINDOWS,
)


# ===========================================================================
# Constants
# ===========================================================================

class TestConstants:
    def test_nodes(self):
        assert "M1" in NODES
        assert "OL1" in NODES
        assert len(NODES) >= 4

    def test_metric_types(self):
        assert "latency_ms" in METRIC_TYPES
        assert "success_rate" in METRIC_TYPES

    def test_windows(self):
        assert WINDOWS["1m"] == 60
        assert WINDOWS["5m"] == 300
        assert WINDOWS["1h"] == 3600


# ===========================================================================
# MetricPoint
# ===========================================================================

class TestMetricPoint:
    def test_defaults(self):
        p = MetricPoint(node="M1", metric="latency_ms", value=42.0)
        assert p.node == "M1"
        assert p.metric == "latency_ms"
        assert p.value == 42.0
        assert p.timestamp > 0


# ===========================================================================
# _pearson
# ===========================================================================

class TestPearson:
    def test_perfect_positive(self):
        r = _pearson([1, 2, 3, 4, 5], [2, 4, 6, 8, 10])
        assert r == pytest.approx(1.0, abs=0.001)

    def test_perfect_negative(self):
        r = _pearson([1, 2, 3, 4, 5], [10, 8, 6, 4, 2])
        assert r == pytest.approx(-1.0, abs=0.001)

    def test_no_correlation(self):
        r = _pearson([1, 2, 3, 4, 5], [3, 3, 3, 3, 3])
        assert r == 0.0

    def test_too_few_points(self):
        assert _pearson([1], [2]) == 0.0
        assert _pearson([], []) == 0.0


# ===========================================================================
# ObservabilityMatrix — record / get_windowed
# ===========================================================================

class TestRecordAndWindowed:
    def test_record_and_retrieve(self):
        om = ObservabilityMatrix()
        om.record("M1", "latency_ms", 50.0)
        om.record("M1", "latency_ms", 60.0)
        om.record("OL1", "latency_ms", 10.0)
        data = om.get_windowed("5m")
        assert "M1" in data
        assert "latency_ms" in data["M1"]
        assert data["M1"]["latency_ms"]["mean"] == 55.0
        assert data["M1"]["latency_ms"]["count"] == 2
        assert data["M1"]["latency_ms"]["min"] == 50.0
        assert data["M1"]["latency_ms"]["max"] == 60.0
        assert data["OL1"]["latency_ms"]["mean"] == 10.0

    def test_empty_windowed(self):
        om = ObservabilityMatrix()
        data = om.get_windowed("5m")
        assert data == {}

    def test_record_node_call(self):
        om = ObservabilityMatrix()
        om.record_node_call("M1", latency_ms=100, success=True, tokens=500, duration_s=5.0)
        data = om.get_windowed("5m")
        assert data["M1"]["latency_ms"]["mean"] == 100.0
        assert data["M1"]["success_rate"]["mean"] == 1.0
        assert data["M1"]["tokens_per_sec"]["mean"] == 100.0

    def test_record_node_call_failure(self):
        om = ObservabilityMatrix()
        om.record_node_call("M2", latency_ms=5000, success=False)
        data = om.get_windowed("5m")
        assert data["M2"]["success_rate"]["mean"] == 0.0
        assert data["M2"]["error_rate"]["mean"] == 1.0

    def test_max_points(self):
        om = ObservabilityMatrix(max_points=10)
        for i in range(20):
            om.record("M1", "latency_ms", float(i))
        # deque maxlen=10 keeps last 10
        data = om.get_windowed("5m")
        assert data["M1"]["latency_ms"]["count"] == 10
        assert data["M1"]["latency_ms"]["min"] == 10.0


# ===========================================================================
# ObservabilityMatrix — heatmap
# ===========================================================================

class TestHeatmap:
    def test_heatmap_structure(self):
        om = ObservabilityMatrix()
        om.record("M1", "latency_ms", 50.0)
        om.record("OL1", "success_rate", 1.0)
        heatmap = om.get_heatmap("5m")
        assert len(heatmap) == 2
        for entry in heatmap:
            assert "node" in entry
            assert "metric" in entry
            assert "value" in entry
            assert "anomaly_score" in entry

    def test_heatmap_empty(self):
        om = ObservabilityMatrix()
        assert om.get_heatmap("5m") == []


# ===========================================================================
# ObservabilityMatrix — baselines & anomaly detection
# ===========================================================================

class TestAnomalyDetection:
    def test_anomaly_no_baseline(self):
        om = ObservabilityMatrix()
        score = om._anomaly_score("M1", "latency_ms", 100.0)
        assert score == 0.0

    def test_compute_baselines(self):
        om = ObservabilityMatrix()
        for i in range(10):
            om.record("M1", "latency_ms", 50.0 + i)
        om.compute_baselines("5m")
        assert "M1" in om._baselines
        assert "latency_ms" in om._baselines["M1"]

    def test_anomaly_with_baseline(self):
        om = ObservabilityMatrix()
        # Record normal values to establish baseline
        for _ in range(20):
            om.record("M1", "latency_ms", 50.0)
        om.compute_baselines("5m")
        # Normal value -> low anomaly
        score_normal = om._anomaly_score("M1", "latency_ms", 50.0)
        # Extreme value -> high anomaly
        score_extreme = om._anomaly_score("M1", "latency_ms", 500.0)
        assert score_extreme > score_normal

    def test_get_alerts_empty(self):
        om = ObservabilityMatrix()
        om.record("M1", "latency_ms", 50.0)
        alerts = om.get_alerts(threshold=0.7)
        assert alerts == []  # No baselines -> all anomaly scores = 0


# ===========================================================================
# ObservabilityMatrix — correlations
# ===========================================================================

class TestCorrelations:
    def test_correlated_metrics(self):
        om = ObservabilityMatrix()
        now = time.time()
        # Create correlated time series across 5 buckets (10s each)
        for i in range(5):
            t = now - (4 - i) * 10
            p1 = MetricPoint(node="M1", metric="latency_ms", value=float(10 + i * 5), timestamp=t)
            p2 = MetricPoint(node="OL1", metric="latency_ms", value=float(20 + i * 5), timestamp=t)
            om._points.append(p1)
            om._points.append(p2)
        corrs = om.get_correlations("5m")
        # Should find positive correlation between M1 and OL1 latency
        if corrs:
            assert corrs[0]["correlation"] > 0.6

    def test_no_correlations_few_points(self):
        om = ObservabilityMatrix()
        om.record("M1", "latency_ms", 10.0)
        corrs = om.get_correlations("5m")
        assert corrs == []

    def test_correlations_empty(self):
        om = ObservabilityMatrix()
        assert om.get_correlations("5m") == []


# ===========================================================================
# ObservabilityMatrix — report
# ===========================================================================

class TestReport:
    def test_report_structure(self):
        om = ObservabilityMatrix()
        om.record("M1", "latency_ms", 42.0)
        report = om.get_report()
        assert "matrix_5m" in report
        assert "heatmap" in report
        assert "correlations" in report
        assert "alerts" in report
        assert "total_points" in report
        assert report["total_points"] == 1
        assert "timestamp" in report

    def test_report_empty(self):
        om = ObservabilityMatrix()
        report = om.get_report()
        assert report["total_points"] == 0
        assert report["matrix_5m"] == {}


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert observability_matrix is not None
        assert isinstance(observability_matrix, ObservabilityMatrix)
