"""Tests for src/telemetry_collector.py — Usage metrics collection.

Covers: MetricPoint, TelemetryCollector (record, increment, set_gauge,
record_histogram, get_counter, get_gauge, get_histogram_stats,
query, get_counters, get_gauges, get_stats), telemetry singleton.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.telemetry_collector import MetricPoint, TelemetryCollector, telemetry


class TestMetricPoint:
    def test_defaults(self):
        m = MetricPoint(name="api.call", value=1.0)
        assert m.tags == {}
        assert m.ts > 0


class TestRecord:
    def test_record(self):
        tc = TelemetryCollector()
        tc.record("api.call", 1.0, {"service": "auth"})
        points = tc.query()
        assert len(points) == 1
        assert points[0]["name"] == "api.call"
        assert points[0]["tags"]["service"] == "auth"

    def test_max_points(self):
        tc = TelemetryCollector(max_points=5)
        for i in range(10):
            tc.record("metric", float(i))
        assert len(tc.query(limit=100)) == 5


class TestCounters:
    def test_increment(self):
        tc = TelemetryCollector()
        tc.increment("requests")
        tc.increment("requests", 5)
        assert tc.get_counter("requests") == 6

    def test_get_counter_missing(self):
        tc = TelemetryCollector()
        assert tc.get_counter("missing") == 0

    def test_get_counters(self):
        tc = TelemetryCollector()
        tc.increment("a")
        tc.increment("b", 3)
        counters = tc.get_counters()
        assert counters["a"] == 1
        assert counters["b"] == 3


class TestGauges:
    def test_set_gauge(self):
        tc = TelemetryCollector()
        tc.set_gauge("cpu", 55.0)
        assert tc.get_gauge("cpu") == 55.0

    def test_get_gauge_missing(self):
        tc = TelemetryCollector()
        assert tc.get_gauge("missing") is None

    def test_get_gauges(self):
        tc = TelemetryCollector()
        tc.set_gauge("cpu", 50.0)
        tc.set_gauge("mem", 70.0)
        assert len(tc.get_gauges()) == 2


class TestHistograms:
    def test_record_histogram(self):
        tc = TelemetryCollector()
        for v in [10, 20, 30, 40, 50]:
            tc.record_histogram("latency", float(v))
        stats = tc.get_histogram_stats("latency")
        assert stats["count"] == 5
        assert stats["min"] == 10.0
        assert stats["max"] == 50.0
        assert stats["avg"] == 30.0

    def test_histogram_missing(self):
        tc = TelemetryCollector()
        assert tc.get_histogram_stats("nope") is None

    def test_histogram_truncation(self):
        tc = TelemetryCollector()
        for i in range(1100):
            tc.record_histogram("big", float(i))
        stats = tc.get_histogram_stats("big")
        assert stats["count"] == 1000


class TestQuery:
    def test_query_by_name(self):
        tc = TelemetryCollector()
        tc.record("a", 1.0)
        tc.record("b", 2.0)
        assert len(tc.query(name="a")) == 1

    def test_query_since(self):
        tc = TelemetryCollector()
        tc.record("old", 1.0)
        time.sleep(0.01)
        cutoff = time.time()
        time.sleep(0.01)
        tc.record("new", 2.0)
        results = tc.query(since=cutoff)
        assert all(r["name"] == "new" for r in results)

    def test_query_limit(self):
        tc = TelemetryCollector()
        for i in range(10):
            tc.record("m", float(i))
        assert len(tc.query(limit=3)) == 3


class TestStats:
    def test_stats(self):
        tc = TelemetryCollector()
        tc.record("a", 1.0)
        tc.increment("c")
        tc.set_gauge("g", 1.0)
        tc.record_histogram("h", 1.0)
        stats = tc.get_stats()
        assert stats["total_points"] == 1
        assert stats["counters"] == 1
        assert stats["gauges"] == 1
        assert stats["histograms"] == 1


class TestSingleton:
    def test_exists(self):
        assert isinstance(telemetry, TelemetryCollector)
