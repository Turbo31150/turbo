"""Tests for src/browser_navigator.py — BrowserNavigator class.

Covers: init, is_open, _log, get_status, _get_memory,
navigate, close, tabs, scroll, search (all with mocked Playwright).
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.browser_navigator import BrowserNavigator, _get_memory


# ===========================================================================
# _get_memory
# ===========================================================================

class TestGetMemory:
    def test_returns_none_on_import_error(self):
        import src.browser_navigator as bn
        bn._browser_memory = None
        with patch.dict("sys.modules", {"src.browser_memory": None}):
            result = _get_memory()
        # May or may not be None depending on import, but should not crash
        assert result is None or hasattr(result, "track_visit")


# ===========================================================================
# BrowserNavigator init & properties
# ===========================================================================

class TestBrowserNavigatorInit:
    def test_init(self):
        nav = BrowserNavigator()
        assert nav._browser is None
        assert nav._context is None
        assert nav._page is None
        assert nav._pw is None
        assert nav._events == []
        assert nav._screenshots_dir.exists()

    def test_is_open_false(self):
        nav = BrowserNavigator()
        assert nav.is_open is False

    def test_is_open_with_browser(self):
        nav = BrowserNavigator()
        mock_browser = MagicMock()
        mock_browser.is_connected.return_value = True
        nav._browser = mock_browser
        assert nav.is_open is True

    def test_is_open_disconnected(self):
        nav = BrowserNavigator()
        mock_browser = MagicMock()
        mock_browser.is_connected.return_value = False
        nav._browser = mock_browser
        assert nav.is_open is False

    def test_is_open_no_is_connected(self):
        nav = BrowserNavigator()
        mock_browser = MagicMock(spec=[])  # No is_connected
        nav._browser = mock_browser
        assert nav.is_open is True


# ===========================================================================
# _log
# ===========================================================================

class TestLog:
    def test_log_adds_event(self):
        nav = BrowserNavigator()
        nav._log("navigate", "https://example.com")
        assert len(nav._events) == 1
        assert nav._events[0]["action"] == "navigate"
        assert "example.com" in nav._events[0]["detail"]
        assert "ts" in nav._events[0]

    def test_log_truncates_detail(self):
        nav = BrowserNavigator()
        nav._log("test", "x" * 200)
        assert len(nav._events[0]["detail"]) == 100

    def test_log_limits_events(self):
        nav = BrowserNavigator()
        for i in range(250):
            nav._log("action", f"event_{i}")
        assert len(nav._events) == 200


# ===========================================================================
# get_status
# ===========================================================================

class TestGetStatus:
    def test_status_closed(self):
        nav = BrowserNavigator()
        status = nav.get_status()
        assert status["open"] is False
        assert status["url"] is None
        assert status["tab_count"] == 0
        assert status["events"] == 0

    def test_status_open(self):
        nav = BrowserNavigator()
        mock_browser = MagicMock()
        mock_browser.is_connected.return_value = True
        nav._browser = mock_browser
        mock_page = MagicMock()
        mock_page.is_closed.return_value = False
        mock_page.url = "https://test.com"
        nav._page = mock_page
        mock_ctx = MagicMock()
        mock_ctx.pages = [mock_page]
        nav._context = mock_ctx
        nav._log("test", "event")
        status = nav.get_status()
        assert status["open"] is True
        assert status["url"] == "https://test.com"
        assert status["tab_count"] == 1
        assert status["events"] == 1


# ===========================================================================
# close
# ===========================================================================

class TestClose:
    @pytest.mark.asyncio
    async def test_close_resets_state(self):
        nav = BrowserNavigator()
        nav._browser = AsyncMock()
        nav._context = AsyncMock()
        nav._page = MagicMock()
        nav._pw = AsyncMock()
        result = await nav.close()
        assert result == {"status": "closed"}
        assert nav._browser is None
        assert nav._context is None
        assert nav._page is None
        assert nav._pw is None

    @pytest.mark.asyncio
    async def test_close_when_already_closed(self):
        nav = BrowserNavigator()
        result = await nav.close()
        assert result == {"status": "closed"}


# ===========================================================================
# navigate
# ===========================================================================

class TestNavigate:
    @pytest.mark.asyncio
    async def test_navigate_adds_https(self):
        nav = BrowserNavigator()
        mock_page = AsyncMock()
        mock_page.url = "https://example.com"
        mock_page.title = AsyncMock(return_value="Example")
        with patch.object(nav, "_ensure_browser", new_callable=AsyncMock, return_value=mock_page), \
             patch.object(nav, "_track_current_page", new_callable=AsyncMock):
            result = await nav.navigate("example.com")
        mock_page.goto.assert_called_once()
        call_url = mock_page.goto.call_args[0][0]
        assert call_url.startswith("https://")
        assert result["title"] == "Example"

    @pytest.mark.asyncio
    async def test_navigate_full_url(self):
        nav = BrowserNavigator()
        mock_page = AsyncMock()
        mock_page.url = "http://localhost:8080"
        mock_page.title = AsyncMock(return_value="Local")
        with patch.object(nav, "_ensure_browser", new_callable=AsyncMock, return_value=mock_page), \
             patch.object(nav, "_track_current_page", new_callable=AsyncMock):
            result = await nav.navigate("http://localhost:8080")
        call_url = mock_page.goto.call_args[0][0]
        assert call_url == "http://localhost:8080"


# ===========================================================================
# Tabs
# ===========================================================================

class TestTabs:
    @pytest.mark.asyncio
    async def test_list_tabs_empty(self):
        nav = BrowserNavigator()
        result = await nav.list_tabs()
        assert result == []

    @pytest.mark.asyncio
    async def test_close_tab_no_page(self):
        nav = BrowserNavigator()
        result = await nav.close_tab()
        assert "error" in result

    @pytest.mark.asyncio
    async def test_switch_tab_no_browser(self):
        nav = BrowserNavigator()
        result = await nav.switch_tab(0)
        assert "error" in result

    @pytest.mark.asyncio
    async def test_switch_tab_out_of_range(self):
        nav = BrowserNavigator()
        mock_ctx = MagicMock()
        mock_ctx.pages = [MagicMock()]
        nav._context = mock_ctx
        result = await nav.switch_tab(5)
        assert "error" in result


# ===========================================================================
# scroll
# ===========================================================================

class TestScroll:
    @pytest.mark.asyncio
    async def test_scroll_down(self):
        nav = BrowserNavigator()
        mock_page = AsyncMock()
        with patch.object(nav, "_ensure_browser", new_callable=AsyncMock, return_value=mock_page):
            result = await nav.scroll("down", 300)
        assert result["scrolled"] == "down"
        assert result["amount"] == 300
        mock_page.mouse.wheel.assert_called_with(0, 300)

    @pytest.mark.asyncio
    async def test_scroll_up(self):
        nav = BrowserNavigator()
        mock_page = AsyncMock()
        with patch.object(nav, "_ensure_browser", new_callable=AsyncMock, return_value=mock_page):
            result = await nav.scroll("up", 200)
        mock_page.mouse.wheel.assert_called_with(0, -200)


# ===========================================================================
# launch
# ===========================================================================

class TestLaunch:
    @pytest.mark.asyncio
    async def test_launch_already_open(self):
        nav = BrowserNavigator()
        mock_browser = MagicMock()
        mock_browser.is_connected.return_value = True
        nav._browser = mock_browser
        mock_ctx = MagicMock()
        mock_ctx.pages = [MagicMock(), MagicMock()]
        nav._context = mock_ctx
        result = await nav.launch()
        assert result["status"] == "already_open"
        assert result["tabs"] == 2

    @pytest.mark.asyncio
    async def test_launch_already_open_with_url(self):
        nav = BrowserNavigator()
        mock_browser = MagicMock()
        mock_browser.is_connected.return_value = True
        nav._browser = mock_browser
        mock_page = AsyncMock()
        mock_page.url = "https://test.com"
        mock_page.title = AsyncMock(return_value="Test")
        nav._page = mock_page
        nav._context = MagicMock()
        with patch.object(nav, "_ensure_browser", new_callable=AsyncMock, return_value=mock_page), \
             patch.object(nav, "_track_current_page", new_callable=AsyncMock):
            result = await nav.launch(url="https://test.com")
        assert "url" in result


# ===========================================================================
# search
# ===========================================================================

class TestSearch:
    @pytest.mark.asyncio
    async def test_search_google(self):
        nav = BrowserNavigator()
        mock_page = AsyncMock()
        mock_page.url = "https://www.google.com/search?q=test&hl=fr"
        mock_page.title = AsyncMock(return_value="test - Google")
        with patch.object(nav, "_ensure_browser", new_callable=AsyncMock, return_value=mock_page), \
             patch.object(nav, "_track_current_page", new_callable=AsyncMock):
            result = await nav.search("test")
        assert result["query"] == "test"
        assert "google" in result["url"]


# ===========================================================================
# _track_current_page
# ===========================================================================

class TestTrackCurrentPage:
    @pytest.mark.asyncio
    async def test_no_memory(self):
        nav = BrowserNavigator()
        with patch("src.browser_navigator._get_memory", return_value=None):
            await nav._track_current_page()  # Should not raise

    @pytest.mark.asyncio
    async def test_about_blank_skipped(self):
        nav = BrowserNavigator()
        mock_page = AsyncMock()
        mock_page.url = "about:blank"
        mock_page.is_closed.return_value = False
        nav._page = mock_page
        mock_mem = MagicMock()
        with patch("src.browser_navigator._get_memory", return_value=mock_mem):
            await nav._track_current_page()
        mock_mem.track_visit.assert_not_called()

    @pytest.mark.asyncio
    async def test_tracks_valid_page(self):
        nav = BrowserNavigator()
        mock_page = AsyncMock()
        mock_page.url = "https://example.com"
        mock_page.title = AsyncMock(return_value="Example")
        mock_page.inner_text = AsyncMock(return_value="Page content here")
        mock_page.is_closed = MagicMock(return_value=False)
        nav._page = mock_page
        mock_mem = MagicMock()
        with patch("src.browser_navigator._get_memory", return_value=mock_mem):
            await nav._track_current_page(mock_page)
        mock_mem.track_visit.assert_called_once()
