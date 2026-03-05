"""Phase 34 Tests — Pagefile Manager, Time Sync Manager, Disk Health, MCP Handlers."""

import asyncio
import json
import pytest


# ═══════════════════════════════════════════════════════════════════════════
# PAGEFILE MANAGER
# ═══════════════════════════════════════════════════════════════════════════

class TestPagefileManager:
    @staticmethod
    def _make():
        from src.pagefile_manager import PagefileManager
        return PagefileManager()

    def test_singleton_exists(self):
        from src.pagefile_manager import pagefile_manager
        assert pagefile_manager is not None

    def test_get_events_empty(self):
        pm = self._make()
        events = pm.get_events()
        assert isinstance(events, list)
        assert len(events) == 0

    def test_record_event(self):
        pm = self._make()
        pm._record("test", True, "ok")
        events = pm.get_events()
        assert len(events) == 1

    def test_pagefile_info_dataclass(self):
        from src.pagefile_manager import PagefileInfo
        pi = PagefileInfo(name="C:\\pagefile.sys", allocated_mb=4096)
        assert pi.name == "C:\\pagefile.sys"
        assert pi.current_usage_mb == 0

    def test_pagefile_event_dataclass(self):
        from src.pagefile_manager import PagefileEvent
        e = PagefileEvent(action="get_usage")
        assert e.action == "get_usage"
        assert e.success is True

    def test_get_stats_structure(self):
        pm = self._make()
        stats = pm.get_stats()
        assert "total_events" in stats

    def test_get_usage_returns_list(self):
        pm = self._make()
        result = pm.get_usage()
        assert isinstance(result, list)

    def test_get_settings_returns_list(self):
        pm = self._make()
        result = pm.get_settings()
        assert isinstance(result, list)

    def test_get_virtual_memory_returns_dict(self):
        pm = self._make()
        result = pm.get_virtual_memory()
        assert isinstance(result, dict)


# ═══════════════════════════════════════════════════════════════════════════
# TIME SYNC MANAGER
# ═══════════════════════════════════════════════════════════════════════════

class TestTimeSyncManager:
    @staticmethod
    def _make():
        from src.time_sync_manager import TimeSyncManager
        return TimeSyncManager()

    def test_singleton_exists(self):
        from src.time_sync_manager import time_sync_manager
        assert time_sync_manager is not None

    def test_get_events_empty(self):
        tsm = self._make()
        events = tsm.get_events()
        assert isinstance(events, list)
        assert len(events) == 0

    def test_record_event(self):
        tsm = self._make()
        tsm._record("test", True, "ok")
        events = tsm.get_events()
        assert len(events) == 1

    def test_timesync_info_dataclass(self):
        from src.time_sync_manager import TimeSyncInfo
        ti = TimeSyncInfo(source="time.windows.com", stratum=3)
        assert ti.source == "time.windows.com"
        assert ti.last_sync == ""

    def test_timesync_event_dataclass(self):
        from src.time_sync_manager import TimeSyncEvent
        e = TimeSyncEvent(action="status")
        assert e.action == "status"
        assert e.success is True

    def test_get_stats_structure(self):
        tsm = self._make()
        stats = tsm.get_stats()
        assert "total_events" in stats

    def test_parse_w32tm(self):
        tsm = self._make()
        sample = "Leap Indicator: 0\nStratum: 3\nSource: time.windows.com\n"
        info = tsm._parse_w32tm(sample)
        assert "stratum" in info
        assert "source" in info

    def test_parse_peers_empty(self):
        tsm = self._make()
        result = tsm._parse_peers("")
        assert result == []

    def test_parse_peers_with_data(self):
        tsm = self._make()
        sample = "Peer: time.windows.com\nState: Active\n"
        result = tsm._parse_peers(sample)
        assert len(result) == 1
        assert result[0]["peer"] == "time.windows.com"

    def test_get_source_returns_dict(self):
        tsm = self._make()
        result = tsm.get_source()
        assert isinstance(result, dict)
        assert "source" in result


# ═══════════════════════════════════════════════════════════════════════════
# DISK HEALTH
# ═══════════════════════════════════════════════════════════════════════════

class TestDiskHealth:
    @staticmethod
    def _make():
        from src.disk_health import DiskHealthMonitor
        return DiskHealthMonitor()

    def test_singleton_exists(self):
        from src.disk_health import disk_health
        assert disk_health is not None

    def test_get_events_empty(self):
        dh = self._make()
        events = dh.get_events()
        assert isinstance(events, list)
        assert len(events) == 0

    def test_record_event(self):
        dh = self._make()
        dh._record("test", True, "ok")
        events = dh.get_events()
        assert len(events) == 1

    def test_disk_info_dataclass(self):
        from src.disk_health import DiskInfo
        di = DiskInfo(friendly_name="Samsung SSD 970", media_type="SSD")
        assert di.friendly_name == "Samsung SSD 970"
        assert di.health_status == ""

    def test_disk_health_event_dataclass(self):
        from src.disk_health import DiskHealthEvent
        e = DiskHealthEvent(action="list")
        assert e.action == "list"
        assert e.success is True

    def test_get_stats_structure(self):
        dh = self._make()
        stats = dh.get_stats()
        assert "total_events" in stats

    def test_health_summary_with_mock(self):
        dh = self._make()
        dh.list_disks = lambda: [
            {"friendly_name": "SSD", "health_status": "Healthy"},
            {"friendly_name": "HDD", "health_status": "Healthy"},
        ]
        summary = dh.get_health_summary()
        assert summary["total_disks"] == 2
        assert summary["healthy"] == 2
        assert summary["unhealthy"] == 0
        assert summary["all_healthy"] is True

    def test_health_summary_unhealthy(self):
        dh = self._make()
        dh.list_disks = lambda: [
            {"friendly_name": "SSD", "health_status": "Healthy"},
            {"friendly_name": "HDD", "health_status": "Warning"},
        ]
        summary = dh.get_health_summary()
        assert summary["unhealthy"] == 1
        assert summary["all_healthy"] is False

    def test_health_summary_empty(self):
        dh = self._make()
        dh.list_disks = lambda: []
        summary = dh.get_health_summary()
        assert summary["total_disks"] == 0
        assert summary["all_healthy"] is False


# ═══════════════════════════════════════════════════════════════════════════
# MCP HANDLERS — Phase 34
# ═══════════════════════════════════════════════════════════════════════════

class TestMCPHandlersPhase34:
    def test_pgfile_usage(self):
        from src.mcp_server import handle_pgfile_usage
        result = asyncio.run(handle_pgfile_usage({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_pgfile_stats(self):
        from src.mcp_server import handle_pgfile_stats
        result = asyncio.run(handle_pgfile_stats({}))
        data = json.loads(result[0].text)
        assert "total_events" in data

    def test_timesync_status(self):
        from src.mcp_server import handle_timesync_status
        result = asyncio.run(handle_timesync_status({}))
        data = json.loads(result[0].text)
        assert isinstance(data, dict)

    def test_timesync_stats(self):
        from src.mcp_server import handle_timesync_stats
        result = asyncio.run(handle_timesync_stats({}))
        data = json.loads(result[0].text)
        assert "total_events" in data

    def test_diskhlth_list(self):
        from src.mcp_server import handle_diskhlth_list
        result = asyncio.run(handle_diskhlth_list({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_diskhlth_stats(self):
        from src.mcp_server import handle_diskhlth_stats
        result = asyncio.run(handle_diskhlth_stats({}))
        data = json.loads(result[0].text)
        assert "total_events" in data


# ═══════════════════════════════════════════════════════════════════════════
# TOOL COUNT PHASE 34
# ═══════════════════════════════════════════════════════════════════════════

class TestToolCountPhase34:
    def test_tool_count_at_least_420(self):
        """411 + 3 pgfile + 3 timesync + 3 diskhlth = 420."""
        from src.mcp_server import TOOL_DEFINITIONS
        assert len(TOOL_DEFINITIONS) >= 420, f"Expected >= 420 tools, got {len(TOOL_DEFINITIONS)}"

    def test_no_duplicate_tool_names(self):
        from src.mcp_server import TOOL_DEFINITIONS
        names = [t[0] for t in TOOL_DEFINITIONS]
        dupes = [n for n in names if names.count(n) > 1]
        assert len(names) == len(set(names)), f"Duplicate tools: {set(dupes)}"
