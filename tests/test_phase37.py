"""Phase 37 Tests — Hotfix Manager, Volume Manager, Defender Status, MCP Handlers."""

import asyncio
import json
import pytest


# ═══════════════════════════════════════════════════════════════════════════
# HOTFIX MANAGER
# ═══════════════════════════════════════════════════════════════════════════

class TestHotfixManager:
    @staticmethod
    def _make():
        from src.hotfix_manager import HotfixManager
        return HotfixManager()

    def test_singleton_exists(self):
        from src.hotfix_manager import hotfix_manager
        assert hotfix_manager is not None

    def test_get_events_empty(self):
        hm = self._make()
        assert hm.get_events() == []

    def test_record_event(self):
        hm = self._make()
        hm._record("test", True, "ok")
        assert len(hm.get_events()) == 1

    def test_hotfix_info_dataclass(self):
        from src.hotfix_manager import HotfixInfo
        hi = HotfixInfo(hotfix_id="KB5001234", description="Security Update")
        assert hi.hotfix_id == "KB5001234"
        assert hi.installed_on == ""

    def test_hotfix_event_dataclass(self):
        from src.hotfix_manager import HotfixEvent
        e = HotfixEvent(action="list")
        assert e.success is True

    def test_get_stats_structure(self):
        hm = self._make()
        assert "total_events" in hm.get_stats()

    def test_search_with_mock(self):
        hm = self._make()
        hm.list_hotfixes = lambda: [
            {"hotfix_id": "KB5001234", "description": "Security Update"},
            {"hotfix_id": "KB5005678", "description": "Quality Update"},
        ]
        results = hm.search("KB500123")
        assert len(results) == 1

    def test_count_by_type_with_mock(self):
        hm = self._make()
        hm.list_hotfixes = lambda: [
            {"hotfix_id": "A", "description": "Security Update"},
            {"hotfix_id": "B", "description": "Security Update"},
            {"hotfix_id": "C", "description": "Update"},
        ]
        counts = hm.count_by_type()
        assert counts["Security Update"] == 2

    def test_get_latest_with_mock(self):
        hm = self._make()
        hm.list_hotfixes = lambda: [
            {"hotfix_id": "A", "installed_on": "2026-01-01"},
            {"hotfix_id": "B", "installed_on": "2026-03-01"},
            {"hotfix_id": "C", "installed_on": "2026-02-01"},
        ]
        latest = hm.get_latest(2)
        assert len(latest) == 2
        assert latest[0]["hotfix_id"] == "B"


# ═══════════════════════════════════════════════════════════════════════════
# VOLUME MANAGER
# ═══════════════════════════════════════════════════════════════════════════

class TestVolumeManager:
    @staticmethod
    def _make():
        from src.volume_manager import VolumeManager
        return VolumeManager()

    def test_singleton_exists(self):
        from src.volume_manager import volume_manager
        assert volume_manager is not None

    def test_get_events_empty(self):
        vm = self._make()
        assert vm.get_events() == []

    def test_record_event(self):
        vm = self._make()
        vm._record("test", True, "ok")
        assert len(vm.get_events()) == 1

    def test_volume_info_dataclass(self):
        from src.volume_manager import VolumeInfo
        vi = VolumeInfo(drive_letter="C", file_system="NTFS", size_gb=476.0)
        assert vi.drive_letter == "C"
        assert vi.free_gb == 0.0

    def test_volume_event_dataclass(self):
        from src.volume_manager import VolumeEvent
        e = VolumeEvent(action="list")
        assert e.success is True

    def test_get_stats_structure(self):
        vm = self._make()
        assert "total_events" in vm.get_stats()

    def test_space_summary_with_mock(self):
        vm = self._make()
        vm.list_volumes = lambda: [
            {"drive_letter": "C", "size_gb": 476, "free_gb": 82},
            {"drive_letter": "F", "size_gb": 446, "free_gb": 104},
        ]
        summary = vm.get_space_summary()
        assert summary["volume_count"] == 2
        assert summary["total_gb"] == 922
        assert summary["free_gb"] == 186

    def test_search_with_mock(self):
        vm = self._make()
        vm.list_volumes = lambda: [
            {"drive_letter": "C", "label": "Windows"},
            {"drive_letter": "F", "label": "Data"},
        ]
        results = vm.search("data")
        assert len(results) == 1

    def test_list_partitions_returns_list(self):
        vm = self._make()
        result = vm.list_partitions()
        assert isinstance(result, list)


# ═══════════════════════════════════════════════════════════════════════════
# DEFENDER STATUS
# ═══════════════════════════════════════════════════════════════════════════

class TestDefenderStatus:
    @staticmethod
    def _make():
        from src.defender_status import DefenderStatus
        return DefenderStatus()

    def test_singleton_exists(self):
        from src.defender_status import defender_status
        assert defender_status is not None

    def test_get_events_empty(self):
        ds = self._make()
        assert ds.get_events() == []

    def test_record_event(self):
        ds = self._make()
        ds._record("test", True, "ok")
        assert len(ds.get_events()) == 1

    def test_defender_info_dataclass(self):
        from src.defender_status import DefenderInfo
        di = DefenderInfo(realtime_enabled=True, signature_version="1.400.0")
        assert di.realtime_enabled is True
        assert di.last_scan == ""

    def test_defender_event_dataclass(self):
        from src.defender_status import DefenderEvent
        e = DefenderEvent(action="status")
        assert e.success is True

    def test_get_stats_structure(self):
        ds = self._make()
        assert "total_events" in ds.get_stats()

    def test_get_status_returns_dict(self):
        ds = self._make()
        result = ds.get_status()
        assert isinstance(result, dict)

    def test_is_protected_with_mock(self):
        ds = self._make()
        ds.get_status = lambda: {
            "antivirus_enabled": True,
            "realtime_protection": True,
        }
        assert ds.is_protected() is True

    def test_is_not_protected_with_mock(self):
        ds = self._make()
        ds.get_status = lambda: {
            "antivirus_enabled": True,
            "realtime_protection": False,
        }
        assert ds.is_protected() is False

    def test_get_threat_history_returns_list(self):
        ds = self._make()
        result = ds.get_threat_history()
        assert isinstance(result, list)


# ═══════════════════════════════════════════════════════════════════════════
# MCP HANDLERS — Phase 37
# ═══════════════════════════════════════════════════════════════════════════

class TestMCPHandlersPhase37:
    def test_hotfix_list(self):
        from src.mcp_server import handle_hotfix_list
        result = asyncio.run(handle_hotfix_list({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_hotfix_stats(self):
        from src.mcp_server import handle_hotfix_stats
        result = asyncio.run(handle_hotfix_stats({}))
        data = json.loads(result[0].text)
        assert "total_events" in data

    def test_volmgr_list(self):
        from src.mcp_server import handle_volmgr_list
        result = asyncio.run(handle_volmgr_list({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_volmgr_stats(self):
        from src.mcp_server import handle_volmgr_stats
        result = asyncio.run(handle_volmgr_stats({}))
        data = json.loads(result[0].text)
        assert "total_events" in data

    def test_defender_status(self):
        from src.mcp_server import handle_defender_status
        result = asyncio.run(handle_defender_status({}))
        data = json.loads(result[0].text)
        assert isinstance(data, dict)

    def test_defender_stats(self):
        from src.mcp_server import handle_defender_stats
        result = asyncio.run(handle_defender_stats({}))
        data = json.loads(result[0].text)
        assert "total_events" in data


# ═══════════════════════════════════════════════════════════════════════════
# TOOL COUNT PHASE 37
# ═══════════════════════════════════════════════════════════════════════════

class TestToolCountPhase37:
    def test_tool_count_at_least_447(self):
        """438 + 3 hotfix + 3 volmgr + 3 defender = 447."""
        from src.mcp_server import TOOL_DEFINITIONS
        assert len(TOOL_DEFINITIONS) >= 447, f"Expected >= 447 tools, got {len(TOOL_DEFINITIONS)}"

    def test_no_duplicate_tool_names(self):
        from src.mcp_server import TOOL_DEFINITIONS
        names = [t[0] for t in TOOL_DEFINITIONS]
        dupes = [n for n in names if names.count(n) > 1]
        assert len(names) == len(set(names)), f"Duplicate tools: {set(dupes)}"
