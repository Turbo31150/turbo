"""Phase 26 Tests — WiFi Manager, Display Manager, USB Monitor, MCP Handlers."""

import asyncio
import json
import pytest


# ═══════════════════════════════════════════════════════════════════════════
# WIFI MANAGER
# ═══════════════════════════════════════════════════════════════════════════

class TestWiFiManager:
    @staticmethod
    def _make():
        from src.wifi_manager import WiFiManager
        return WiFiManager()

    def test_singleton_exists(self):
        from src.wifi_manager import wifi_manager
        assert wifi_manager is not None

    def test_get_events_empty(self):
        wm = self._make()
        events = wm.get_events()
        assert isinstance(events, list)
        assert len(events) == 0

    def test_record_event(self):
        wm = self._make()
        wm._record("test", "MySSID", True, "ok")
        events = wm.get_events()
        assert len(events) == 1
        assert events[0]["action"] == "test"
        assert events[0]["ssid"] == "MySSID"

    def test_wifi_network_dataclass(self):
        from src.wifi_manager import WiFiNetwork
        n = WiFiNetwork(ssid="Home", signal=85, auth="WPA2")
        assert n.ssid == "Home"
        assert n.signal == 85

    def test_wifi_event_dataclass(self):
        from src.wifi_manager import WiFiEvent
        e = WiFiEvent(action="scan", ssid="", success=True)
        assert e.action == "scan"

    def test_get_stats_structure(self):
        wm = self._make()
        stats = wm.get_stats()
        assert "total_events" in stats
        assert "connected" in stats

    def test_list_profiles(self):
        wm = self._make()
        profiles = wm.list_profiles()
        assert isinstance(profiles, list)

    def test_get_current(self):
        wm = self._make()
        current = wm.get_current()
        assert "connected" in current


# ═══════════════════════════════════════════════════════════════════════════
# DISPLAY MANAGER
# ═══════════════════════════════════════════════════════════════════════════

class TestDisplayManager:
    @staticmethod
    def _make():
        from src.display_manager import DisplayManager
        return DisplayManager()

    def test_singleton_exists(self):
        from src.display_manager import display_manager
        assert display_manager is not None

    def test_list_displays(self):
        dm = self._make()
        displays = dm.list_displays()
        assert isinstance(displays, list)
        assert len(displays) >= 1

    def test_display_has_fields(self):
        dm = self._make()
        displays = dm.list_displays()
        if displays:
            d = displays[0]
            assert "width" in d
            assert "height" in d
            assert "refresh_rate" in d
            assert d["width"] > 0

    def test_get_primary(self):
        dm = self._make()
        primary = dm.get_primary()
        assert "width" in primary
        assert primary["width"] > 0

    def test_get_screen_size(self):
        dm = self._make()
        size = dm.get_screen_size()
        assert size["width"] > 0
        assert size["height"] > 0

    def test_get_virtual_screen(self):
        dm = self._make()
        vs = dm.get_virtual_screen()
        assert vs["width"] > 0

    def test_get_monitor_count(self):
        dm = self._make()
        count = dm.get_monitor_count()
        assert count >= 1

    def test_get_dpi(self):
        dm = self._make()
        dpi = dm.get_dpi()
        assert "dpi_x" in dpi
        assert dpi["dpi_x"] > 0
        assert "scale" in dpi

    def test_get_supported_modes(self):
        dm = self._make()
        modes = dm.get_supported_modes()
        assert isinstance(modes, list)
        assert len(modes) >= 1
        assert modes[0]["width"] > 0

    def test_get_events_empty(self):
        dm = self._make()
        events = dm.get_events()
        assert isinstance(events, list)

    def test_get_stats(self):
        dm = self._make()
        stats = dm.get_stats()
        assert "display_count" in stats
        assert "monitor_count" in stats
        assert "dpi_scale" in stats
        assert stats["display_count"] >= 1

    def test_orientations_mapping(self):
        from src.display_manager import ORIENTATIONS
        assert ORIENTATIONS[0] == "landscape"
        assert ORIENTATIONS[1] == "portrait"


# ═══════════════════════════════════════════════════════════════════════════
# USB MONITOR
# ═══════════════════════════════════════════════════════════════════════════

class TestUSBMonitor:
    @staticmethod
    def _make():
        from src.usb_monitor import USBMonitor
        return USBMonitor()

    def test_singleton_exists(self):
        from src.usb_monitor import usb_monitor
        assert usb_monitor is not None

    def test_get_events_empty(self):
        um = self._make()
        events = um.get_events()
        assert isinstance(events, list)
        assert len(events) == 0

    def test_record_event(self):
        um = self._make()
        um._record("test", "USB Keyboard", True, "ok")
        events = um.get_events()
        assert len(events) == 1
        assert events[0]["device_name"] == "USB Keyboard"

    def test_get_stats(self):
        um = self._make()
        stats = um.get_stats()
        assert "total_events" in stats
        assert "known_devices" in stats
        assert stats["known_devices"] == 0

    def test_snapshot_devices(self):
        um = self._make()
        # Manually set known devices to avoid slow subprocess
        with um._lock:
            um._known_devices = {"dev1": {"name": "Mouse", "device_id": "dev1"}}
        stats = um.get_stats()
        assert stats["known_devices"] == 1

    def test_usb_device_dataclass(self):
        from src.usb_monitor import USBDevice
        d = USBDevice(name="Mouse", device_id="USB/VID_1234", status="OK")
        assert d.name == "Mouse"
        assert d.manufacturer == ""

    def test_usb_event_dataclass(self):
        from src.usb_monitor import USBEvent
        e = USBEvent(action="connected", device_name="Keyboard", success=True)
        assert e.action == "connected"

    def test_get_device_empty(self):
        um = self._make()
        # Override list_devices to avoid subprocess
        um.list_devices = lambda: [{"name": "Mouse", "device_id": "d1"}]
        results = um.get_device("Mouse")
        assert len(results) == 1

    def test_get_device_no_match(self):
        um = self._make()
        um.list_devices = lambda: [{"name": "Mouse", "device_id": "d1"}]
        results = um.get_device("Keyboard")
        assert len(results) == 0

    def test_count_by_status(self):
        um = self._make()
        um.list_devices = lambda: [
            {"name": "A", "status": "OK"},
            {"name": "B", "status": "OK"},
            {"name": "C", "status": "Error"},
        ]
        counts = um.count_by_status()
        assert counts["OK"] == 2
        assert counts["Error"] == 1


# ═══════════════════════════════════════════════════════════════════════════
# MCP HANDLERS — Phase 26
# ═══════════════════════════════════════════════════════════════════════════

class TestMCPHandlersPhase26:
    def test_wifimgr_profiles(self):
        from src.mcp_server import handle_wifimgr_profiles
        result = asyncio.run(handle_wifimgr_profiles({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_wifimgr_events(self):
        from src.mcp_server import handle_wifimgr_events
        result = asyncio.run(handle_wifimgr_events({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_wifimgr_stats(self):
        from src.mcp_server import handle_wifimgr_stats
        result = asyncio.run(handle_wifimgr_stats({}))
        data = json.loads(result[0].text)
        assert "total_events" in data

    def test_dispmgr_list(self):
        from src.mcp_server import handle_dispmgr_list
        result = asyncio.run(handle_dispmgr_list({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_dispmgr_events(self):
        from src.mcp_server import handle_dispmgr_events
        result = asyncio.run(handle_dispmgr_events({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_dispmgr_stats(self):
        from src.mcp_server import handle_dispmgr_stats
        result = asyncio.run(handle_dispmgr_stats({}))
        data = json.loads(result[0].text)
        assert "display_count" in data

    def test_usbmon_events(self):
        from src.mcp_server import handle_usbmon_events
        result = asyncio.run(handle_usbmon_events({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_usbmon_stats(self):
        from src.mcp_server import handle_usbmon_stats
        result = asyncio.run(handle_usbmon_stats({}))
        data = json.loads(result[0].text)
        assert "total_events" in data


# ═══════════════════════════════════════════════════════════════════════════
# TOOL COUNT PHASE 26
# ═══════════════════════════════════════════════════════════════════════════

class TestToolCountPhase26:
    def test_tool_count_at_least_348(self):
        """339 + 3 wifimgr + 3 dispmgr + 3 usbmon = 348."""
        from src.mcp_server import TOOL_DEFINITIONS
        assert len(TOOL_DEFINITIONS) >= 348, f"Expected >= 348 tools, got {len(TOOL_DEFINITIONS)}"

    def test_no_duplicate_tool_names(self):
        from src.mcp_server import TOOL_DEFINITIONS
        names = [t[0] for t in TOOL_DEFINITIONS]
        dupes = [n for n in names if names.count(n) > 1]
        assert len(names) == len(set(names)), f"Duplicate tools: {set(dupes)}"
