"""Tests for src/system_info_collector.py — Windows system information.

Covers: SystemProfile, SysInfoEvent, SystemInfoCollector (get_os_info,
get_cpu_info, get_bios_info, get_computer_info, get_full_profile,
get_events, get_stats), system_info_collector singleton.
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

from src.system_info_collector import (
    SystemProfile, SysInfoEvent, SystemInfoCollector, system_info_collector,
)


# ===========================================================================
# Dataclasses
# ===========================================================================

class TestSystemProfile:
    def test_defaults(self):
        p = SystemProfile()
        assert p.hostname == ""
        assert p.os_name == ""
        assert p.cpu == ""


class TestSysInfoEvent:
    def test_defaults(self):
        e = SysInfoEvent(action="get_os_info")
        assert e.success is True
        assert e.detail == ""
        assert e.timestamp > 0


# ===========================================================================
# SystemInfoCollector — get_os_info (mocked)
# ===========================================================================

OS_INFO_JSON = json.dumps({
    "Caption": "Microsoft Windows 11 Pro",
    "Version": "10.0.26300",
    "BuildNumber": "26300",
    "OSArchitecture": "64-bit",
    "SystemDirectory": "/\Windows/system32",
    "TotalVisibleMemorySize": 65536000,
    "FreePhysicalMemory": 32000000,
    "LastBootUpTime": "2026-03-07T08:00:00",
})


class TestGetOsInfo:
    def test_parses_info(self):
        sic = SystemInfoCollector()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = OS_INFO_JSON
        with patch("subprocess.run", return_value=mock_result):
            info = sic.get_os_info()
        assert info["caption"] == "Microsoft Windows 11 Pro"
        assert info["version"] == "10.0.26300"
        assert info["arch"] == "64-bit"
        assert info["total_ram_kb"] == 65536000

    def test_empty_output(self):
        sic = SystemInfoCollector()
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        with patch("subprocess.run", return_value=mock_result):
            assert sic.get_os_info() == {}

    def test_exception(self):
        sic = SystemInfoCollector()
        with patch("subprocess.run", side_effect=Exception("fail")):
            assert sic.get_os_info() == {}
        events = sic.get_events()
        assert events[-1]["success"] is False

    def test_boot_time_dict(self):
        sic = SystemInfoCollector()
        data = {"Caption": "Win11", "Version": "10.0", "BuildNumber": "26300",
                "OSArchitecture": "64-bit", "SystemDirectory": "/\Windows",
                "TotalVisibleMemorySize": 1000, "FreePhysicalMemory": 500,
                "LastBootUpTime": {"DateTime": "2026-03-07T08:00:00"}}
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(data)
        with patch("subprocess.run", return_value=mock_result):
            info = sic.get_os_info()
        assert "2026-03-07" in info["last_boot"]


# ===========================================================================
# SystemInfoCollector — get_cpu_info (mocked)
# ===========================================================================

CPU_INFO_JSON = json.dumps({
    "Name": "AMD Ryzen 5 3600",
    "NumberOfCores": 6,
    "NumberOfLogicalProcessors": 12,
    "MaxClockSpeed": 3600,
    "CurrentClockSpeed": 3500,
    "LoadPercentage": 25,
})


class TestGetCpuInfo:
    def test_parses_cpu(self):
        sic = SystemInfoCollector()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = CPU_INFO_JSON
        with patch("subprocess.run", return_value=mock_result):
            cpus = sic.get_cpu_info()
        assert len(cpus) == 1
        assert cpus[0]["name"] == "AMD Ryzen 5 3600"
        assert cpus[0]["cores"] == 6
        assert cpus[0]["logical_processors"] == 12

    def test_multiple_cpus(self):
        sic = SystemInfoCollector()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps([
            {"Name": "CPU1", "NumberOfCores": 4, "NumberOfLogicalProcessors": 8,
             "MaxClockSpeed": 3000, "CurrentClockSpeed": 2800, "LoadPercentage": 10},
            {"Name": "CPU2", "NumberOfCores": 4, "NumberOfLogicalProcessors": 8,
             "MaxClockSpeed": 3000, "CurrentClockSpeed": 2900, "LoadPercentage": 15},
        ])
        with patch("subprocess.run", return_value=mock_result):
            cpus = sic.get_cpu_info()
        assert len(cpus) == 2

    def test_empty(self):
        sic = SystemInfoCollector()
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        with patch("subprocess.run", return_value=mock_result):
            assert sic.get_cpu_info() == []

    def test_exception(self):
        sic = SystemInfoCollector()
        with patch("subprocess.run", side_effect=Exception("fail")):
            assert sic.get_cpu_info() == []


# ===========================================================================
# SystemInfoCollector — get_bios_info (mocked)
# ===========================================================================

BIOS_JSON = json.dumps({
    "Manufacturer": "American Megatrends",
    "Name": "BIOS Date: 01/01/2025",
    "Version": "ALASKA - 1072009",
    "SerialNumber": "SN12345",
    "SMBIOSBIOSVersion": "F10",
})


class TestGetBiosInfo:
    def test_parses_bios(self):
        sic = SystemInfoCollector()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = BIOS_JSON
        with patch("subprocess.run", return_value=mock_result):
            bios = sic.get_bios_info()
        assert bios["manufacturer"] == "American Megatrends"
        assert bios["serial"] == "SN12345"

    def test_empty(self):
        sic = SystemInfoCollector()
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        with patch("subprocess.run", return_value=mock_result):
            assert sic.get_bios_info() == {}

    def test_exception(self):
        sic = SystemInfoCollector()
        with patch("subprocess.run", side_effect=Exception("fail")):
            assert sic.get_bios_info() == {}


# ===========================================================================
# SystemInfoCollector — get_computer_info (mocked)
# ===========================================================================

COMPUTER_JSON = json.dumps({
    "Name": "DESKTOP-JARVIS",
    "Manufacturer": "Custom",
    "Model": "Gaming PC",
    "SystemType": "x64-based PC",
    "Domain": "WORKGROUP",
    "TotalPhysicalMemory": 68719476736,  # 64 GB
})


class TestGetComputerInfo:
    def test_parses_computer(self):
        sic = SystemInfoCollector()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = COMPUTER_JSON
        with patch("subprocess.run", return_value=mock_result):
            info = sic.get_computer_info()
        assert info["name"] == "DESKTOP-JARVIS"
        assert info["total_ram_gb"] == 64.0

    def test_empty(self):
        sic = SystemInfoCollector()
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        with patch("subprocess.run", return_value=mock_result):
            assert sic.get_computer_info() == {}

    def test_exception(self):
        sic = SystemInfoCollector()
        with patch("subprocess.run", side_effect=Exception("fail")):
            assert sic.get_computer_info() == {}

    def test_zero_ram(self):
        sic = SystemInfoCollector()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({
            "Name": "PC", "Manufacturer": "", "Model": "",
            "SystemType": "", "Domain": "", "TotalPhysicalMemory": 0,
        })
        with patch("subprocess.run", return_value=mock_result):
            info = sic.get_computer_info()
        assert info["total_ram_gb"] == 0


# ===========================================================================
# SystemInfoCollector — get_full_profile
# ===========================================================================

class TestFullProfile:
    def test_profile_structure(self):
        sic = SystemInfoCollector()
        with patch.object(sic, "get_os_info", return_value={"caption": "Win11"}), \
             patch.object(sic, "get_cpu_info", return_value=[{"name": "CPU"}]), \
             patch.object(sic, "get_bios_info", return_value={"manufacturer": "AMI"}), \
             patch.object(sic, "get_computer_info", return_value={"name": "PC"}):
            profile = sic.get_full_profile()
        assert profile["os"]["caption"] == "Win11"
        assert profile["cpu"][0]["name"] == "CPU"
        assert profile["bios"]["manufacturer"] == "AMI"
        assert profile["computer"]["name"] == "PC"


# ===========================================================================
# SystemInfoCollector — events / stats
# ===========================================================================

class TestEventsAndStats:
    def test_events_empty(self):
        sic = SystemInfoCollector()
        assert sic.get_events() == []

    def test_events_recorded(self):
        sic = SystemInfoCollector()
        sic._record("test", True, "detail")
        events = sic.get_events()
        assert len(events) == 1
        assert events[0]["action"] == "test"

    def test_stats(self):
        sic = SystemInfoCollector()
        sic._record("a", True)
        stats = sic.get_stats()
        assert stats["total_events"] == 1


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert system_info_collector is not None
        assert isinstance(system_info_collector, SystemInfoCollector)
