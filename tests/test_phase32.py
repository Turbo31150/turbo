"""Phase 32 Tests — Locale Manager, GPU Monitor, Share Manager, MCP Handlers."""

import asyncio
import json
import pytest


# ═══════════════════════════════════════════════════════════════════════════
# LOCALE MANAGER
# ═══════════════════════════════════════════════════════════════════════════

class TestLocaleManager:
    @staticmethod
    def _make():
        from src.locale_manager import LocaleManager
        return LocaleManager()

    def test_singleton_exists(self):
        from src.locale_manager import locale_manager
        assert locale_manager is not None

    def test_get_events_empty(self):
        lm = self._make()
        events = lm.get_events()
        assert isinstance(events, list)
        assert len(events) == 0

    def test_record_event(self):
        lm = self._make()
        lm._record("test", True, "ok")
        events = lm.get_events()
        assert len(events) == 1

    def test_locale_info_dataclass(self):
        from src.locale_manager import LocaleInfo
        li = LocaleInfo(name="fr-FR", display_name="French (France)")
        assert li.name == "fr-FR"
        assert li.language_tag == ""

    def test_locale_event_dataclass(self):
        from src.locale_manager import LocaleEvent
        e = LocaleEvent(action="get_locale")
        assert e.action == "get_locale"
        assert e.success is True

    def test_get_stats_structure(self):
        lm = self._make()
        stats = lm.get_stats()
        assert "total_events" in stats
        assert "system_locale" in stats

    def test_get_system_locale_returns_dict(self):
        lm = self._make()
        result = lm.get_system_locale()
        assert isinstance(result, dict)
        assert "name" in result

    def test_get_timezone_returns_dict(self):
        lm = self._make()
        result = lm.get_timezone()
        assert isinstance(result, dict)
        assert "id" in result

    def test_get_date_format_returns_dict(self):
        lm = self._make()
        result = lm.get_date_format()
        assert isinstance(result, dict)

    def test_get_user_language_returns_list(self):
        lm = self._make()
        result = lm.get_user_language()
        assert isinstance(result, list)

    def test_get_keyboard_layouts_returns_list(self):
        lm = self._make()
        result = lm.get_keyboard_layouts()
        assert isinstance(result, list)


# ═══════════════════════════════════════════════════════════════════════════
# GPU MONITOR
# ═══════════════════════════════════════════════════════════════════════════

class TestGPUMonitor:
    @staticmethod
    def _make():
        from src.gpu_monitor import GPUMonitor
        return GPUMonitor()

    def test_singleton_exists(self):
        from src.gpu_monitor import gpu_monitor
        assert gpu_monitor is not None

    def test_get_events_empty(self):
        gm = self._make()
        events = gm.get_events()
        assert isinstance(events, list)
        assert len(events) == 0

    def test_record_event(self):
        gm = self._make()
        gm._record("test", True, "ok")
        events = gm.get_events()
        assert len(events) == 1

    def test_gpu_info_dataclass(self):
        from src.gpu_monitor import GPUInfo
        gi = GPUInfo(name="RTX 2060", vram_total_mb=6144)
        assert gi.name == "RTX 2060"
        assert gi.driver_version == ""
        assert gi.temperature == 0

    def test_gpu_event_dataclass(self):
        from src.gpu_monitor import GPUEvent
        e = GPUEvent(action="snapshot")
        assert e.action == "snapshot"
        assert e.success is True

    def test_get_history_empty(self):
        gm = self._make()
        history = gm.get_history()
        assert isinstance(history, list)
        assert len(history) == 0

    def test_get_stats_structure(self):
        gm = self._make()
        stats = gm.get_stats()
        assert "total_events" in stats
        assert "history_size" in stats

    def test_snapshot_returns_dict(self):
        gm = self._make()
        snap = gm.snapshot()
        assert isinstance(snap, dict)
        assert "timestamp" in snap
        assert "gpu_count" in snap
        assert "gpus" in snap

    def test_snapshot_stored_in_history(self):
        gm = self._make()
        gm.snapshot()
        history = gm.get_history()
        assert len(history) == 1

    def test_history_limit(self):
        gm = self._make()
        gm._max_history = 3
        for _ in range(5):
            gm.snapshot()
        assert len(gm.get_history()) == 3


# ═══════════════════════════════════════════════════════════════════════════
# SHARE MANAGER
# ═══════════════════════════════════════════════════════════════════════════

class TestShareManager:
    @staticmethod
    def _make():
        from src.share_manager import ShareManager
        return ShareManager()

    def test_singleton_exists(self):
        from src.share_manager import share_manager
        assert share_manager is not None

    def test_get_events_empty(self):
        sm = self._make()
        events = sm.get_events()
        assert isinstance(events, list)
        assert len(events) == 0

    def test_record_event(self):
        sm = self._make()
        sm._record("test", True, "ok")
        events = sm.get_events()
        assert len(events) == 1

    def test_share_info_dataclass(self):
        from src.share_manager import ShareInfo
        si = ShareInfo(name="Documents", path="/\Users/Public")
        assert si.name == "Documents"
        assert si.remark == ""
        assert si.share_type == ""

    def test_share_event_dataclass(self):
        from src.share_manager import ShareEvent
        e = ShareEvent(action="list")
        assert e.action == "list"
        assert e.success is True

    def test_get_stats_structure(self):
        sm = self._make()
        stats = sm.get_stats()
        assert "total_events" in stats

    def test_search_with_mock(self):
        sm = self._make()
        sm.list_shares = lambda: [
            {"name": "Documents", "path": "/\Docs"},
            {"name": "Music", "path": "/\Music"},
        ]
        results = sm.search_shares("doc")
        assert len(results) == 1

    def test_search_no_match(self):
        sm = self._make()
        sm.list_shares = lambda: [
            {"name": "Documents", "path": "/\Docs"},
        ]
        results = sm.search_shares("video")
        assert len(results) == 0

    def test_list_mapped_drives_returns_list(self):
        sm = self._make()
        result = sm.list_mapped_drives()
        assert isinstance(result, list)


# ═══════════════════════════════════════════════════════════════════════════
# MCP HANDLERS — Phase 32
# ═══════════════════════════════════════════════════════════════════════════

class TestMCPHandlersPhase32:
    def test_localemgr_info(self):
        from src.mcp_server import handle_localemgr_info
        result = asyncio.run(handle_localemgr_info({}))
        data = json.loads(result[0].text)
        assert "system_locale" in data

    def test_localemgr_stats(self):
        from src.mcp_server import handle_localemgr_stats
        result = asyncio.run(handle_localemgr_stats({}))
        data = json.loads(result[0].text)
        assert "total_events" in data

    def test_gpumon_snapshot(self):
        from src.mcp_server import handle_gpumon_snapshot
        result = asyncio.run(handle_gpumon_snapshot({}))
        data = json.loads(result[0].text)
        assert "gpu_count" in data

    def test_gpumon_stats(self):
        from src.mcp_server import handle_gpumon_stats
        result = asyncio.run(handle_gpumon_stats({}))
        data = json.loads(result[0].text)
        assert "total_events" in data

    def test_sharemgr_list(self):
        from src.mcp_server import handle_sharemgr_list
        result = asyncio.run(handle_sharemgr_list({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_sharemgr_stats(self):
        from src.mcp_server import handle_sharemgr_stats
        result = asyncio.run(handle_sharemgr_stats({}))
        data = json.loads(result[0].text)
        assert "total_events" in data


# ═══════════════════════════════════════════════════════════════════════════
# TOOL COUNT PHASE 32
# ═══════════════════════════════════════════════════════════════════════════

class TestToolCountPhase32:
    def test_tool_count_at_least_402(self):
        """393 + 3 localemgr + 3 gpumon + 3 sharemgr = 402."""
        from src.mcp_server import TOOL_DEFINITIONS
        assert len(TOOL_DEFINITIONS) >= 402, f"Expected >= 402 tools, got {len(TOOL_DEFINITIONS)}"

    def test_no_duplicate_tool_names(self):
        from src.mcp_server import TOOL_DEFINITIONS
        names = [t[0] for t in TOOL_DEFINITIONS]
        dupes = [n for n in names if names.count(n) > 1]
        assert len(names) == len(set(names)), f"Duplicate tools: {set(dupes)}"
