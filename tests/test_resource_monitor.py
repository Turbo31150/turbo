"""Tests for src/resource_monitor.py — System resource tracking.

Covers: ResourceSnapshot, ResourceMonitor (sample, set_threshold,
get_thresholds, _query_gpus, _query_disks, get_latest, get_history,
get_stats, _check_alerts), resource_monitor singleton.
All psutil/subprocess calls are mocked.
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

from src.resource_monitor import ResourceMonitor, ResourceSnapshot, resource_monitor


# ===========================================================================
# ResourceSnapshot dataclass
# ===========================================================================

class TestResourceSnapshot:
    def test_create(self):
        snap = ResourceSnapshot(
            ts=1.0, cpu_percent=50.0, ram_used_gb=8.0,
            ram_total_gb=16.0, ram_percent=50.0, gpus=[], disks=[],
        )
        assert snap.cpu_percent == 50.0


# ===========================================================================
# ResourceMonitor — thresholds
# ===========================================================================

class TestThresholds:
    def test_defaults(self):
        rm = ResourceMonitor()
        t = rm.get_thresholds()
        assert t["cpu_percent"] == 90.0
        assert t["gpu_temp_c"] == 85.0

    def test_set_threshold(self):
        rm = ResourceMonitor()
        rm.set_threshold("cpu_percent", 80.0)
        assert rm.get_thresholds()["cpu_percent"] == 80.0

    def test_set_invalid_key(self):
        rm = ResourceMonitor()
        rm.set_threshold("nonexistent", 42)
        assert "nonexistent" not in rm.get_thresholds()


# ===========================================================================
# ResourceMonitor — sample (mocked)
# ===========================================================================

class TestSample:
    def test_sample_with_psutil(self):
        rm = ResourceMonitor()
        mock_psutil = MagicMock()
        mock_psutil.cpu_percent.return_value = 45.0
        mock_mem = MagicMock()
        mock_mem.used = 8 * (1024**3)
        mock_mem.total = 16 * (1024**3)
        mock_mem.percent = 50.0
        mock_psutil.virtual_memory.return_value = mock_mem
        mock_psutil.disk_partitions.return_value = []

        with patch.dict("sys.modules", {"psutil": mock_psutil}), \
             patch.object(rm, "_query_gpus", return_value=[]), \
             patch.object(rm, "_query_disks", return_value=[]), \
             patch.object(rm, "_check_alerts"):
            snap = rm.sample()

        assert snap["cpu_percent"] == 45.0
        assert snap["ram_percent"] == 50.0
        assert len(rm._history) == 1

    def test_sample_without_psutil(self):
        rm = ResourceMonitor()
        with patch.dict("sys.modules", {"psutil": None}), \
             patch.object(rm, "_query_gpus", return_value=[]), \
             patch.object(rm, "_query_disks", return_value=[]), \
             patch.object(rm, "_check_alerts"):
            snap = rm.sample()
        assert snap["cpu_percent"] == 0.0
        assert snap["ram_percent"] == 0.0


# ===========================================================================
# ResourceMonitor — _query_gpus (mocked)
# ===========================================================================

class TestQueryGpus:
    def test_success(self):
        rm = ResourceMonitor()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "0, NVIDIA GeForce RTX 3090, 55, 4096, 24576, 30\n"
        with patch("subprocess.run", return_value=mock_result):
            gpus = rm._query_gpus()
        assert len(gpus) == 1
        assert gpus[0]["name"] == "NVIDIA GeForce RTX 3090"
        assert gpus[0]["temp_c"] == 55.0

    def test_nvidia_smi_not_found(self):
        rm = ResourceMonitor()
        with patch("subprocess.run", side_effect=FileNotFoundError):
            gpus = rm._query_gpus()
        assert gpus == []

    def test_nvidia_smi_error(self):
        rm = ResourceMonitor()
        mock_result = MagicMock()
        mock_result.returncode = 1
        with patch("subprocess.run", return_value=mock_result):
            gpus = rm._query_gpus()
        assert gpus == []


# ===========================================================================
# ResourceMonitor — _query_disks (mocked)
# ===========================================================================

class TestQueryDisks:
    def test_success(self):
        rm = ResourceMonitor()
        mock_psutil = MagicMock()
        mock_part = MagicMock()
        mock_part.mountpoint = "C:\\"
        mock_psutil.disk_partitions.return_value = [mock_part]
        mock_usage = MagicMock()
        mock_usage.total = 500 * (1024**3)
        mock_usage.used = 300 * (1024**3)
        mock_usage.percent = 60.0
        mock_psutil.disk_usage.return_value = mock_usage

        with patch.dict("sys.modules", {"psutil": mock_psutil}):
            disks = rm._query_disks()
        assert len(disks) == 1
        assert disks[0]["mount"] == "C:\\"
        assert disks[0]["percent"] == 60.0

    def test_no_psutil(self):
        rm = ResourceMonitor()
        with patch.dict("sys.modules", {"psutil": None}):
            disks = rm._query_disks()
        assert disks == []


# ===========================================================================
# ResourceMonitor — history & stats
# ===========================================================================

class TestHistoryStats:
    def test_get_latest_empty(self):
        rm = ResourceMonitor()
        assert rm.get_latest() == {}

    def test_get_latest(self):
        rm = ResourceMonitor()
        rm._history.append({"ts": time.time(), "cpu": 50})
        latest = rm.get_latest()
        assert latest["cpu"] == 50

    def test_get_history_filtered(self):
        rm = ResourceMonitor()
        rm._history.append({"ts": time.time() - 7200})  # 2h ago
        rm._history.append({"ts": time.time() - 10})  # 10s ago
        recent = rm.get_history(minutes=60)
        assert len(recent) == 1

    def test_stats(self):
        rm = ResourceMonitor()
        stats = rm.get_stats()
        assert stats["samples"] == 0
        assert stats["max_history"] == 360


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert resource_monitor is not None
        assert isinstance(resource_monitor, ResourceMonitor)
