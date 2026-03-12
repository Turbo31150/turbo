"""Phase 36 Tests — Memory Diagnostics, System Info Collector, Crash Dump Reader, MCP Handlers."""

import asyncio
import json
import pytest


# ═══════════════════════════════════════════════════════════════════════════
# MEMORY DIAGNOSTICS
# ═══════════════════════════════════════════════════════════════════════════

class TestMemoryDiagnostics:
    @staticmethod
    def _make():
        from src.memory_diagnostics import MemoryDiagnostics
        return MemoryDiagnostics()

    def test_singleton_exists(self):
        from src.memory_diagnostics import memory_diagnostics
        assert memory_diagnostics is not None

    def test_get_events_empty(self):
        md = self._make()
        assert md.get_events() == []

    def test_record_event(self):
        md = self._make()
        md._record("test", True, "ok")
        assert len(md.get_events()) == 1

    def test_ram_module_dataclass(self):
        from src.memory_diagnostics import RAMModule
        rm = RAMModule(bank="BANK0", capacity_gb=8.0, speed_mhz=3200)
        assert rm.bank == "BANK0"
        assert rm.manufacturer == ""

    def test_memdiag_event_dataclass(self):
        from src.memory_diagnostics import MemDiagEvent
        e = MemDiagEvent(action="list")
        assert e.success is True

    def test_memory_types_mapping(self):
        from src.memory_diagnostics import _MEMORY_TYPES
        assert _MEMORY_TYPES[26] == "DDR4"
        assert _MEMORY_TYPES[34] == "DDR5"

    def test_get_stats_structure(self):
        md = self._make()
        stats = md.get_stats()
        assert "total_events" in stats

    def test_summary_with_mock(self):
        md = self._make()
        md.list_modules = lambda: [
            {"bank": "B0", "capacity_gb": 8.0, "speed_mhz": 3200, "memory_type": "DDR4"},
            {"bank": "B1", "capacity_gb": 8.0, "speed_mhz": 3200, "memory_type": "DDR4"},
        ]
        summary = md.get_summary()
        assert summary["total_gb"] == 16.0
        assert summary["module_count"] == 2
        assert summary["max_speed_mhz"] == 3200

    def test_summary_empty(self):
        md = self._make()
        md.list_modules = lambda: []
        summary = md.get_summary()
        assert summary["total_gb"] == 0
        assert summary["module_count"] == 0


# ═══════════════════════════════════════════════════════════════════════════
# SYSTEM INFO COLLECTOR
# ═══════════════════════════════════════════════════════════════════════════

class TestSystemInfoCollector:
    @staticmethod
    def _make():
        from src.system_info_collector import SystemInfoCollector
        return SystemInfoCollector()

    def test_singleton_exists(self):
        from src.system_info_collector import system_info_collector
        assert system_info_collector is not None

    def test_get_events_empty(self):
        sic = self._make()
        assert sic.get_events() == []

    def test_record_event(self):
        sic = self._make()
        sic._record("test", True, "ok")
        assert len(sic.get_events()) == 1

    def test_system_profile_dataclass(self):
        from src.system_info_collector import SystemProfile
        sp = SystemProfile(hostname="PC", os_name="Windows 11")
        assert sp.hostname == "PC"
        assert sp.cpu == ""

    def test_sysinfo_event_dataclass(self):
        from src.system_info_collector import SysInfoEvent
        e = SysInfoEvent(action="profile")
        assert e.success is True

    def test_get_stats_structure(self):
        sic = self._make()
        stats = sic.get_stats()
        assert "total_events" in stats

    def test_get_os_info_returns_dict(self):
        sic = self._make()
        result = sic.get_os_info()
        assert isinstance(result, dict)

    def test_get_cpu_info_returns_list(self):
        sic = self._make()
        result = sic.get_cpu_info()
        assert isinstance(result, list)

    def test_get_full_profile_structure(self):
        sic = self._make()
        profile = sic.get_full_profile()
        assert "os" in profile
        assert "cpu" in profile
        assert "bios" in profile
        assert "computer" in profile


# ═══════════════════════════════════════════════════════════════════════════
# CRASH DUMP READER
# ═══════════════════════════════════════════════════════════════════════════

class TestCrashDumpReader:
    @staticmethod
    def _make():
        from src.crash_dump_reader import CrashDumpReader
        return CrashDumpReader()

    def test_singleton_exists(self):
        from src.crash_dump_reader import crash_dump_reader
        assert crash_dump_reader is not None

    def test_get_events_empty(self):
        cdr = self._make()
        assert cdr.get_events() == []

    def test_record_event(self):
        cdr = self._make()
        cdr._record("test", True, "ok")
        assert len(cdr.get_events()) == 1

    def test_crash_dump_dataclass(self):
        from src.crash_dump_reader import CrashDump
        cd = CrashDump(filename="Mini.dmp", size_kb=256)
        assert cd.filename == "Mini.dmp"
        assert cd.created == ""

    def test_crash_event_dataclass(self):
        from src.crash_dump_reader import CrashEvent
        e = CrashEvent(action="list")
        assert e.success is True

    def test_get_stats_structure(self):
        cdr = self._make()
        stats = cdr.get_stats()
        assert "total_events" in stats

    def test_minidump_dir_constant(self):
        from src.crash_dump_reader import MINIDUMP_DIR
        assert "Minidump" in MINIDUMP_DIR

    def test_list_minidumps_returns_list(self):
        cdr = self._make()
        result = cdr.list_minidumps()
        assert isinstance(result, list)

    def test_crash_summary_structure(self):
        cdr = self._make()
        summary = cdr.get_crash_summary()
        assert "minidump_count" in summary
        assert "minidump_dir" in summary
        assert "minidump_dir_exists" in summary


# ═══════════════════════════════════════════════════════════════════════════
# MCP HANDLERS — Phase 36
# ═══════════════════════════════════════════════════════════════════════════

class TestMCPHandlersPhase36:
    def test_memdiag_modules(self):
        from src.mcp_server import handle_memdiag_modules
        result = asyncio.run(handle_memdiag_modules({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_memdiag_stats(self):
        from src.mcp_server import handle_memdiag_stats
        result = asyncio.run(handle_memdiag_stats({}))
        data = json.loads(result[0].text)
        assert "total_events" in data

    def test_sysinfo_profile(self):
        from src.mcp_server import handle_sysinfo_profile
        result = asyncio.run(handle_sysinfo_profile({}))
        data = json.loads(result[0].text)
        assert "os" in data

    def test_sysinfo_stats(self):
        from src.mcp_server import handle_sysinfo_stats
        result = asyncio.run(handle_sysinfo_stats({}))
        data = json.loads(result[0].text)
        assert "total_events" in data

    def test_crashdmp_list(self):
        from src.mcp_server import handle_crashdmp_list
        result = asyncio.run(handle_crashdmp_list({}))
        data = json.loads(result[0].text)
        assert "minidump_count" in data

    def test_crashdmp_stats(self):
        from src.mcp_server import handle_crashdmp_stats
        result = asyncio.run(handle_crashdmp_stats({}))
        data = json.loads(result[0].text)
        assert "total_events" in data


# ═══════════════════════════════════════════════════════════════════════════
# TOOL COUNT PHASE 36
# ═══════════════════════════════════════════════════════════════════════════

class TestToolCountPhase36:
    def test_tool_count_at_least_438(self):
        """429 + 3 memdiag + 3 sysinfo + 3 crashdmp = 438."""
        from src.mcp_server import TOOL_DEFINITIONS
        assert len(TOOL_DEFINITIONS) >= 438, f"Expected >= 438 tools, got {len(TOOL_DEFINITIONS)}"

    def test_no_duplicate_tool_names(self):
        from src.mcp_server import TOOL_DEFINITIONS
        names = [t[0] for t in TOOL_DEFINITIONS]
        dupes = [n for n in names if names.count(n) > 1]
        assert len(names) == len(set(names)), f"Duplicate tools: {set(dupes)}"
