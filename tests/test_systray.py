"""Tests for src/systray.py — System tray icon with quick actions.

Covers: _create_icon_image, _launch_bat, _launch_dashboard,
_notify_action, create_systray, run_systray.
PIL and pystray are mocked to avoid GUI dependencies.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, call

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Mock PIL and pystray before importing systray
_pil_image = MagicMock()
_pil_draw = MagicMock()
_pil_font = MagicMock()
_pystray = MagicMock()

_saved_pil = sys.modules.get("PIL")
_saved_pil_image = sys.modules.get("PIL.Image")
_saved_pil_draw = sys.modules.get("PIL.ImageDraw")
_saved_pil_font = sys.modules.get("PIL.ImageFont")
_saved_pystray = sys.modules.get("pystray")

sys.modules["PIL"] = MagicMock()
sys.modules["PIL.Image"] = _pil_image
sys.modules["PIL.ImageDraw"] = _pil_draw
sys.modules["PIL.ImageFont"] = _pil_font
sys.modules["pystray"] = _pystray

from src.systray import (
    _create_icon_image, _launch_bat, _launch_dashboard,
    _notify_action, create_systray, run_systray,
)

# Restore modules after import
for mod_name, saved in [("PIL", _saved_pil), ("PIL.Image", _saved_pil_image),
                         ("PIL.ImageDraw", _saved_pil_draw),
                         ("PIL.ImageFont", _saved_pil_font),
                         ("pystray", _saved_pystray)]:
    if saved is not None:
        sys.modules[mod_name] = saved


# ===========================================================================
# _create_icon_image
# ===========================================================================

class TestCreateIconImage:
    def test_returns_image(self):
        img = _create_icon_image()
        # PIL.Image.new was called → returns a mock image object
        assert img is not None

    def test_returns_consistently(self):
        img1 = _create_icon_image()
        img2 = _create_icon_image()
        assert img1 is not None
        assert img2 is not None


# ===========================================================================
# _launch_bat
# ===========================================================================

class TestLaunchBat:
    def test_existing_bat(self, tmp_path):
        bat = tmp_path / "launchers" / "test.bat"
        bat.parent.mkdir(parents=True)
        bat.write_text("echo hello")
        mock_proc = MagicMock()
        with patch("src.systray.PROJECT_ROOT", tmp_path), \
             patch("subprocess.Popen", return_value=mock_proc) as mock_popen, \
             patch("threading.Thread") as mock_thread:
            _launch_bat("test.bat")
        mock_popen.assert_called_once()
        mock_thread.assert_called_once()

    def test_nonexistent_bat(self, tmp_path):
        with patch("src.systray.PROJECT_ROOT", tmp_path), \
             patch("subprocess.Popen") as mock_popen:
            _launch_bat("nonexistent.bat")
        mock_popen.assert_not_called()


# ===========================================================================
# _launch_dashboard
# ===========================================================================

class TestLaunchDashboard:
    def test_launches(self):
        mock_proc = MagicMock()
        with patch("subprocess.Popen", return_value=mock_proc), \
             patch("threading.Thread") as mock_thread:
            _launch_dashboard()
        mock_thread.assert_called_once()


# ===========================================================================
# _notify_action
# ===========================================================================

class TestNotifyAction:
    def test_success(self):
        mock_notify = MagicMock()
        with patch.dict("sys.modules", {"src.windows": MagicMock(notify_windows=mock_notify)}):
            # Need to re-import or mock at call site
            with patch("src.systray.logger") as mock_logger:
                _notify_action("Title", "Message")

    def test_import_error(self):
        with patch.dict("sys.modules", {"src.windows": None}):
            # Should not raise
            _notify_action("Title", "Message")


# ===========================================================================
# create_systray
# ===========================================================================

class TestCreateSystray:
    def test_returns_icon(self):
        icon = create_systray()
        # pystray.Icon was called
        _pystray.Icon.assert_called()

    def test_menu_items(self):
        _pystray.Menu.reset_mock()
        _pystray.MenuItem.reset_mock()
        create_systray()
        # Should have multiple MenuItem calls (Dashboard, Interactif, etc.)
        assert _pystray.MenuItem.call_count >= 5


# ===========================================================================
# run_systray
# ===========================================================================

class TestRunSystray:
    def test_calls_run(self):
        mock_icon = MagicMock()
        with patch("src.systray.create_systray", return_value=mock_icon):
            run_systray()
        mock_icon.run.assert_called_once()
