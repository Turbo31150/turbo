"""Tests for src/commands_browser.py — Browser voice commands structure & execution.

Covers: BrowserVoiceCommand structure, BROWSER_COMMANDS integrity,
execute_browser_command routing, helper functions.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.commands_browser import (
    BROWSER_COMMANDS,
    BrowserVoiceCommand,
    execute_browser_command,
)


# ===========================================================================
# 1. BrowserVoiceCommand dataclass
# ===========================================================================

class TestBrowserVoiceCommand:
    def test_basic_creation(self):
        cmd = BrowserVoiceCommand("test", "Test command", ["test trigger"])
        assert cmd.name == "test"
        assert cmd.description == "Test command"
        assert cmd.triggers == ["test trigger"]
        assert cmd.params == []

    def test_with_params(self):
        cmd = BrowserVoiceCommand("test", "Test", ["test {url}"], ["url"])
        assert cmd.params == ["url"]


# ===========================================================================
# 2. BROWSER_COMMANDS list integrity
# ===========================================================================

class TestBrowserCommandsList:
    def test_is_list(self):
        assert isinstance(BROWSER_COMMANDS, list)

    def test_not_empty(self):
        assert len(BROWSER_COMMANDS) >= 20

    def test_all_have_name(self):
        for cmd in BROWSER_COMMANDS:
            assert cmd.name, f"Command with empty name: {cmd}"

    def test_all_names_unique(self):
        names = [cmd.name for cmd in BROWSER_COMMANDS]
        assert len(set(names)) == len(names), "Duplicate command names found"

    def test_all_have_description(self):
        for cmd in BROWSER_COMMANDS:
            assert cmd.description, f"Command {cmd.name} has no description"

    def test_all_have_triggers(self):
        for cmd in BROWSER_COMMANDS:
            assert cmd.triggers, f"Command {cmd.name} has no triggers"
            assert all(isinstance(t, str) for t in cmd.triggers)

    def test_params_is_list(self):
        for cmd in BROWSER_COMMANDS:
            assert isinstance(cmd.params, list)

    def test_all_names_prefixed(self):
        for cmd in BROWSER_COMMANDS:
            assert cmd.name.startswith("browser_"), (
                f"Command {cmd.name} should start with 'browser_'"
            )


class TestCommandGroups:
    def test_navigation_commands_exist(self):
        names = {c.name for c in BROWSER_COMMANDS}
        for expected in ["browser_open", "browser_navigate", "browser_back",
                         "browser_forward", "browser_reload"]:
            assert expected in names, f"Missing navigation command: {expected}"

    def test_tab_commands_exist(self):
        names = {c.name for c in BROWSER_COMMANDS}
        for expected in ["browser_close_tab", "browser_new_tab", "browser_list_tabs"]:
            assert expected in names, f"Missing tab command: {expected}"

    def test_interaction_commands_exist(self):
        names = {c.name for c in BROWSER_COMMANDS}
        for expected in ["browser_click", "browser_scroll_down", "browser_scroll_up",
                         "browser_search", "browser_read"]:
            assert expected in names, f"Missing interaction command: {expected}"

    def test_memory_commands_exist(self):
        names = {c.name for c in BROWSER_COMMANDS}
        for expected in ["browser_bookmark", "browser_bookmarks_list", "browser_history",
                         "browser_search_history", "browser_landmarks", "browser_summarize",
                         "browser_save_session", "browser_restore_session"]:
            assert expected in names, f"Missing memory command: {expected}"

    def test_parameterized_commands_have_placeholders(self):
        for cmd in BROWSER_COMMANDS:
            for param in cmd.params:
                placeholder = "{" + param + "}"
                in_triggers = any(placeholder in t for t in cmd.triggers)
                assert in_triggers, (
                    f"Command {cmd.name} has param '{param}' but no {placeholder} in triggers"
                )


# ===========================================================================
# 3. execute_browser_command
# ===========================================================================

class TestExecuteBrowserCommand:
    @pytest.mark.asyncio
    async def test_unknown_command_returns_error(self):
        result = await execute_browser_command("browser_nonexistent")
        assert "error" in result
        assert "Unknown" in result["error"]

    @pytest.mark.asyncio
    async def test_open_command_routes_to_launch(self):
        mock_nav = MagicMock()
        mock_nav.launch = AsyncMock(return_value={"launched": True})
        with patch("src.browser_navigator.browser_nav", mock_nav):
            result = await execute_browser_command("browser_open")
        assert result["status"] == "ok"
        mock_nav.launch.assert_called_once()

    @pytest.mark.asyncio
    async def test_navigate_passes_site_param(self):
        mock_nav = MagicMock()
        mock_nav.navigate = AsyncMock(return_value={"url": "https://google.com"})
        with patch("src.browser_navigator.browser_nav", mock_nav):
            result = await execute_browser_command("browser_navigate", {"site": "https://google.com"})
        assert result["status"] == "ok"
        mock_nav.navigate.assert_called_once_with("https://google.com")

    @pytest.mark.asyncio
    async def test_scroll_down_calls_scroll(self):
        mock_nav = MagicMock()
        mock_nav.scroll = AsyncMock(return_value={"scrolled": "down"})
        with patch("src.browser_navigator.browser_nav", mock_nav):
            result = await execute_browser_command("browser_scroll_down")
        mock_nav.scroll.assert_called_once_with("down")

    @pytest.mark.asyncio
    async def test_scroll_up_calls_scroll(self):
        mock_nav = MagicMock()
        mock_nav.scroll = AsyncMock(return_value={"scrolled": "up"})
        with patch("src.browser_navigator.browser_nav", mock_nav):
            result = await execute_browser_command("browser_scroll_up")
        mock_nav.scroll.assert_called_once_with("up")

    @pytest.mark.asyncio
    async def test_click_passes_text_param(self):
        mock_nav = MagicMock()
        mock_nav.click_text = AsyncMock(return_value={"clicked": True})
        with patch("src.browser_navigator.browser_nav", mock_nav):
            result = await execute_browser_command("browser_click", {"text": "Submit"})
        mock_nav.click_text.assert_called_once_with("Submit")

    @pytest.mark.asyncio
    async def test_search_passes_query(self):
        mock_nav = MagicMock()
        mock_nav.search = AsyncMock(return_value={"searched": True})
        with patch("src.browser_navigator.browser_nav", mock_nav):
            result = await execute_browser_command("browser_search", {"query": "python"})
        mock_nav.search.assert_called_once_with("python")

    @pytest.mark.asyncio
    async def test_handler_exception_returns_error(self):
        mock_nav = MagicMock()
        mock_nav.launch = AsyncMock(side_effect=RuntimeError("Connection failed"))
        with patch("src.browser_navigator.browser_nav", mock_nav):
            result = await execute_browser_command("browser_open")
        assert result["status"] == "error"
        assert "Connection failed" in result["error"]

    @pytest.mark.asyncio
    async def test_empty_params_default(self):
        mock_nav = MagicMock()
        mock_nav.navigate = AsyncMock(return_value={})
        with patch("src.browser_navigator.browser_nav", mock_nav):
            result = await execute_browser_command("browser_navigate")
        mock_nav.navigate.assert_called_once_with("")

    @pytest.mark.asyncio
    async def test_bookmark_without_tags(self):
        mock_nav = MagicMock()
        mock_nav.bookmark_current = AsyncMock(return_value={"bookmarked": True})
        with patch("src.browser_navigator.browser_nav", mock_nav):
            result = await execute_browser_command("browser_bookmark")
        mock_nav.bookmark_current.assert_called_once_with(tags=None, notes="")


# ===========================================================================
# 4. Helper functions
# ===========================================================================

class TestHelperFunctions:
    @pytest.mark.asyncio
    async def test_format_bookmarks_empty(self):
        from src.commands_browser import _format_bookmarks
        mock_mem = MagicMock()
        mock_mem.get_bookmarks.return_value = []
        with patch("src.browser_memory.browser_memory", mock_mem):
            result = await _format_bookmarks()
        assert "Aucun" in result["message"]

    @pytest.mark.asyncio
    async def test_format_bookmarks_with_data(self):
        from src.commands_browser import _format_bookmarks
        mock_mem = MagicMock()
        mock_mem.get_bookmarks.return_value = [
            {"title": "Python", "domain": "python.org", "url": "https://python.org"},
        ]
        with patch("src.browser_memory.browser_memory", mock_mem):
            result = await _format_bookmarks()
        assert result["count"] == 1
        assert "Python" in result["message"]

    @pytest.mark.asyncio
    async def test_format_history_empty(self):
        from src.commands_browser import _format_history
        mock_mem = MagicMock()
        mock_mem.recent_pages.return_value = []
        with patch("src.browser_memory.browser_memory", mock_mem):
            result = await _format_history()
        assert "Aucune" in result["message"]

    @pytest.mark.asyncio
    async def test_format_most_visited_empty(self):
        from src.commands_browser import _format_most_visited
        mock_mem = MagicMock()
        mock_mem.most_visited.return_value = []
        with patch("src.browser_memory.browser_memory", mock_mem):
            result = await _format_most_visited()
        assert "Aucune" in result["message"]

    @pytest.mark.asyncio
    async def test_add_note_no_page_open(self):
        from src.commands_browser import _add_note_to_current
        mock_nav = MagicMock()
        mock_nav._page = None
        with patch("src.browser_navigator.browser_nav", mock_nav):
            result = await _add_note_to_current("test note")
        assert "error" in result


# ===========================================================================
# 5. All commands have matching handlers
# ===========================================================================

class TestAllCommandsHaveHandlers:
    @pytest.mark.asyncio
    async def test_all_commands_have_handler(self):
        """Every BROWSER_COMMANDS entry should have a handler in execute_browser_command."""
        mock_nav = MagicMock()
        for attr in ["launch", "navigate", "go_back", "go_forward", "reload",
                      "close_tab", "new_tab", "list_tabs", "click_text", "scroll",
                      "search", "fill_field", "read_page", "screenshot_page",
                      "move_to_screen", "fullscreen", "bookmark_current",
                      "search_history", "goto_remembered", "get_page_landmarks_voice",
                      "scroll_to_landmark", "summarize_page", "save_tab_session",
                      "restore_tab_session"]:
            setattr(mock_nav, attr, AsyncMock(return_value={}))
        mock_nav._page = None

        mock_mem = MagicMock()
        mock_mem.get_bookmarks.return_value = []
        mock_mem.recent_pages.return_value = []
        mock_mem.most_visited.return_value = []
        mock_mem.add_note.return_value = False

        with patch("src.browser_navigator.browser_nav", mock_nav), \
             patch("src.browser_memory.browser_memory", mock_mem):
            for cmd in BROWSER_COMMANDS:
                result = await execute_browser_command(cmd.name)
                assert "error" not in result or "Unknown" not in result.get("error", ""), (
                    f"Command {cmd.name} has no handler in execute_browser_command"
                )
