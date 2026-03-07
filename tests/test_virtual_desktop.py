"""Tests for src/virtual_desktop.py — Windows virtual desktops.

Covers: DesktopInfo, DesktopEvent, VirtualDesktopManager (get_desktop_count,
list_desktops, get_current_desktop, get_screen_info, get_events, get_stats),
virtual_desktop singleton. All subprocess/ctypes calls are mocked.
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

from src.virtual_desktop import (
    DesktopInfo, DesktopEvent, VirtualDesktopManager, virtual_desktop,
)

DESKTOPS_JSON = json.dumps([
    {"Id": "guid-1", "Name": "Desktop 1", "IsCurrentDesktop": True},
    {"Id": "guid-2", "Name": "Desktop 2", "IsCurrentDesktop": False},
])


# ===========================================================================
# Dataclasses
# ===========================================================================

class TestDataclasses:
    def test_desktop_info(self):
        d = DesktopInfo(index=0)
        assert d.name == ""
        assert d.is_current is False

    def test_desktop_event(self):
        e = DesktopEvent(action="list_desktops")
        assert e.success is True


# ===========================================================================
# VirtualDesktopManager — get_desktop_count
# ===========================================================================

class TestDesktopCount:
    def test_success(self):
        vdm = VirtualDesktopManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "3"
        with patch("subprocess.run", return_value=mock_result):
            count = vdm.get_desktop_count()
        assert count == 3

    def test_failure(self):
        vdm = VirtualDesktopManager()
        with patch("subprocess.run", side_effect=Exception("fail")):
            count = vdm.get_desktop_count()
        assert count == 1  # fallback


# ===========================================================================
# VirtualDesktopManager — list_desktops
# ===========================================================================

class TestListDesktops:
    def test_success(self):
        vdm = VirtualDesktopManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = DESKTOPS_JSON
        with patch("subprocess.run", return_value=mock_result):
            desktops = vdm.list_desktops()
        assert len(desktops) == 2
        assert desktops[0]["is_current"] is True

    def test_failure(self):
        vdm = VirtualDesktopManager()
        with patch("subprocess.run", side_effect=Exception("fail")):
            desktops = vdm.list_desktops()
        assert len(desktops) == 1
        assert desktops[0]["is_current"] is True  # fallback


# ===========================================================================
# VirtualDesktopManager — get_current_desktop
# ===========================================================================

class TestCurrentDesktop:
    def test_current(self):
        vdm = VirtualDesktopManager()
        fake = [
            {"index": 0, "is_current": False},
            {"index": 1, "is_current": True, "name": "Work"},
        ]
        with patch.object(vdm, "list_desktops", return_value=fake):
            current = vdm.get_current_desktop()
        assert current["index"] == 1

    def test_fallback(self):
        vdm = VirtualDesktopManager()
        with patch.object(vdm, "list_desktops", return_value=[]):
            current = vdm.get_current_desktop()
        assert current["index"] == 0


# ===========================================================================
# VirtualDesktopManager — get_screen_info
# ===========================================================================

class TestScreenInfo:
    def test_screen_info(self):
        vdm = VirtualDesktopManager()
        with patch("src.virtual_desktop.user32") as mock_user32:
            mock_user32.GetSystemMetrics.side_effect = lambda x: {
                0: 1920, 1: 1080, 78: 3840, 79: 1080, 80: 2
            }.get(x, 0)
            info = vdm.get_screen_info()
        assert info["width"] == 1920
        assert info["height"] == 1080
        assert info["monitors"] == 2


# ===========================================================================
# Events & stats
# ===========================================================================

class TestEventsStats:
    def test_events_empty(self):
        vdm = VirtualDesktopManager()
        assert vdm.get_events() == []

    def test_stats(self):
        vdm = VirtualDesktopManager()
        assert vdm.get_stats()["total_events"] == 0


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert virtual_desktop is not None
        assert isinstance(virtual_desktop, VirtualDesktopManager)
