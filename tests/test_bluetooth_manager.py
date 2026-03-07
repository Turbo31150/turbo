"""Tests for src/bluetooth_manager.py — Windows Bluetooth management.

Covers: BluetoothDevice, BluetoothEvent, BluetoothManager (list_devices,
get_device, get_status, count_by_status, get_events, get_stats),
bluetooth_manager singleton. All subprocess calls are mocked.
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

from src.bluetooth_manager import (
    BluetoothDevice, BluetoothEvent, BluetoothManager, bluetooth_manager,
)

DEVICES_JSON = json.dumps([
    {"FriendlyName": "Intel Bluetooth", "InstanceId": "USB\\VID_8087",
     "Status": "OK", "Class": "Bluetooth", "Manufacturer": "Intel"},
    {"FriendlyName": "AirPods Pro", "InstanceId": "BTHENUM\\123",
     "Status": "OK", "Class": "Bluetooth", "Manufacturer": "Apple"},
])

ADAPTER_JSON = json.dumps([
    {"Status": "OK"},
])


# ===========================================================================
# Dataclasses
# ===========================================================================

class TestDataclasses:
    def test_bluetooth_device(self):
        d = BluetoothDevice(name="Test")
        assert d.status == ""

    def test_bluetooth_event(self):
        e = BluetoothEvent(action="list_devices")
        assert e.success is True


# ===========================================================================
# BluetoothManager — list_devices
# ===========================================================================

class TestListDevices:
    def test_success(self):
        bm = BluetoothManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = DEVICES_JSON
        with patch("subprocess.run", return_value=mock_result):
            devices = bm.list_devices()
        assert len(devices) == 2
        assert devices[0]["name"] == "Intel Bluetooth"
        assert devices[1]["manufacturer"] == "Apple"

    def test_failure(self):
        bm = BluetoothManager()
        with patch("subprocess.run", side_effect=Exception("fail")):
            devices = bm.list_devices()
        assert devices == []


# ===========================================================================
# BluetoothManager — get_device (search)
# ===========================================================================

class TestGetDevice:
    def test_search(self):
        bm = BluetoothManager()
        fake = [{"name": "Intel Bluetooth"}, {"name": "AirPods Pro"}]
        with patch.object(bm, "list_devices", return_value=fake):
            results = bm.get_device("airpods")
        assert len(results) == 1

    def test_no_match(self):
        bm = BluetoothManager()
        with patch.object(bm, "list_devices", return_value=[]):
            results = bm.get_device("nope")
        assert results == []


# ===========================================================================
# BluetoothManager — get_status
# ===========================================================================

class TestGetStatus:
    def test_available(self):
        bm = BluetoothManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ADAPTER_JSON
        with patch("subprocess.run", return_value=mock_result):
            status = bm.get_status()
        assert status["available"] is True
        assert status["enabled"] is True

    def test_unavailable(self):
        bm = BluetoothManager()
        with patch("subprocess.run", side_effect=Exception("fail")):
            status = bm.get_status()
        assert status["available"] is False


# ===========================================================================
# BluetoothManager — count_by_status
# ===========================================================================

class TestCountByStatus:
    def test_count(self):
        bm = BluetoothManager()
        fake = [{"status": "OK"}, {"status": "OK"}, {"status": "Error"}]
        with patch.object(bm, "list_devices", return_value=fake):
            counts = bm.count_by_status()
        assert counts["OK"] == 2
        assert counts["Error"] == 1


# ===========================================================================
# Events & stats
# ===========================================================================

class TestEventsStats:
    def test_events_empty(self):
        bm = BluetoothManager()
        assert bm.get_events() == []

    def test_stats(self):
        bm = BluetoothManager()
        assert bm.get_stats()["total_events"] == 0


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert bluetooth_manager is not None
        assert isinstance(bluetooth_manager, BluetoothManager)
