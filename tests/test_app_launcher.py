"""Tests for src/app_launcher.py — Windows application launcher and registry.

Covers: AppEntry, LaunchEvent, AppLauncher (register, unregister, set_favorite,
launch, launch_path, get, list_apps, list_groups, search, get_history,
get_most_used, get_stats), app_launcher singleton.
All subprocess.Popen calls are mocked.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.app_launcher import (
    AppEntry, LaunchEvent, AppLauncher, app_launcher,
)


# ===========================================================================
# Dataclasses
# ===========================================================================

class TestAppEntry:
    def test_defaults(self):
        a = AppEntry(name="notepad", path="C:\\Windows\\notepad.exe")
        assert a.args == []
        assert a.cwd is None
        assert a.group == "default"
        assert a.description == ""
        assert a.favorite is False
        assert a.launch_count == 0
        assert a.last_launched is None
        assert a.created_at > 0


class TestLaunchEvent:
    def test_defaults(self):
        e = LaunchEvent(app_name="notepad")
        assert e.success is True
        assert e.pid is None
        assert e.error == ""
        assert e.timestamp > 0


# ===========================================================================
# AppLauncher — registration
# ===========================================================================

class TestRegistration:
    def test_register(self):
        al = AppLauncher()
        app = al.register("notepad", "C:\\Windows\\notepad.exe", group="editors")
        assert app.name == "notepad"
        assert app.group == "editors"
        assert al.get("notepad") is app

    def test_register_with_args(self):
        al = AppLauncher()
        app = al.register("code", "C:\\code.exe", args=["--new-window"])
        assert app.args == ["--new-window"]

    def test_unregister(self):
        al = AppLauncher()
        al.register("test", "test.exe")
        assert al.unregister("test") is True
        assert al.unregister("test") is False

    def test_unregister_nonexistent(self):
        al = AppLauncher()
        assert al.unregister("nope") is False

    def test_set_favorite(self):
        al = AppLauncher()
        al.register("app", "app.exe")
        assert al.set_favorite("app", True) is True
        assert al.get("app").favorite is True
        assert al.set_favorite("app", False) is True
        assert al.get("app").favorite is False

    def test_set_favorite_nonexistent(self):
        al = AppLauncher()
        assert al.set_favorite("nope") is False


# ===========================================================================
# AppLauncher — launch (mocked Popen)
# ===========================================================================

class TestLaunch:
    def test_launch_success(self):
        al = AppLauncher()
        al.register("notepad", "notepad.exe")
        mock_proc = MagicMock()
        mock_proc.pid = 12345
        with patch("subprocess.Popen", return_value=mock_proc):
            result = al.launch("notepad")
        assert result["success"] is True
        assert result["pid"] == 12345
        assert result["app"] == "notepad"
        assert al.get("notepad").launch_count == 1
        assert al.get("notepad").last_launched is not None

    def test_launch_with_extra_args(self):
        al = AppLauncher()
        al.register("code", "code.exe", args=["--new-window"])
        mock_proc = MagicMock()
        mock_proc.pid = 999
        with patch("subprocess.Popen", return_value=mock_proc) as mock_popen:
            al.launch("code", extra_args=["file.txt"])
        cmd = mock_popen.call_args[0][0]
        assert cmd == ["code.exe", "--new-window", "file.txt"]

    def test_launch_not_found(self):
        al = AppLauncher()
        result = al.launch("nonexistent")
        assert result["success"] is False
        assert "not found" in result["error"]

    def test_launch_exception(self):
        al = AppLauncher()
        al.register("bad", "bad.exe")
        with patch("subprocess.Popen", side_effect=FileNotFoundError("not found")):
            result = al.launch("bad")
        assert result["success"] is False
        assert "not found" in result["error"]
        history = al.get_history()
        assert history[-1]["success"] is False

    def test_launch_records_history(self):
        al = AppLauncher()
        al.register("app", "app.exe")
        mock_proc = MagicMock()
        mock_proc.pid = 100
        with patch("subprocess.Popen", return_value=mock_proc):
            al.launch("app")
        history = al.get_history()
        assert len(history) == 1
        assert history[0]["app_name"] == "app"
        assert history[0]["pid"] == 100


# ===========================================================================
# AppLauncher — launch_path (mocked Popen)
# ===========================================================================

class TestLaunchPath:
    def test_launch_path_success(self):
        al = AppLauncher()
        mock_proc = MagicMock()
        mock_proc.pid = 555
        with patch("subprocess.Popen", return_value=mock_proc):
            result = al.launch_path("C:\\tools\\app.exe", args=["--flag"])
        assert result["success"] is True
        assert result["pid"] == 555

    def test_launch_path_exception(self):
        al = AppLauncher()
        with patch("subprocess.Popen", side_effect=Exception("denied")):
            result = al.launch_path("bad.exe")
        assert result["success"] is False
        assert "denied" in result["error"]


# ===========================================================================
# AppLauncher — query methods
# ===========================================================================

class TestQuery:
    def _populated(self):
        al = AppLauncher()
        al.register("notepad", "notepad.exe", group="editors", description="Text editor")
        al.register("calc", "calc.exe", group="tools", description="Calculator", favorite=True)
        al.register("code", "code.exe", group="editors", description="VS Code")
        return al

    def test_list_apps_all(self):
        al = self._populated()
        apps = al.list_apps()
        assert len(apps) == 3

    def test_list_apps_by_group(self):
        al = self._populated()
        apps = al.list_apps(group="editors")
        assert len(apps) == 2
        assert all(a["group"] == "editors" for a in apps)

    def test_list_apps_favorites_only(self):
        al = self._populated()
        apps = al.list_apps(favorites_only=True)
        assert len(apps) == 1
        assert apps[0]["name"] == "calc"

    def test_list_groups(self):
        al = self._populated()
        groups = al.list_groups()
        assert set(groups) == {"editors", "tools"}

    def test_search_by_name(self):
        al = self._populated()
        results = al.search("note")
        assert len(results) == 1
        assert results[0]["name"] == "notepad"

    def test_search_by_description(self):
        al = self._populated()
        results = al.search("calculator")
        assert len(results) == 1
        assert results[0]["name"] == "calc"

    def test_search_no_match(self):
        al = self._populated()
        results = al.search("firefox")
        assert results == []

    def test_get_history_all(self):
        al = AppLauncher()
        al.register("a", "a.exe")
        al.register("b", "b.exe")
        mock_proc = MagicMock()
        mock_proc.pid = 1
        with patch("subprocess.Popen", return_value=mock_proc):
            al.launch("a")
            al.launch("b")
        history = al.get_history()
        assert len(history) == 2

    def test_get_history_filtered(self):
        al = AppLauncher()
        al.register("a", "a.exe")
        al.register("b", "b.exe")
        mock_proc = MagicMock()
        mock_proc.pid = 1
        with patch("subprocess.Popen", return_value=mock_proc):
            al.launch("a")
            al.launch("b")
            al.launch("a")
        history = al.get_history(app_name="a")
        assert len(history) == 2

    def test_get_most_used(self):
        al = AppLauncher()
        al.register("a", "a.exe")
        al.register("b", "b.exe")
        mock_proc = MagicMock()
        mock_proc.pid = 1
        with patch("subprocess.Popen", return_value=mock_proc):
            al.launch("a")
            al.launch("a")
            al.launch("b")
        most = al.get_most_used()
        assert most[0]["name"] == "a"
        assert most[0]["launch_count"] == 2

    def test_get_empty(self):
        al = AppLauncher()
        assert al.get("nope") is None


# ===========================================================================
# AppLauncher — stats
# ===========================================================================

class TestStats:
    def test_stats(self):
        al = AppLauncher()
        al.register("a", "a.exe", group="g1", favorite=True)
        al.register("b", "b.exe", group="g2")
        mock_proc = MagicMock()
        mock_proc.pid = 1
        with patch("subprocess.Popen", return_value=mock_proc):
            al.launch("a")
        stats = al.get_stats()
        assert stats["total_apps"] == 2
        assert stats["favorites"] == 1
        assert stats["groups"] == 2
        assert stats["total_launches"] == 1
        assert stats["failed_launches"] == 0

    def test_stats_empty(self):
        al = AppLauncher()
        stats = al.get_stats()
        assert stats["total_apps"] == 0
        assert stats["total_launches"] == 0


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert app_launcher is not None
        assert isinstance(app_launcher, AppLauncher)
