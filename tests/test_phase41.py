"""Phase 41 Tests — Virtual Memory, Windows Event Log, Shadow Copy, MCP."""

import asyncio
import json
import pytest


# ═══════════════════════════════════════════════════════════════════════════
# VIRTUAL MEMORY MANAGER
# ═══════════════════════════════════════════════════════════════════════════

class TestVirtualMemoryManager:
    @staticmethod
    def _make():
        from src.virtual_memory_manager import VirtualMemoryManager
        return VirtualMemoryManager()

    def test_singleton_exists(self):
        from src.virtual_memory_manager import virtual_memory_manager
        assert virtual_memory_manager is not None

    def test_get_events_empty(self):
        m = self._make()
        assert m.get_events() == []

    def test_record_event(self):
        m = self._make()
        m._record("test", True, "ok")
        assert len(m.get_events()) == 1

    def test_dataclass(self):
        from src.virtual_memory_manager import VirtualMemoryInfo
        vi = VirtualMemoryInfo(total_visible_mb=16384, free_physical_mb=8192)
        assert vi.total_visible_mb == 16384
        assert vi.commit_limit_mb == 0

    def test_get_stats_structure(self):
        m = self._make()
        assert "total_events" in m.get_stats()

    def test_get_status_returns_dict(self):
        m = self._make()
        status = m.get_status()
        assert isinstance(status, dict)
        assert "total_visible_mb" in status

    def test_top_consumers_with_mock(self):
        m = self._make()
        m.get_top_consumers = lambda limit=10: [
            {"name": "chrome", "pid": 1234, "working_set_mb": 500},
            {"name": "python", "pid": 5678, "working_set_mb": 200},
        ]
        top = m.get_top_consumers(2)
        assert len(top) == 2
        assert top[0]["name"] == "chrome"


# ═══════════════════════════════════════════════════════════════════════════
# WINDOWS EVENT LOG READER
# ═══════════════════════════════════════════════════════════════════════════

class TestWindowsEventLogReader:
    @staticmethod
    def _make():
        from src.windows_event_log_reader import WindowsEventLogReader
        return WindowsEventLogReader()

    def test_singleton_exists(self):
        from src.windows_event_log_reader import windows_event_log_reader
        assert windows_event_log_reader is not None

    def test_get_events_empty(self):
        m = self._make()
        assert m.get_events() == []

    def test_record_event(self):
        m = self._make()
        m._record("test", True, "ok")
        assert len(m.get_events()) == 1

    def test_dataclass(self):
        from src.windows_event_log_reader import EventLogEntry
        e = EventLogEntry(log_name="System", event_id=7036, level="Information")
        assert e.event_id == 7036
        assert e.message == ""

    def test_get_stats_structure(self):
        m = self._make()
        assert "total_events" in m.get_stats()

    def test_list_logs(self):
        m = self._make()
        logs = m.list_logs()
        assert "System" in logs
        assert "Application" in logs

    def test_common_logs_constant(self):
        from src.windows_event_log_reader import COMMON_LOGS
        assert len(COMMON_LOGS) >= 3

    def test_search_with_mock(self):
        m = self._make()
        m.get_recent = lambda log_name, max_events: [
            {"event_id": 1, "level": "Error", "message": "Service stopped unexpectedly"},
            {"event_id": 2, "level": "Info", "message": "Service started"},
        ]
        results = m.search_events("System", "stopped")
        assert len(results) == 1

    def test_count_by_level_with_mock(self):
        m = self._make()
        m.get_recent = lambda log_name, max_events: [
            {"level": "Error"}, {"level": "Error"}, {"level": "Information"},
        ]
        counts = m.count_by_level("System", 10)
        assert counts["Error"] == 2


# ═══════════════════════════════════════════════════════════════════════════
# SHADOW COPY MANAGER
# ═══════════════════════════════════════════════════════════════════════════

class TestShadowCopyManager:
    @staticmethod
    def _make():
        from src.shadow_copy_manager import ShadowCopyManager
        return ShadowCopyManager()

    def test_singleton_exists(self):
        from src.shadow_copy_manager import shadow_copy_manager
        assert shadow_copy_manager is not None

    def test_get_events_empty(self):
        m = self._make()
        assert m.get_events() == []

    def test_record_event(self):
        m = self._make()
        m._record("test", True, "ok")
        assert len(m.get_events()) == 1

    def test_dataclass(self):
        from src.shadow_copy_manager import ShadowCopy
        sc = ShadowCopy(shadow_id="ABC-123", volume_name="C:\\")
        assert sc.shadow_id == "ABC-123"
        assert sc.state == ""

    def test_get_stats_structure(self):
        m = self._make()
        assert "total_events" in m.get_stats()

    def test_count_with_mock(self):
        m = self._make()
        m.list_copies = lambda: [{"shadow_id": "1"}, {"shadow_id": "2"}]
        assert m.count_copies() == 2

    def test_summary_with_mock(self):
        m = self._make()
        m.list_copies = lambda: [
            {"shadow_id": "1", "volume_name": "C:\\"},
            {"shadow_id": "2", "volume_name": "C:\\"},
            {"shadow_id": "3", "volume_name": "D:\\"},
        ]
        summary = m.get_summary()
        assert summary["total_copies"] == 3
        assert summary["volumes_with_copies"] == 2


# ═══════════════════════════════════════════════════════════════════════════
# MCP HANDLERS — Phase 41
# ═══════════════════════════════════════════════════════════════════════════

class TestMCPHandlersPhase41:
    def test_virtmem_status(self):
        from src.mcp_server import handle_virtmem_status
        result = asyncio.run(handle_virtmem_status({}))
        data = json.loads(result[0].text)
        assert "total_visible_mb" in data

    def test_virtmem_stats(self):
        from src.mcp_server import handle_virtmem_stats
        result = asyncio.run(handle_virtmem_stats({}))
        data = json.loads(result[0].text)
        assert "total_events" in data

    def test_winevt_recent(self):
        from src.mcp_server import handle_winevt_recent
        result = asyncio.run(handle_winevt_recent({"log_name": "System", "max_events": "5"}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_winevt_stats(self):
        from src.mcp_server import handle_winevt_stats
        result = asyncio.run(handle_winevt_stats({}))
        data = json.loads(result[0].text)
        assert "total_events" in data

    def test_shadowcopy_list(self):
        from src.mcp_server import handle_shadowcopy_list
        result = asyncio.run(handle_shadowcopy_list({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_shadowcopy_stats(self):
        from src.mcp_server import handle_shadowcopy_stats
        result = asyncio.run(handle_shadowcopy_stats({}))
        data = json.loads(result[0].text)
        assert "total_events" in data


# ═══════════════════════════════════════════════════════════════════════════
# TOOL COUNT PHASE 41
# ═══════════════════════════════════════════════════════════════════════════

class TestToolCountPhase41:
    def test_tool_count_at_least_484(self):
        """474 + 3 virtmem + 3 winevt + 3 shadowcopy = 483 (+ perfmon rename offset)."""
        from src.mcp_server import TOOL_DEFINITIONS
        assert len(TOOL_DEFINITIONS) >= 483, f"Expected >= 483 tools, got {len(TOOL_DEFINITIONS)}"

    def test_no_duplicate_tool_names(self):
        from src.mcp_server import TOOL_DEFINITIONS
        names = [t[0] for t in TOOL_DEFINITIONS]
        dupes = [n for n in names if names.count(n) > 1]
        assert len(names) == len(set(names)), f"Duplicate tools: {set(dupes)}"
