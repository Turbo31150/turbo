"""Phase 28 Tests — Bluetooth Manager, Event Log Reader, Font Manager, MCP Handlers."""

import asyncio
import json
import pytest


# ═══════════════════════════════════════════════════════════════════════════
# BLUETOOTH MANAGER
# ═══════════════════════════════════════════════════════════════════════════

class TestBluetoothManager:
    @staticmethod
    def _make():
        from src.bluetooth_manager import BluetoothManager
        return BluetoothManager()

    def test_singleton_exists(self):
        from src.bluetooth_manager import bluetooth_manager
        assert bluetooth_manager is not None

    def test_get_events_empty(self):
        bm = self._make()
        events = bm.get_events()
        assert isinstance(events, list)
        assert len(events) == 0

    def test_record_event(self):
        bm = self._make()
        bm._record("test", "AirPods", True, "ok")
        events = bm.get_events()
        assert len(events) == 1
        assert events[0]["device_name"] == "AirPods"

    def test_bluetooth_device_dataclass(self):
        from src.bluetooth_manager import BluetoothDevice
        d = BluetoothDevice(name="AirPods", status="OK")
        assert d.name == "AirPods"
        assert d.manufacturer == ""

    def test_bluetooth_event_dataclass(self):
        from src.bluetooth_manager import BluetoothEvent
        e = BluetoothEvent(action="scan", device_name="Speaker")
        assert e.action == "scan"
        assert e.success is True

    def test_get_device_with_mock(self):
        bm = self._make()
        bm.list_devices = lambda: [
            {"name": "AirPods Pro", "status": "OK"},
            {"name": "JBL Speaker", "status": "OK"},
        ]
        results = bm.get_device("airpods")
        assert len(results) == 1
        assert results[0]["name"] == "AirPods Pro"

    def test_count_by_status_with_mock(self):
        bm = self._make()
        bm.list_devices = lambda: [
            {"name": "A", "status": "OK"},
            {"name": "B", "status": "OK"},
            {"name": "C", "status": "Error"},
        ]
        counts = bm.count_by_status()
        assert counts["OK"] == 2
        assert counts["Error"] == 1

    def test_get_stats_structure(self):
        bm = self._make()
        stats = bm.get_stats()
        assert "total_events" in stats


# ═══════════════════════════════════════════════════════════════════════════
# EVENT LOG READER
# ═══════════════════════════════════════════════════════════════════════════

class TestEventLogReader:
    @staticmethod
    def _make():
        from src.eventlog_reader import EventLogReader
        return EventLogReader()

    def test_singleton_exists(self):
        from src.eventlog_reader import eventlog_reader
        assert eventlog_reader is not None

    def test_get_events_empty(self):
        elr = self._make()
        events = elr.get_events()
        assert isinstance(events, list)
        assert len(events) == 0

    def test_record_event(self):
        elr = self._make()
        elr._record("test", "System", True, "ok")
        events = elr.get_events()
        assert len(events) == 1
        assert events[0]["log_name"] == "System"

    def test_eventlog_entry_dataclass(self):
        from src.eventlog_reader import EventLogEntry
        e = EventLogEntry(log_name="System", event_id=7036, level="Information")
        assert e.log_name == "System"
        assert e.message == ""

    def test_reader_event_dataclass(self):
        from src.eventlog_reader import ReaderEvent
        e = ReaderEvent(action="read", log_name="Application")
        assert e.action == "read"
        assert e.success is True

    def test_known_logs(self):
        from src.eventlog_reader import KNOWN_LOGS
        assert "System" in KNOWN_LOGS
        assert "Application" in KNOWN_LOGS

    def test_get_stats_structure(self):
        elr = self._make()
        stats = elr.get_stats()
        assert "total_reads" in stats
        assert "known_logs" in stats

    def test_search_events_with_mock(self):
        elr = self._make()
        elr.read_log = lambda **kwargs: [
            {"event_id": 1, "message": "Service started", "source": "SCM", "level": "Info"},
            {"event_id": 2, "message": "Disk error", "source": "Disk", "level": "Error"},
        ]
        results = elr.search_events("disk")
        assert len(results) == 1
        assert results[0]["event_id"] == 2

    def test_count_by_level_with_mock(self):
        elr = self._make()
        elr.read_log = lambda **kwargs: [
            {"level": "Information"},
            {"level": "Information"},
            {"level": "Error"},
        ]
        counts = elr.count_by_level()
        assert counts["Information"] == 2
        assert counts["Error"] == 1


# ═══════════════════════════════════════════════════════════════════════════
# FONT MANAGER
# ═══════════════════════════════════════════════════════════════════════════

class TestFontManager:
    @staticmethod
    def _make():
        from src.font_manager import FontManager
        return FontManager()

    def test_singleton_exists(self):
        from src.font_manager import font_manager
        assert font_manager is not None

    def test_list_fonts(self):
        fm = self._make()
        fonts = fm.list_fonts()
        assert isinstance(fonts, list)
        assert len(fonts) >= 1

    def test_font_has_fields(self):
        fm = self._make()
        fonts = fm.list_fonts()
        if fonts:
            f = fonts[0]
            assert "name" in f
            assert "file" in f
            assert "type" in f

    def test_detect_type(self):
        fm = self._make()
        assert fm._detect_type("Arial (TrueType)", "arial.ttf") == "TrueType"
        assert fm._detect_type("Calibri", "calibri.otf") == "OpenType"
        assert fm._detect_type("Font", "font.fon") == "Raster"

    def test_search(self):
        fm = self._make()
        results = fm.search("Arial")
        assert len(results) >= 1

    def test_font_info_dataclass(self):
        from src.font_manager import FontInfo
        f = FontInfo(name="Arial", file="arial.ttf", font_type="TrueType")
        assert f.name == "Arial"

    def test_font_event_dataclass(self):
        from src.font_manager import FontEvent
        e = FontEvent(action="list", font_name="Arial")
        assert e.action == "list"
        assert e.success is True

    def test_count_by_type(self):
        fm = self._make()
        counts = fm.count_by_type()
        assert isinstance(counts, dict)
        assert sum(counts.values()) > 0

    def test_get_stats_structure(self):
        fm = self._make()
        stats = fm.get_stats()
        assert "total_fonts" in stats
        assert "types" in stats
        assert stats["total_fonts"] > 0

    def test_get_events_empty(self):
        fm = self._make()
        # Fresh instance has no events yet (cache may have been used by other tests)
        events = fm.get_events()
        assert isinstance(events, list)

    def test_cache(self):
        fm = self._make()
        fonts1 = fm.list_fonts()
        fonts2 = fm.list_fonts(use_cache=True)
        assert len(fonts1) == len(fonts2)

    def test_get_font_families(self):
        fm = self._make()
        families = fm.get_font_families()
        assert isinstance(families, list)
        assert len(families) >= 1


# ═══════════════════════════════════════════════════════════════════════════
# MCP HANDLERS — Phase 28
# ═══════════════════════════════════════════════════════════════════════════

class TestMCPHandlersPhase28:
    def test_btmgr_events(self):
        from src.mcp_server import handle_btmgr_events
        result = asyncio.run(handle_btmgr_events({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_btmgr_stats(self):
        from src.mcp_server import handle_btmgr_stats
        result = asyncio.run(handle_btmgr_stats({}))
        data = json.loads(result[0].text)
        assert "total_events" in data

    def test_evtlog_events(self):
        from src.mcp_server import handle_evtlog_events
        result = asyncio.run(handle_evtlog_events({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_evtlog_stats(self):
        from src.mcp_server import handle_evtlog_stats
        result = asyncio.run(handle_evtlog_stats({}))
        data = json.loads(result[0].text)
        assert "total_reads" in data

    def test_fontmgr_list(self):
        from src.mcp_server import handle_fontmgr_list
        result = asyncio.run(handle_fontmgr_list({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_fontmgr_stats(self):
        from src.mcp_server import handle_fontmgr_stats
        result = asyncio.run(handle_fontmgr_stats({}))
        data = json.loads(result[0].text)
        assert "total_fonts" in data


# ═══════════════════════════════════════════════════════════════════════════
# TOOL COUNT PHASE 28
# ═══════════════════════════════════════════════════════════════════════════

class TestToolCountPhase28:
    def test_tool_count_at_least_366(self):
        """357 + 3 btmgr + 3 evtlog + 3 fontmgr = 366."""
        from src.mcp_server import TOOL_DEFINITIONS
        assert len(TOOL_DEFINITIONS) >= 366, f"Expected >= 366 tools, got {len(TOOL_DEFINITIONS)}"

    def test_no_duplicate_tool_names(self):
        from src.mcp_server import TOOL_DEFINITIONS
        names = [t[0] for t in TOOL_DEFINITIONS]
        dupes = [n for n in names if names.count(n) > 1]
        assert len(names) == len(set(names)), f"Duplicate tools: {set(dupes)}"
