"""Tests for src/auto_tune.py — Dynamic resource profiling & workload balancing.

Covers: ResourceSnapshot, NodeLoad, AutoTuneScheduler (sample, get_node_load,
begin_request, end_request, apply_cooldown, recommend_threadpool_size,
get_best_available_node, get_status), auto_tune singleton.
subprocess and psutil calls are mocked.
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

from src.auto_tune import (
    ResourceSnapshot, NodeLoad, AutoTuneScheduler, auto_tune,
)


# ===========================================================================
# Dataclasses
# ===========================================================================

class TestResourceSnapshot:
    def test_defaults(self):
        s = ResourceSnapshot()
        assert s.cpu_percent == 0.0
        assert s.memory_percent == 0.0
        assert s.gpu_temp_c == 0.0
        assert s.timestamp > 0


class TestNodeLoad:
    def test_defaults(self):
        n = NodeLoad(name="M1")
        assert n.active_requests == 0
        assert n.is_cooling is False
        assert n.load_factor == 0.0

    def test_load_factor(self):
        n = NodeLoad(name="M1", active_requests=2, max_concurrent=4)
        assert n.load_factor == 0.5

    def test_load_factor_at_capacity(self):
        n = NodeLoad(name="M1", active_requests=5, max_concurrent=3)
        assert n.load_factor == 1.0  # capped

    def test_is_cooling(self):
        n = NodeLoad(name="M1", cooldown_until=time.time() + 100)
        assert n.is_cooling is True
        assert n.load_factor == 1.0

    def test_not_cooling(self):
        n = NodeLoad(name="M1", cooldown_until=time.time() - 10)
        assert n.is_cooling is False


# ===========================================================================
# AutoTuneScheduler — sample
# ===========================================================================

class TestSample:
    def test_sample_no_psutil_no_gpu(self):
        ats = AutoTuneScheduler()
        with patch.dict("sys.modules", {"psutil": None}), \
             patch("subprocess.check_output", side_effect=FileNotFoundError):
            snap = ats.sample()
        assert isinstance(snap, ResourceSnapshot)
        assert len(ats._history) == 1

    def test_sample_with_psutil(self):
        ats = AutoTuneScheduler()
        mock_psutil = MagicMock()
        mock_psutil.cpu_percent.return_value = 45.0
        mock_psutil.virtual_memory.return_value = MagicMock(percent=60.0)
        with patch.dict("sys.modules", {"psutil": mock_psutil}), \
             patch("subprocess.check_output", side_effect=FileNotFoundError):
            snap = ats.sample()
        assert snap.cpu_percent == 45.0
        assert snap.memory_percent == 60.0

    def test_sample_with_gpu(self):
        ats = AutoTuneScheduler()
        gpu_output = "65, 80, 4096, 8192\n70, 90, 6000, 12288"
        with patch.dict("sys.modules", {"psutil": None}), \
             patch("subprocess.check_output", return_value=gpu_output):
            snap = ats.sample()
        assert snap.gpu_temp_c == 70.0  # max of two GPUs
        assert snap.gpu_util_percent == 90.0
        assert snap.gpu_memory_used_mb == 10096.0  # 4096 + 6000


# ===========================================================================
# AutoTuneScheduler — node load tracking
# ===========================================================================

class TestNodeLoadTracking:
    def test_get_node_load_creates(self):
        ats = AutoTuneScheduler()
        load = ats.get_node_load("M1")
        assert load.name == "M1"
        assert load.active_requests == 0

    def test_begin_end_request(self):
        ats = AutoTuneScheduler()
        ats.begin_request("M1")
        assert ats.get_node_load("M1").active_requests == 1
        ats.end_request("M1", latency_ms=100.0, success=True)
        assert ats.get_node_load("M1").active_requests == 0
        assert ats.get_node_load("M1").avg_latency_ms > 0

    def test_end_request_failure(self):
        ats = AutoTuneScheduler()
        ats.begin_request("M1")
        ats.end_request("M1", latency_ms=5000, success=False)
        assert ats.get_node_load("M1").error_rate > 0

    def test_apply_cooldown(self):
        ats = AutoTuneScheduler()
        ats.apply_cooldown("M2", seconds=60)
        load = ats.get_node_load("M2")
        assert load.is_cooling is True


# ===========================================================================
# AutoTuneScheduler — threadpool recommendation
# ===========================================================================

class TestThreadpool:
    def test_not_enough_data(self):
        ats = AutoTuneScheduler()
        assert ats.recommend_threadpool_size() == 4  # default

    def test_high_load_reduces(self):
        ats = AutoTuneScheduler()
        for _ in range(10):
            ats._history.append(ResourceSnapshot(
                cpu_percent=90, memory_percent=50, gpu_util_percent=30))
        result = ats.recommend_threadpool_size()
        assert result < 4

    def test_low_load_increases(self):
        ats = AutoTuneScheduler()
        for _ in range(10):
            ats._history.append(ResourceSnapshot(
                cpu_percent=20, memory_percent=30, gpu_util_percent=20))
        result = ats.recommend_threadpool_size()
        assert result > 4


# ===========================================================================
# AutoTuneScheduler — best available node
# ===========================================================================

class TestBestNode:
    def test_best_node(self):
        ats = AutoTuneScheduler()
        ats.begin_request("M1")
        ats.begin_request("M1")
        # OL1 has no requests → lowest load
        best = ats.get_best_available_node(["M1", "OL1"])
        assert best == "OL1"

    def test_all_cooling(self):
        ats = AutoTuneScheduler()
        ats.apply_cooldown("M1", 60)
        ats.apply_cooldown("M2", 60)
        assert ats.get_best_available_node(["M1", "M2"]) is None

    def test_empty_candidates(self):
        ats = AutoTuneScheduler()
        assert ats.get_best_available_node([]) is None


# ===========================================================================
# AutoTuneScheduler — status
# ===========================================================================

class TestStatus:
    def test_status_structure(self):
        ats = AutoTuneScheduler()
        ats.begin_request("M1")
        status = ats.get_status()
        assert "resource_snapshot" in status
        assert "threadpool_size" in status
        assert "nodes" in status
        assert "M1" in status["nodes"]
        assert status["nodes"]["M1"]["active_requests"] == 1

    def test_status_empty(self):
        ats = AutoTuneScheduler()
        status = ats.get_status()
        assert status["history_size"] == 0
        assert status["nodes"] == {}


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert auto_tune is not None
        assert isinstance(auto_tune, AutoTuneScheduler)
