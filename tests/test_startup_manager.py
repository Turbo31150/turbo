"""Tests for src/startup_manager.py — Windows startup programs management.

Covers: StartupEntry, StartupEvent, StartupManager (list_entries, list_all,
add_entry, remove_entry, disable_entry, enable_entry, search, backup,
get_disabled, get_events, get_stats), startup_manager singleton.
All winreg calls are mocked.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, call

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.startup_manager import (
    StartupEntry, StartupEvent, StartupManager, startup_manager, STARTUP_KEYS,
)


# ===========================================================================
# Dataclasses
# ===========================================================================

class TestStartupEntry:
    def test_defaults(self):
        e = StartupEntry(name="app", command="app.exe", scope="user")
        assert e.enabled is True


class TestStartupEvent:
    def test_defaults(self):
        e = StartupEvent(action="add", entry_name="app")
        assert e.success is True
        assert e.detail == ""
        assert e.timestamp > 0


# ===========================================================================
# StartupManager — list_entries (mocked winreg)
# ===========================================================================

class TestListEntries:
    def test_list_user_entries(self):
        sm = StartupManager()
        mock_key = MagicMock()
        with patch("src.startup_manager.winreg.OpenKey", return_value=mock_key), \
             patch("src.startup_manager.winreg.EnumValue") as mock_enum:
            mock_enum.side_effect = [
                ("App1", "C:\\app1.exe", 1),
                ("App2", "C:\\app2.exe", 1),
                OSError("no more"),
            ]
            mock_key.__enter__ = MagicMock(return_value=mock_key)
            mock_key.__exit__ = MagicMock(return_value=False)
            entries = sm.list_entries("user")
        assert len(entries) == 2
        assert entries[0]["name"] == "App1"
        assert entries[0]["scope"] == "user"

    def test_list_invalid_scope(self):
        sm = StartupManager()
        assert sm.list_entries("invalid") == []

    def test_list_exception(self):
        sm = StartupManager()
        with patch("src.startup_manager.winreg.OpenKey", side_effect=Exception("denied")):
            entries = sm.list_entries("user")
        assert entries == []

    def test_list_all(self):
        sm = StartupManager()
        with patch.object(sm, "list_entries") as mock_list:
            mock_list.return_value = [{"name": "App", "command": "app.exe", "scope": "user", "enabled": True}]
            result = sm.list_all()
        assert len(result) == 3  # called 3 times (user, user_once, machine)


# ===========================================================================
# StartupManager — add_entry / remove_entry (mocked winreg)
# ===========================================================================

class TestAddRemove:
    def test_add_entry_success(self):
        sm = StartupManager()
        mock_key = MagicMock()
        mock_key.__enter__ = MagicMock(return_value=mock_key)
        mock_key.__exit__ = MagicMock(return_value=False)
        with patch("src.startup_manager.winreg.OpenKey", return_value=mock_key), \
             patch("src.startup_manager.winreg.SetValueEx") as mock_set:
            result = sm.add_entry("MyApp", "C:\\myapp.exe", scope="user")
        assert result is True
        mock_set.assert_called_once()

    def test_add_entry_invalid_scope(self):
        sm = StartupManager()
        assert sm.add_entry("MyApp", "app.exe", scope="invalid") is False
        events = sm.get_events()
        assert events[-1]["success"] is False

    def test_add_entry_permission_error(self):
        sm = StartupManager()
        mock_key = MagicMock()
        mock_key.__enter__ = MagicMock(return_value=mock_key)
        mock_key.__exit__ = MagicMock(return_value=False)
        with patch("src.startup_manager.winreg.OpenKey", return_value=mock_key), \
             patch("src.startup_manager.winreg.SetValueEx", side_effect=PermissionError):
            result = sm.add_entry("MyApp", "app.exe")
        assert result is False

    def test_remove_entry_success(self):
        sm = StartupManager()
        mock_key = MagicMock()
        mock_key.__enter__ = MagicMock(return_value=mock_key)
        mock_key.__exit__ = MagicMock(return_value=False)
        with patch("src.startup_manager.winreg.OpenKey", return_value=mock_key), \
             patch("src.startup_manager.winreg.DeleteValue"):
            result = sm.remove_entry("MyApp")
        assert result is True

    def test_remove_entry_not_found(self):
        sm = StartupManager()
        mock_key = MagicMock()
        mock_key.__enter__ = MagicMock(return_value=mock_key)
        mock_key.__exit__ = MagicMock(return_value=False)
        with patch("src.startup_manager.winreg.OpenKey", return_value=mock_key), \
             patch("src.startup_manager.winreg.DeleteValue", side_effect=FileNotFoundError):
            result = sm.remove_entry("NoApp")
        assert result is False

    def test_remove_entry_permission_error(self):
        sm = StartupManager()
        mock_key = MagicMock()
        mock_key.__enter__ = MagicMock(return_value=mock_key)
        mock_key.__exit__ = MagicMock(return_value=False)
        with patch("src.startup_manager.winreg.OpenKey", return_value=mock_key), \
             patch("src.startup_manager.winreg.DeleteValue", side_effect=PermissionError):
            result = sm.remove_entry("App")
        assert result is False

    def test_remove_invalid_scope(self):
        sm = StartupManager()
        assert sm.remove_entry("App", scope="invalid") is False


# ===========================================================================
# StartupManager — disable / enable
# ===========================================================================

class TestDisableEnable:
    def test_disable_entry(self):
        sm = StartupManager()
        with patch.object(sm, "list_entries", return_value=[
            {"name": "App", "command": "app.exe", "scope": "user", "enabled": True}
        ]):
            with patch.object(sm, "remove_entry", return_value=True):
                result = sm.disable_entry("App")
        assert result is True
        disabled = sm.get_disabled()
        assert len(disabled) == 1
        assert disabled[0]["name"] == "App"

    def test_disable_not_found(self):
        sm = StartupManager()
        with patch.object(sm, "list_entries", return_value=[]):
            result = sm.disable_entry("NoApp")
        assert result is False

    def test_enable_entry(self):
        sm = StartupManager()
        sm._disabled["App"] = "app.exe"
        with patch.object(sm, "add_entry", return_value=True):
            result = sm.enable_entry("App")
        assert result is True
        assert sm.get_disabled() == []

    def test_enable_not_disabled(self):
        sm = StartupManager()
        result = sm.enable_entry("App")
        assert result is False


# ===========================================================================
# StartupManager — search / backup
# ===========================================================================

class TestSearchBackup:
    def test_search(self):
        sm = StartupManager()
        with patch.object(sm, "list_all", return_value=[
            {"name": "Chrome", "command": "chrome.exe", "scope": "user", "enabled": True},
            {"name": "Firefox", "command": "firefox.exe", "scope": "user", "enabled": True},
        ]):
            results = sm.search("chrome")
        assert len(results) == 1
        assert results[0]["name"] == "Chrome"

    def test_search_by_command(self):
        sm = StartupManager()
        with patch.object(sm, "list_all", return_value=[
            {"name": "App", "command": "C:\\Program Files\\app.exe", "scope": "user", "enabled": True},
        ]):
            results = sm.search("program files")
        assert len(results) == 1

    def test_backup(self):
        sm = StartupManager()
        with patch.object(sm, "list_entries", return_value=[
            {"name": "App", "command": "app.exe", "scope": "user", "enabled": True},
        ]):
            backup = sm.backup("user")
        assert len(backup) == 1


# ===========================================================================
# StartupManager — events / stats
# ===========================================================================

class TestEventsAndStats:
    def test_events_empty(self):
        sm = StartupManager()
        assert sm.get_events() == []

    def test_events_recorded(self):
        sm = StartupManager()
        sm._record("test", "app", True, "detail")
        events = sm.get_events()
        assert len(events) == 1
        assert events[0]["action"] == "test"
        assert events[0]["entry_name"] == "app"

    def test_stats(self):
        sm = StartupManager()
        sm._record("a", "app", True)
        sm._disabled["x"] = "x.exe"
        with patch.object(sm, "list_entries", return_value=[]):
            stats = sm.get_stats()
        assert stats["total_events"] == 1
        assert stats["disabled_entries"] == 1


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert startup_manager is not None
        assert isinstance(startup_manager, StartupManager)
