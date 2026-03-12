"""Tests for src/file_watcher.py — File system change monitoring.

Covers: ChangeType, FileEvent, WatchConfig, FileWatcher (add_watch,
remove_watch, enable/disable_watch, _scan_directory, _matches_patterns,
poll, _check_watch, list_watches, list_groups, get_events, get_stats),
file_watcher singleton.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.file_watcher import (
    ChangeType, FileEvent, WatchConfig, FileWatcher, file_watcher,
)


# ===========================================================================
# Enums & Dataclasses
# ===========================================================================

class TestChangeType:
    def test_values(self):
        assert ChangeType.CREATED.value == "created"
        assert ChangeType.MODIFIED.value == "modified"
        assert ChangeType.DELETED.value == "deleted"


class TestFileEvent:
    def test_defaults(self):
        e = FileEvent(path="/tmp/x.txt", change_type=ChangeType.CREATED)
        assert e.timestamp > 0
        assert e.size is None
        assert e.watch_name == ""


class TestWatchConfig:
    def test_defaults(self):
        w = WatchConfig(name="test", directory="/tmp")
        assert w.patterns == ["*"]
        assert w.recursive is False
        assert w.group == "default"
        assert w.callback is None
        assert w.debounce_ms == 100
        assert w.enabled is True


# ===========================================================================
# FileWatcher — _matches_patterns (static)
# ===========================================================================

class TestMatchesPatterns:
    def test_wildcard(self):
        assert FileWatcher._matches_patterns("anything.txt", ["*"]) is True

    def test_extension_match(self):
        assert FileWatcher._matches_patterns("test.py", ["*.py"]) is True
        assert FileWatcher._matches_patterns("test.js", ["*.py"]) is False

    def test_multiple_patterns(self):
        assert FileWatcher._matches_patterns("test.py", ["*.js", "*.py"]) is True

    def test_exact_name(self):
        assert FileWatcher._matches_patterns("Makefile", ["Makefile"]) is True
        assert FileWatcher._matches_patterns("other", ["Makefile"]) is False


# ===========================================================================
# FileWatcher — _scan_directory
# ===========================================================================

class TestScanDirectory:
    def test_nonexistent_dir(self):
        fw = FileWatcher()
        result = fw._scan_directory("/nonexistent/path/xyz", ["*"], False)
        assert result == {}

    def test_real_dir(self):
        fw = FileWatcher()
        with tempfile.TemporaryDirectory() as d:
            Path(d, "test.txt").write_text("hello")
            Path(d, "test.py").write_text("x=1")
            result = fw._scan_directory(d, ["*.txt"], False)
        assert len(result) == 1
        assert any("test.txt" in k for k in result)

    def test_wildcard_all_files(self):
        fw = FileWatcher()
        with tempfile.TemporaryDirectory() as d:
            Path(d, "a.txt").write_text("a")
            Path(d, "b.py").write_text("b")
            result = fw._scan_directory(d, ["*"], False)
        assert len(result) == 2

    def test_recursive(self):
        fw = FileWatcher()
        with tempfile.TemporaryDirectory() as d:
            sub = Path(d, "sub")
            sub.mkdir()
            Path(d, "top.txt").write_text("top")
            Path(sub, "deep.txt").write_text("deep")
            result = fw._scan_directory(d, ["*.txt"], True)
        assert len(result) == 2


# ===========================================================================
# FileWatcher — add/remove/enable/disable watch
# ===========================================================================

class TestWatchManagement:
    def test_add_watch(self):
        fw = FileWatcher()
        with tempfile.TemporaryDirectory() as d:
            w = fw.add_watch("test", d, patterns=["*.py"])
        assert w.name == "test"
        assert w.patterns == ["*.py"]

    def test_remove_watch(self):
        fw = FileWatcher()
        with tempfile.TemporaryDirectory() as d:
            fw.add_watch("test", d)
        assert fw.remove_watch("test") is True
        assert fw.remove_watch("test") is False

    def test_enable_disable(self):
        fw = FileWatcher()
        with tempfile.TemporaryDirectory() as d:
            fw.add_watch("test", d)
        assert fw.disable_watch("test") is True
        watches = fw.list_watches()
        assert watches[0]["enabled"] is False
        assert fw.enable_watch("test") is True
        watches = fw.list_watches()
        assert watches[0]["enabled"] is True

    def test_enable_nonexistent(self):
        fw = FileWatcher()
        assert fw.enable_watch("nope") is False
        assert fw.disable_watch("nope") is False


# ===========================================================================
# FileWatcher — poll / _check_watch
# ===========================================================================

class TestPoll:
    def test_no_changes(self):
        fw = FileWatcher()
        with tempfile.TemporaryDirectory() as d:
            Path(d, "test.txt").write_text("hello")
            fw.add_watch("test", d)
            events = fw.poll()
        assert events == []

    def test_detects_new_file(self):
        fw = FileWatcher()
        with tempfile.TemporaryDirectory() as d:
            fw.add_watch("test", d)
            Path(d, "new.txt").write_text("new")
            events = fw.poll()
        assert len(events) == 1
        assert events[0].change_type == ChangeType.CREATED
        assert "new.txt" in events[0].path

    def test_detects_deleted_file(self):
        fw = FileWatcher()
        with tempfile.TemporaryDirectory() as d:
            f = Path(d, "to_delete.txt")
            f.write_text("bye")
            fw.add_watch("test", d)
            f.unlink()
            events = fw.poll()
        assert len(events) == 1
        assert events[0].change_type == ChangeType.DELETED

    def test_disabled_watch_skipped(self):
        fw = FileWatcher()
        with tempfile.TemporaryDirectory() as d:
            fw.add_watch("test", d)
            fw.disable_watch("test")
            Path(d, "new.txt").write_text("ignored")
            events = fw.poll()
        assert events == []

    def test_callback_fired(self):
        fw = FileWatcher()
        called = []
        with tempfile.TemporaryDirectory() as d:
            fw.add_watch("test", d, callback=lambda e: called.append(e))
            Path(d, "x.txt").write_text("x")
            fw.poll()
        assert len(called) == 1

    def test_callback_error_graceful(self):
        fw = FileWatcher()
        def bad_callback(e):
            raise ValueError("boom")
        with tempfile.TemporaryDirectory() as d:
            fw.add_watch("test", d, callback=bad_callback)
            Path(d, "x.txt").write_text("x")
            events = fw.poll()  # should not raise
        assert len(events) == 1

    def test_poll_specific_watch(self):
        fw = FileWatcher()
        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            fw.add_watch("w1", d1)
            fw.add_watch("w2", d2)
            Path(d1, "a.txt").write_text("a")
            Path(d2, "b.txt").write_text("b")
            events = fw.poll(name="w1")
        assert len(events) == 1
        assert events[0].watch_name == "w1"


# ===========================================================================
# FileWatcher — list_watches / list_groups
# ===========================================================================

class TestListMethods:
    def test_list_watches_empty(self):
        fw = FileWatcher()
        assert fw.list_watches() == []

    def test_list_watches_with_data(self):
        fw = FileWatcher()
        with tempfile.TemporaryDirectory() as d:
            fw.add_watch("a", d, group="g1")
            fw.add_watch("b", d, group="g2")
        result = fw.list_watches()
        assert len(result) == 2

    def test_list_watches_filter_group(self):
        fw = FileWatcher()
        with tempfile.TemporaryDirectory() as d:
            fw.add_watch("a", d, group="web")
            fw.add_watch("b", d, group="db")
        result = fw.list_watches(group="web")
        assert len(result) == 1

    def test_list_groups(self):
        fw = FileWatcher()
        with tempfile.TemporaryDirectory() as d:
            fw.add_watch("a", d, group="web")
            fw.add_watch("b", d, group="db")
        groups = fw.list_groups()
        assert set(groups) == {"web", "db"}


# ===========================================================================
# FileWatcher — get_events / get_stats
# ===========================================================================

class TestEventsAndStats:
    def test_get_events_empty(self):
        fw = FileWatcher()
        assert fw.get_events() == []

    def test_get_events_filter(self):
        fw = FileWatcher()
        with tempfile.TemporaryDirectory() as d:
            fw.add_watch("w1", d)
            Path(d, "a.txt").write_text("a")
            fw.poll()
        events = fw.get_events(watch_name="w1")
        assert len(events) == 1
        events = fw.get_events(change_type="created")
        assert len(events) == 1
        events = fw.get_events(change_type="deleted")
        assert len(events) == 0

    def test_get_stats_empty(self):
        fw = FileWatcher()
        stats = fw.get_stats()
        assert stats["total_watches"] == 0
        assert stats["total_events"] == 0

    def test_get_stats_with_data(self):
        fw = FileWatcher()
        with tempfile.TemporaryDirectory() as d:
            Path(d, "a.txt").write_text("a")
            fw.add_watch("test", d)
            Path(d, "b.txt").write_text("b")
            fw.poll()
        stats = fw.get_stats()
        assert stats["total_watches"] == 1
        assert stats["enabled"] == 1
        assert stats["events_created"] == 1


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert file_watcher is not None
        assert isinstance(file_watcher, FileWatcher)
