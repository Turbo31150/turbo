"""Tests for src/clipboard_manager.py — Windows clipboard history and management.

Covers: ClipCategory, ClipEntry, _detect_category, ClipboardManager (capture,
get_current, set_clipboard, get_history, search, pin, unpin, clear,
cleanup_expired, get_stats), clipboard_manager singleton.
subprocess calls are mocked.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.clipboard_manager import (
    ClipCategory, ClipEntry, _detect_category, ClipboardManager, clipboard_manager,
)


# ===========================================================================
# ClipCategory & ClipEntry
# ===========================================================================

class TestClipEntry:
    def test_defaults(self):
        e = ClipEntry(content="hello")
        assert e.category == ClipCategory.TEXT
        assert e.pinned is False
        assert e.tags == []
        assert e.source == ""
        assert e.timestamp > 0

    def test_preview_short(self):
        e = ClipEntry(content="short text")
        assert e.preview == "short text"

    def test_preview_truncated(self):
        e = ClipEntry(content="x" * 200)
        assert e.preview.endswith("...")
        assert len(e.preview) == 83  # 80 + "..."


# ===========================================================================
# _detect_category
# ===========================================================================

class TestDetectCategory:
    def test_url_http(self):
        assert _detect_category("https://example.com") == ClipCategory.URL

    def test_url_ftp(self):
        assert _detect_category("ftp://files.example.com") == ClipCategory.URL

    def test_path_windows(self):
        assert _detect_category("/\Users/test/file.txt") == ClipCategory.PATH

    def test_path_unix(self):
        assert _detect_category("/home/user/file.txt") == ClipCategory.PATH

    def test_code_def(self):
        assert _detect_category("def hello():") == ClipCategory.CODE

    def test_code_import(self):
        assert _detect_category("import os") == ClipCategory.CODE

    def test_code_braces(self):
        assert _detect_category("function() { return 1; }") == ClipCategory.CODE

    def test_text_default(self):
        assert _detect_category("just some regular text") == ClipCategory.TEXT


# ===========================================================================
# ClipboardManager — capture
# ===========================================================================

class TestCapture:
    def test_capture_adds_to_history(self):
        cm = ClipboardManager()
        entry = cm.capture("hello world")
        assert entry.content == "hello world"
        assert entry.category == ClipCategory.TEXT
        history = cm.get_history()
        assert len(history) == 1

    def test_capture_auto_detects_category(self):
        cm = ClipboardManager()
        entry = cm.capture("https://example.com")
        assert entry.category == ClipCategory.URL

    def test_capture_with_source_and_tags(self):
        cm = ClipboardManager()
        entry = cm.capture("text", source="browser", tags=["important"])
        assert entry.source == "browser"
        assert entry.tags == ["important"]

    def test_capture_max_history_evicts_unpinned(self):
        cm = ClipboardManager(max_history=3)
        cm.capture("a")
        cm.capture("b")
        cm.capture("c")
        cm.capture("d")  # should evict oldest unpinned
        assert len(cm.get_history(limit=100)) == 3


# ===========================================================================
# ClipboardManager — clipboard operations (mocked)
# ===========================================================================

class TestClipboardOps:
    def test_get_current(self):
        cm = ClipboardManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "clipboard content\n"
        with patch("subprocess.run", return_value=mock_result):
            content = cm.get_current()
        assert content == "clipboard content"

    def test_get_current_failure(self):
        cm = ClipboardManager()
        with patch("subprocess.run", side_effect=Exception("fail")):
            content = cm.get_current()
        assert content is None

    def test_set_clipboard_success(self):
        cm = ClipboardManager()
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        with patch("subprocess.Popen", return_value=mock_proc):
            result = cm.set_clipboard("test")
        assert result is True

    def test_set_clipboard_failure(self):
        cm = ClipboardManager()
        with patch("subprocess.Popen", side_effect=Exception("fail")):
            result = cm.set_clipboard("test")
        assert result is False


# ===========================================================================
# ClipboardManager — history & search
# ===========================================================================

class TestHistorySearch:
    def test_get_history(self):
        cm = ClipboardManager()
        cm.capture("first")
        cm.capture("second")
        history = cm.get_history()
        assert len(history) == 2
        assert history[0]["full_content"] == "first"

    def test_get_history_filter_category(self):
        cm = ClipboardManager()
        cm.capture("hello text")
        cm.capture("https://example.com")
        history = cm.get_history(category="url")
        assert len(history) == 1
        assert history[0]["category"] == "url"

    def test_search(self):
        cm = ClipboardManager()
        cm.capture("Hello World")
        cm.capture("Goodbye World")
        cm.capture("Something else")
        results = cm.search("world")
        assert len(results) == 2

    def test_search_no_match(self):
        cm = ClipboardManager()
        cm.capture("hello")
        results = cm.search("xyz")
        assert results == []


# ===========================================================================
# ClipboardManager — pin/unpin
# ===========================================================================

class TestPinUnpin:
    def test_pin(self):
        cm = ClipboardManager()
        cm.capture("a")
        cm.capture("b")
        assert cm.pin(0) is True  # pins last entry ("b")
        history = cm.get_history()
        assert history[-1]["pinned"] is True

    def test_unpin(self):
        cm = ClipboardManager()
        cm.capture("a")
        cm.pin(0)
        assert cm.unpin(0) is True
        history = cm.get_history()
        assert history[-1]["pinned"] is False

    def test_pin_invalid_index(self):
        cm = ClipboardManager()
        assert cm.pin(99) is False

    def test_unpin_invalid_index(self):
        cm = ClipboardManager()
        assert cm.unpin(99) is False


# ===========================================================================
# ClipboardManager — clear & cleanup
# ===========================================================================

class TestClearCleanup:
    def test_clear_keeps_pinned(self):
        cm = ClipboardManager()
        cm.capture("a")
        cm.capture("b")
        cm.pin(0)  # pin "b"
        removed = cm.clear(keep_pinned=True)
        assert removed == 1
        assert len(cm.get_history()) == 1

    def test_clear_all(self):
        cm = ClipboardManager()
        cm.capture("a")
        cm.capture("b")
        removed = cm.clear(keep_pinned=False)
        assert removed == 2
        assert cm.get_history() == []

    def test_cleanup_expired(self):
        cm = ClipboardManager(ttl_seconds=1)
        cm.capture("old")
        # Manually expire the entry
        cm._history[0].timestamp = time.time() - 10
        cm.capture("new")
        removed = cm.cleanup_expired()
        assert removed == 1
        assert len(cm.get_history()) == 1

    def test_cleanup_keeps_pinned(self):
        cm = ClipboardManager(ttl_seconds=1)
        cm.capture("pinned")
        cm._history[0].timestamp = time.time() - 10
        cm._history[0].pinned = True
        removed = cm.cleanup_expired()
        assert removed == 0


# ===========================================================================
# ClipboardManager — stats
# ===========================================================================

class TestStats:
    def test_stats(self):
        cm = ClipboardManager()
        cm.capture("hello")
        cm.capture("https://example.com")
        cm.pin(0)
        stats = cm.get_stats()
        assert stats["total_entries"] == 2
        assert stats["pinned"] == 1
        assert "text" in stats["categories"]
        assert "url" in stats["categories"]

    def test_stats_empty(self):
        cm = ClipboardManager()
        stats = cm.get_stats()
        assert stats["total_entries"] == 0
        assert stats["pinned"] == 0


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert clipboard_manager is not None
        assert isinstance(clipboard_manager, ClipboardManager)
