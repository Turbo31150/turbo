"""Phase 31 Tests — System Restore, Performance Counter, Credential Vault, MCP Handlers."""

import asyncio
import json
import pytest


# ═══════════════════════════════════════════════════════════════════════════
# SYSTEM RESTORE MANAGER
# ═══════════════════════════════════════════════════════════════════════════

class TestSysRestoreManager:
    @staticmethod
    def _make():
        from src.sysrestore_manager import SysRestoreManager
        return SysRestoreManager()

    def test_singleton_exists(self):
        from src.sysrestore_manager import sysrestore_manager
        assert sysrestore_manager is not None

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

    def test_restore_point_dataclass(self):
        from src.sysrestore_manager import RestorePoint
        rp = RestorePoint(sequence=1, description="Before update")
        assert rp.sequence == 1
        assert rp.event_type == ""

    def test_restore_event_dataclass(self):
        from src.sysrestore_manager import RestoreEvent
        e = RestoreEvent(action="list")
        assert e.action == "list"
        assert e.success is True

    def test_get_stats_structure(self):
        sm = self._make()
        stats = sm.get_stats()
        assert "total_events" in stats

    def test_search_with_mock(self):
        sm = self._make()
        sm.list_points = lambda: [
            {"sequence": 1, "description": "Before Windows Update"},
            {"sequence": 2, "description": "Manual checkpoint"},
        ]
        results = sm.search("update")
        assert len(results) == 1

    def test_get_latest_with_mock(self):
        sm = self._make()
        sm.list_points = lambda: [
            {"sequence": 1, "description": "First"},
            {"sequence": 2, "description": "Latest"},
        ]
        latest = sm.get_latest()
        assert latest["sequence"] == 2

    def test_count_with_mock(self):
        sm = self._make()
        sm.list_points = lambda: [{"sequence": 1}, {"sequence": 2}]
        assert sm.count_points() == 2


# ═══════════════════════════════════════════════════════════════════════════
# PERFORMANCE COUNTER
# ═══════════════════════════════════════════════════════════════════════════

class TestPerfCounter:
    @staticmethod
    def _make():
        from src.perfcounter import PerfCounter
        return PerfCounter()

    def test_singleton_exists(self):
        from src.perfcounter import perfcounter
        assert perfcounter is not None

    def test_get_events_empty(self):
        pc = self._make()
        events = pc.get_events()
        assert isinstance(events, list)
        assert len(events) == 0

    def test_record_event(self):
        pc = self._make()
        pc._record("test", True, "ok")
        events = pc.get_events()
        assert len(events) == 1

    def test_perf_sample_dataclass(self):
        from src.perfcounter import PerfSample
        s = PerfSample(counter="cpu", value=45.2)
        assert s.counter == "cpu"
        assert s.value == 45.2

    def test_perf_event_dataclass(self):
        from src.perfcounter import PerfEvent
        e = PerfEvent(action="read")
        assert e.action == "read"
        assert e.success is True

    def test_counter_paths(self):
        from src.perfcounter import COUNTER_PATHS
        assert "cpu" in COUNTER_PATHS
        assert "memory" in COUNTER_PATHS
        assert len(COUNTER_PATHS) >= 5

    def test_list_counters(self):
        pc = self._make()
        counters = pc.list_counters()
        assert "cpu" in counters

    def test_get_history_empty(self):
        pc = self._make()
        history = pc.get_history()
        assert isinstance(history, list)
        assert len(history) == 0

    def test_read_named_invalid(self):
        pc = self._make()
        result = pc.read_named("nonexistent")
        assert result is None

    def test_get_stats_structure(self):
        pc = self._make()
        stats = pc.get_stats()
        assert "total_events" in stats
        assert "history_size" in stats
        assert "available_counters" in stats


# ═══════════════════════════════════════════════════════════════════════════
# CREDENTIAL VAULT
# ═══════════════════════════════════════════════════════════════════════════

class TestCredentialVault:
    @staticmethod
    def _make():
        from src.credential_vault import CredentialVault
        return CredentialVault()

    def test_singleton_exists(self):
        from src.credential_vault import credential_vault
        assert credential_vault is not None

    def test_get_events_empty(self):
        cv = self._make()
        events = cv.get_events()
        assert isinstance(events, list)
        assert len(events) == 0

    def test_record_event(self):
        cv = self._make()
        cv._record("test", True, "ok")
        events = cv.get_events()
        assert len(events) == 1

    def test_credential_entry_dataclass(self):
        from src.credential_vault import CredentialEntry
        c = CredentialEntry(target="git:https://github.com", cred_type="Generic")
        assert c.target == "git:https://github.com"
        assert c.user == ""

    def test_vault_event_dataclass(self):
        from src.credential_vault import VaultEvent
        e = VaultEvent(action="list")
        assert e.action == "list"
        assert e.success is True

    def test_parse_cmdkey(self):
        cv = self._make()
        sample = (
            "Currently stored credentials:\n\n"
            "    Target: git:https://github.com\n"
            "    Type: Generic\n"
            "    User: user@email.com\n"
            "    Persistence: Local Machine\n\n"
            "    Target: TERMSRV/server1\n"
            "    Type: Domain Password\n"
            "    User: DOMAIN/admin\n"
        )
        creds = cv._parse_cmdkey(sample)
        assert len(creds) == 2
        assert creds[0]["target"] == "git:https://github.com"
        assert creds[0]["user"] == "user@email.com"
        assert creds[1]["target"] == "TERMSRV/server1"

    def test_search_with_mock(self):
        cv = self._make()
        cv.list_credentials = lambda: [
            {"target": "git:https://github.com", "type": "Generic"},
            {"target": "TERMSRV/server1", "type": "Domain"},
        ]
        results = cv.search("github")
        assert len(results) == 1

    def test_count_by_type_with_mock(self):
        cv = self._make()
        cv.list_credentials = lambda: [
            {"target": "A", "type": "Generic"},
            {"target": "B", "type": "Generic"},
            {"target": "C", "type": "Domain"},
        ]
        counts = cv.count_by_type()
        assert counts["Generic"] == 2
        assert counts["Domain"] == 1

    def test_has_credential_with_mock(self):
        cv = self._make()
        cv.list_credentials = lambda: [{"target": "git:https://github.com"}]
        assert cv.has_credential("github") is True
        assert cv.has_credential("gitlab") is False

    def test_get_stats_structure(self):
        cv = self._make()
        stats = cv.get_stats()
        assert "total_events" in stats


# ═══════════════════════════════════════════════════════════════════════════
# MCP HANDLERS — Phase 31
# ═══════════════════════════════════════════════════════════════════════════

class TestMCPHandlersPhase31:
    def test_sysrest_events(self):
        from src.mcp_server import handle_sysrest_events
        result = asyncio.run(handle_sysrest_events({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_sysrest_stats(self):
        from src.mcp_server import handle_sysrest_stats
        result = asyncio.run(handle_sysrest_stats({}))
        data = json.loads(result[0].text)
        assert "total_events" in data

    def test_perfctr_counters(self):
        from src.mcp_server import handle_perfctr_counters
        result = asyncio.run(handle_perfctr_counters({}))
        data = json.loads(result[0].text)
        assert "cpu" in data

    def test_perfctr_stats(self):
        from src.mcp_server import handle_perfctr_stats
        result = asyncio.run(handle_perfctr_stats({}))
        data = json.loads(result[0].text)
        assert "available_counters" in data

    def test_credvlt_events(self):
        from src.mcp_server import handle_credvlt_events
        result = asyncio.run(handle_credvlt_events({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_credvlt_stats(self):
        from src.mcp_server import handle_credvlt_stats
        result = asyncio.run(handle_credvlt_stats({}))
        data = json.loads(result[0].text)
        assert "total_events" in data


# ═══════════════════════════════════════════════════════════════════════════
# TOOL COUNT PHASE 31
# ═══════════════════════════════════════════════════════════════════════════

class TestToolCountPhase31:
    def test_tool_count_at_least_393(self):
        """384 + 3 sysrest + 3 perfctr + 3 credvlt = 393."""
        from src.mcp_server import TOOL_DEFINITIONS
        assert len(TOOL_DEFINITIONS) >= 393, f"Expected >= 393 tools, got {len(TOOL_DEFINITIONS)}"

    def test_no_duplicate_tool_names(self):
        from src.mcp_server import TOOL_DEFINITIONS
        names = [t[0] for t in TOOL_DEFINITIONS]
        dupes = [n for n in names if names.count(n) > 1]
        assert len(names) == len(set(names)), f"Duplicate tools: {set(dupes)}"
