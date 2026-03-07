"""Tests for src/metrics_aggregator.py — Unified real-time metrics.

Covers: MetricsAggregator (snapshot, sample, get_history, get_latest,
get_summary), metrics_aggregator singleton.
All subsystem imports are mocked (they may fail gracefully).
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.metrics_aggregator import MetricsAggregator, metrics_aggregator


# ===========================================================================
# MetricsAggregator — snapshot
# ===========================================================================

class TestSnapshot:
    def test_snapshot_returns_dict(self):
        ma = MetricsAggregator()
        snap = ma.snapshot()
        assert isinstance(snap, dict)
        assert "ts" in snap

    def test_snapshot_has_subsystems(self):
        ma = MetricsAggregator()
        snap = ma.snapshot()
        # Some may have errors (subsystem not importable in test)
        expected_keys = ["orchestrator", "load_balancer", "autonomous_loop",
                         "agent_memory", "conversations", "proactive",
                         "optimizer", "event_bus"]
        for key in expected_keys:
            assert key in snap


# ===========================================================================
# MetricsAggregator — sample
# ===========================================================================

class TestSample:
    def test_sample_first_time(self):
        ma = MetricsAggregator()
        snap = ma.sample()
        assert snap is not None
        assert len(ma._history) == 1

    def test_sample_rate_limited(self):
        ma = MetricsAggregator()
        ma.sample()
        # Second call too fast → returns None
        result = ma.sample()
        assert result is None
        assert len(ma._history) == 1

    def test_sample_after_interval(self):
        ma = MetricsAggregator()
        ma.sample()
        # Force interval
        ma._last_sample = time.time() - 20
        result = ma.sample()
        assert result is not None
        assert len(ma._history) == 2


# ===========================================================================
# MetricsAggregator — history
# ===========================================================================

class TestHistory:
    def test_get_history_empty(self):
        ma = MetricsAggregator()
        assert ma.get_history() == []

    def test_get_history_filtered(self):
        ma = MetricsAggregator()
        # Add old sample
        ma._history.append({"ts": time.time() - 7200})  # 2h ago
        ma._history.append({"ts": time.time() - 10})  # 10s ago
        recent = ma.get_history(minutes=60)
        assert len(recent) == 1

    def test_get_latest(self):
        ma = MetricsAggregator()
        assert ma.get_latest() is None
        ma._history.append({"ts": 1234, "data": "test"})
        latest = ma.get_latest()
        assert latest["ts"] == 1234

    def test_get_latest_none(self):
        ma = MetricsAggregator()
        assert ma.get_latest() is None


# ===========================================================================
# MetricsAggregator — summary
# ===========================================================================

class TestSummary:
    def test_summary(self):
        ma = MetricsAggregator()
        summary = ma.get_summary()
        assert summary["sample_count"] == 0
        assert summary["max_samples"] == 360
        assert summary["sample_interval_s"] == 10.0

    def test_summary_after_samples(self):
        ma = MetricsAggregator()
        ma.sample()
        summary = ma.get_summary()
        assert summary["sample_count"] == 1
        assert summary["last_sample_ts"] > 0


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert metrics_aggregator is not None
        assert isinstance(metrics_aggregator, MetricsAggregator)
