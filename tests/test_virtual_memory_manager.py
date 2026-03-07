"""Tests for src/virtual_memory_manager.py — Windows virtual memory.

Covers: VirtualMemoryInfo, VMEvent, VirtualMemoryManager (get_status,
get_top_consumers, get_events, get_stats), virtual_memory_manager singleton.
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

from src.virtual_memory_manager import (
    VirtualMemoryInfo, VMEvent, VirtualMemoryManager, virtual_memory_manager,
)

STATUS_JSON = json.dumps({
    "TotalVisibleMemorySize": 16777216,
    "FreePhysicalMemory": 8388608,
    "TotalVirtualMemorySize": 33554432,
    "FreeVirtualMemory": 20000000,
    "SizeStoredInPagingFiles": 8388608,
    "FreeSpaceInPagingFiles": 5000000,
})

CONSUMERS_JSON = json.dumps([
    {"Name": "chrome", "Id": 1234, "WorkingSetMB": 512.5, "VirtualMB": 1024.0},
    {"Name": "python", "Id": 5678, "WorkingSetMB": 256.0, "VirtualMB": 800.0},
])


class TestDataclasses:
    def test_vm_info(self):
        v = VirtualMemoryInfo()
        assert v.total_visible_mb == 0

    def test_vm_event(self):
        e = VMEvent(action="get_status")
        assert e.success is True


class TestGetStatus:
    def test_success(self):
        vmm = VirtualMemoryManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = STATUS_JSON
        with patch("subprocess.run", return_value=mock_result):
            status = vmm.get_status()
        assert status["total_visible_mb"] == 16384
        assert status["free_physical_mb"] == 8192
        assert status["used_percent"] == 50.0

    def test_failure(self):
        vmm = VirtualMemoryManager()
        with patch("subprocess.run", side_effect=Exception("fail")):
            status = vmm.get_status()
        assert status["total_visible_mb"] == 0


class TestGetTopConsumers:
    def test_success(self):
        vmm = VirtualMemoryManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = CONSUMERS_JSON
        with patch("subprocess.run", return_value=mock_result):
            procs = vmm.get_top_consumers()
        assert len(procs) == 2
        assert procs[0]["name"] == "chrome"
        assert procs[0]["working_set_mb"] == 512.5

    def test_failure(self):
        vmm = VirtualMemoryManager()
        with patch("subprocess.run", side_effect=Exception("fail")):
            assert vmm.get_top_consumers() == []


class TestEventsStats:
    def test_events_empty(self):
        assert VirtualMemoryManager().get_events() == []

    def test_stats(self):
        assert VirtualMemoryManager().get_stats()["total_events"] == 0


class TestSingleton:
    def test_exists(self):
        assert isinstance(virtual_memory_manager, VirtualMemoryManager)
