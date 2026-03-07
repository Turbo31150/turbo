"""Tests for src/audio_device_manager.py — Windows audio devices inventory.

Covers: AudioDevice, AudioEvent, AudioDeviceManager (list_devices, search,
count_by_status, get_events, get_stats), audio_device_manager singleton.
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

from src.audio_device_manager import (
    AudioDevice, AudioEvent, AudioDeviceManager, audio_device_manager,
)

DEVICES_JSON = json.dumps([
    {"Name": "NVIDIA High Definition Audio", "Manufacturer": "NVIDIA",
     "Status": "OK", "DeviceID": "HDAUDIO\\FUNC_01"},
    {"Name": "Realtek High Definition Audio", "Manufacturer": "Realtek",
     "Status": "OK", "DeviceID": "HDAUDIO\\FUNC_02"},
])


class TestDataclasses:
    def test_audio_device(self):
        d = AudioDevice(name="Test")
        assert d.manufacturer == ""
        assert d.status == ""

    def test_audio_event(self):
        e = AudioEvent(action="list")
        assert e.success is True


class TestListDevices:
    def test_success(self):
        adm = AudioDeviceManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = DEVICES_JSON
        with patch("subprocess.run", return_value=mock_result):
            devices = adm.list_devices()
        assert len(devices) == 2
        assert devices[0]["name"] == "NVIDIA High Definition Audio"
        assert devices[1]["manufacturer"] == "Realtek"

    def test_single_dict(self):
        adm = AudioDeviceManager()
        data = json.dumps({"Name": "Audio", "Manufacturer": "X",
                           "Status": "OK", "DeviceID": "Y"})
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = data
        with patch("subprocess.run", return_value=mock_result):
            assert len(adm.list_devices()) == 1

    def test_failure(self):
        adm = AudioDeviceManager()
        with patch("subprocess.run", side_effect=Exception("fail")):
            assert adm.list_devices() == []


class TestSearch:
    def test_search_by_name(self):
        adm = AudioDeviceManager()
        fake = [{"name": "NVIDIA Audio", "manufacturer": "NVIDIA"},
                {"name": "Realtek Audio", "manufacturer": "Realtek"}]
        with patch.object(adm, "list_devices", return_value=fake):
            assert len(adm.search("realtek")) == 1

    def test_search_by_manufacturer(self):
        adm = AudioDeviceManager()
        fake = [{"name": "HD Audio", "manufacturer": "NVIDIA"}]
        with patch.object(adm, "list_devices", return_value=fake):
            assert len(adm.search("nvidia")) == 1


class TestCountByStatus:
    def test_count(self):
        adm = AudioDeviceManager()
        fake = [{"status": "OK"}, {"status": "OK"}, {"status": "Error"}]
        with patch.object(adm, "list_devices", return_value=fake):
            counts = adm.count_by_status()
        assert counts["OK"] == 2
        assert counts["Error"] == 1


class TestEventsStats:
    def test_events_empty(self):
        assert AudioDeviceManager().get_events() == []

    def test_stats(self):
        assert AudioDeviceManager().get_stats()["total_events"] == 0


class TestSingleton:
    def test_exists(self):
        assert isinstance(audio_device_manager, AudioDeviceManager)
