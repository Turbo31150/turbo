"""Tests for src/bios_settings.py — Windows BIOS/UEFI information reader.

Covers: BIOSInfo, BIOSEvent, BIOSSettingsReader (get_info,
get_secure_boot_status, get_events, get_stats), bios_settings singleton.
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

from src.bios_settings import (
    BIOSInfo, BIOSEvent, BIOSSettingsReader, bios_settings,
)

BIOS_JSON = json.dumps({
    "Manufacturer": "American Megatrends Inc.",
    "Name": "BIOS Date: 08/12/2024",
    "Version": "ALASKA - 1072009",
    "SerialNumber": "ABC123",
    "SMBIOSBIOSVersion": "F15",
    "SMBIOSMajorVersion": 3,
    "SMBIOSMinorVersion": 5,
    "ReleaseDate": "2024-08-12T00:00:00",
    "PrimaryBIOS": True,
})

SECUREBOOT_JSON = json.dumps({"secure_boot": True, "uefi": True})


class TestDataclasses:
    def test_bios_info(self):
        b = BIOSInfo()
        assert b.manufacturer == ""
        assert b.version == ""

    def test_bios_event(self):
        e = BIOSEvent(action="get_info")
        assert e.success is True


class TestGetInfo:
    def test_success(self):
        br = BIOSSettingsReader()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = BIOS_JSON
        with patch("subprocess.run", return_value=mock_result):
            info = br.get_info()
        assert info["manufacturer"] == "American Megatrends Inc."
        assert info["smbios_version"] == "3.5"
        assert info["primary_bios"] is True

    def test_release_date_dict(self):
        br = BIOSSettingsReader()
        data = json.dumps({"Manufacturer": "Test", "Name": "BIOS",
                           "Version": "1.0", "SerialNumber": "X",
                           "SMBIOSBIOSVersion": "V1", "SMBIOSMajorVersion": 2,
                           "SMBIOSMinorVersion": 0,
                           "ReleaseDate": {"DateTime": "2024-01-01"},
                           "PrimaryBIOS": False})
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = data
        with patch("subprocess.run", return_value=mock_result):
            info = br.get_info()
        assert "2024-01-01" in info["release_date"]

    def test_list_response(self):
        br = BIOSSettingsReader()
        data = json.dumps([{"Manufacturer": "Test", "Name": "BIOS",
                            "Version": "1.0", "SerialNumber": "X",
                            "SMBIOSBIOSVersion": "V1", "SMBIOSMajorVersion": 2,
                            "SMBIOSMinorVersion": 0, "ReleaseDate": "",
                            "PrimaryBIOS": True}])
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = data
        with patch("subprocess.run", return_value=mock_result):
            info = br.get_info()
        assert info["manufacturer"] == "Test"

    def test_failure(self):
        br = BIOSSettingsReader()
        with patch("subprocess.run", side_effect=Exception("fail")):
            info = br.get_info()
        assert info["manufacturer"] == ""


class TestGetSecureBootStatus:
    def test_success(self):
        br = BIOSSettingsReader()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = SECUREBOOT_JSON
        with patch("subprocess.run", return_value=mock_result):
            sb = br.get_secure_boot_status()
        assert sb["secure_boot"] is True
        assert sb["uefi"] is True

    def test_failure(self):
        br = BIOSSettingsReader()
        with patch("subprocess.run", side_effect=Exception("fail")):
            sb = br.get_secure_boot_status()
        assert sb["secure_boot"] is False


class TestEventsStats:
    def test_events_empty(self):
        assert BIOSSettingsReader().get_events() == []

    def test_stats(self):
        assert BIOSSettingsReader().get_stats()["total_events"] == 0


class TestSingleton:
    def test_exists(self):
        assert isinstance(bios_settings, BIOSSettingsReader)
