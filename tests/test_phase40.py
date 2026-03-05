"""Phase 40 Tests — Screen Resolution, BIOS Settings, Performance Counters, MCP."""

import asyncio
import json
import pytest


# ═══════════════════════════════════════════════════════════════════════════
# SCREEN RESOLUTION MANAGER
# ═══════════════════════════════════════════════════════════════════════════

class TestScreenResolutionManager:
    @staticmethod
    def _make():
        from src.screen_resolution_manager import ScreenResolutionManager
        return ScreenResolutionManager()

    def test_singleton_exists(self):
        from src.screen_resolution_manager import screen_resolution_manager
        assert screen_resolution_manager is not None

    def test_get_events_empty(self):
        m = self._make()
        assert m.get_events() == []

    def test_record_event(self):
        m = self._make()
        m._record("test", True, "ok")
        assert len(m.get_events()) == 1

    def test_display_info_dataclass(self):
        from src.screen_resolution_manager import DisplayInfo
        di = DisplayInfo(name="NVIDIA RTX 2060", resolution="1920x1080", refresh_rate=60)
        assert di.resolution == "1920x1080"
        assert di.adapter_ram_mb == 0

    def test_get_stats_structure(self):
        m = self._make()
        assert "total_events" in m.get_stats()

    def test_search_with_mock(self):
        m = self._make()
        m.list_displays = lambda: [
            {"name": "NVIDIA GeForce RTX 2060", "resolution": "1920x1080"},
            {"name": "Intel UHD 630", "resolution": "1920x1080"},
        ]
        results = m.search("nvidia")
        assert len(results) == 1

    def test_get_primary_resolution_with_mock(self):
        m = self._make()
        m.list_displays = lambda: [{"name": "GPU", "resolution": "2560x1440"}]
        assert m.get_primary_resolution() == "2560x1440"

    def test_get_primary_resolution_empty(self):
        m = self._make()
        m.list_displays = lambda: []
        assert m.get_primary_resolution() == "Unknown"


# ═══════════════════════════════════════════════════════════════════════════
# BIOS SETTINGS
# ═══════════════════════════════════════════════════════════════════════════

class TestBIOSSettings:
    @staticmethod
    def _make():
        from src.bios_settings import BIOSSettingsReader
        return BIOSSettingsReader()

    def test_singleton_exists(self):
        from src.bios_settings import bios_settings
        assert bios_settings is not None

    def test_get_events_empty(self):
        m = self._make()
        assert m.get_events() == []

    def test_record_event(self):
        m = self._make()
        m._record("test", True, "ok")
        assert len(m.get_events()) == 1

    def test_bios_info_dataclass(self):
        from src.bios_settings import BIOSInfo
        bi = BIOSInfo(manufacturer="American Megatrends", version="F20")
        assert bi.manufacturer == "American Megatrends"
        assert bi.serial_number == ""

    def test_get_stats_structure(self):
        m = self._make()
        assert "total_events" in m.get_stats()

    def test_get_info_returns_dict(self):
        m = self._make()
        info = m.get_info()
        assert isinstance(info, dict)
        assert "manufacturer" in info

    def test_get_secure_boot_returns_dict(self):
        m = self._make()
        sb = m.get_secure_boot_status()
        assert isinstance(sb, dict)
        assert "secure_boot" in sb


# ═══════════════════════════════════════════════════════════════════════════
# PERFORMANCE COUNTER
# ═══════════════════════════════════════════════════════════════════════════

class TestPerformanceCounter:
    @staticmethod
    def _make():
        from src.performance_counter import PerformanceCounterManager
        return PerformanceCounterManager()

    def test_singleton_exists(self):
        from src.performance_counter import performance_counter
        assert performance_counter is not None

    def test_get_events_empty(self):
        m = self._make()
        assert m.get_events() == []

    def test_record_event(self):
        m = self._make()
        m._record("test", True, "ok")
        assert len(m.get_events()) == 1

    def test_counter_snapshot_dataclass(self):
        from src.performance_counter import CounterSnapshot
        cs = CounterSnapshot(timestamp=123.0, counters={"cpu": 50.0})
        assert cs.counters["cpu"] == 50.0

    def test_get_stats_structure(self):
        m = self._make()
        stats = m.get_stats()
        assert "total_events" in stats
        assert "history_size" in stats

    def test_get_history_empty(self):
        m = self._make()
        assert m.get_history() == []

    def test_counter_paths_defined(self):
        from src.performance_counter import COUNTER_PATHS
        assert len(COUNTER_PATHS) >= 4


# ═══════════════════════════════════════════════════════════════════════════
# MCP HANDLERS — Phase 40
# ═══════════════════════════════════════════════════════════════════════════

class TestMCPHandlersPhase40:
    def test_screenres_list(self):
        from src.mcp_server import handle_screenres_list
        result = asyncio.run(handle_screenres_list({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_screenres_stats(self):
        from src.mcp_server import handle_screenres_stats
        result = asyncio.run(handle_screenres_stats({}))
        data = json.loads(result[0].text)
        assert "total_events" in data

    def test_biosinfo_get(self):
        from src.mcp_server import handle_biosinfo_get
        result = asyncio.run(handle_biosinfo_get({}))
        data = json.loads(result[0].text)
        assert "manufacturer" in data

    def test_biosinfo_stats(self):
        from src.mcp_server import handle_biosinfo_stats
        result = asyncio.run(handle_biosinfo_stats({}))
        data = json.loads(result[0].text)
        assert "total_events" in data

    def test_perfctr_snapshot(self):
        from src.mcp_server import handle_perfmon_snapshot
        result = asyncio.run(handle_perfmon_snapshot({}))
        data = json.loads(result[0].text)
        assert "timestamp" in data

    def test_perfctr_stats(self):
        from src.mcp_server import handle_perfmon_stats
        result = asyncio.run(handle_perfmon_stats({}))
        data = json.loads(result[0].text)
        assert "total_events" in data


# ═══════════════════════════════════════════════════════════════════════════
# TOOL COUNT PHASE 40
# ═══════════════════════════════════════════════════════════════════════════

class TestToolCountPhase40:
    def test_tool_count_at_least_474(self):
        """465 + 3 screenres + 3 biosinfo + 3 perfctr = 474."""
        from src.mcp_server import TOOL_DEFINITIONS
        assert len(TOOL_DEFINITIONS) >= 474, f"Expected >= 474 tools, got {len(TOOL_DEFINITIONS)}"

    def test_no_duplicate_tool_names(self):
        from src.mcp_server import TOOL_DEFINITIONS
        names = [t[0] for t in TOOL_DEFINITIONS]
        dupes = [n for n in names if names.count(n) > 1]
        assert len(names) == len(set(names)), f"Duplicate tools: {set(dupes)}"
