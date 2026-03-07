"""Tests for src/window_manager.py — Windows window control and enumeration.

Covers: WindowInfo, WindowEvent, WindowManager (list_windows, find_window,
get_foreground, focus, minimize, maximize, restore, close, move_resize,
set_topmost, _record, get_events, get_stats), window_manager singleton.
Note: ctypes user32 calls are tested via real Win32 API (Windows test machine).
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.window_manager import (
    WindowInfo, WindowEvent, WindowManager, window_manager,
)


# ===========================================================================
# Dataclasses
# ===========================================================================

class TestWindowInfo:
    def test_defaults(self):
        w = WindowInfo(hwnd=123, title="Test")
        assert w.class_name == ""
        assert w.visible is True
        assert w.x == 0
        assert w.y == 0
        assert w.width == 0
        assert w.height == 0
        assert w.pid == 0


class TestWindowEvent:
    def test_defaults(self):
        e = WindowEvent(hwnd=123, title="Test", action="focus")
        assert e.success is True
        assert e.timestamp > 0


# ===========================================================================
# WindowManager — enumeration (real ctypes on Windows)
# ===========================================================================

class TestEnumeration:
    def test_list_windows(self):
        wm = WindowManager()
        windows = wm.list_windows()
        assert isinstance(windows, list)
        assert len(windows) >= 1  # At least 1 visible window on Windows
        w = windows[0]
        assert "hwnd" in w
        assert "title" in w
        assert "class_name" in w
        assert "visible" in w
        assert "width" in w
        assert "pid" in w

    def test_list_windows_visible_only(self):
        wm = WindowManager()
        visible = wm.list_windows(visible_only=True)
        all_windows = wm.list_windows(visible_only=False)
        assert len(all_windows) >= len(visible)

    def test_find_window(self):
        wm = WindowManager()
        # There should be at least one window; search for something common
        windows = wm.list_windows()
        if windows:
            title_part = windows[0]["title"][:5]
            found = wm.find_window(title_part)
            assert len(found) >= 1

    def test_find_window_no_match(self):
        wm = WindowManager()
        result = wm.find_window("XYZNONEXISTENT99999")
        assert result == []

    def test_get_foreground(self):
        wm = WindowManager()
        fg = wm.get_foreground()
        # May be None in headless CI, but on real Windows should exist
        if fg is not None:
            assert "hwnd" in fg
            assert "title" in fg


# ===========================================================================
# WindowManager — actions (mock user32 to avoid real window manipulation)
# ===========================================================================

class TestActions:
    def _make_wm(self):
        return WindowManager()

    def test_focus(self):
        wm = self._make_wm()
        with patch("src.window_manager.user32") as mock_u32:
            mock_u32.ShowWindow.return_value = 1
            mock_u32.SetForegroundWindow.return_value = 1
            mock_u32.GetWindowTextLengthW.return_value = 4
            mock_u32.GetWindowTextW.return_value = 0
            result = wm.focus(12345)
        assert result is True

    def test_minimize(self):
        wm = self._make_wm()
        with patch("src.window_manager.user32") as mock_u32:
            mock_u32.ShowWindow.return_value = 1
            mock_u32.GetWindowTextLengthW.return_value = 0
            result = wm.minimize(12345)
        assert result is True

    def test_maximize(self):
        wm = self._make_wm()
        with patch("src.window_manager.user32") as mock_u32:
            mock_u32.ShowWindow.return_value = 3
            mock_u32.GetWindowTextLengthW.return_value = 0
            result = wm.maximize(12345)
        assert result is True

    def test_restore(self):
        wm = self._make_wm()
        with patch("src.window_manager.user32") as mock_u32:
            mock_u32.ShowWindow.return_value = 1
            mock_u32.GetWindowTextLengthW.return_value = 0
            result = wm.restore(12345)
        assert result is True

    def test_close(self):
        wm = self._make_wm()
        with patch("src.window_manager.user32") as mock_u32:
            mock_u32.PostMessageW.return_value = 1
            mock_u32.GetWindowTextLengthW.return_value = 0
            result = wm.close(12345)
        assert result is True

    def test_move_resize(self):
        wm = self._make_wm()
        with patch("src.window_manager.user32") as mock_u32:
            mock_u32.MoveWindow.return_value = 1
            mock_u32.GetWindowTextLengthW.return_value = 0
            result = wm.move_resize(12345, 100, 100, 800, 600)
        assert result is True

    def test_set_topmost(self):
        wm = self._make_wm()
        with patch("src.window_manager.user32") as mock_u32:
            mock_u32.SetWindowPos.return_value = 1
            mock_u32.GetWindowTextLengthW.return_value = 0
            result = wm.set_topmost(12345, True)
        assert result is True

    def test_set_topmost_false(self):
        wm = self._make_wm()
        with patch("src.window_manager.user32") as mock_u32:
            mock_u32.SetWindowPos.return_value = 1
            mock_u32.GetWindowTextLengthW.return_value = 0
            result = wm.set_topmost(12345, False)
        assert result is True

    def test_focus_exception(self):
        wm = self._make_wm()
        with patch("src.window_manager.user32") as mock_u32:
            mock_u32.ShowWindow.side_effect = Exception("fail")
            result = wm.focus(12345)
        assert result is False

    def test_close_exception(self):
        wm = self._make_wm()
        with patch("src.window_manager.user32") as mock_u32:
            mock_u32.PostMessageW.side_effect = Exception("fail")
            result = wm.close(12345)
        assert result is False


# ===========================================================================
# WindowManager — events / stats
# ===========================================================================

class TestEventsAndStats:
    def test_events_empty(self):
        wm = WindowManager()
        assert wm.get_events() == []

    def test_events_recorded(self):
        wm = WindowManager()
        wm._events.append(WindowEvent(hwnd=1, title="T", action="focus"))
        events = wm.get_events()
        assert len(events) == 1
        assert events[0]["action"] == "focus"

    def test_events_limit(self):
        wm = WindowManager()
        for i in range(100):
            wm._events.append(WindowEvent(hwnd=i, title=f"W{i}", action="test"))
        events = wm.get_events(limit=10)
        assert len(events) == 10

    def test_stats(self):
        wm = WindowManager()
        wm._events.append(WindowEvent(hwnd=1, title="T", action="focus"))
        wm._events.append(WindowEvent(hwnd=2, title="T2", action="close"))
        with patch.object(wm, "list_windows", return_value=[{}, {}, {}]):
            stats = wm.get_stats()
        assert stats["open_windows"] == 3
        assert stats["total_events"] == 2
        assert "focus" in stats["actions"]
        assert "close" in stats["actions"]


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert window_manager is not None
        assert isinstance(window_manager, WindowManager)
