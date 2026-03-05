"""Phase 35 Tests — User Account Manager, Group Policy Reader, Windows Feature Manager, MCP Handlers."""

import asyncio
import json
import pytest


# ═══════════════════════════════════════════════════════════════════════════
# USER ACCOUNT MANAGER
# ═══════════════════════════════════════════════════════════════════════════

class TestUserAccountManager:
    @staticmethod
    def _make():
        from src.user_account_manager import UserAccountManager
        return UserAccountManager()

    def test_singleton_exists(self):
        from src.user_account_manager import user_account_manager
        assert user_account_manager is not None

    def test_get_events_empty(self):
        uam = self._make()
        assert uam.get_events() == []

    def test_record_event(self):
        uam = self._make()
        uam._record("test", True, "ok")
        assert len(uam.get_events()) == 1

    def test_user_account_dataclass(self):
        from src.user_account_manager import UserAccount
        ua = UserAccount(name="Admin", enabled=True)
        assert ua.name == "Admin"
        assert ua.full_name == ""

    def test_user_event_dataclass(self):
        from src.user_account_manager import UserEvent
        e = UserEvent(action="list")
        assert e.success is True

    def test_get_stats_structure(self):
        uam = self._make()
        stats = uam.get_stats()
        assert "total_events" in stats

    def test_search_with_mock(self):
        uam = self._make()
        uam.list_users = lambda: [
            {"name": "Administrator", "enabled": True},
            {"name": "Guest", "enabled": False},
        ]
        results = uam.search_users("admin")
        assert len(results) == 1

    def test_count_by_status_with_mock(self):
        uam = self._make()
        uam.list_users = lambda: [
            {"name": "A", "enabled": True},
            {"name": "B", "enabled": True},
            {"name": "C", "enabled": False},
        ]
        counts = uam.count_by_status()
        assert counts["enabled"] == 2
        assert counts["disabled"] == 1

    def test_list_groups_returns_list(self):
        uam = self._make()
        result = uam.list_groups()
        assert isinstance(result, list)


# ═══════════════════════════════════════════════════════════════════════════
# GROUP POLICY READER
# ═══════════════════════════════════════════════════════════════════════════

class TestGroupPolicyReader:
    @staticmethod
    def _make():
        from src.group_policy_reader import GroupPolicyReader
        return GroupPolicyReader()

    def test_singleton_exists(self):
        from src.group_policy_reader import group_policy_reader
        assert group_policy_reader is not None

    def test_get_events_empty(self):
        gpr = self._make()
        assert gpr.get_events() == []

    def test_record_event(self):
        gpr = self._make()
        gpr._record("test", True, "ok")
        assert len(gpr.get_events()) == 1

    def test_gpo_info_dataclass(self):
        from src.group_policy_reader import GPOInfo
        gi = GPOInfo(name="Default Domain Policy")
        assert gi.name == "Default Domain Policy"
        assert gi.status == ""

    def test_gpo_event_dataclass(self):
        from src.group_policy_reader import GPOEvent
        e = GPOEvent(action="rsop")
        assert e.success is True

    def test_get_stats_structure(self):
        gpr = self._make()
        stats = gpr.get_stats()
        assert "total_events" in stats

    def test_parse_gpresult(self):
        gpr = self._make()
        sample = (
            "Computer Name: WORKSTATION\n"
            "Domain Name: WORKGROUP\n"
            "Site Name: N/A\n"
            "\n"
            "Applied Group Policy Objects:\n"
            "  Default Policy\n"
            "  Security Policy\n"
            "\n"
        )
        result = gpr._parse_gpresult(sample)
        assert result["computer_name"] == "WORKSTATION"
        assert result["domain"] == "WORKGROUP"

    def test_parse_gpresult_empty(self):
        gpr = self._make()
        result = gpr._parse_gpresult("")
        assert result["computer_name"] == ""

    def test_get_raw_returns_string(self):
        gpr = self._make()
        result = gpr.get_raw()
        assert isinstance(result, str)


# ═══════════════════════════════════════════════════════════════════════════
# WINDOWS FEATURE MANAGER
# ═══════════════════════════════════════════════════════════════════════════

class TestWindowsFeatureManager:
    @staticmethod
    def _make():
        from src.windows_feature_manager import WindowsFeatureManager
        return WindowsFeatureManager()

    def test_singleton_exists(self):
        from src.windows_feature_manager import windows_feature_manager
        assert windows_feature_manager is not None

    def test_get_events_empty(self):
        wfm = self._make()
        assert wfm.get_events() == []

    def test_record_event(self):
        wfm = self._make()
        wfm._record("test", True, "ok")
        assert len(wfm.get_events()) == 1

    def test_windows_feature_dataclass(self):
        from src.windows_feature_manager import WindowsFeature
        wf = WindowsFeature(name="Microsoft-Hyper-V", state="Enabled")
        assert wf.name == "Microsoft-Hyper-V"

    def test_feature_event_dataclass(self):
        from src.windows_feature_manager import FeatureEvent
        e = FeatureEvent(action="list")
        assert e.success is True

    def test_get_stats_structure(self):
        wfm = self._make()
        stats = wfm.get_stats()
        assert "total_events" in stats

    def test_list_enabled_with_mock(self):
        wfm = self._make()
        wfm.list_features = lambda: [
            {"name": "WSL", "state": "Enabled"},
            {"name": "HyperV", "state": "Disabled"},
        ]
        enabled = wfm.list_enabled()
        assert len(enabled) == 1
        assert enabled[0]["name"] == "WSL"

    def test_list_disabled_with_mock(self):
        wfm = self._make()
        wfm.list_features = lambda: [
            {"name": "WSL", "state": "Enabled"},
            {"name": "HyperV", "state": "Disabled"},
        ]
        disabled = wfm.list_disabled()
        assert len(disabled) == 1

    def test_search_with_mock(self):
        wfm = self._make()
        wfm.list_features = lambda: [
            {"name": "Microsoft-Windows-Subsystem-Linux", "state": "Enabled"},
            {"name": "TelnetClient", "state": "Disabled"},
        ]
        results = wfm.search("linux")
        assert len(results) == 1

    def test_is_enabled_with_mock(self):
        wfm = self._make()
        wfm.list_features = lambda: [
            {"name": "WSL", "state": "Enabled"},
        ]
        assert wfm.is_enabled("WSL") is True
        assert wfm.is_enabled("HyperV") is False

    def test_count_by_state_with_mock(self):
        wfm = self._make()
        wfm.list_features = lambda: [
            {"name": "A", "state": "Enabled"},
            {"name": "B", "state": "Enabled"},
            {"name": "C", "state": "Disabled"},
        ]
        counts = wfm.count_by_state()
        assert counts["Enabled"] == 2
        assert counts["Disabled"] == 1


# ═══════════════════════════════════════════════════════════════════════════
# MCP HANDLERS — Phase 35
# ═══════════════════════════════════════════════════════════════════════════

class TestMCPHandlersPhase35:
    def test_usracct_list(self):
        from src.mcp_server import handle_usracct_list
        result = asyncio.run(handle_usracct_list({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_usracct_stats(self):
        from src.mcp_server import handle_usracct_stats
        result = asyncio.run(handle_usracct_stats({}))
        data = json.loads(result[0].text)
        assert "total_events" in data

    def test_gpo_rsop(self):
        from src.mcp_server import handle_gpo_rsop
        result = asyncio.run(handle_gpo_rsop({}))
        data = json.loads(result[0].text)
        assert isinstance(data, dict)

    def test_gpo_stats(self):
        from src.mcp_server import handle_gpo_stats
        result = asyncio.run(handle_gpo_stats({}))
        data = json.loads(result[0].text)
        assert "total_events" in data

    def test_winfeat_list(self):
        from src.mcp_server import handle_winfeat_list
        result = asyncio.run(handle_winfeat_list({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_winfeat_stats(self):
        from src.mcp_server import handle_winfeat_stats
        result = asyncio.run(handle_winfeat_stats({}))
        data = json.loads(result[0].text)
        assert "total_events" in data


# ═══════════════════════════════════════════════════════════════════════════
# TOOL COUNT PHASE 35
# ═══════════════════════════════════════════════════════════════════════════

class TestToolCountPhase35:
    def test_tool_count_at_least_429(self):
        """420 + 3 usracct + 3 gpo + 3 winfeat = 429."""
        from src.mcp_server import TOOL_DEFINITIONS
        assert len(TOOL_DEFINITIONS) >= 429, f"Expected >= 429 tools, got {len(TOOL_DEFINITIONS)}"

    def test_no_duplicate_tool_names(self):
        from src.mcp_server import TOOL_DEFINITIONS
        names = [t[0] for t in TOOL_DEFINITIONS]
        dupes = [n for n in names if names.count(n) > 1]
        assert len(names) == len(set(names)), f"Duplicate tools: {set(dupes)}"
