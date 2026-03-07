"""Tests for src/wmi_explorer.py — Generic WMI/CIM query engine.

Covers: WMIResult, WMIEvent, WMIExplorer (query_class, list_common_classes,
get_system_summary, count_instances, get_events, get_stats),
wmi_explorer singleton.
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

from src.wmi_explorer import (
    WMIResult, WMIEvent, WMIExplorer, COMMON_CLASSES, wmi_explorer,
)


# ===========================================================================
# Dataclasses
# ===========================================================================

class TestDataclasses:
    def test_wmi_result(self):
        r = WMIResult(class_name="Win32_OS")
        assert r.instance_count == 0
        assert r.data == []

    def test_wmi_event(self):
        e = WMIEvent(action="query")
        assert e.success is True
        assert e.timestamp > 0


# ===========================================================================
# WMIExplorer — query_class (mocked)
# ===========================================================================

class TestQueryClass:
    def test_success_list(self):
        wmi = WMIExplorer()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps([
            {"Name": "CPU0", "Cores": 8},
            {"Name": "CPU1", "Cores": 4},
        ])
        with patch("subprocess.run", return_value=mock_result):
            data = wmi.query_class("Win32_Processor")
        assert len(data) == 2
        assert data[0]["Name"] == "CPU0"

    def test_success_single_dict(self):
        wmi = WMIExplorer()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({"Name": "Windows 11"})
        with patch("subprocess.run", return_value=mock_result):
            data = wmi.query_class("Win32_OperatingSystem")
        assert len(data) == 1

    def test_non_serializable_values(self):
        wmi = WMIExplorer()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({"Name": "test", "Complex": {"nested": True}})
        with patch("subprocess.run", return_value=mock_result):
            data = wmi.query_class("Win32_Test")
        assert len(data) == 1
        # Complex dict should be converted to str
        assert isinstance(data[0]["Complex"], str)

    def test_failure(self):
        wmi = WMIExplorer()
        with patch("subprocess.run", side_effect=Exception("fail")):
            data = wmi.query_class("Win32_Test")
        assert data == []

    def test_empty_class_name(self):
        wmi = WMIExplorer()
        data = wmi.query_class("!!!!")
        assert data == []

    def test_injection_sanitized(self):
        wmi = WMIExplorer()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "[]"
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            wmi.query_class("Win32_OS; rm -rf /")
        # Class name should be sanitized
        cmd = mock_run.call_args[0][0]
        ps_cmd = cmd[2]  # powershell -Command <cmd>
        assert ";" not in ps_cmd.split("Get-CimInstance")[1].split("|")[0]


# ===========================================================================
# WMIExplorer — list_common_classes
# ===========================================================================

class TestListClasses:
    def test_returns_list(self):
        wmi = WMIExplorer()
        classes = wmi.list_common_classes()
        assert isinstance(classes, list)
        assert "Win32_OperatingSystem" in classes
        assert len(classes) == len(COMMON_CLASSES)


# ===========================================================================
# WMIExplorer — get_system_summary
# ===========================================================================

class TestSystemSummary:
    def test_summary(self):
        wmi = WMIExplorer()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({"Name": "test"})
        with patch("subprocess.run", return_value=mock_result):
            summary = wmi.get_system_summary()
        assert len(summary) == 3  # OS, Computer, Processor


# ===========================================================================
# WMIExplorer — count_instances
# ===========================================================================

class TestCountInstances:
    def test_success(self):
        wmi = WMIExplorer()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "42\n"
        with patch("subprocess.run", return_value=mock_result):
            count = wmi.count_instances("Win32_Process")
        assert count == 42

    def test_failure(self):
        wmi = WMIExplorer()
        with patch("subprocess.run", side_effect=Exception("fail")):
            count = wmi.count_instances("Win32_Process")
        assert count == 0

    def test_empty_class(self):
        wmi = WMIExplorer()
        assert wmi.count_instances("$$$$") == 0


# ===========================================================================
# WMIExplorer — events & stats
# ===========================================================================

class TestEventsStats:
    def test_events_empty(self):
        wmi = WMIExplorer()
        assert wmi.get_events() == []

    def test_stats(self):
        wmi = WMIExplorer()
        stats = wmi.get_stats()
        assert stats["total_events"] == 0
        assert stats["common_classes"] == len(COMMON_CLASSES)

    def test_events_recorded(self):
        wmi = WMIExplorer()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "[]"
        with patch("subprocess.run", return_value=mock_result):
            wmi.query_class("Win32_OS")
        events = wmi.get_events()
        assert len(events) == 1
        assert events[0]["action"] == "query_class"


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert wmi_explorer is not None
        assert isinstance(wmi_explorer, WMIExplorer)
