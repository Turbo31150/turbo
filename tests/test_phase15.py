"""Phase 15 Tests — Permission Manager, Env Manager, Telemetry Collector, MCP Handlers."""

import asyncio
import json
import tempfile
import time
from pathlib import Path
import pytest


# ═══════════════════════════════════════════════════════════════════════════
# PERMISSION MANAGER
# ═══════════════════════════════════════════════════════════════════════════

class TestPermissionManager:
    @staticmethod
    def _make():
        from src.permission_manager import PermissionManager
        return PermissionManager()

    def test_singleton_exists(self):
        from src.permission_manager import permission_manager
        assert permission_manager is not None

    def test_default_roles(self):
        pm = self._make()
        roles = pm.list_roles()
        names = [r["name"] for r in roles]
        assert "admin" in names
        assert "operator" in names
        assert "viewer" in names

    def test_admin_wildcard(self):
        pm = self._make()
        pm.assign_role("root", "admin")
        assert pm.check_permission("root", "anything.at.all")

    def test_operator_permissions(self):
        pm = self._make()
        pm.assign_role("op1", "operator")
        assert pm.check_permission("op1", "cluster.read")
        assert not pm.check_permission("op1", "admin.delete")

    def test_viewer_read_only(self):
        pm = self._make()
        pm.assign_role("viewer1", "viewer")
        assert pm.check_permission("viewer1", "cluster.read")
        assert not pm.check_permission("viewer1", "cluster.write")

    def test_unknown_user(self):
        pm = self._make()
        assert not pm.check_permission("nobody", "cluster.read")

    def test_create_role(self):
        pm = self._make()
        pm.create_role("custom", {"custom.read", "custom.write"}, "Custom role")
        pm.assign_role("u1", "custom")
        assert pm.check_permission("u1", "custom.read")

    def test_delete_role(self):
        pm = self._make()
        pm.create_role("temp_role", {"temp.perm"})
        assert pm.delete_role("temp_role")
        assert not pm.delete_role("temp_role")

    def test_add_permission(self):
        pm = self._make()
        pm.create_role("ext", {"base.perm"})
        pm.add_permission("ext", "new.perm")
        pm.assign_role("u2", "ext")
        assert pm.check_permission("u2", "new.perm")

    def test_remove_permission(self):
        pm = self._make()
        pm.create_role("shrink", {"a", "b"})
        pm.remove_permission("shrink", "a")
        pm.assign_role("u3", "shrink")
        assert not pm.check_permission("u3", "a")
        assert pm.check_permission("u3", "b")

    def test_revoke_role(self):
        pm = self._make()
        pm.assign_role("u4", "admin")
        assert pm.check_permission("u4", "x")
        pm.revoke_role("u4", "admin")
        assert not pm.check_permission("u4", "x")

    def test_multi_role(self):
        pm = self._make()
        pm.create_role("r1", {"perm_a"})
        pm.create_role("r2", {"perm_b"})
        pm.assign_role("multi", "r1")
        pm.assign_role("multi", "r2")
        assert pm.check_permission("multi", "perm_a")
        assert pm.check_permission("multi", "perm_b")

    def test_get_user_permissions(self):
        pm = self._make()
        pm.create_role("perms_role", {"x", "y"})
        pm.assign_role("u5", "perms_role")
        perms = pm.get_user_permissions("u5")
        assert "x" in perms

    def test_stats(self):
        pm = self._make()
        pm.assign_role("u6", "viewer")
        pm.check_permission("u6", "cluster.read")
        stats = pm.get_stats()
        assert stats["total_roles"] >= 3
        assert stats["check_count"] >= 1


# ═══════════════════════════════════════════════════════════════════════════
# ENVIRONMENT MANAGER
# ═══════════════════════════════════════════════════════════════════════════

class TestEnvManager:
    @staticmethod
    def _make():
        from src.env_manager import EnvManager
        return EnvManager(store_path=Path(tempfile.mkdtemp()) / "env.json")

    def test_singleton_exists(self):
        from src.env_manager import env_manager
        assert env_manager is not None

    def test_default_profiles(self):
        em = self._make()
        profiles = em.list_profiles()
        names = [p["name"] for p in profiles]
        assert "dev" in names
        assert "staging" in names
        assert "prod" in names

    def test_default_active(self):
        em = self._make()
        assert em.active_profile == "dev"

    def test_set_active(self):
        em = self._make()
        assert em.set_active("prod")
        assert em.active_profile == "prod"

    def test_set_active_invalid(self):
        em = self._make()
        assert not em.set_active("nonexistent")

    def test_set_and_get_var(self):
        em = self._make()
        em.set_var("API_KEY", "abc123")
        assert em.get_var("API_KEY") == "abc123"

    def test_var_per_profile(self):
        em = self._make()
        em.set_var("DB_HOST", "localhost", profile="dev")
        em.set_var("DB_HOST", "db.prod.com", profile="prod")
        assert em.get_var("DB_HOST", "dev") == "localhost"
        assert em.get_var("DB_HOST", "prod") == "db.prod.com"

    def test_delete_var(self):
        em = self._make()
        em.set_var("TEMP", "val")
        assert em.delete_var("TEMP")
        assert em.get_var("TEMP") is None

    def test_create_profile(self):
        em = self._make()
        assert em.create_profile("test", {"TEST_VAR": "1"})
        assert em.get_var("TEST_VAR", "test") == "1"

    def test_create_duplicate(self):
        em = self._make()
        assert not em.create_profile("dev")  # already exists

    def test_delete_profile(self):
        em = self._make()
        em.create_profile("temp_env")
        assert em.delete_profile("temp_env")

    def test_delete_protected(self):
        em = self._make()
        assert not em.delete_profile("dev")
        assert not em.delete_profile("prod")

    def test_merge_profiles(self):
        em = self._make()
        em.set_var("A", "1", "dev")
        em.set_var("B", "2", "dev")
        em.set_var("B", "override", "staging")
        em.set_var("C", "3", "staging")
        merged = em.merge_profiles("dev", "staging")
        assert merged["A"] == "1"
        assert merged["B"] == "override"
        assert merged["C"] == "3"

    def test_persistence(self):
        path = Path(tempfile.mkdtemp()) / "persist_env.json"
        from src.env_manager import EnvManager
        em1 = EnvManager(store_path=path)
        em1.set_var("PERSIST", "yes")
        em2 = EnvManager(store_path=path)
        assert em2.get_var("PERSIST") == "yes"

    def test_stats(self):
        em = self._make()
        em.set_var("X", "1")
        stats = em.get_stats()
        assert stats["total_profiles"] >= 3
        assert stats["total_vars"] >= 1


# ═══════════════════════════════════════════════════════════════════════════
# TELEMETRY COLLECTOR
# ═══════════════════════════════════════════════════════════════════════════

class TestTelemetryCollector:
    @staticmethod
    def _make():
        from src.telemetry_collector import TelemetryCollector
        return TelemetryCollector(max_points=100)

    def test_singleton_exists(self):
        from src.telemetry_collector import telemetry
        assert telemetry is not None

    def test_record_and_query(self):
        tc = self._make()
        tc.record("api.calls", 1.0, {"endpoint": "/test"})
        results = tc.query(name="api.calls")
        assert len(results) >= 1

    def test_increment_counter(self):
        tc = self._make()
        tc.increment("requests")
        tc.increment("requests", 5)
        assert tc.get_counter("requests") == 6

    def test_gauge(self):
        tc = self._make()
        tc.set_gauge("cpu_temp", 65.0)
        assert tc.get_gauge("cpu_temp") == 65.0

    def test_histogram(self):
        tc = self._make()
        for v in [10, 20, 30, 40, 50]:
            tc.record_histogram("latency", v)
        stats = tc.get_histogram_stats("latency")
        assert stats["count"] == 5
        assert stats["min"] == 10
        assert stats["max"] == 50
        assert stats["avg"] == 30.0

    def test_histogram_missing(self):
        tc = self._make()
        assert tc.get_histogram_stats("nope") is None

    def test_query_since(self):
        tc = self._make()
        tc.record("old", 1.0)
        time.sleep(0.02)
        t = time.time()
        time.sleep(0.02)
        tc.record("new", 2.0)
        results = tc.query(since=t)
        assert len(results) == 1
        assert results[0]["name"] == "new"

    def test_query_limit(self):
        tc = self._make()
        for i in range(20):
            tc.record("bulk", float(i))
        results = tc.query(limit=5)
        assert len(results) == 5

    def test_rotation(self):
        tc = self._make()  # max 100
        for i in range(150):
            tc.record("rot", float(i))
        assert len(tc.query(limit=200)) <= 100

    def test_get_counters(self):
        tc = self._make()
        tc.increment("a")
        tc.increment("b", 3)
        counters = tc.get_counters()
        assert counters["a"] == 1
        assert counters["b"] == 3

    def test_get_gauges(self):
        tc = self._make()
        tc.set_gauge("g1", 1.0)
        tc.set_gauge("g2", 2.0)
        gauges = tc.get_gauges()
        assert len(gauges) == 2

    def test_stats(self):
        tc = self._make()
        tc.record("x", 1.0)
        tc.increment("c")
        tc.set_gauge("g", 5.0)
        stats = tc.get_stats()
        assert stats["total_points"] >= 1
        assert stats["counters"] >= 1
        assert stats["gauges"] >= 1


# ═══════════════════════════════════════════════════════════════════════════
# MCP HANDLERS — Phase 15
# ═══════════════════════════════════════════════════════════════════════════

class TestMCPHandlersPhase15:
    def test_perm_roles(self):
        from src.mcp_server import handle_perm_roles
        result = asyncio.run(handle_perm_roles({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_perm_users(self):
        from src.mcp_server import handle_perm_users
        result = asyncio.run(handle_perm_users({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_perm_check(self):
        from src.mcp_server import handle_perm_check
        result = asyncio.run(handle_perm_check({"user_id": "nobody", "permission": "test"}))
        data = json.loads(result[0].text)
        assert data["allowed"] is False

    def test_perm_stats(self):
        from src.mcp_server import handle_perm_stats
        result = asyncio.run(handle_perm_stats({}))
        data = json.loads(result[0].text)
        assert "total_roles" in data

    def test_env_profiles(self):
        from src.mcp_server import handle_env_profiles
        result = asyncio.run(handle_env_profiles({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_env_get(self):
        from src.mcp_server import handle_env_get
        result = asyncio.run(handle_env_get({"profile": "dev"}))
        data = json.loads(result[0].text)
        assert isinstance(data, dict)

    def test_env_stats(self):
        from src.mcp_server import handle_env_stats
        result = asyncio.run(handle_env_stats({}))
        data = json.loads(result[0].text)
        assert "total_profiles" in data

    def test_telemetry_counters(self):
        from src.mcp_server import handle_telemetry_counters
        result = asyncio.run(handle_telemetry_counters({}))
        data = json.loads(result[0].text)
        assert isinstance(data, dict)

    def test_telemetry_gauges(self):
        from src.mcp_server import handle_telemetry_gauges
        result = asyncio.run(handle_telemetry_gauges({}))
        data = json.loads(result[0].text)
        assert isinstance(data, dict)

    def test_telemetry_stats(self):
        from src.mcp_server import handle_telemetry_stats
        result = asyncio.run(handle_telemetry_stats({}))
        data = json.loads(result[0].text)
        assert "total_points" in data


# ═══════════════════════════════════════════════════════════════════════════
# TOOL COUNT PHASE 15
# ═══════════════════════════════════════════════════════════════════════════

class TestToolCountPhase15:
    def test_tool_count_at_least_220(self):
        """210 + 4 perm + 3 env + 3 telemetry = 220."""
        from src.mcp_server import TOOL_DEFINITIONS
        assert len(TOOL_DEFINITIONS) >= 220, f"Expected >= 220 tools, got {len(TOOL_DEFINITIONS)}"

    def test_no_duplicate_tool_names(self):
        from src.mcp_server import TOOL_DEFINITIONS
        names = [t[0] for t in TOOL_DEFINITIONS]
        dupes = [n for n in names if names.count(n) > 1]
        assert len(names) == len(set(names)), f"Duplicate tools: {set(dupes)}"
