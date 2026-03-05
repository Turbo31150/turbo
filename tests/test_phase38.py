"""Phase 38 Tests — IP Config, Recycle Bin, Installed Apps, MCP Handlers."""

import asyncio
import json
import pytest


# ═══════════════════════════════════════════════════════════════════════════
# IP CONFIG MANAGER
# ═══════════════════════════════════════════════════════════════════════════

class TestIPConfigManager:
    @staticmethod
    def _make():
        from src.ip_config_manager import IPConfigManager
        return IPConfigManager()

    def test_singleton_exists(self):
        from src.ip_config_manager import ip_config_manager
        assert ip_config_manager is not None

    def test_get_events_empty(self):
        ipc = self._make()
        assert ipc.get_events() == []

    def test_record_event(self):
        ipc = self._make()
        ipc._record("test", True, "ok")
        assert len(ipc.get_events()) == 1

    def test_ip_interface_dataclass(self):
        from src.ip_config_manager import IPInterface
        ipi = IPInterface(name="Ethernet", ipv4="192.168.1.100")
        assert ipi.name == "Ethernet"
        assert ipi.gateway == ""

    def test_get_stats_structure(self):
        ipc = self._make()
        assert "total_events" in ipc.get_stats()

    def test_parse_ipconfig(self):
        ipc = self._make()
        sample = (
            "Ethernet adapter Ethernet:\n\n"
            "   IPv4 Address. . . . . . . . . . . : 192.168.1.100\n"
            "   Subnet Mask . . . . . . . . . . . : 255.255.255.0\n"
            "   Default Gateway . . . . . . . . . : 192.168.1.1\n"
            "   DHCP Enabled. . . . . . . . . . . : Yes\n"
            "   DNS Servers . . . . . . . . . . . : 8.8.8.8\n"
            "                                       8.8.4.4\n"
        )
        interfaces = ipc._parse_ipconfig(sample)
        assert len(interfaces) == 1
        assert interfaces[0]["ipv4"] == "192.168.1.100"
        assert interfaces[0]["gateway"] == "192.168.1.1"
        assert interfaces[0]["dhcp_enabled"] is True

    def test_get_dns_with_mock(self):
        ipc = self._make()
        ipc.get_all = lambda: [{"dns_servers": ["8.8.8.8"]}, {"dns_servers": ["1.1.1.1"]}]
        dns = ipc.get_dns_servers()
        assert "8.8.8.8" in dns

    def test_search_with_mock(self):
        ipc = self._make()
        ipc.get_all = lambda: [
            {"name": "Ethernet", "ipv4": "192.168.1.1"},
            {"name": "WiFi", "ipv4": "10.0.0.1"},
        ]
        results = ipc.search("wifi")
        assert len(results) == 1


# ═══════════════════════════════════════════════════════════════════════════
# RECYCLE BIN MANAGER
# ═══════════════════════════════════════════════════════════════════════════

class TestRecycleBinManager:
    @staticmethod
    def _make():
        from src.recycle_bin_manager import RecycleBinManager
        return RecycleBinManager()

    def test_singleton_exists(self):
        from src.recycle_bin_manager import recycle_bin_manager
        assert recycle_bin_manager is not None

    def test_get_events_empty(self):
        rb = self._make()
        assert rb.get_events() == []

    def test_record_event(self):
        rb = self._make()
        rb._record("test", True, "ok")
        assert len(rb.get_events()) == 1

    def test_recycle_bin_info_dataclass(self):
        from src.recycle_bin_manager import RecycleBinInfo
        rbi = RecycleBinInfo(item_count=5, total_size_mb=12.5)
        assert rbi.item_count == 5

    def test_get_stats_structure(self):
        rb = self._make()
        assert "total_events" in rb.get_stats()

    def test_get_info_returns_dict(self):
        rb = self._make()
        info = rb.get_info()
        assert isinstance(info, dict)
        assert "item_count" in info

    def test_is_empty_with_mock(self):
        rb = self._make()
        rb.get_info = lambda: {"item_count": 0, "size_mb": 0}
        assert rb.is_empty() is True

    def test_is_not_empty_with_mock(self):
        rb = self._make()
        rb.get_info = lambda: {"item_count": 3, "size_mb": 1.5}
        assert rb.is_empty() is False


# ═══════════════════════════════════════════════════════════════════════════
# INSTALLED APPS MANAGER
# ═══════════════════════════════════════════════════════════════════════════

class TestInstalledAppsManager:
    @staticmethod
    def _make():
        from src.installed_apps_manager import InstalledAppsManager
        return InstalledAppsManager()

    def test_singleton_exists(self):
        from src.installed_apps_manager import installed_apps_manager
        assert installed_apps_manager is not None

    def test_get_events_empty(self):
        iam = self._make()
        assert iam.get_events() == []

    def test_record_event(self):
        iam = self._make()
        iam._record("test", True, "ok")
        assert len(iam.get_events()) == 1

    def test_installed_app_dataclass(self):
        from src.installed_apps_manager import InstalledApp
        ia = InstalledApp(name="Python 3.12", version="3.12.10", app_type="Win32")
        assert ia.name == "Python 3.12"
        assert ia.publisher == ""

    def test_get_stats_structure(self):
        iam = self._make()
        assert "total_events" in iam.get_stats()

    def test_search_with_mock(self):
        iam = self._make()
        iam.list_win32_apps = lambda: [
            {"name": "Python 3.12", "type": "Win32"},
            {"name": "Node.js", "type": "Win32"},
        ]
        iam.list_uwp_apps = lambda: [
            {"name": "Microsoft.WindowsStore", "type": "UWP"},
        ]
        results = iam.search("python")
        assert len(results) == 1

    def test_count_by_type_with_mock(self):
        iam = self._make()
        iam.list_win32_apps = lambda: [{"name": "A"}, {"name": "B"}]
        iam.list_uwp_apps = lambda: [{"name": "C"}]
        counts = iam.count_by_type()
        assert counts["Win32"] == 2
        assert counts["UWP"] == 1


# ═══════════════════════════════════════════════════════════════════════════
# MCP HANDLERS — Phase 38
# ═══════════════════════════════════════════════════════════════════════════

class TestMCPHandlersPhase38:
    def test_ipcfg_all(self):
        from src.mcp_server import handle_ipcfg_all
        result = asyncio.run(handle_ipcfg_all({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_ipcfg_stats(self):
        from src.mcp_server import handle_ipcfg_stats
        result = asyncio.run(handle_ipcfg_stats({}))
        data = json.loads(result[0].text)
        assert "total_events" in data

    def test_recyclebin_info(self):
        from src.mcp_server import handle_recyclebin_info
        result = asyncio.run(handle_recyclebin_info({}))
        data = json.loads(result[0].text)
        assert "item_count" in data

    def test_recyclebin_stats(self):
        from src.mcp_server import handle_recyclebin_stats
        result = asyncio.run(handle_recyclebin_stats({}))
        data = json.loads(result[0].text)
        assert "total_events" in data

    def test_instapp_list(self):
        from src.mcp_server import handle_instapp_list
        result = asyncio.run(handle_instapp_list({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_instapp_stats(self):
        from src.mcp_server import handle_instapp_stats
        result = asyncio.run(handle_instapp_stats({}))
        data = json.loads(result[0].text)
        assert "total_events" in data


# ═══════════════════════════════════════════════════════════════════════════
# TOOL COUNT PHASE 38
# ═══════════════════════════════════════════════════════════════════════════

class TestToolCountPhase38:
    def test_tool_count_at_least_456(self):
        """447 + 3 ipcfg + 3 recyclebin + 3 instapp = 456."""
        from src.mcp_server import TOOL_DEFINITIONS
        assert len(TOOL_DEFINITIONS) >= 456, f"Expected >= 456 tools, got {len(TOOL_DEFINITIONS)}"

    def test_no_duplicate_tool_names(self):
        from src.mcp_server import TOOL_DEFINITIONS
        names = [t[0] for t in TOOL_DEFINITIONS]
        dupes = [n for n in names if names.count(n) > 1]
        assert len(names) == len(set(names)), f"Duplicate tools: {set(dupes)}"
