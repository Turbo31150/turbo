"""Tests for src/display_manager.py — Windows display and monitor management.

Covers: DisplayInfo, DisplayEvent, ORIENTATIONS, DisplayManager (_record,
get_events, get_dpi, get_screen_size, get_virtual_screen, get_monitor_count),
display_manager singleton.
Note: ctypes user32 calls are tested via mock where needed.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.display_manager import (
    DisplayInfo, DisplayEvent, ORIENTATIONS, DisplayManager, display_manager,
)


# ===========================================================================
# Dataclasses & Constants
# ===========================================================================

class TestDisplayInfo:
    def test_defaults(self):
        d = DisplayInfo(device_name="DISPLAY1", width=1920, height=1080,
                        refresh_rate=60, bits_per_pixel=32)
        assert d.orientation == "landscape"
        assert d.is_primary is False
        assert d.x == 0


class TestDisplayEvent:
    def test_defaults(self):
        e = DisplayEvent(action="resolution_change")
        assert e.device == ""
        assert e.success is True
        assert e.timestamp > 0


class TestOrientations:
    def test_values(self):
        assert ORIENTATIONS[0] == "landscape"
        assert ORIENTATIONS[1] == "portrait"
        assert ORIENTATIONS[2] == "landscape_flipped"
        assert ORIENTATIONS[3] == "portrait_flipped"


# ===========================================================================
# DisplayManager — screen metrics (real ctypes, should work on Windows)
# ===========================================================================

class TestScreenMetrics:
    def test_get_screen_size(self):
        dm = DisplayManager()
        size = dm.get_screen_size()
        assert "width" in size
        assert "height" in size
        assert size["width"] > 0
        assert size["height"] > 0

    def test_get_virtual_screen(self):
        dm = DisplayManager()
        vs = dm.get_virtual_screen()
        assert "width" in vs
        assert "height" in vs
        assert vs["width"] > 0

    def test_get_monitor_count(self):
        dm = DisplayManager()
        count = dm.get_monitor_count()
        assert count >= 1

    def test_get_dpi(self):
        dm = DisplayManager()
        dpi = dm.get_dpi()
        assert "dpi_x" in dpi
        assert "scale" in dpi
        assert dpi["dpi_x"] >= 96


# ===========================================================================
# DisplayManager — events
# ===========================================================================

class TestEvents:
    def test_events_empty(self):
        dm = DisplayManager()
        assert dm.get_events() == []

    def test_record_event(self):
        dm = DisplayManager()
        dm._record("test_action", "DISPLAY1", True, "detail")
        events = dm.get_events()
        assert len(events) == 1
        assert events[0]["action"] == "test_action"
        assert events[0]["device"] == "DISPLAY1"

    def test_list_displays(self):
        dm = DisplayManager()
        displays = dm.list_displays()
        assert isinstance(displays, list)
        # On a real Windows machine, there should be at least 1
        assert len(displays) >= 1
        assert "width" in displays[0]
        assert "height" in displays[0]

    def test_get_primary(self):
        dm = DisplayManager()
        primary = dm.get_primary()
        assert primary["width"] > 0
        assert primary["height"] > 0


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert display_manager is not None
        assert isinstance(display_manager, DisplayManager)
