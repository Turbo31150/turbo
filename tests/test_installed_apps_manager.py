"""Tests for src/installed_apps_manager.py — Windows installed applications.

Covers: InstalledApp, AppEvent, InstalledAppsManager (list_win32_apps,
list_uwp_apps, search, count_by_type, get_events, get_stats),
installed_apps_manager singleton. All subprocess calls are mocked.
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

from src.installed_apps_manager import (
    InstalledApp, AppEvent, InstalledAppsManager, installed_apps_manager,
)

WIN32_JSON = json.dumps([
    {"DisplayName": "Python 3.12", "DisplayVersion": "3.12.0",
     "Publisher": "Python Software Foundation", "InstallDate": "20250101"},
    {"DisplayName": "Git", "DisplayVersion": "2.44.0",
     "Publisher": "The Git Development Community", "InstallDate": "20250201"},
])

UWP_JSON = json.dumps([
    {"Name": "Microsoft.WindowsCalculator", "Version": "11.2401.0",
     "Publisher": "CN=Microsoft"},
])


# ===========================================================================
# Dataclasses
# ===========================================================================

class TestDataclasses:
    def test_installed_app(self):
        a = InstalledApp(name="Test")
        assert a.version == ""
        assert a.app_type == ""

    def test_app_event(self):
        e = AppEvent(action="list_win32_apps")
        assert e.success is True


# ===========================================================================
# InstalledAppsManager — list_win32_apps
# ===========================================================================

class TestListWin32:
    def test_success(self):
        iam = InstalledAppsManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = WIN32_JSON
        with patch("subprocess.run", return_value=mock_result):
            apps = iam.list_win32_apps()
        assert len(apps) == 2
        assert apps[0]["name"] == "Python 3.12"
        assert apps[0]["type"] == "Win32"

    def test_failure(self):
        iam = InstalledAppsManager()
        with patch("subprocess.run", side_effect=Exception("fail")):
            apps = iam.list_win32_apps()
        assert apps == []


# ===========================================================================
# InstalledAppsManager — list_uwp_apps
# ===========================================================================

class TestListUwp:
    def test_success(self):
        iam = InstalledAppsManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = UWP_JSON
        with patch("subprocess.run", return_value=mock_result):
            apps = iam.list_uwp_apps()
        assert len(apps) == 1
        assert apps[0]["type"] == "UWP"

    def test_failure(self):
        iam = InstalledAppsManager()
        with patch("subprocess.run", side_effect=Exception("fail")):
            apps = iam.list_uwp_apps()
        assert apps == []


# ===========================================================================
# InstalledAppsManager — search
# ===========================================================================

class TestSearch:
    def test_search(self):
        iam = InstalledAppsManager()
        fake_win32 = [{"name": "Python 3.12", "type": "Win32"},
                      {"name": "Git", "type": "Win32"}]
        fake_uwp = [{"name": "Microsoft.Python", "type": "UWP"}]
        with patch.object(iam, "list_win32_apps", return_value=fake_win32), \
             patch.object(iam, "list_uwp_apps", return_value=fake_uwp):
            results = iam.search("python")
        assert len(results) == 2


# ===========================================================================
# InstalledAppsManager — count_by_type
# ===========================================================================

class TestCountByType:
    def test_count(self):
        iam = InstalledAppsManager()
        with patch.object(iam, "list_win32_apps", return_value=[{}, {}]), \
             patch.object(iam, "list_uwp_apps", return_value=[{}]):
            counts = iam.count_by_type()
        assert counts["Win32"] == 2
        assert counts["UWP"] == 1


# ===========================================================================
# InstalledAppsManager — events & stats
# ===========================================================================

class TestEventsStats:
    def test_events_empty(self):
        iam = InstalledAppsManager()
        assert iam.get_events() == []

    def test_stats(self):
        iam = InstalledAppsManager()
        assert iam.get_stats()["total_events"] == 0


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert installed_apps_manager is not None
        assert isinstance(installed_apps_manager, InstalledAppsManager)
