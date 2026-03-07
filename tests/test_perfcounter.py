"""Tests for src/perfcounter.py — Windows performance counters.

Covers: PerfSample, PerfEvent, PerfCounter (read_counter, read_named,
snapshot, list_counters, get_history, get_events, get_stats),
perfcounter singleton.
All subprocess calls are mocked.
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

from src.perfcounter import (
    PerfSample, PerfEvent, PerfCounter, COUNTER_PATHS, perfcounter,
)


# ===========================================================================
# Dataclasses
# ===========================================================================

class TestDataclasses:
    def test_perf_sample(self):
        ps = PerfSample(counter="cpu", value=45.0)
        assert ps.timestamp > 0

    def test_perf_event(self):
        pe = PerfEvent(action="read")
        assert pe.success is True


# ===========================================================================
# PerfCounter — read_counter (mocked)
# ===========================================================================

class TestReadCounter:
    def test_success(self):
        pc = PerfCounter()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "45.67\n"
        with patch("subprocess.run", return_value=mock_result):
            val = pc.read_counter("\\Processor(_Total)\\% Processor Time")
        assert val == pytest.approx(45.67)

    def test_failure(self):
        pc = PerfCounter()
        with patch("subprocess.run", side_effect=Exception("fail")):
            val = pc.read_counter("\\Processor\\test")
        assert val is None

    def test_nonzero_return(self):
        pc = PerfCounter()
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        with patch("subprocess.run", return_value=mock_result):
            val = pc.read_counter("\\Test")
        assert val is None


# ===========================================================================
# PerfCounter — read_named
# ===========================================================================

class TestReadNamed:
    def test_known_name(self):
        pc = PerfCounter()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "8192.0\n"
        with patch("subprocess.run", return_value=mock_result):
            val = pc.read_named("memory")
        assert val == 8192.0

    def test_unknown_name(self):
        pc = PerfCounter()
        val = pc.read_named("nonexistent")
        assert val is None


# ===========================================================================
# PerfCounter — snapshot (mocked)
# ===========================================================================

SNAPSHOT_JSON = json.dumps([
    {"Path": "\\\\pc\\processor(_total)\\% processor time", "CookedValue": 32.5},
    {"Path": "\\\\pc\\memory\\available mbytes", "CookedValue": 16384.0},
    {"Path": "\\\\pc\\system\\processes", "CookedValue": 250},
    {"Path": "\\\\pc\\system\\threads", "CookedValue": 3000},
])


class TestSnapshot:
    def test_success(self):
        pc = PerfCounter()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = SNAPSHOT_JSON
        with patch("subprocess.run", return_value=mock_result):
            snap = pc.snapshot()
        assert snap["cpu_percent"] == 32.5
        assert snap["available_mb"] == 16384.0
        assert snap["processes"] == 250
        assert snap["threads"] == 3000

    def test_failure(self):
        pc = PerfCounter()
        with patch("subprocess.run", side_effect=Exception("fail")):
            snap = pc.snapshot()
        assert "error" in snap

    def test_stores_history(self):
        pc = PerfCounter()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = SNAPSHOT_JSON
        with patch("subprocess.run", return_value=mock_result):
            pc.snapshot()
            pc.snapshot()
        assert len(pc.get_history()) == 2


# ===========================================================================
# PerfCounter — list_counters
# ===========================================================================

class TestListCounters:
    def test_returns_dict(self):
        pc = PerfCounter()
        counters = pc.list_counters()
        assert isinstance(counters, dict)
        assert "cpu" in counters
        assert "memory" in counters


# ===========================================================================
# PerfCounter — events & stats
# ===========================================================================

class TestEventsStats:
    def test_events_empty(self):
        pc = PerfCounter()
        assert pc.get_events() == []

    def test_stats(self):
        pc = PerfCounter()
        stats = pc.get_stats()
        assert stats["total_events"] == 0
        assert stats["history_size"] == 0
        assert stats["available_counters"] == len(COUNTER_PATHS)


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert perfcounter is not None
        assert isinstance(perfcounter, PerfCounter)
