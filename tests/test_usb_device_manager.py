"""Tests for src/usb_device_manager.py — Windows USB devices inventory.

Covers: USBDevice, USBEvent, USBDeviceManager (list_devices, search,
count_by_class, get_events, get_stats), usb_device_manager singleton.
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

from src.usb_device_manager import (
    USBDevice, USBEvent, USBDeviceManager, usb_device_manager,
)

DEVICES_JSON = json.dumps([
    {"Name": "USB Mass Storage Device", "DeviceID": "USB\\VID_0781",
     "Manufacturer": "SanDisk", "Status": "OK", "PNPClass": "USB"},
    {"Name": "USB Composite Device", "DeviceID": "USB\\VID_046D",
     "Manufacturer": "Logitech", "Status": "OK", "PNPClass": "USB"},
    {"Name": "USB Input Device", "DeviceID": "USB\\VID_046D",
     "Manufacturer": "Logitech", "Status": "OK", "PNPClass": "HIDClass"},
])


class TestDataclasses:
    def test_usb_device(self):
        d = USBDevice(name="Test")
        assert d.device_id == ""
        assert d.status == ""

    def test_usb_event(self):
        e = USBEvent(action="list")
        assert e.success is True


class TestListDevices:
    def test_success(self):
        um = USBDeviceManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = DEVICES_JSON
        with patch("subprocess.run", return_value=mock_result):
            devices = um.list_devices()
        assert len(devices) == 3
        assert devices[0]["name"] == "USB Mass Storage Device"
        assert devices[0]["manufacturer"] == "SanDisk"

    def test_single_dict(self):
        um = USBDeviceManager()
        data = json.dumps({"Name": "USB Hub", "DeviceID": "USB\\X",
                           "Manufacturer": "", "Status": "OK", "PNPClass": "USB"})
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = data
        with patch("subprocess.run", return_value=mock_result):
            assert len(um.list_devices()) == 1

    def test_failure(self):
        um = USBDeviceManager()
        with patch("subprocess.run", side_effect=Exception("fail")):
            assert um.list_devices() == []


class TestSearch:
    def test_search_by_name(self):
        um = USBDeviceManager()
        fake = [{"name": "USB Mass Storage", "manufacturer": "SanDisk"},
                {"name": "USB Input", "manufacturer": "Logitech"}]
        with patch.object(um, "list_devices", return_value=fake):
            assert len(um.search("storage")) == 1

    def test_search_by_manufacturer(self):
        um = USBDeviceManager()
        fake = [{"name": "USB Device", "manufacturer": "Logitech"}]
        with patch.object(um, "list_devices", return_value=fake):
            assert len(um.search("logitech")) == 1


class TestCountByClass:
    def test_count(self):
        um = USBDeviceManager()
        fake = [{"pnp_class": "USB"}, {"pnp_class": "USB"}, {"pnp_class": "HIDClass"}]
        with patch.object(um, "list_devices", return_value=fake):
            counts = um.count_by_class()
        assert counts["USB"] == 2
        assert counts["HIDClass"] == 1

    def test_null_class(self):
        um = USBDeviceManager()
        fake = [{"pnp_class": ""}, {"pnp_class": "USB"}]
        with patch.object(um, "list_devices", return_value=fake):
            counts = um.count_by_class()
        assert counts["Unknown"] == 1


class TestEventsStats:
    def test_events_empty(self):
        assert USBDeviceManager().get_events() == []

    def test_stats(self):
        assert USBDeviceManager().get_stats()["total_events"] == 0


class TestSingleton:
    def test_exists(self):
        assert isinstance(usb_device_manager, USBDeviceManager)
