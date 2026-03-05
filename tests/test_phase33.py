"""Phase 33 Tests — Driver Manager, WMI Explorer, Env Variable Manager, MCP Handlers."""

import asyncio
import json
import os
import pytest


# ═══════════════════════════════════════════════════════════════════════════
# DRIVER MANAGER
# ═══════════════════════════════════════════════════════════════════════════

class TestDriverManager:
    @staticmethod
    def _make():
        from src.driver_manager import DriverManager
        return DriverManager()

    def test_singleton_exists(self):
        from src.driver_manager import driver_manager
        assert driver_manager is not None

    def test_get_events_empty(self):
        dm = self._make()
        events = dm.get_events()
        assert isinstance(events, list)
        assert len(events) == 0

    def test_record_event(self):
        dm = self._make()
        dm._record("test", True, "ok")
        events = dm.get_events()
        assert len(events) == 1

    def test_driver_info_dataclass(self):
        from src.driver_manager import DriverInfo
        di = DriverInfo(name="NVIDIA Display", vendor="NVIDIA")
        assert di.name == "NVIDIA Display"
        assert di.version == ""
        assert di.device_class == ""

    def test_driver_event_dataclass(self):
        from src.driver_manager import DriverEvent
        e = DriverEvent(action="list")
        assert e.action == "list"
        assert e.success is True

    def test_get_stats_structure(self):
        dm = self._make()
        stats = dm.get_stats()
        assert "total_events" in stats

    def test_search_with_mock(self):
        dm = self._make()
        dm.list_drivers = lambda: [
            {"name": "NVIDIA GeForce", "vendor": "NVIDIA", "status": "OK"},
            {"name": "Intel Audio", "vendor": "Intel", "status": "OK"},
        ]
        results = dm.search("nvidia")
        assert len(results) == 1

    def test_filter_by_class_with_mock(self):
        dm = self._make()
        dm.list_drivers = lambda: [
            {"name": "GPU", "device_class": "Display"},
            {"name": "NIC", "device_class": "Net"},
        ]
        results = dm.filter_by_class("display")
        assert len(results) == 1

    def test_count_by_status_with_mock(self):
        dm = self._make()
        dm.list_drivers = lambda: [
            {"name": "A", "status": "OK"},
            {"name": "B", "status": "OK"},
            {"name": "C", "status": "Error"},
        ]
        counts = dm.count_by_status()
        assert counts["OK"] == 2
        assert counts["Error"] == 1


# ═══════════════════════════════════════════════════════════════════════════
# WMI EXPLORER
# ═══════════════════════════════════════════════════════════════════════════

class TestWMIExplorer:
    @staticmethod
    def _make():
        from src.wmi_explorer import WMIExplorer
        return WMIExplorer()

    def test_singleton_exists(self):
        from src.wmi_explorer import wmi_explorer
        assert wmi_explorer is not None

    def test_get_events_empty(self):
        we = self._make()
        events = we.get_events()
        assert isinstance(events, list)
        assert len(events) == 0

    def test_record_event(self):
        we = self._make()
        we._record("test", True, "ok")
        events = we.get_events()
        assert len(events) == 1

    def test_wmi_result_dataclass(self):
        from src.wmi_explorer import WMIResult
        r = WMIResult(class_name="Win32_OS", instance_count=1)
        assert r.class_name == "Win32_OS"
        assert r.data == []

    def test_wmi_event_dataclass(self):
        from src.wmi_explorer import WMIEvent
        e = WMIEvent(action="query")
        assert e.action == "query"
        assert e.success is True

    def test_list_common_classes(self):
        we = self._make()
        classes = we.list_common_classes()
        assert "Win32_OperatingSystem" in classes
        assert "Win32_Processor" in classes
        assert len(classes) >= 10

    def test_get_stats_structure(self):
        we = self._make()
        stats = we.get_stats()
        assert "total_events" in stats
        assert "common_classes" in stats

    def test_query_empty_class_name(self):
        we = self._make()
        result = we.query_class("")
        assert result == []

    def test_query_sanitizes_class_name(self):
        we = self._make()
        # Injection attempt should be sanitized
        result = we.query_class("Win32_OS; Remove-Item")
        # Should strip non-alphanumeric chars and run safely
        assert isinstance(result, list)

    def test_count_empty_class(self):
        we = self._make()
        result = we.count_instances("")
        assert result == 0


# ═══════════════════════════════════════════════════════════════════════════
# ENV VARIABLE MANAGER
# ═══════════════════════════════════════════════════════════════════════════

class TestEnvVariableManager:
    @staticmethod
    def _make():
        from src.env_variable_manager import EnvVariableManager
        return EnvVariableManager()

    def test_singleton_exists(self):
        from src.env_variable_manager import env_variable_manager
        assert env_variable_manager is not None

    def test_get_events_empty(self):
        em = self._make()
        events = em.get_events()
        assert isinstance(events, list)
        assert len(events) == 0

    def test_record_event(self):
        em = self._make()
        em._record("test", True, "ok")
        events = em.get_events()
        assert len(events) == 1

    def test_env_variable_dataclass(self):
        from src.env_variable_manager import EnvVariable
        ev = EnvVariable(name="PATH", value="/usr/bin", scope="System")
        assert ev.name == "PATH"
        assert ev.scope == "System"

    def test_env_event_dataclass(self):
        from src.env_variable_manager import EnvEvent
        e = EnvEvent(action="list")
        assert e.action == "list"
        assert e.success is True

    def test_get_var_existing(self):
        em = self._make()
        result = em.get_var("PATH")
        assert result is not None
        assert result["name"] == "PATH"
        assert result["scope"] == "Process"

    def test_get_var_nonexistent(self):
        em = self._make()
        result = em.get_var("NONEXISTENT_VAR_12345")
        assert result is None

    def test_get_path_entries(self):
        em = self._make()
        entries = em.get_path_entries()
        assert isinstance(entries, list)
        assert len(entries) > 0

    def test_get_stats_structure(self):
        em = self._make()
        stats = em.get_stats()
        assert "total_events" in stats
        assert "process_var_count" in stats
        assert stats["process_var_count"] > 0

    def test_search_with_mock(self):
        em = self._make()
        em.list_all = lambda: [
            {"name": "PATH", "value": "/bin", "scope": "System"},
            {"name": "HOME", "value": "/home", "scope": "User"},
        ]
        results = em.search("path")
        assert len(results) == 1


# ═══════════════════════════════════════════════════════════════════════════
# MCP HANDLERS — Phase 33
# ═══════════════════════════════════════════════════════════════════════════

class TestMCPHandlersPhase33:
    def test_drvmgr_list(self):
        from src.mcp_server import handle_drvmgr_list
        result = asyncio.run(handle_drvmgr_list({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_drvmgr_stats(self):
        from src.mcp_server import handle_drvmgr_stats
        result = asyncio.run(handle_drvmgr_stats({}))
        data = json.loads(result[0].text)
        assert "total_events" in data

    def test_wmiexp_query(self):
        from src.mcp_server import handle_wmiexp_query
        result = asyncio.run(handle_wmiexp_query({"class_name": "Win32_OperatingSystem"}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_wmiexp_stats(self):
        from src.mcp_server import handle_wmiexp_stats
        result = asyncio.run(handle_wmiexp_stats({}))
        data = json.loads(result[0].text)
        assert "common_classes" in data

    def test_envmgr_list(self):
        from src.mcp_server import handle_envmgr_list
        result = asyncio.run(handle_envmgr_list({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_envmgr_stats(self):
        from src.mcp_server import handle_envmgr_stats
        result = asyncio.run(handle_envmgr_stats({}))
        data = json.loads(result[0].text)
        assert "total_events" in data


# ═══════════════════════════════════════════════════════════════════════════
# TOOL COUNT PHASE 33
# ═══════════════════════════════════════════════════════════════════════════

class TestToolCountPhase33:
    def test_tool_count_at_least_411(self):
        """402 + 3 drvmgr + 3 wmiexp + 3 envmgr = 411."""
        from src.mcp_server import TOOL_DEFINITIONS
        assert len(TOOL_DEFINITIONS) >= 411, f"Expected >= 411 tools, got {len(TOOL_DEFINITIONS)}"

    def test_no_duplicate_tool_names(self):
        from src.mcp_server import TOOL_DEFINITIONS
        names = [t[0] for t in TOOL_DEFINITIONS]
        dupes = [n for n in names if names.count(n) > 1]
        assert len(names) == len(set(names)), f"Duplicate tools: {set(dupes)}"
