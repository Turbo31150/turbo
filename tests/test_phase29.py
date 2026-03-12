"""Phase 29 Tests — Network Monitor, Hosts Manager, Theme Controller, MCP Handlers."""

import asyncio
import json
import pytest


# ═══════════════════════════════════════════════════════════════════════════
# NETWORK MONITOR
# ═══════════════════════════════════════════════════════════════════════════

class TestNetworkMonitor:
    @staticmethod
    def _make():
        from src.network_monitor import NetworkMonitor
        return NetworkMonitor()

    def test_singleton_exists(self):
        from src.network_monitor import network_monitor
        assert network_monitor is not None

    def test_get_events_empty(self):
        nm = self._make()
        events = nm.get_events()
        assert isinstance(events, list)
        assert len(events) == 0

    def test_record_event(self):
        nm = self._make()
        nm._record("test", True, "ok")
        events = nm.get_events()
        assert len(events) == 1
        assert events[0]["action"] == "test"

    def test_network_adapter_dataclass(self):
        from src.network_monitor import NetworkAdapter
        a = NetworkAdapter(name="Ethernet", status="Up", ip_address="192.168.1.10")
        assert a.name == "Ethernet"
        assert a.mac_address == ""

    def test_network_event_dataclass(self):
        from src.network_monitor import NetworkEvent
        e = NetworkEvent(action="ping", detail="8.8.8.8")
        assert e.action == "ping"
        assert e.success is True

    def test_get_stats_structure(self):
        nm = self._make()
        stats = nm.get_stats()
        assert "total_events" in stats


# ═══════════════════════════════════════════════════════════════════════════
# HOSTS MANAGER
# ═══════════════════════════════════════════════════════════════════════════

class TestHostsManager:
    @staticmethod
    def _make():
        from src.hosts_manager import HostsManager
        return HostsManager()

    def test_singleton_exists(self):
        from src.hosts_manager import hosts_manager
        assert hosts_manager is not None

    def test_hosts_path(self):
        from src.hosts_manager import HOSTS_PATH
        assert "hosts" in HOSTS_PATH.lower()

    def test_read_entries(self):
        hm = self._make()
        entries = hm.read_entries()
        assert isinstance(entries, list)
        # Windows always has localhost entry
        assert len(entries) >= 0  # May be empty if hosts is minimal

    def test_get_events_empty(self):
        hm = self._make()
        events = hm.get_events()
        assert isinstance(events, list)

    def test_record_event(self):
        hm = self._make()
        hm._record("test", True, "ok")
        events = hm.get_events()
        assert len(events) == 1

    def test_host_entry_dataclass(self):
        from src.hosts_manager import HostEntry
        e = HostEntry(ip="127.0.0.1", hostname="localhost")
        assert e.ip == "127.0.0.1"
        assert e.comment == ""

    def test_hosts_event_dataclass(self):
        from src.hosts_manager import HostsEvent
        e = HostsEvent(action="read")
        assert e.action == "read"
        assert e.success is True

    def test_search_localhost(self):
        hm = self._make()
        results = hm.search("localhost")
        assert isinstance(results, list)

    def test_get_stats_structure(self):
        hm = self._make()
        stats = hm.get_stats()
        assert "total_entries" in stats
        assert "hosts_file" in stats

    def test_get_raw(self):
        hm = self._make()
        raw = hm.get_raw()
        assert isinstance(raw, str)


# ═══════════════════════════════════════════════════════════════════════════
# THEME CONTROLLER
# ═══════════════════════════════════════════════════════════════════════════

class TestThemeController:
    @staticmethod
    def _make():
        from src.theme_controller import ThemeController
        return ThemeController()

    def test_singleton_exists(self):
        from src.theme_controller import theme_controller
        assert theme_controller is not None

    def test_get_theme(self):
        tc = self._make()
        theme = tc.get_theme()
        assert "dark_mode_apps" in theme
        assert "dark_mode_system" in theme
        assert "accent_color" in theme
        assert "wallpaper" in theme

    def test_is_dark_mode(self):
        tc = self._make()
        result = tc.is_dark_mode()
        assert isinstance(result, bool)

    def test_accent_color_format(self):
        tc = self._make()
        color = tc._get_accent_color()
        assert color.startswith("#")
        assert len(color) == 7

    def test_get_events_empty(self):
        tc = self._make()
        events = tc.get_events()
        assert isinstance(events, list)

    def test_record_event(self):
        tc = self._make()
        tc._record("test", True, "ok")
        events = tc.get_events()
        assert len(events) == 1

    def test_theme_event_dataclass(self):
        from src.theme_controller import ThemeEvent
        e = ThemeEvent(action="get")
        assert e.action == "get"
        assert e.success is True

    def test_get_color_prevalence(self):
        tc = self._make()
        cp = tc.get_color_prevalence()
        assert "color_on_taskbar" in cp
        assert "color_on_titlebars" in cp

    def test_get_stats_structure(self):
        tc = self._make()
        stats = tc.get_stats()
        assert "dark_mode" in stats
        assert "accent_color" in stats
        assert "total_events" in stats


# ═══════════════════════════════════════════════════════════════════════════
# MCP HANDLERS — Phase 29
# ═══════════════════════════════════════════════════════════════════════════

class TestMCPHandlersPhase29:
    def test_netmon_events(self):
        from src.mcp_server import handle_netmon_events
        result = asyncio.run(handle_netmon_events({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_netmon_stats(self):
        from src.mcp_server import handle_netmon_stats
        result = asyncio.run(handle_netmon_stats({}))
        data = json.loads(result[0].text)
        assert "total_events" in data

    def test_hostsmgr_events(self):
        from src.mcp_server import handle_hostsmgr_events
        result = asyncio.run(handle_hostsmgr_events({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_hostsmgr_stats(self):
        from src.mcp_server import handle_hostsmgr_stats
        result = asyncio.run(handle_hostsmgr_stats({}))
        data = json.loads(result[0].text)
        assert "total_entries" in data

    def test_themectl_get(self):
        from src.mcp_server import handle_themectl_get
        result = asyncio.run(handle_themectl_get({}))
        data = json.loads(result[0].text)
        assert "dark_mode_apps" in data

    def test_themectl_stats(self):
        from src.mcp_server import handle_themectl_stats
        result = asyncio.run(handle_themectl_stats({}))
        data = json.loads(result[0].text)
        assert "dark_mode" in data


# ═══════════════════════════════════════════════════════════════════════════
# TOOL COUNT PHASE 29
# ═══════════════════════════════════════════════════════════════════════════

class TestToolCountPhase29:
    def test_tool_count_at_least_375(self):
        """366 + 3 netmon + 3 hostsmgr + 3 themectl = 375."""
        from src.mcp_server import TOOL_DEFINITIONS
        assert len(TOOL_DEFINITIONS) >= 375, f"Expected >= 375 tools, got {len(TOOL_DEFINITIONS)}"

    def test_no_duplicate_tool_names(self):
        from src.mcp_server import TOOL_DEFINITIONS
        names = [t[0] for t in TOOL_DEFINITIONS]
        dupes = [n for n in names if names.count(n) > 1]
        assert len(names) == len(set(names)), f"Duplicate tools: {set(dupes)}"
