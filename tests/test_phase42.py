"""Phase 42 Tests — DNS Client, Storage Pool, Power Plan, MCP Handlers."""

import asyncio
import json
import pytest


# ═══════════════════════════════════════════════════════════════════════════
# DNS CLIENT MANAGER
# ═══════════════════════════════════════════════════════════════════════════

class TestDNSClientManager:
    @staticmethod
    def _make():
        from src.dns_client_manager import DNSClientManager
        return DNSClientManager()

    def test_singleton_exists(self):
        from src.dns_client_manager import dns_client_manager
        assert dns_client_manager is not None

    def test_get_events_empty(self):
        m = self._make()
        assert m.get_events() == []

    def test_record_event(self):
        m = self._make()
        m._record("test", True, "ok")
        assert len(m.get_events()) == 1

    def test_dataclass(self):
        from src.dns_client_manager import DNSCacheEntry
        e = DNSCacheEntry(name="google.com", record_type="A", data="142.250.0.1")
        assert e.name == "google.com"
        assert e.ttl == 0

    def test_get_stats_structure(self):
        m = self._make()
        assert "total_events" in m.get_stats()

    def test_search_cache_with_mock(self):
        m = self._make()
        m.get_cache = lambda limit=200: [
            {"entry": "google.com", "data": "1.2.3.4"},
            {"entry": "github.com", "data": "5.6.7.8"},
        ]
        results = m.search_cache("google")
        assert len(results) == 1


# ═══════════════════════════════════════════════════════════════════════════
# STORAGE POOL MANAGER
# ═══════════════════════════════════════════════════════════════════════════

class TestStoragePoolManager:
    @staticmethod
    def _make():
        from src.storage_pool_manager import StoragePoolManager
        return StoragePoolManager()

    def test_singleton_exists(self):
        from src.storage_pool_manager import storage_pool_manager
        assert storage_pool_manager is not None

    def test_get_events_empty(self):
        m = self._make()
        assert m.get_events() == []

    def test_record_event(self):
        m = self._make()
        m._record("test", True, "ok")
        assert len(m.get_events()) == 1

    def test_dataclass(self):
        from src.storage_pool_manager import StoragePool
        sp = StoragePool(name="Pool1", health_status="Healthy", size_gb=500.0)
        assert sp.name == "Pool1"
        assert sp.allocated_gb == 0.0

    def test_get_stats_structure(self):
        m = self._make()
        assert "total_events" in m.get_stats()

    def test_list_pools_returns_list(self):
        m = self._make()
        pools = m.list_pools()
        assert isinstance(pools, list)

    def test_get_physical_disks_returns_list(self):
        m = self._make()
        disks = m.get_physical_disks()
        assert isinstance(disks, list)


# ═══════════════════════════════════════════════════════════════════════════
# POWER PLAN MANAGER
# ═══════════════════════════════════════════════════════════════════════════

class TestPowerPlanManager:
    @staticmethod
    def _make():
        from src.power_plan_manager import PowerPlanManager
        return PowerPlanManager()

    def test_singleton_exists(self):
        from src.power_plan_manager import power_plan_manager
        assert power_plan_manager is not None

    def test_get_events_empty(self):
        m = self._make()
        assert m.get_events() == []

    def test_record_event(self):
        m = self._make()
        m._record("test", True, "ok")
        assert len(m.get_events()) == 1

    def test_dataclass(self):
        from src.power_plan_manager import PowerPlan
        pp = PowerPlan(name="Balanced", guid="381b4222-f694-41f0-9685-ff5bb260df2e")
        assert pp.name == "Balanced"
        assert pp.is_active is False

    def test_get_stats_structure(self):
        m = self._make()
        assert "total_events" in m.get_stats()

    def test_list_plans_returns_list(self):
        m = self._make()
        plans = m.list_plans()
        assert isinstance(plans, list)

    def test_get_active_plan_with_mock(self):
        m = self._make()
        m.list_plans = lambda: [
            {"name": "Balanced", "guid": "abc", "is_active": False},
            {"name": "High Performance", "guid": "def", "is_active": True},
        ]
        active = m.get_active_plan()
        assert active["name"] == "High Performance"

    def test_get_active_plan_fallback(self):
        m = self._make()
        m.list_plans = lambda: []
        active = m.get_active_plan()
        assert active["name"] == "Unknown"


# ═══════════════════════════════════════════════════════════════════════════
# MCP HANDLERS — Phase 42
# ═══════════════════════════════════════════════════════════════════════════

class TestMCPHandlersPhase42:
    def test_dnscli_servers(self):
        from src.mcp_server import handle_dnscli_servers
        result = asyncio.run(handle_dnscli_servers({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_dnscli_stats(self):
        from src.mcp_server import handle_dnscli_stats
        result = asyncio.run(handle_dnscli_stats({}))
        data = json.loads(result[0].text)
        assert "total_events" in data

    def test_storpool_list(self):
        from src.mcp_server import handle_storpool_list
        result = asyncio.run(handle_storpool_list({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_storpool_stats(self):
        from src.mcp_server import handle_storpool_stats
        result = asyncio.run(handle_storpool_stats({}))
        data = json.loads(result[0].text)
        assert "total_events" in data

    def test_pwrplan_list(self):
        from src.mcp_server import handle_pwrplan_list
        result = asyncio.run(handle_pwrplan_list({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_pwrplan_stats(self):
        from src.mcp_server import handle_pwrplan_stats
        result = asyncio.run(handle_pwrplan_stats({}))
        data = json.loads(result[0].text)
        assert "total_events" in data


# ═══════════════════════════════════════════════════════════════════════════
# TOOL COUNT PHASE 42
# ═══════════════════════════════════════════════════════════════════════════

class TestToolCountPhase42:
    def test_tool_count_at_least_492(self):
        """483 + 3 dnscli + 3 storpool + 3 pwrplan = 492."""
        from src.mcp_server import TOOL_DEFINITIONS
        assert len(TOOL_DEFINITIONS) >= 492, f"Expected >= 492 tools, got {len(TOOL_DEFINITIONS)}"

    def test_no_duplicate_tool_names(self):
        from src.mcp_server import TOOL_DEFINITIONS
        names = [t[0] for t in TOOL_DEFINITIONS]
        dupes = [n for n in names if names.count(n) > 1]
        assert len(names) == len(set(names)), f"Duplicate tools: {set(dupes)}"
