"""Tests for src/pagefile_manager.py — Windows pagefile management.

Covers: PagefileInfo, PagefileEvent, PagefileManager (get_usage, get_settings,
get_virtual_memory, get_events, get_stats), pagefile_manager singleton.
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

from src.pagefile_manager import (
    PagefileInfo, PagefileEvent, PagefileManager, pagefile_manager,
)


USAGE_JSON = json.dumps([
    {"Name": "C:\\pagefile.sys", "AllocatedBaseSize": 8192,
     "CurrentUsage": 1024, "PeakUsage": 2048},
])

SETTINGS_JSON = json.dumps([
    {"Name": "C:\\pagefile.sys", "InitialSize": 4096, "MaximumSize": 8192},
])

VIRTUAL_MEM_JSON = json.dumps({
    "TotalVirtualMemorySize": 16777216,
    "FreeVirtualMemory": 8388608,
    "TotalVisibleMemorySize": 8388608,
    "FreePhysicalMemory": 4194304,
})


# ===========================================================================
# Dataclasses
# ===========================================================================

class TestDataclasses:
    def test_pagefile_info(self):
        p = PagefileInfo(name="C:\\pagefile.sys")
        assert p.allocated_mb == 0
        assert p.current_usage_mb == 0
        assert p.peak_usage_mb == 0

    def test_pagefile_event(self):
        e = PagefileEvent(action="get_usage")
        assert e.success is True


# ===========================================================================
# PagefileManager — get_usage
# ===========================================================================

class TestGetUsage:
    def test_success(self):
        pm = PagefileManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = USAGE_JSON
        with patch("subprocess.run", return_value=mock_result):
            pages = pm.get_usage()
        assert len(pages) == 1
        assert pages[0]["name"] == "C:\\pagefile.sys"
        assert pages[0]["allocated_mb"] == 8192
        assert pages[0]["current_usage_mb"] == 1024

    def test_single_object(self):
        pm = PagefileManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(
            {"Name": "D:\\pagefile.sys", "AllocatedBaseSize": 4096,
             "CurrentUsage": 512, "PeakUsage": 1024}
        )
        with patch("subprocess.run", return_value=mock_result):
            pages = pm.get_usage()
        assert len(pages) == 1
        assert pages[0]["name"] == "D:\\pagefile.sys"

    def test_failure(self):
        pm = PagefileManager()
        with patch("subprocess.run", side_effect=Exception("fail")):
            pages = pm.get_usage()
        assert pages == []

    def test_empty_stdout(self):
        pm = PagefileManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        with patch("subprocess.run", return_value=mock_result):
            pages = pm.get_usage()
        assert pages == []


# ===========================================================================
# PagefileManager — get_settings
# ===========================================================================

class TestGetSettings:
    def test_success(self):
        pm = PagefileManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = SETTINGS_JSON
        with patch("subprocess.run", return_value=mock_result):
            settings = pm.get_settings()
        assert len(settings) == 1
        assert settings[0]["initial_size_mb"] == 4096
        assert settings[0]["max_size_mb"] == 8192

    def test_failure(self):
        pm = PagefileManager()
        with patch("subprocess.run", side_effect=Exception("fail")):
            settings = pm.get_settings()
        assert settings == []


# ===========================================================================
# PagefileManager — get_virtual_memory
# ===========================================================================

class TestGetVirtualMemory:
    def test_success(self):
        pm = PagefileManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = VIRTUAL_MEM_JSON
        with patch("subprocess.run", return_value=mock_result):
            vm = pm.get_virtual_memory()
        assert vm["total_virtual_kb"] == 16777216
        assert vm["free_virtual_kb"] == 8388608
        assert vm["total_physical_kb"] == 8388608
        assert vm["free_physical_kb"] == 4194304

    def test_failure(self):
        pm = PagefileManager()
        with patch("subprocess.run", side_effect=Exception("fail")):
            vm = pm.get_virtual_memory()
        assert vm == {}


# ===========================================================================
# PagefileManager — events & stats
# ===========================================================================

class TestEventsStats:
    def test_events_empty(self):
        pm = PagefileManager()
        assert pm.get_events() == []

    def test_events_after_usage(self):
        pm = PagefileManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = USAGE_JSON
        with patch("subprocess.run", return_value=mock_result):
            pm.get_usage()
        events = pm.get_events()
        assert len(events) == 1
        assert events[0]["action"] == "get_usage"

    def test_stats(self):
        pm = PagefileManager()
        assert pm.get_stats()["total_events"] == 0


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert pagefile_manager is not None
        assert isinstance(pagefile_manager, PagefileManager)
