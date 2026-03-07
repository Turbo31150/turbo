"""Tests for src/locale_manager.py — Windows locale and regional settings.

Covers: LocaleInfo, LocaleEvent, LocaleManager (get_system_locale,
get_user_language, get_keyboard_layouts, get_timezone, get_date_format,
get_events, get_stats), locale_manager singleton.
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

from src.locale_manager import (
    LocaleInfo, LocaleEvent, LocaleManager, locale_manager,
)


# ===========================================================================
# Dataclasses
# ===========================================================================

class TestLocaleInfo:
    def test_defaults(self):
        li = LocaleInfo(name="fr-FR")
        assert li.display_name == ""
        assert li.language_tag == ""


class TestLocaleEvent:
    def test_defaults(self):
        e = LocaleEvent(action="get_system_locale")
        assert e.success is True
        assert e.detail == ""
        assert e.timestamp > 0


# ===========================================================================
# LocaleManager — get_system_locale (mocked)
# ===========================================================================

class TestGetSystemLocale:
    def test_parses_locale(self):
        lm = LocaleManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({"Name": "fr-FR", "DisplayName": "French (France)", "LCID": 1036})
        with patch("subprocess.run", return_value=mock_result):
            locale = lm.get_system_locale()
        assert locale["name"] == "fr-FR"
        assert locale["display_name"] == "French (France)"
        assert locale["lcid"] == 1036

    def test_failure_returns_unknown(self):
        lm = LocaleManager()
        with patch("subprocess.run", side_effect=Exception("fail")):
            locale = lm.get_system_locale()
        assert locale["name"] == "unknown"

    def test_records_event(self):
        lm = LocaleManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({"Name": "en-US", "DisplayName": "English", "LCID": 1033})
        with patch("subprocess.run", return_value=mock_result):
            lm.get_system_locale()
        events = lm.get_events()
        assert len(events) >= 1
        assert events[0]["action"] == "get_system_locale"


# ===========================================================================
# LocaleManager — get_user_language (mocked)
# ===========================================================================

class TestGetUserLanguage:
    def test_parses_languages(self):
        lm = LocaleManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps([
            {"LanguageTag": "fr-FR", "Autonym": "Francais", "EnglishName": "French"},
            {"LanguageTag": "en-US", "Autonym": "English", "EnglishName": "English"},
        ])
        with patch("subprocess.run", return_value=mock_result):
            langs = lm.get_user_language()
        assert len(langs) == 2
        assert langs[0]["language_tag"] == "fr-FR"

    def test_single_language_dict(self):
        lm = LocaleManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(
            {"LanguageTag": "en-US", "Autonym": "English", "EnglishName": "English"})
        with patch("subprocess.run", return_value=mock_result):
            langs = lm.get_user_language()
        assert len(langs) == 1

    def test_failure_returns_empty(self):
        lm = LocaleManager()
        with patch("subprocess.run", side_effect=Exception("fail")):
            langs = lm.get_user_language()
        assert langs == []


# ===========================================================================
# LocaleManager — get_keyboard_layouts (mocked)
# ===========================================================================

class TestGetKeyboardLayouts:
    def test_parses_layouts(self):
        lm = LocaleManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(["040C:0000040C", "0409:00000409"])
        with patch("subprocess.run", return_value=mock_result):
            layouts = lm.get_keyboard_layouts()
        assert len(layouts) == 2
        assert layouts[0]["layout_id"] == "040C:0000040C"

    def test_single_string(self):
        lm = LocaleManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps("040C:0000040C")
        with patch("subprocess.run", return_value=mock_result):
            layouts = lm.get_keyboard_layouts()
        assert len(layouts) == 1

    def test_failure_returns_empty(self):
        lm = LocaleManager()
        with patch("subprocess.run", side_effect=Exception("fail")):
            layouts = lm.get_keyboard_layouts()
        assert layouts == []


# ===========================================================================
# LocaleManager — get_timezone (mocked)
# ===========================================================================

class TestGetTimezone:
    def test_parses_timezone(self):
        lm = LocaleManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({
            "Id": "Romance Standard Time",
            "DisplayName": "(UTC+01:00) Brussels, Copenhagen",
            "BaseUtcOffset": {"Hours": 1, "Minutes": 0},
        })
        with patch("subprocess.run", return_value=mock_result):
            tz = lm.get_timezone()
        assert tz["id"] == "Romance Standard Time"
        assert tz["utc_offset_hours"] == 1

    def test_failure_returns_unknown(self):
        lm = LocaleManager()
        with patch("subprocess.run", side_effect=Exception("fail")):
            tz = lm.get_timezone()
        assert tz["id"] == "unknown"


# ===========================================================================
# LocaleManager — get_date_format (mocked)
# ===========================================================================

class TestGetDateFormat:
    def test_parses_format(self):
        lm = LocaleManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({
            "ShortDatePattern": "dd/MM/yyyy",
            "LongDatePattern": "dddd d MMMM yyyy",
            "ShortTimePattern": "HH:mm",
            "LongTimePattern": "HH:mm:ss",
        })
        with patch("subprocess.run", return_value=mock_result):
            fmt = lm.get_date_format()
        assert fmt["ShortDatePattern"] == "dd/MM/yyyy"

    def test_failure_returns_empty(self):
        lm = LocaleManager()
        with patch("subprocess.run", side_effect=Exception("fail")):
            fmt = lm.get_date_format()
        assert fmt == {}


# ===========================================================================
# LocaleManager — events & stats
# ===========================================================================

class TestEventsStats:
    def test_events_empty(self):
        lm = LocaleManager()
        assert lm.get_events() == []

    def test_stats(self):
        lm = LocaleManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({"Name": "fr-FR", "DisplayName": "French", "LCID": 1036})
        with patch("subprocess.run", return_value=mock_result):
            stats = lm.get_stats()
        assert stats["system_locale"] == "fr-FR"


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert locale_manager is not None
        assert isinstance(locale_manager, LocaleManager)
