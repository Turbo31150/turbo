"""Tests for src/driver_manager.py — Windows device drivers.

Covers: DriverInfo, DriverEvent, DriverManager (list_drivers, search,
filter_by_class, count_by_status, get_events, get_stats),
driver_manager singleton.
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

from src.driver_manager import (
    DriverInfo, DriverEvent, DriverManager, driver_manager,
)

DRIVERS_JSON = json.dumps([
    {"DeviceName": "NVIDIA GeForce GTX 1660", "Manufacturer": "NVIDIA",
     "DriverVersion": "31.0.15", "Status": "OK", "DeviceClass": "Display"},
    {"DeviceName": "Intel Ethernet", "Manufacturer": "Intel",
     "DriverVersion": "12.19", "Status": "OK", "DeviceClass": "Net"},
    {"DeviceName": None, "Manufacturer": "Unknown",
     "DriverVersion": "1.0", "Status": "OK", "DeviceClass": "System"},
])


class TestDataclasses:
    def test_driver_info(self):
        d = DriverInfo(name="Test")
        assert d.vendor == ""

    def test_driver_event(self):
        e = DriverEvent(action="list_drivers")
        assert e.success is True


class TestListDrivers:
    def test_success(self):
        dm = DriverManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = DRIVERS_JSON
        with patch("subprocess.run", return_value=mock_result):
            drivers = dm.list_drivers()
        # Null DeviceName is skipped
        assert len(drivers) == 2
        assert drivers[0]["name"] == "NVIDIA GeForce GTX 1660"

    def test_failure(self):
        dm = DriverManager()
        with patch("subprocess.run", side_effect=Exception("fail")):
            assert dm.list_drivers() == []


class TestSearch:
    def test_search_by_name(self):
        dm = DriverManager()
        fake = [{"name": "NVIDIA GeForce", "vendor": "NVIDIA"},
                {"name": "Intel Ethernet", "vendor": "Intel"}]
        with patch.object(dm, "list_drivers", return_value=fake):
            assert len(dm.search("nvidia")) == 1

    def test_search_by_vendor(self):
        dm = DriverManager()
        fake = [{"name": "Audio", "vendor": "Realtek"}]
        with patch.object(dm, "list_drivers", return_value=fake):
            assert len(dm.search("realtek")) == 1


class TestFilter:
    def test_filter_by_class(self):
        dm = DriverManager()
        fake = [{"device_class": "Display"}, {"device_class": "Net"}]
        with patch.object(dm, "list_drivers", return_value=fake):
            assert len(dm.filter_by_class("display")) == 1

    def test_count_by_status(self):
        dm = DriverManager()
        fake = [{"status": "OK"}, {"status": "OK"}, {"status": "Error"}]
        with patch.object(dm, "list_drivers", return_value=fake):
            counts = dm.count_by_status()
        assert counts["OK"] == 2
        assert counts["Error"] == 1


class TestEventsStats:
    def test_events_empty(self):
        assert DriverManager().get_events() == []

    def test_stats(self):
        assert DriverManager().get_stats()["total_events"] == 0


class TestSingleton:
    def test_exists(self):
        assert isinstance(driver_manager, DriverManager)
