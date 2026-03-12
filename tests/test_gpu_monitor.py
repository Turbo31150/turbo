"""Tests for src/gpu_monitor.py — Windows GPU monitoring and management.

Covers: GPUInfo, GPUEvent, GPUMonitor (get_nvidia_info, list_gpus, snapshot,
get_history, get_events, get_stats), gpu_monitor singleton.
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

from src.gpu_monitor import GPUInfo, GPUEvent, GPUMonitor, gpu_monitor


# ===========================================================================
# Dataclasses
# ===========================================================================

class TestGPUInfo:
    def test_defaults(self):
        g = GPUInfo(name="RTX 3060")
        assert g.driver_version == ""
        assert g.vram_total_mb == 0
        assert g.temperature == 0


class TestGPUEvent:
    def test_defaults(self):
        e = GPUEvent(action="get_nvidia_info")
        assert e.success is True
        assert e.timestamp > 0


# ===========================================================================
# GPUMonitor — get_nvidia_info (mocked)
# ===========================================================================

NVIDIA_CSV = "NVIDIA GeForce RTX 3060, 55, 30, 12288, 4096, 8192, 537.34\n"


class TestGetNvidiaInfo:
    def test_parses_nvidia_smi(self):
        gm = GPUMonitor()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = NVIDIA_CSV
        with patch("subprocess.run", return_value=mock_result):
            gpus = gm.get_nvidia_info()
        assert len(gpus) == 1
        assert gpus[0]["name"] == "NVIDIA GeForce RTX 3060"
        assert gpus[0]["temperature"] == 55
        assert gpus[0]["utilization"] == 30
        assert gpus[0]["vram_total_mb"] == 12288
        assert gpus[0]["driver_version"] == "537.34"

    def test_multiple_gpus(self):
        gm = GPUMonitor()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = (
            "RTX 3060, 55, 30, 12288, 4096, 8192, 537.34\n"
            "GTX 1660, 65, 80, 6144, 5000, 1144, 537.34\n"
        )
        with patch("subprocess.run", return_value=mock_result):
            gpus = gm.get_nvidia_info()
        assert len(gpus) == 2

    def test_nvidia_smi_not_found(self):
        gm = GPUMonitor()
        with patch("subprocess.run", side_effect=FileNotFoundError):
            gpus = gm.get_nvidia_info()
        assert gpus == []

    def test_nvidia_smi_exception(self):
        gm = GPUMonitor()
        with patch("subprocess.run", side_effect=Exception("fail")):
            gpus = gm.get_nvidia_info()
        assert gpus == []


# ===========================================================================
# GPUMonitor — list_gpus (WMI, mocked)
# ===========================================================================

class TestListGpus:
    def test_parses_wmi(self):
        gm = GPUMonitor()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps([
            {"Name": "RTX 3060", "DriverVersion": "537.34",
             "AdapterRAM": 12884901888, "VideoProcessor": "GP106", "Status": "OK"},
        ])
        with patch("subprocess.run", return_value=mock_result):
            gpus = gm.list_gpus()
        assert len(gpus) == 1
        assert gpus[0]["name"] == "RTX 3060"
        assert gpus[0]["vram_mb"] == 12288

    def test_single_gpu_dict(self):
        gm = GPUMonitor()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(
            {"Name": "Intel HD", "DriverVersion": "1.0", "AdapterRAM": 0,
             "VideoProcessor": "", "Status": "OK"})
        with patch("subprocess.run", return_value=mock_result):
            gpus = gm.list_gpus()
        assert len(gpus) == 1

    def test_exception(self):
        gm = GPUMonitor()
        with patch("subprocess.run", side_effect=Exception("fail")):
            gpus = gm.list_gpus()
        assert gpus == []


# ===========================================================================
# GPUMonitor — snapshot
# ===========================================================================

class TestSnapshot:
    def test_snapshot_nvidia(self):
        gm = GPUMonitor()
        with patch.object(gm, "get_nvidia_info", return_value=[
            {"name": "RTX 3060", "temperature": 60, "vram_total_mb": 12288,
             "vram_used_mb": 4096, "utilization": 50},
        ]):
            snap = gm.snapshot()
        assert snap["gpu_count"] == 1
        assert snap["max_temp"] == 60
        assert snap["total_vram_mb"] == 12288

    def test_snapshot_wmi_fallback(self):
        gm = GPUMonitor()
        with patch.object(gm, "get_nvidia_info", return_value=[]), \
             patch.object(gm, "list_gpus", return_value=[
                 {"name": "Intel HD", "vram_mb": 512},
             ]):
            snap = gm.snapshot()
        assert snap["gpu_count"] == 1
        assert snap["max_temp"] == 0
        assert snap["total_vram_mb"] == 512

    def test_snapshot_history(self):
        gm = GPUMonitor()
        with patch.object(gm, "get_nvidia_info", return_value=[]):
            with patch.object(gm, "list_gpus", return_value=[]):
                gm.snapshot()
                gm.snapshot()
        history = gm.get_history()
        assert len(history) == 2


# ===========================================================================
# GPUMonitor — events & stats
# ===========================================================================

class TestEventsStats:
    def test_events_empty(self):
        gm = GPUMonitor()
        assert gm.get_events() == []

    def test_stats(self):
        gm = GPUMonitor()
        stats = gm.get_stats()
        assert stats["total_events"] == 0
        assert stats["history_size"] == 0


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert gpu_monitor is not None
        assert isinstance(gpu_monitor, GPUMonitor)
