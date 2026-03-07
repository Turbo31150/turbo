"""Tests for src/registry_manager.py — Windows Registry read/write operations.

Covers: RegistryEvent, RegistryFavorite, RegistryManager (favorites CRUD,
search_values, export_key, _record, get_events, get_stats), HIVES, TYPE_MAP.
Note: actual winreg calls are mocked to avoid modifying the real registry.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.registry_manager import (
    RegistryEvent, RegistryFavorite, RegistryManager,
    HIVES, TYPE_MAP, registry_manager,
)


# ===========================================================================
# Dataclasses & Constants
# ===========================================================================

class TestRegistryEvent:
    def test_defaults(self):
        e = RegistryEvent(action="read", hive="HKCU", path="Software\\Test")
        assert e.value_name == ""
        assert e.success is True
        assert e.detail == ""
        assert e.timestamp > 0


class TestRegistryFavorite:
    def test_defaults(self):
        f = RegistryFavorite(name="startup", hive="HKCU", path="Software\\Microsoft\\Windows\\CurrentVersion\\Run")
        assert f.description == ""
        assert f.created_at > 0


class TestConstants:
    def test_hives(self):
        assert "HKCU" in HIVES
        assert "HKLM" in HIVES
        assert len(HIVES) == 5

    def test_type_map(self):
        import winreg
        assert TYPE_MAP[winreg.REG_SZ] == "REG_SZ"
        assert TYPE_MAP[winreg.REG_DWORD] == "REG_DWORD"


# ===========================================================================
# RegistryManager — Favorites
# ===========================================================================

class TestFavorites:
    def test_add(self):
        rm = RegistryManager()
        fav = rm.add_favorite("startup", "HKCU", "Software\\Test", "test")
        assert fav.name == "startup"
        assert fav.description == "test"

    def test_remove(self):
        rm = RegistryManager()
        rm.add_favorite("a", "HKCU", "path")
        assert rm.remove_favorite("a") is True
        assert rm.remove_favorite("a") is False

    def test_list_favorites(self):
        rm = RegistryManager()
        rm.add_favorite("a", "HKCU", "path1")
        rm.add_favorite("b", "HKLM", "path2")
        result = rm.list_favorites()
        assert len(result) == 2
        assert any(f["name"] == "a" for f in result)

    def test_list_favorites_empty(self):
        rm = RegistryManager()
        assert rm.list_favorites() == []


# ===========================================================================
# RegistryManager — read_value (mocked)
# ===========================================================================

class TestReadValue:
    def test_unknown_hive(self):
        rm = RegistryManager()
        result = rm.read_value("INVALID", "path", "name")
        assert "error" in result
        assert "Unknown hive" in result["error"]

    def test_success(self):
        rm = RegistryManager()
        import winreg
        mock_key = MagicMock()
        with patch("src.registry_manager.winreg.OpenKey", return_value=mock_key), \
             patch("src.registry_manager.winreg.QueryValueEx", return_value=("test_value", winreg.REG_SZ)):
            mock_key.__enter__ = MagicMock(return_value=mock_key)
            mock_key.__exit__ = MagicMock(return_value=False)
            result = rm.read_value("HKCU", "Software\\Test", "MyKey")
        assert result["value"] == "test_value"
        assert result["type"] == "REG_SZ"

    def test_not_found(self):
        rm = RegistryManager()
        with patch("src.registry_manager.winreg.OpenKey", side_effect=FileNotFoundError):
            result = rm.read_value("HKCU", "Software\\Nope", "key")
        assert "error" in result
        assert "not found" in result["error"]

    def test_permission_denied(self):
        rm = RegistryManager()
        with patch("src.registry_manager.winreg.OpenKey", side_effect=PermissionError):
            result = rm.read_value("HKCU", "path", "key")
        assert "Permission denied" in result["error"]


# ===========================================================================
# RegistryManager — list_values (mocked)
# ===========================================================================

class TestListValues:
    def test_unknown_hive(self):
        rm = RegistryManager()
        assert rm.list_values("INVALID", "path") == []

    def test_success(self):
        rm = RegistryManager()
        import winreg
        mock_key = MagicMock()
        mock_key.__enter__ = MagicMock(return_value=mock_key)
        mock_key.__exit__ = MagicMock(return_value=False)

        call_count = [0]
        def mock_enum(key, index):
            call_count[0] += 1
            if call_count[0] == 1:
                return ("Name", "Value", winreg.REG_SZ)
            raise OSError("no more")

        with patch("src.registry_manager.winreg.OpenKey", return_value=mock_key), \
             patch("src.registry_manager.winreg.EnumValue", side_effect=mock_enum):
            values = rm.list_values("HKCU", "Software\\Test")
        assert len(values) == 1
        assert values[0]["name"] == "Name"


# ===========================================================================
# RegistryManager — list_subkeys (mocked)
# ===========================================================================

class TestListSubkeys:
    def test_unknown_hive(self):
        rm = RegistryManager()
        assert rm.list_subkeys("INVALID", "path") == []

    def test_success(self):
        rm = RegistryManager()
        mock_key = MagicMock()
        mock_key.__enter__ = MagicMock(return_value=mock_key)
        mock_key.__exit__ = MagicMock(return_value=False)

        call_count = [0]
        def mock_enum(key, index):
            call_count[0] += 1
            if call_count[0] <= 2:
                return f"SubKey{call_count[0]}"
            raise OSError("no more")

        with patch("src.registry_manager.winreg.OpenKey", return_value=mock_key), \
             patch("src.registry_manager.winreg.EnumKey", side_effect=mock_enum):
            keys = rm.list_subkeys("HKCU", "Software\\Test")
        assert keys == ["SubKey1", "SubKey2"]


# ===========================================================================
# RegistryManager — write_value / delete_value (mocked)
# ===========================================================================

class TestWriteDelete:
    def test_write_unknown_hive(self):
        rm = RegistryManager()
        assert rm.write_value("INVALID", "path", "name", "value") is False

    def test_write_success(self):
        rm = RegistryManager()
        mock_key = MagicMock()
        mock_key.__enter__ = MagicMock(return_value=mock_key)
        mock_key.__exit__ = MagicMock(return_value=False)
        with patch("src.registry_manager.winreg.CreateKeyEx", return_value=mock_key), \
             patch("src.registry_manager.winreg.SetValueEx"):
            assert rm.write_value("HKCU", "Software\\Test", "name", "value") is True

    def test_delete_unknown_hive(self):
        rm = RegistryManager()
        assert rm.delete_value("INVALID", "path", "name") is False

    def test_delete_success(self):
        rm = RegistryManager()
        mock_key = MagicMock()
        mock_key.__enter__ = MagicMock(return_value=mock_key)
        mock_key.__exit__ = MagicMock(return_value=False)
        with patch("src.registry_manager.winreg.OpenKey", return_value=mock_key), \
             patch("src.registry_manager.winreg.DeleteValue"):
            assert rm.delete_value("HKCU", "Software\\Test", "name") is True


# ===========================================================================
# RegistryManager — search_values
# ===========================================================================

class TestSearchValues:
    def test_search(self):
        rm = RegistryManager()
        import winreg
        mock_key = MagicMock()
        mock_key.__enter__ = MagicMock(return_value=mock_key)
        mock_key.__exit__ = MagicMock(return_value=False)

        call_count = [0]
        def mock_enum(key, index):
            call_count[0] += 1
            if call_count[0] == 1:
                return ("PythonPath", "C:\\Python", winreg.REG_SZ)
            if call_count[0] == 2:
                return ("JavaPath", "C:\\Java", winreg.REG_SZ)
            raise OSError("no more")

        with patch("src.registry_manager.winreg.OpenKey", return_value=mock_key), \
             patch("src.registry_manager.winreg.EnumValue", side_effect=mock_enum):
            results = rm.search_values("HKCU", "Software", "python")
        assert len(results) == 1
        assert results[0]["name"] == "PythonPath"


# ===========================================================================
# RegistryManager — export_key
# ===========================================================================

class TestExportKey:
    def test_export(self):
        rm = RegistryManager()
        with patch.object(rm, "list_values", return_value=[{"name": "v1"}]), \
             patch.object(rm, "list_subkeys", return_value=["sub1"]):
            export = rm.export_key("HKCU", "Software\\Test")
        assert export["hive"] == "HKCU"
        assert export["path"] == "Software\\Test"
        assert len(export["values"]) == 1
        assert export["subkeys"] == ["sub1"]
        assert "exported_at" in export


# ===========================================================================
# RegistryManager — get_events / get_stats
# ===========================================================================

class TestEventsAndStats:
    def test_events_empty(self):
        rm = RegistryManager()
        assert rm.get_events() == []

    def test_events_recorded(self):
        rm = RegistryManager()
        rm._record("read", "HKCU", "path", "key", True)
        events = rm.get_events()
        assert len(events) == 1
        assert events[0]["action"] == "read"

    def test_stats(self):
        rm = RegistryManager()
        rm._record("read", "HKCU", "path", "key", True)
        rm.add_favorite("fav", "HKCU", "path")
        stats = rm.get_stats()
        assert stats["total_events"] == 1
        assert stats["total_favorites"] == 1
        assert "HKCU" in stats["supported_hives"]


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert registry_manager is not None
        assert isinstance(registry_manager, RegistryManager)
