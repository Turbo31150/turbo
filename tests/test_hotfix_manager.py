"""Tests for src/hotfix_manager.py — Windows hotfix/update management.

Covers: HotfixInfo, HotfixEvent, HotfixManager (list_hotfixes, search,
count_by_type, get_latest, get_events, get_stats), hotfix_manager singleton.
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

from src.hotfix_manager import (
    HotfixInfo, HotfixEvent, HotfixManager, hotfix_manager,
)

HOTFIXES_JSON = json.dumps([
    {"HotFixID": "KB5034441", "Description": "Security Update",
     "InstalledOn": "2026-02-15", "InstalledBy": "NT AUTHORITY\\SYSTEM"},
    {"HotFixID": "KB5035853", "Description": "Update",
     "InstalledOn": "2026-03-01", "InstalledBy": "NT AUTHORITY\\SYSTEM"},
    {"HotFixID": "KB5032392", "Description": "Security Update",
     "InstalledOn": {"DateTime": "2026-01-10"}, "InstalledBy": ""},
])


class TestDataclasses:
    def test_hotfix_info(self):
        h = HotfixInfo(hotfix_id="KB123")
        assert h.description == ""

    def test_hotfix_event(self):
        e = HotfixEvent(action="list")
        assert e.success is True


class TestListHotfixes:
    def test_success(self):
        hm = HotfixManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = HOTFIXES_JSON
        with patch("subprocess.run", return_value=mock_result):
            fixes = hm.list_hotfixes()
        assert len(fixes) == 3
        assert fixes[0]["hotfix_id"] == "KB5034441"
        assert fixes[0]["description"] == "Security Update"

    def test_installed_on_dict(self):
        hm = HotfixManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = HOTFIXES_JSON
        with patch("subprocess.run", return_value=mock_result):
            fixes = hm.list_hotfixes()
        assert "2026-01-10" in fixes[2]["installed_on"]

    def test_single_dict(self):
        hm = HotfixManager()
        data = json.dumps({"HotFixID": "KB1", "Description": "Update",
                           "InstalledOn": "2026-01-01", "InstalledBy": ""})
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = data
        with patch("subprocess.run", return_value=mock_result):
            assert len(hm.list_hotfixes()) == 1

    def test_failure(self):
        hm = HotfixManager()
        with patch("subprocess.run", side_effect=Exception("fail")):
            assert hm.list_hotfixes() == []


class TestSearch:
    def test_search_by_id(self):
        hm = HotfixManager()
        fake = [{"hotfix_id": "KB5034441", "description": "Security Update"},
                {"hotfix_id": "KB5035853", "description": "Update"}]
        with patch.object(hm, "list_hotfixes", return_value=fake):
            assert len(hm.search("KB5034")) == 1

    def test_search_by_description(self):
        hm = HotfixManager()
        fake = [{"hotfix_id": "KB1", "description": "Security Update"},
                {"hotfix_id": "KB2", "description": "Update"}]
        with patch.object(hm, "list_hotfixes", return_value=fake):
            assert len(hm.search("security")) == 1


class TestCountByType:
    def test_count(self):
        hm = HotfixManager()
        fake = [{"description": "Security Update"}, {"description": "Security Update"},
                {"description": "Update"}]
        with patch.object(hm, "list_hotfixes", return_value=fake):
            counts = hm.count_by_type()
        assert counts["Security Update"] == 2
        assert counts["Update"] == 1


class TestGetLatest:
    def test_latest(self):
        hm = HotfixManager()
        fake = [{"installed_on": "2026-01-01"}, {"installed_on": "2026-03-01"},
                {"installed_on": "2026-02-01"}]
        with patch.object(hm, "list_hotfixes", return_value=fake):
            latest = hm.get_latest(2)
        assert len(latest) == 2
        assert latest[0]["installed_on"] == "2026-03-01"


class TestEventsStats:
    def test_events_empty(self):
        assert HotfixManager().get_events() == []

    def test_stats(self):
        assert HotfixManager().get_stats()["total_events"] == 0


class TestSingleton:
    def test_exists(self):
        assert isinstance(hotfix_manager, HotfixManager)
