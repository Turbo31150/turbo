"""Tests for src/screen_resolution_manager.py — Windows display inventory.

Covers: DisplayInfo, ScreenEvent, ScreenResolutionManager (list_displays,
get_primary_resolution, search, get_events, get_stats),
screen_resolution_manager singleton.
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

from src.screen_resolution_manager import (
    DisplayInfo, ScreenEvent, ScreenResolutionManager, screen_resolution_manager,
)

DISPLAYS_JSON = json.dumps([
    {"Name": "NVIDIA GeForce GTX 1660 SUPER",
     "CurrentHorizontalResolution": 2560, "CurrentVerticalResolution": 1440,
     "CurrentRefreshRate": 144, "AdapterRAM": 6442450944,
     "VideoModeDescription": "2560 x 1440 x 32", "Status": "OK"},
    {"Name": "NVIDIA GeForce GTX 1650",
     "CurrentHorizontalResolution": 1920, "CurrentVerticalResolution": 1080,
     "CurrentRefreshRate": 60, "AdapterRAM": 4294967296,
     "VideoModeDescription": "1920 x 1080 x 32", "Status": "OK"},
])


class TestDataclasses:
    def test_display_info(self):
        d = DisplayInfo(name="Test")
        assert d.resolution == ""
        assert d.refresh_rate == 0

    def test_screen_event(self):
        e = ScreenEvent(action="list")
        assert e.success is True


class TestListDisplays:
    def test_success(self):
        srm = ScreenResolutionManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = DISPLAYS_JSON
        with patch("subprocess.run", return_value=mock_result):
            displays = srm.list_displays()
        assert len(displays) == 2
        assert displays[0]["resolution"] == "2560x1440"
        assert displays[0]["refresh_rate"] == 144
        assert displays[0]["adapter_ram_mb"] == 6144

    def test_null_resolution(self):
        srm = ScreenResolutionManager()
        data = json.dumps([{"Name": "Test", "CurrentHorizontalResolution": None,
                            "CurrentVerticalResolution": None,
                            "CurrentRefreshRate": None, "AdapterRAM": None,
                            "VideoModeDescription": "", "Status": ""}])
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = data
        with patch("subprocess.run", return_value=mock_result):
            displays = srm.list_displays()
        assert displays[0]["resolution"] == ""
        assert displays[0]["adapter_ram_mb"] == 0

    def test_single_dict(self):
        srm = ScreenResolutionManager()
        data = json.dumps({"Name": "GPU", "CurrentHorizontalResolution": 1920,
                           "CurrentVerticalResolution": 1080,
                           "CurrentRefreshRate": 60, "AdapterRAM": 0,
                           "VideoModeDescription": "", "Status": "OK"})
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = data
        with patch("subprocess.run", return_value=mock_result):
            assert len(srm.list_displays()) == 1

    def test_failure(self):
        srm = ScreenResolutionManager()
        with patch("subprocess.run", side_effect=Exception("fail")):
            assert srm.list_displays() == []


class TestGetPrimaryResolution:
    def test_with_displays(self):
        srm = ScreenResolutionManager()
        fake = [{"resolution": "2560x1440"}, {"resolution": "1920x1080"}]
        with patch.object(srm, "list_displays", return_value=fake):
            assert srm.get_primary_resolution() == "2560x1440"

    def test_empty(self):
        srm = ScreenResolutionManager()
        with patch.object(srm, "list_displays", return_value=[]):
            assert srm.get_primary_resolution() == "Unknown"


class TestSearch:
    def test_search(self):
        srm = ScreenResolutionManager()
        fake = [{"name": "NVIDIA GTX 1660"}, {"name": "NVIDIA GTX 1650"}]
        with patch.object(srm, "list_displays", return_value=fake):
            assert len(srm.search("1660")) == 1

    def test_search_no_match(self):
        srm = ScreenResolutionManager()
        fake = [{"name": "NVIDIA"}]
        with patch.object(srm, "list_displays", return_value=fake):
            assert len(srm.search("AMD")) == 0


class TestEventsStats:
    def test_events_empty(self):
        assert ScreenResolutionManager().get_events() == []

    def test_stats(self):
        assert ScreenResolutionManager().get_stats()["total_events"] == 0


class TestSingleton:
    def test_exists(self):
        assert isinstance(screen_resolution_manager, ScreenResolutionManager)
