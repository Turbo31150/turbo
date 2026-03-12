"""Phase 43 Tests — Network Adapter, Windows Update, Local Security Policy, MCP."""

import asyncio
import json
import pytest


# ═══════════════════════════════════════════════════════════════════════════
# NETWORK ADAPTER MANAGER
# ═══════════════════════════════════════════════════════════════════════════

class TestNetworkAdapterManager:
    @staticmethod
    def _make():
        from src.network_adapter_manager import NetworkAdapterManager
        return NetworkAdapterManager()

    def test_singleton_exists(self):
        from src.network_adapter_manager import network_adapter_manager
        assert network_adapter_manager is not None

    def test_get_events_empty(self):
        m = self._make()
        assert m.get_events() == []

    def test_record_event(self):
        m = self._make()
        m._record("test", True, "ok")
        assert len(m.get_events()) == 1

    def test_dataclass(self):
        from src.network_adapter_manager import NetworkAdapter
        na = NetworkAdapter(name="Ethernet", status="Up", link_speed="1 Gbps")
        assert na.name == "Ethernet"
        assert na.mac_address == ""

    def test_get_stats_structure(self):
        m = self._make()
        assert "total_events" in m.get_stats()

    def test_search_with_mock(self):
        m = self._make()
        m.list_adapters = lambda: [
            {"name": "Ethernet", "description": "Realtek", "status": "Up"},
            {"name": "Wi-Fi", "description": "Intel Wireless", "status": "Up"},
        ]
        results = m.search("wifi")
        assert len(results) == 0  # exact match "wifi" vs "Wi-Fi"
        results2 = m.search("wi-fi")
        assert len(results2) == 1

    def test_count_by_status_with_mock(self):
        m = self._make()
        m.list_adapters = lambda: [
            {"name": "A", "status": "Up"},
            {"name": "B", "status": "Up"},
            {"name": "C", "status": "Disconnected"},
        ]
        counts = m.count_by_status()
        assert counts["Up"] == 2


# ═══════════════════════════════════════════════════════════════════════════
# WINDOWS UPDATE MANAGER
# ═══════════════════════════════════════════════════════════════════════════

class TestWindowsUpdateManager:
    @staticmethod
    def _make():
        from src.windows_update_manager import WindowsUpdateManager
        return WindowsUpdateManager()

    def test_singleton_exists(self):
        from src.windows_update_manager import windows_update_manager
        assert windows_update_manager is not None

    def test_get_events_empty(self):
        m = self._make()
        assert m.get_events() == []

    def test_record_event(self):
        m = self._make()
        m._record("test", True, "ok")
        assert len(m.get_events()) == 1

    def test_dataclass(self):
        from src.windows_update_manager import WindowsUpdate
        wu = WindowsUpdate(title="KB123456", kb_article="123456")
        assert wu.title == "KB123456"
        assert wu.result_code == 0

    def test_get_stats_structure(self):
        m = self._make()
        assert "total_events" in m.get_stats()

    def test_search_with_mock(self):
        m = self._make()
        m.get_update_history = lambda limit=100: [
            {"title": "2024-01 Cumulative Update", "date": "2024-01-10"},
            {"title": "Security Intelligence Update", "date": "2024-01-12"},
        ]
        results = m.search_history("cumulative")
        assert len(results) == 1


# ═══════════════════════════════════════════════════════════════════════════
# LOCAL SECURITY POLICY
# ═══════════════════════════════════════════════════════════════════════════

class TestLocalSecurityPolicy:
    @staticmethod
    def _make():
        from src.local_security_policy import LocalSecurityPolicy
        return LocalSecurityPolicy()

    def test_singleton_exists(self):
        from src.local_security_policy import local_security_policy
        assert local_security_policy is not None

    def test_get_events_empty(self):
        m = self._make()
        assert m.get_events() == []

    def test_record_event(self):
        m = self._make()
        m._record("test", True, "ok")
        assert len(m.get_events()) == 1

    def test_dataclass(self):
        from src.local_security_policy import SecuritySetting
        ss = SecuritySetting(section="System Access", key="MinimumPasswordLength", value="8")
        assert ss.section == "System Access"

    def test_get_stats_structure(self):
        m = self._make()
        assert "total_events" in m.get_stats()

    def test_password_policy_with_mock(self):
        m = self._make()
        m.export_policy = lambda: {
            "System Access": {"MinimumPasswordLength": "8", "PasswordComplexity": "1"},
            "Event Audit": {"AuditLogonEvents": "3"},
        }
        pp = m.get_password_policy()
        assert pp["MinimumPasswordLength"] == "8"

    def test_audit_policy_with_mock(self):
        m = self._make()
        m.export_policy = lambda: {
            "System Access": {},
            "Event Audit": {"AuditLogonEvents": "3"},
        }
        ap = m.get_audit_policy()
        assert "AuditLogonEvents" in ap

    def test_get_sections_with_mock(self):
        m = self._make()
        m.export_policy = lambda: {"System Access": {}, "Event Audit": {}}
        sections = m.get_sections()
        assert "System Access" in sections


# ═══════════════════════════════════════════════════════════════════════════
# MCP HANDLERS — Phase 43
# ═══════════════════════════════════════════════════════════════════════════

class TestMCPHandlersPhase43:
    def test_netadapt_list(self):
        from src.mcp_server import handle_netadapt_list
        result = asyncio.run(handle_netadapt_list({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_netadapt_stats(self):
        from src.mcp_server import handle_netadapt_stats
        result = asyncio.run(handle_netadapt_stats({}))
        data = json.loads(result[0].text)
        assert "total_events" in data

    def test_winupd_history(self):
        from src.mcp_server import handle_winupd_history
        result = asyncio.run(handle_winupd_history({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_winupd_stats(self):
        from src.mcp_server import handle_winupd_stats
        result = asyncio.run(handle_winupd_stats({}))
        data = json.loads(result[0].text)
        assert "total_events" in data

    def test_secpol_export(self):
        from src.mcp_server import handle_secpol_export
        result = asyncio.run(handle_secpol_export({}))
        data = json.loads(result[0].text)
        assert isinstance(data, dict)

    def test_secpol_stats(self):
        from src.mcp_server import handle_secpol_stats
        result = asyncio.run(handle_secpol_stats({}))
        data = json.loads(result[0].text)
        assert "total_events" in data


# ═══════════════════════════════════════════════════════════════════════════
# TOOL COUNT PHASE 43
# ═══════════════════════════════════════════════════════════════════════════

class TestToolCountPhase43:
    def test_tool_count_at_least_501(self):
        """492 + 3 netadapt + 3 winupd + 3 secpol = 501."""
        from src.mcp_server import TOOL_DEFINITIONS
        assert len(TOOL_DEFINITIONS) >= 501, f"Expected >= 501 tools, got {len(TOOL_DEFINITIONS)}"

    def test_no_duplicate_tool_names(self):
        from src.mcp_server import TOOL_DEFINITIONS
        names = [t[0] for t in TOOL_DEFINITIONS]
        dupes = [n for n in names if names.count(n) > 1]
        assert len(names) == len(set(names)), f"Duplicate tools: {set(dupes)}"
