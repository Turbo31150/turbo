"""Tests for src/memory_diagnostics.py — Windows RAM hardware diagnostics.

Covers: RAMModule, MemDiagEvent, MemoryDiagnostics (list_modules,
get_summary, get_events, get_stats), memory_diagnostics singleton.
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

from src.memory_diagnostics import (
    RAMModule, MemDiagEvent, MemoryDiagnostics, memory_diagnostics,
)

GB = 1024 ** 3

MODULES_JSON = json.dumps([
    {"BankLabel": "BANK 0", "DeviceLocator": "DIMM1",
     "Capacity": 16 * GB, "Speed": 3200,
     "Manufacturer": "Samsung", "PartNumber": "M471A2K43",
     "SMBIOSMemoryType": 26},
    {"BankLabel": "BANK 1", "DeviceLocator": "DIMM2",
     "Capacity": 16 * GB, "Speed": 3200,
     "Manufacturer": "Samsung", "PartNumber": "M471A2K43",
     "SMBIOSMemoryType": 26},
])

SINGLE_MODULE_JSON = json.dumps(
    {"BankLabel": "BANK 0", "DeviceLocator": "DIMM1",
     "Capacity": 8 * GB, "Speed": 2666,
     "Manufacturer": "Kingston", "PartNumber": "KVR26",
     "SMBIOSMemoryType": 24}
)


class TestDataclasses:
    def test_ram_module(self):
        r = RAMModule(bank="BANK 0")
        assert r.capacity_gb == 0.0
        assert r.memory_type == ""

    def test_mem_diag_event(self):
        e = MemDiagEvent(action="list_modules")
        assert e.success is True


class TestListModules:
    def test_success_multiple(self):
        md = MemoryDiagnostics()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = MODULES_JSON
        with patch("subprocess.run", return_value=mock_result):
            modules = md.list_modules()
        assert len(modules) == 2
        assert modules[0]["bank"] == "BANK 0"
        assert modules[0]["capacity_gb"] == 16.0
        assert modules[0]["speed_mhz"] == 3200
        assert modules[0]["manufacturer"] == "Samsung"
        assert modules[0]["memory_type"] == "DDR4"

    def test_success_single_dict(self):
        md = MemoryDiagnostics()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = SINGLE_MODULE_JSON
        with patch("subprocess.run", return_value=mock_result):
            modules = md.list_modules()
        assert len(modules) == 1
        assert modules[0]["capacity_gb"] == 8.0
        assert modules[0]["memory_type"] == "DDR3"

    def test_null_capacity(self):
        md = MemoryDiagnostics()
        data = json.dumps([{"BankLabel": "BANK 0", "Capacity": None,
                            "Speed": None, "Manufacturer": None,
                            "PartNumber": None, "SMBIOSMemoryType": None,
                            "DeviceLocator": None}])
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = data
        with patch("subprocess.run", return_value=mock_result):
            modules = md.list_modules()
        assert modules[0]["capacity_gb"] == 0
        assert modules[0]["speed_mhz"] == 0

    def test_unknown_memory_type(self):
        md = MemoryDiagnostics()
        data = json.dumps([{"BankLabel": "BANK 0", "Capacity": 8 * GB,
                            "Speed": 2400, "Manufacturer": "X",
                            "PartNumber": "Y", "SMBIOSMemoryType": 99,
                            "DeviceLocator": "DIMM1"}])
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = data
        with patch("subprocess.run", return_value=mock_result):
            modules = md.list_modules()
        assert modules[0]["memory_type"] == "Type_99"

    def test_failure(self):
        md = MemoryDiagnostics()
        with patch("subprocess.run", side_effect=Exception("fail")):
            assert md.list_modules() == []


class TestGetSummary:
    def test_with_modules(self):
        md = MemoryDiagnostics()
        fake = [
            {"capacity_gb": 16.0, "speed_mhz": 3200, "memory_type": "DDR4"},
            {"capacity_gb": 16.0, "speed_mhz": 3200, "memory_type": "DDR4"},
        ]
        with patch.object(md, "list_modules", return_value=fake):
            s = md.get_summary()
        assert s["total_gb"] == 32.0
        assert s["module_count"] == 2
        assert s["max_speed_mhz"] == 3200
        assert s["memory_type"] == "DDR4"

    def test_empty(self):
        md = MemoryDiagnostics()
        with patch.object(md, "list_modules", return_value=[]):
            s = md.get_summary()
        assert s["total_gb"] == 0
        assert s["module_count"] == 0


class TestEventsStats:
    def test_events_empty(self):
        assert MemoryDiagnostics().get_events() == []

    def test_stats(self):
        assert MemoryDiagnostics().get_stats()["total_events"] == 0


class TestSingleton:
    def test_exists(self):
        assert isinstance(memory_diagnostics, MemoryDiagnostics)
