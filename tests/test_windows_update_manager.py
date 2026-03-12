"""Tests for src/windows_update_manager.py — Windows Update history.

Covers: WindowsUpdate, WUEvent, WindowsUpdateManager (get_update_history,
get_pending_updates, search_history, get_events, get_stats),
windows_update_manager singleton. All subprocess calls are mocked.
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

from src.windows_update_manager import (
    WindowsUpdate, WUEvent, WindowsUpdateManager, windows_update_manager,
)

HISTORY_JSON = json.dumps([
    {"Title": "2026-03 Cumulative Update for Windows 11",
     "Date": "2026-03-05 10:00", "ResultCode": 2, "UpdateID": "guid-1"},
    {"Title": "Security Intelligence Update",
     "Date": "2026-03-04 08:00", "ResultCode": 2, "UpdateID": "guid-2"},
])

PENDING_JSON = json.dumps([
    {"Title": "Feature Update 26H2", "IsDownloaded": False, "IsMandatory": True},
])


# ===========================================================================
# Dataclasses
# ===========================================================================

class TestDataclasses:
    def test_windows_update(self):
        wu = WindowsUpdate(title="Test Update")
        assert wu.kb_article == ""

    def test_wu_event(self):
        e = WUEvent(action="get_update_history")
        assert e.success is True


# ===========================================================================
# WindowsUpdateManager — get_update_history
# ===========================================================================

class TestGetHistory:
    def test_success(self):
        wum = WindowsUpdateManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = HISTORY_JSON
        with patch("subprocess.run", return_value=mock_result):
            updates = wum.get_update_history()
        assert len(updates) == 2
        assert "Cumulative" in updates[0]["title"]

    def test_failure(self):
        wum = WindowsUpdateManager()
        with patch("subprocess.run", side_effect=Exception("fail")):
            updates = wum.get_update_history()
        assert updates == []


# ===========================================================================
# WindowsUpdateManager — get_pending_updates
# ===========================================================================

class TestGetPending:
    def test_success(self):
        wum = WindowsUpdateManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = PENDING_JSON
        with patch("subprocess.run", return_value=mock_result):
            pending = wum.get_pending_updates()
        assert len(pending) == 1
        assert pending[0]["is_mandatory"] is True

    def test_failure(self):
        wum = WindowsUpdateManager()
        with patch("subprocess.run", side_effect=Exception("fail")):
            pending = wum.get_pending_updates()
        assert pending == []


# ===========================================================================
# WindowsUpdateManager — search_history
# ===========================================================================

class TestSearchHistory:
    def test_search(self):
        wum = WindowsUpdateManager()
        fake = [{"title": "Cumulative Update"}, {"title": "Security Update"}]
        with patch.object(wum, "get_update_history", return_value=fake):
            results = wum.search_history("cumulative")
        assert len(results) == 1


# ===========================================================================
# Events & stats
# ===========================================================================

class TestEventsStats:
    def test_events_empty(self):
        wum = WindowsUpdateManager()
        assert wum.get_events() == []

    def test_stats(self):
        wum = WindowsUpdateManager()
        assert wum.get_stats()["total_events"] == 0


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert windows_update_manager is not None
        assert isinstance(windows_update_manager, WindowsUpdateManager)
