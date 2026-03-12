"""Tests for src/performance_counter.py — Windows perf counters.

Covers: CounterSnapshot, PerfEvent, PerformanceCounterManager (snapshot,
get_history, get_counter, get_events, get_stats),
performance_counter singleton. All subprocess calls are mocked.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.performance_counter import (
    CounterSnapshot, PerfEvent, PerformanceCounterManager, performance_counter,
)

SNAPSHOT_JSON = json.dumps({
    "//desktop/processor(_total)/% processor time": 25.5,
    "//desktop/memory/available mbytes": 4096.0,
})


# ===========================================================================
# Dataclasses
# ===========================================================================

class TestDataclasses:
    def test_counter_snapshot(self):
        s = CounterSnapshot()
        assert s.counters == {}

    def test_perf_event(self):
        e = PerfEvent(action="snapshot")
        assert e.success is True


# ===========================================================================
# PerformanceCounterManager — snapshot
# ===========================================================================

class TestSnapshot:
    def test_success(self):
        pcm = PerformanceCounterManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = SNAPSHOT_JSON
        with patch("subprocess.run", return_value=mock_result):
            snap = pcm.snapshot()
        assert "counters" in snap
        assert len(snap["counters"]) == 2

    def test_failure(self):
        pcm = PerformanceCounterManager()
        with patch("subprocess.run", side_effect=Exception("fail")):
            snap = pcm.snapshot()
        assert snap["counters"] == {}


# ===========================================================================
# PerformanceCounterManager — get_history
# ===========================================================================

class TestHistory:
    def test_history(self):
        pcm = PerformanceCounterManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = SNAPSHOT_JSON
        with patch("subprocess.run", return_value=mock_result):
            pcm.snapshot()
            pcm.snapshot()
        history = pcm.get_history()
        assert len(history) == 2


# ===========================================================================
# PerformanceCounterManager — get_counter
# ===========================================================================

class TestGetCounter:
    def test_success(self):
        pcm = PerformanceCounterManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({"path": "/cpu/time", "value": 42.0})
        with patch("subprocess.run", return_value=mock_result):
            counter = pcm.get_counter("/cpu/time")
        assert counter["value"] == 42.0

    def test_failure(self):
        pcm = PerformanceCounterManager()
        with patch("subprocess.run", side_effect=Exception("fail")):
            counter = pcm.get_counter("/cpu/time")
        assert counter["value"] == 0


# ===========================================================================
# Events & stats
# ===========================================================================

class TestEventsStats:
    def test_events_empty(self):
        pcm = PerformanceCounterManager()
        assert pcm.get_events() == []

    def test_stats(self):
        pcm = PerformanceCounterManager()
        stats = pcm.get_stats()
        assert stats["total_events"] == 0
        assert stats["history_size"] == 0


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert performance_counter is not None
        assert isinstance(performance_counter, PerformanceCounterManager)
