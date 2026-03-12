"""Tests for src/theme_controller.py — Windows theme management.

Covers: ThemeEvent, ThemeController (get_theme, is_dark_mode,
_read_personalize, _get_accent_color, _get_wallpaper,
get_color_prevalence, get_events, get_stats),
theme_controller singleton. All winreg calls are mocked.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.theme_controller import (
    ThemeEvent, ThemeController, theme_controller,
)


# ===========================================================================
# Dataclass
# ===========================================================================

class TestDataclass:
    def test_theme_event(self):
        e = ThemeEvent(action="get_theme")
        assert e.success is True


# ===========================================================================
# ThemeController — get_theme (mocked winreg)
# ===========================================================================

class TestGetTheme:
    def test_dark_mode(self):
        tc = ThemeController()
        with patch.object(tc, "_read_personalize", side_effect=lambda v: {
            "AppsUseLightTheme": 0, "SystemUsesLightTheme": 0,
            "EnableTransparency": 1,
        }.get(v, -1)), \
             patch.object(tc, "_get_accent_color", return_value="#ff6600"), \
             patch.object(tc, "_get_wallpaper", return_value="/\wall.jpg"):
            theme = tc.get_theme()
        assert theme["dark_mode_apps"] is True
        assert theme["dark_mode_system"] is True
        assert theme["transparency"] is True
        assert theme["accent_color"] == "#ff6600"
        assert theme["wallpaper"] == "/\wall.jpg"

    def test_light_mode(self):
        tc = ThemeController()
        with patch.object(tc, "_read_personalize", return_value=1), \
             patch.object(tc, "_get_accent_color", return_value="#0078d4"), \
             patch.object(tc, "_get_wallpaper", return_value=""):
            theme = tc.get_theme()
        assert theme["dark_mode_apps"] is False


# ===========================================================================
# ThemeController — is_dark_mode
# ===========================================================================

class TestIsDarkMode:
    def test_dark(self):
        tc = ThemeController()
        with patch.object(tc, "_read_personalize", return_value=0):
            assert tc.is_dark_mode() is True

    def test_light(self):
        tc = ThemeController()
        with patch.object(tc, "_read_personalize", return_value=1):
            assert tc.is_dark_mode() is False


# ===========================================================================
# ThemeController — _read_personalize
# ===========================================================================

class TestReadPersonalize:
    def test_success(self):
        tc = ThemeController()
        mock_key = MagicMock()
        with patch("winreg.OpenKey", return_value=mock_key), \
             patch("winreg.QueryValueEx", return_value=(0, 4)), \
             patch("winreg.CloseKey"):
            val = tc._read_personalize("AppsUseLightTheme")
        assert val == 0

    def test_exception(self):
        tc = ThemeController()
        with patch("winreg.OpenKey", side_effect=OSError("not found")):
            val = tc._read_personalize("Nonexistent")
        assert val == -1


# ===========================================================================
# ThemeController — _get_accent_color
# ===========================================================================

class TestAccentColor:
    def test_success(self):
        tc = ThemeController()
        # ABGR: 0xFF0066FF → B=0x00, G=0x66, R=0xFF → #ff6600
        color_val = 0xFF006600  # just example
        mock_key = MagicMock()
        with patch("winreg.OpenKey", return_value=mock_key), \
             patch("winreg.QueryValueEx", return_value=(0xFFBB6633, 4)), \
             patch("winreg.CloseKey"):
            color = tc._get_accent_color()
        assert color.startswith("#")

    def test_fallback(self):
        tc = ThemeController()
        with patch("winreg.OpenKey", side_effect=OSError):
            color = tc._get_accent_color()
        assert color == "#0078d4"


# ===========================================================================
# ThemeController — events & stats
# ===========================================================================

class TestEventsStats:
    def test_events_empty(self):
        tc = ThemeController()
        assert tc.get_events() == []

    def test_stats(self):
        tc = ThemeController()
        with patch.object(tc, "get_theme", return_value={
            "dark_mode_apps": True, "accent_color": "#ff0000"
        }):
            stats = tc.get_stats()
        assert stats["dark_mode"] is True


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert theme_controller is not None
        assert isinstance(theme_controller, ThemeController)
