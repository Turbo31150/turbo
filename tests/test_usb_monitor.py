"""Tests for src/usb_monitor.py — Windows USB device detection and management.

Covers: USBDevice, USBEvent, USBMonitor (list_devices, _list_devices_simple,
get_device, snapshot_devices, detect_changes, count_by_status, get_events,
get_stats), usb_monitor singleton.
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

from src.usb_monitor import USBDevice, USBEvent, USBMonitor, usb_monitor


# ===========================================================================
# Dataclasses
# ===========================================================================

class TestUSBDevice:
    def test_defaults(self):
        d = USBDevice(name="USB Drive")
        assert d.device_id == ""
        assert d.status == ""
        assert d.device_type == ""
        assert d.manufacturer == ""


class TestUSBEvent:
    def test_defaults(self):
        e = USBEvent(action="list_devices")
        assert e.device_name == ""
        assert e.success is True
        assert e.timestamp > 0
        assert e.detail == ""


# ===========================================================================
# USBMonitor — list_devices (mocked)
# ===========================================================================

DEVICES_JSON = json.dumps([
    {"Name": "USB Keyboard", "DeviceID": "USB/VID_1234", "Status": "OK", "Manufacturer": "Logitech"},
    {"Name": "USB Mouse", "DeviceID": "USB/VID_5678", "Status": "OK", "Manufacturer": "Razer"},
])


class TestListDevices:
    def test_parses_devices(self):
        um = USBMonitor()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = DEVICES_JSON
        with patch("subprocess.run", return_value=mock_result):
            devices = um.list_devices()
        assert len(devices) == 2
        assert devices[0]["name"] == "USB Keyboard"
        assert devices[0]["device_id"] == "USB/VID_1234"
        assert devices[1]["manufacturer"] == "Razer"

    def test_single_device_dict(self):
        um = USBMonitor()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(
            {"Name": "Hub", "DeviceID": "USB/HUB1", "Status": "OK", "Manufacturer": ""})
        with patch("subprocess.run", return_value=mock_result):
            devices = um.list_devices()
        assert len(devices) == 1
        assert devices[0]["name"] == "Hub"

    def test_exception_falls_back_to_simple(self):
        um = USBMonitor()
        pnp_output = "Instance ID:    USB/VID_1234\nDevice Description:    Keyboard\nStatus:    Started\n"
        mock_pnp = MagicMock()
        mock_pnp.stdout = pnp_output
        with patch("subprocess.run", side_effect=[Exception("fail"), mock_pnp]):
            devices = um.list_devices()
        assert isinstance(devices, list)
        assert len(devices) == 1
        assert devices[0]["name"] == "Keyboard"

    def test_records_event(self):
        um = USBMonitor()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = DEVICES_JSON
        with patch("subprocess.run", return_value=mock_result):
            um.list_devices()
        events = um.get_events()
        assert len(events) >= 1
        assert events[0]["action"] == "list_devices"


# ===========================================================================
# USBMonitor — _list_devices_simple (mocked)
# ===========================================================================

class TestListDevicesSimple:
    def test_parses_pnputil_output(self):
        um = USBMonitor()
        pnp_output = (
            "Instance ID:    USB/VID_A\n"
            "Device Description:    Webcam\n"
            "Status:    Started\n"
            "\n"
            "Instance ID:    USB/VID_B\n"
            "Device Description:    Mic\n"
            "Status:    OK\n"
        )
        mock_result = MagicMock()
        mock_result.stdout = pnp_output
        with patch("subprocess.run", return_value=mock_result):
            devices = um._list_devices_simple()
        assert len(devices) == 2
        assert devices[0]["name"] == "Webcam"
        assert devices[1]["status"] == "OK"

    def test_exception_returns_empty(self):
        um = USBMonitor()
        with patch("subprocess.run", side_effect=Exception("fail")):
            devices = um._list_devices_simple()
        assert devices == []


# ===========================================================================
# USBMonitor — get_device
# ===========================================================================

class TestGetDevice:
    def test_search(self):
        um = USBMonitor()
        with patch.object(um, "list_devices", return_value=[
            {"name": "USB Keyboard", "device_id": "K1"},
            {"name": "USB Mouse", "device_id": "M1"},
        ]):
            results = um.get_device("keyboard")
        assert len(results) == 1
        assert results[0]["name"] == "USB Keyboard"

    def test_no_match(self):
        um = USBMonitor()
        with patch.object(um, "list_devices", return_value=[
            {"name": "USB Mouse"},
        ]):
            results = um.get_device("printer")
        assert results == []


# ===========================================================================
# USBMonitor — snapshot_devices & detect_changes
# ===========================================================================

class TestChangeDetection:
    def test_snapshot_devices(self):
        um = USBMonitor()
        with patch.object(um, "list_devices", return_value=[
            {"name": "Dev1", "device_id": "D1"},
            {"name": "Dev2", "device_id": "D2"},
        ]):
            snapshot = um.snapshot_devices()
        assert "D1" in snapshot
        assert "D2" in snapshot

    def test_detect_added(self):
        um = USBMonitor()
        # First snapshot: 1 device
        with patch.object(um, "list_devices", return_value=[
            {"name": "Dev1", "device_id": "D1"},
        ]):
            um.snapshot_devices()
        # Second call detects added device
        with patch.object(um, "list_devices", return_value=[
            {"name": "Dev1", "device_id": "D1"},
            {"name": "Dev2", "device_id": "D2"},
        ]):
            changes = um.detect_changes()
        assert len(changes["added"]) == 1
        assert changes["added"][0]["name"] == "Dev2"
        assert changes["removed"] == []

    def test_detect_removed(self):
        um = USBMonitor()
        with patch.object(um, "list_devices", return_value=[
            {"name": "Dev1", "device_id": "D1"},
            {"name": "Dev2", "device_id": "D2"},
        ]):
            um.snapshot_devices()
        with patch.object(um, "list_devices", return_value=[
            {"name": "Dev1", "device_id": "D1"},
        ]):
            changes = um.detect_changes()
        assert len(changes["removed"]) == 1
        assert changes["removed"][0]["name"] == "Dev2"
        assert changes["total_current"] == 1


# ===========================================================================
# USBMonitor — count_by_status
# ===========================================================================

class TestCountByStatus:
    def test_counts(self):
        um = USBMonitor()
        with patch.object(um, "list_devices", return_value=[
            {"name": "D1", "status": "OK"},
            {"name": "D2", "status": "OK"},
            {"name": "D3", "status": "Error"},
        ]):
            counts = um.count_by_status()
        assert counts["OK"] == 2
        assert counts["Error"] == 1


# ===========================================================================
# USBMonitor — events & stats
# ===========================================================================

class TestEventsAndStats:
    def test_events_empty(self):
        um = USBMonitor()
        assert um.get_events() == []

    def test_events_recorded(self):
        um = USBMonitor()
        um._record("test_action", "Dev1", True, "detail")
        events = um.get_events()
        assert len(events) == 1
        assert events[0]["action"] == "test_action"
        assert events[0]["device_name"] == "Dev1"

    def test_stats(self):
        um = USBMonitor()
        stats = um.get_stats()
        assert stats["total_events"] == 0
        assert stats["known_devices"] == 0


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert usb_monitor is not None
        assert isinstance(usb_monitor, USBMonitor)
