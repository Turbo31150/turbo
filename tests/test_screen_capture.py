"""Tests for src/screen_capture.py — Windows screenshot and region capture.

Covers: CaptureInfo, CaptureEvent, ScreenCapture (get_screen_size,
get_virtual_screen, get_monitor_count, capture_full, capture_region,
list_captures, get_capture, delete_capture, get_events, get_stats),
screen_capture singleton.
Note: ctypes GDI calls tested via mock for capture, real for screen metrics.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.screen_capture import (
    CaptureInfo, CaptureEvent, ScreenCapture, screen_capture,
)


# ===========================================================================
# Dataclasses
# ===========================================================================

class TestCaptureInfo:
    def test_defaults(self):
        c = CaptureInfo(capture_id="c1", filepath="/tmp/test.bmp",
                        width=1920, height=1080)
        assert c.region is None
        assert c.size_bytes == 0
        assert c.timestamp > 0


class TestCaptureEvent:
    def test_defaults(self):
        e = CaptureEvent(action="capture")
        assert e.capture_id == ""
        assert e.success is True
        assert e.detail == ""
        assert e.timestamp > 0


# ===========================================================================
# ScreenCapture — screen metrics (real ctypes)
# ===========================================================================

class TestScreenMetrics:
    def test_get_screen_size(self):
        sc = ScreenCapture()
        size = sc.get_screen_size()
        assert size["width"] > 0
        assert size["height"] > 0

    def test_get_virtual_screen(self):
        sc = ScreenCapture()
        vs = sc.get_virtual_screen()
        assert vs["width"] > 0
        assert vs["height"] > 0
        assert "x" in vs
        assert "y" in vs

    def test_get_monitor_count(self):
        sc = ScreenCapture()
        count = sc.get_monitor_count()
        assert count >= 1


# ===========================================================================
# ScreenCapture — capture (mocked GDI to avoid real screenshots)
# ===========================================================================

class TestCapture:
    def test_capture_full(self, tmp_path):
        sc = ScreenCapture(save_dir=str(tmp_path))
        with patch("src.screen_capture.user32") as mock_u32, \
             patch("src.screen_capture.gdi32") as mock_gdi:
            mock_u32.GetSystemMetrics.side_effect = lambda x: {0: 1920, 1: 1080}.get(x, 0)
            mock_u32.GetDC.return_value = 1
            mock_gdi.CreateCompatibleDC.return_value = 2
            mock_gdi.CreateCompatibleBitmap.return_value = 3
            mock_gdi.SelectObject.return_value = 4
            with patch.object(sc, "_save_bmp", return_value=5760054):
                info = sc.capture_full()
        assert info is not None
        assert info.width == 1920
        assert info.height == 1080
        assert info.size_bytes == 5760054

    def test_capture_region(self, tmp_path):
        sc = ScreenCapture(save_dir=str(tmp_path))
        with patch("src.screen_capture.user32") as mock_u32, \
             patch("src.screen_capture.gdi32") as mock_gdi:
            mock_u32.GetDC.return_value = 1
            mock_gdi.CreateCompatibleDC.return_value = 2
            mock_gdi.CreateCompatibleBitmap.return_value = 3
            mock_gdi.SelectObject.return_value = 4
            with patch.object(sc, "_save_bmp", return_value=100000):
                info = sc.capture_region(100, 100, 400, 300)
        assert info is not None
        assert info.width == 400
        assert info.height == 300
        assert info.region == (100, 100, 400, 300)

    def test_capture_exception(self, tmp_path):
        sc = ScreenCapture(save_dir=str(tmp_path))
        with patch("src.screen_capture.user32") as mock_u32:
            mock_u32.GetDC.side_effect = Exception("GDI error")
            mock_u32.GetSystemMetrics.side_effect = lambda x: {0: 1920, 1: 1080}.get(x, 0)
            info = sc.capture_full()
        assert info is None
        events = sc.get_events()
        assert events[-1]["success"] is False

    def test_capture_with_custom_filename(self, tmp_path):
        sc = ScreenCapture(save_dir=str(tmp_path))
        filepath = str(tmp_path / "custom.bmp")
        with patch("src.screen_capture.user32") as mock_u32, \
             patch("src.screen_capture.gdi32") as mock_gdi:
            mock_u32.GetDC.return_value = 1
            mock_gdi.CreateCompatibleDC.return_value = 2
            mock_gdi.CreateCompatibleBitmap.return_value = 3
            mock_gdi.SelectObject.return_value = 4
            with patch.object(sc, "_save_bmp", return_value=100):
                info = sc.capture_region(0, 0, 100, 100, filename=filepath)
        assert info is not None
        assert info.filepath == filepath


# ===========================================================================
# ScreenCapture — history / query
# ===========================================================================

class TestHistory:
    def test_list_captures_empty(self):
        sc = ScreenCapture()
        assert sc.list_captures() == []

    def test_list_captures_with_data(self):
        sc = ScreenCapture()
        sc._captures.append(CaptureInfo(
            capture_id="c1", filepath="/tmp/a.bmp",
            width=100, height=100, size_bytes=1000))
        result = sc.list_captures()
        assert len(result) == 1
        assert result[0]["id"] == "c1"

    def test_get_capture_found(self):
        sc = ScreenCapture()
        cap = CaptureInfo(capture_id="c1", filepath="/tmp/a.bmp",
                          width=100, height=100)
        sc._captures.append(cap)
        assert sc.get_capture("c1") is cap

    def test_get_capture_not_found(self):
        sc = ScreenCapture()
        assert sc.get_capture("nope") is None

    def test_delete_capture(self, tmp_path):
        sc = ScreenCapture()
        filepath = str(tmp_path / "test.bmp")
        Path(filepath).write_bytes(b"BMP")
        cap = CaptureInfo(capture_id="c1", filepath=filepath,
                          width=100, height=100)
        sc._captures.append(cap)
        assert sc.delete_capture("c1") is True
        assert not os.path.exists(filepath)
        assert sc.list_captures() == []

    def test_delete_capture_not_found(self):
        sc = ScreenCapture()
        assert sc.delete_capture("nope") is False

    def test_delete_capture_file_missing(self):
        sc = ScreenCapture()
        cap = CaptureInfo(capture_id="c1", filepath="/nonexistent/file.bmp",
                          width=100, height=100)
        sc._captures.append(cap)
        assert sc.delete_capture("c1") is True


# ===========================================================================
# ScreenCapture — events / stats
# ===========================================================================

class TestEventsAndStats:
    def test_events_empty(self):
        sc = ScreenCapture()
        assert sc.get_events() == []

    def test_events_recorded(self):
        sc = ScreenCapture()
        sc._record("capture", "c1", True, "1920x1080")
        events = sc.get_events()
        assert len(events) == 1
        assert events[0]["action"] == "capture"

    def test_stats(self):
        sc = ScreenCapture()
        sc._captures.append(CaptureInfo(
            capture_id="c1", filepath="/tmp/a.bmp",
            width=100, height=100, size_bytes=5000))
        stats = sc.get_stats()
        assert stats["total_captures"] == 1
        assert stats["total_bytes"] == 5000
        assert stats["screen_width"] > 0
        assert stats["monitor_count"] >= 1


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert screen_capture is not None
        assert isinstance(screen_capture, ScreenCapture)
