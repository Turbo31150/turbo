"""Tests for src/font_manager.py — Windows font enumeration.

Covers: FontInfo, FontEvent, FontManager (_detect_type, list_fonts cache,
search, get_font, count_by_type, get_font_families, get_events, get_stats),
font_manager singleton.
All winreg calls are mocked.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.font_manager import FontInfo, FontEvent, FontManager, font_manager


MOCK_FONTS = [
    ("Arial (TrueType)", "arial.ttf", 1),
    ("Consolas (TrueType)", "consola.ttf", 1),
    ("Segoe UI Bold (TrueType)", "segoeuib.ttf", 1),
    ("Cascadia Code (OpenType)", "CascadiaCode.otf", 1),
]


def _mock_list_fonts(fm):
    """Inject mock font data bypassing winreg."""
    fonts = []
    for name, file, _ in MOCK_FONTS:
        fonts.append({
            "name": name,
            "file": file,
            "type": fm._detect_type(name, file),
        })
    fm._cache = fonts
    fm._cache_time = __import__("time").time()
    return fonts


# ===========================================================================
# Dataclasses
# ===========================================================================

class TestDataclasses:
    def test_font_info(self):
        f = FontInfo(name="Arial")
        assert f.file == ""
        assert f.font_type == ""

    def test_font_event(self):
        e = FontEvent(action="list_fonts")
        assert e.success is True
        assert e.timestamp > 0


# ===========================================================================
# FontManager — _detect_type
# ===========================================================================

class TestDetectType:
    def test_ttf(self):
        fm = FontManager()
        assert fm._detect_type("Arial", "arial.ttf") == "TrueType"

    def test_otf(self):
        fm = FontManager()
        assert fm._detect_type("Code", "code.otf") == "OpenType"

    def test_ttc(self):
        fm = FontManager()
        assert fm._detect_type("MS", "msgothic.ttc") == "TrueType Collection"

    def test_fon(self):
        fm = FontManager()
        assert fm._detect_type("Terminal", "term.fon") == "Raster"

    def test_name_truetype(self):
        fm = FontManager()
        assert fm._detect_type("Arial (TrueType)", "arial.dat") == "TrueType"

    def test_name_opentype(self):
        fm = FontManager()
        assert fm._detect_type("Code (OpenType)", "code.dat") == "OpenType"

    def test_unknown(self):
        fm = FontManager()
        assert fm._detect_type("Mystery", "mystery.xyz") == "unknown"


# ===========================================================================
# FontManager — list_fonts with cache
# ===========================================================================

class TestListFonts:
    def test_cache_hit(self):
        fm = FontManager()
        _mock_list_fonts(fm)
        # Should return cache without calling winreg
        fonts = fm.list_fonts(use_cache=True)
        assert len(fonts) == 4

    def test_cache_bypass(self):
        fm = FontManager()
        _mock_list_fonts(fm)
        # When use_cache=False, tries winreg (which we mock to fail)
        with patch("winreg.OpenKey", side_effect=OSError("mock")):
            fonts = fm.list_fonts(use_cache=False)
        assert fonts == []


# ===========================================================================
# FontManager — search & get_font
# ===========================================================================

class TestSearchGet:
    def test_search(self):
        fm = FontManager()
        _mock_list_fonts(fm)
        results = fm.search("arial")
        assert len(results) == 1
        assert "Arial" in results[0]["name"]

    def test_search_no_match(self):
        fm = FontManager()
        _mock_list_fonts(fm)
        results = fm.search("nonexistent")
        assert results == []

    def test_get_font(self):
        fm = FontManager()
        _mock_list_fonts(fm)
        font = fm.get_font("Arial (TrueType)")
        assert font is not None
        assert font["file"] == "arial.ttf"

    def test_get_font_not_found(self):
        fm = FontManager()
        _mock_list_fonts(fm)
        assert fm.get_font("Nope") is None


# ===========================================================================
# FontManager — count_by_type & families
# ===========================================================================

class TestCountFamilies:
    def test_count_by_type(self):
        fm = FontManager()
        _mock_list_fonts(fm)
        counts = fm.count_by_type()
        assert counts.get("TrueType", 0) >= 2
        assert counts.get("OpenType", 0) >= 1

    def test_font_families(self):
        fm = FontManager()
        _mock_list_fonts(fm)
        families = fm.get_font_families()
        assert isinstance(families, list)
        assert "Arial" in families
        assert "Consolas" in families


# ===========================================================================
# FontManager — events & stats
# ===========================================================================

class TestEventsStats:
    def test_events_empty(self):
        fm = FontManager()
        assert fm.get_events() == []

    def test_stats(self):
        fm = FontManager()
        _mock_list_fonts(fm)
        stats = fm.get_stats()
        assert stats["total_fonts"] == 4


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert font_manager is not None
        assert isinstance(font_manager, FontManager)
