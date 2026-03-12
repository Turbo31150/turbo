"""Phase 17 Tests — Service Mesh, Config Vault, Rule Engine, MCP Handlers."""

import asyncio
import json
import tempfile
import time
from pathlib import Path
import pytest


# ═══════════════════════════════════════════════════════════════════════════
# SERVICE MESH
# ═══════════════════════════════════════════════════════════════════════════

class TestServiceMesh:
    @staticmethod
    def _make():
        from src.service_mesh import ServiceMesh
        return ServiceMesh()

    def test_singleton_exists(self):
        from src.service_mesh import service_mesh
        assert service_mesh is not None

    def test_register(self):
        sm = self._make()
        inst = sm.register("s1", "api", "127.0.0.1", 8080)
        assert inst.name == "api"

    def test_deregister(self):
        sm = self._make()
        sm.register("s1", "api", "127.0.0.1", 8080)
        assert sm.deregister("s1")
        assert not sm.deregister("s1")

    def test_discover(self):
        sm = self._make()
        sm.register("s1", "api", "127.0.0.1", 8080)
        sm.register("s2", "api", "127.0.0.1", 8081)
        sm.register("s3", "db", "127.0.0.1", 5432)
        assert len(sm.discover("api")) == 2
        assert len(sm.discover("db")) == 1

    def test_discover_healthy_only(self):
        from src.service_mesh import ServiceStatus
        sm = self._make()
        sm.register("s1", "api", "127.0.0.1", 8080)
        sm.register("s2", "api", "127.0.0.1", 8081)
        sm.set_status("s2", ServiceStatus.UNHEALTHY)
        assert len(sm.discover("api", healthy_only=True)) == 1

    def test_list_services(self):
        sm = self._make()
        sm.register("s1", "api", "127.0.0.1", 8080)
        services = sm.list_services()
        assert len(services) == 1
        assert services[0]["name"] == "api"

    def test_list_service_names(self):
        sm = self._make()
        sm.register("s1", "api", "127.0.0.1", 8080)
        sm.register("s2", "db", "127.0.0.1", 5432)
        names = sm.list_service_names()
        assert "api" in names
        assert "db" in names

    def test_resolve_round_robin(self):
        from src.service_mesh import LBStrategy
        sm = self._make()
        sm.register("s1", "api", "h1", 8080)
        sm.register("s2", "api", "h2", 8081)
        r1 = sm.resolve("api", LBStrategy.ROUND_ROBIN)
        r2 = sm.resolve("api", LBStrategy.ROUND_ROBIN)
        assert {r1.host, r2.host} == {"h1", "h2"}

    def test_resolve_random(self):
        from src.service_mesh import LBStrategy
        sm = self._make()
        sm.register("s1", "api", "127.0.0.1", 8080)
        r = sm.resolve("api", LBStrategy.RANDOM)
        assert r is not None

    def test_resolve_least_conn(self):
        from src.service_mesh import LBStrategy
        sm = self._make()
        sm.register("s1", "api", "h1", 8080)
        sm.register("s2", "api", "h2", 8081)
        sm.connect("s1")
        sm.connect("s1")
        r = sm.resolve("api", LBStrategy.LEAST_CONN)
        assert r.host == "h2"

    def test_resolve_empty(self):
        sm = self._make()
        assert sm.resolve("nonexistent") is None

    def test_connect_disconnect(self):
        sm = self._make()
        sm.register("s1", "api", "127.0.0.1", 8080)
        sm.connect("s1")
        assert sm.get_instance("s1").active_connections == 1
        sm.disconnect("s1")
        assert sm.get_instance("s1").active_connections == 0

    def test_heartbeat(self):
        sm = self._make()
        sm.register("s1", "api", "127.0.0.1", 8080)
        assert sm.heartbeat("s1")
        assert not sm.heartbeat("nope")

    def test_check_heartbeats(self):
        sm = self._make()
        sm._heartbeat_timeout = 0.01
        sm.register("s1", "api", "127.0.0.1", 8080)
        time.sleep(0.02)
        expired = sm.check_heartbeats()
        assert "s1" in expired

    def test_stats(self):
        sm = self._make()
        sm.register("s1", "api", "127.0.0.1", 8080)
        stats = sm.get_stats()
        assert stats["total_instances"] == 1
        assert stats["healthy"] == 1


# ═══════════════════════════════════════════════════════════════════════════
# CONFIG VAULT
# ═══════════════════════════════════════════════════════════════════════════

class TestConfigVault:
    @staticmethod
    def _make():
        from src.config_vault import ConfigVault
        return ConfigVault()

    def test_singleton_exists(self):
        from src.config_vault import config_vault
        assert config_vault is not None

    def test_set_and_get(self):
        v = self._make()
        v.set_secret("API_KEY", "sk-123")
        assert v.get_secret("API_KEY") == "sk-123"

    def test_get_missing(self):
        v = self._make()
        assert v.get_secret("nope") is None

    def test_delete(self):
        v = self._make()
        v.set_secret("temp", "val")
        assert v.delete_secret("temp")
        assert v.get_secret("temp") is None

    def test_has_secret(self):
        v = self._make()
        v.set_secret("k", "v")
        assert v.has_secret("k")
        assert not v.has_secret("nope")

    def test_namespaces(self):
        v = self._make()
        v.set_secret("k1", "v1", namespace="prod")
        v.set_secret("k2", "v2", namespace="dev")
        ns = v.list_namespaces()
        assert "prod" in ns
        assert "dev" in ns

    def test_list_keys(self):
        v = self._make()
        v.set_secret("a", "1")
        v.set_secret("b", "2")
        keys = v.list_keys()
        assert "a" in keys
        assert "b" in keys

    def test_namespace_isolation(self):
        v = self._make()
        v.set_secret("key", "prod_val", namespace="prod")
        v.set_secret("key", "dev_val", namespace="dev")
        assert v.get_secret("key", "prod") == "prod_val"
        assert v.get_secret("key", "dev") == "dev_val"

    def test_delete_namespace(self):
        v = self._make()
        v.set_secret("a", "1", namespace="temp")
        v.set_secret("b", "2", namespace="temp")
        count = v.delete_namespace("temp")
        assert count == 2
        assert v.list_keys("temp") == []

    def test_rotate_secret(self):
        v = self._make()
        v.set_secret("k", "old")
        assert v.rotate_secret("k", "new")
        assert v.get_secret("k") == "new"

    def test_rotate_missing(self):
        v = self._make()
        assert not v.rotate_secret("nope", "val")

    def test_ttl_expiry(self):
        v = self._make()
        v.set_secret("exp", "val", ttl=0.01)
        time.sleep(0.02)
        assert v.get_secret("exp") is None

    def test_audit_log(self):
        v = self._make()
        v.set_secret("k", "v")
        v.get_secret("k")
        log = v.get_audit_log()
        assert len(log) >= 2
        actions = [e["action"] for e in log]
        assert "set" in actions
        assert "get" in actions

    def test_persistence(self):
        path = Path(tempfile.mkdtemp()) / "vault.json"
        from src.config_vault import ConfigVault
        v1 = ConfigVault(store_path=path)
        v1.set_secret("persist", "yes")
        v2 = ConfigVault(store_path=path)
        assert v2.get_secret("persist") == "yes"

    def test_stats(self):
        v = self._make()
        v.set_secret("k1", "v1")
        v.set_secret("k2", "v2", namespace="other")
        stats = v.get_stats()
        assert stats["total_secrets"] == 2
        assert stats["namespaces"] == 2


# ═══════════════════════════════════════════════════════════════════════════
# RULE ENGINE
# ═══════════════════════════════════════════════════════════════════════════

class TestRuleEngine:
    @staticmethod
    def _make():
        from src.rule_engine import RuleEngine
        return RuleEngine()

    def test_singleton_exists(self):
        from src.rule_engine import rule_engine
        assert rule_engine is not None

    def test_add_and_list(self):
        re = self._make()
        re.add_rule("r1", lambda ctx: True, lambda ctx: "ok")
        rules = re.list_rules()
        assert len(rules) == 1

    def test_remove_rule(self):
        re = self._make()
        re.add_rule("r1", lambda ctx: True, lambda ctx: "ok")
        assert re.remove_rule("r1")
        assert not re.remove_rule("r1")

    def test_enable_disable(self):
        re = self._make()
        re.add_rule("r1", lambda ctx: True, lambda ctx: "ok")
        re.disable_rule("r1")
        assert not re.get_rule("r1").enabled
        re.enable_rule("r1")
        assert re.get_rule("r1").enabled

    def test_evaluate(self):
        re = self._make()
        re.add_rule("high_temp", lambda ctx: ctx.get("temp", 0) > 80, lambda ctx: "alert")
        results = re.evaluate({"temp": 90})
        assert len(results) == 1
        assert results[0]["fired"]
        assert results[0]["result"] == "alert"

    def test_evaluate_no_match(self):
        re = self._make()
        re.add_rule("high_temp", lambda ctx: ctx.get("temp", 0) > 80, lambda ctx: "alert")
        results = re.evaluate({"temp": 50})
        assert len(results) == 0

    def test_priority_ordering(self):
        re = self._make()
        fired = []
        re.add_rule("low", lambda ctx: True, lambda ctx: fired.append("low"), priority=1)
        re.add_rule("high", lambda ctx: True, lambda ctx: fired.append("high"), priority=10)
        re.evaluate({})
        assert fired[0] == "high"

    def test_group_filter(self):
        re = self._make()
        re.add_rule("r1", lambda ctx: True, lambda ctx: "a", group="alerts")
        re.add_rule("r2", lambda ctx: True, lambda ctx: "b", group="trading")
        results = re.evaluate({}, group="alerts")
        assert len(results) == 1

    def test_first_match(self):
        re = self._make()
        re.add_rule("r1", lambda ctx: True, lambda ctx: "first", priority=10)
        re.add_rule("r2", lambda ctx: True, lambda ctx: "second", priority=5)
        result = re.evaluate_first({})
        assert result["result"] == "first"

    def test_disabled_rule_skipped(self):
        re = self._make()
        re.add_rule("r1", lambda ctx: True, lambda ctx: "ok")
        re.disable_rule("r1")
        results = re.evaluate({})
        assert len(results) == 0

    def test_fire_count(self):
        re = self._make()
        re.add_rule("r1", lambda ctx: True, lambda ctx: None)
        re.evaluate({})
        re.evaluate({})
        assert re.get_rule("r1").fire_count == 2

    def test_list_groups(self):
        re = self._make()
        re.add_rule("r1", lambda ctx: True, lambda ctx: None, group="a")
        re.add_rule("r2", lambda ctx: True, lambda ctx: None, group="b")
        groups = re.list_groups()
        assert "a" in groups
        assert "b" in groups

    def test_evaluation_log(self):
        re = self._make()
        re.add_rule("r1", lambda ctx: True, lambda ctx: None)
        re.evaluate({"x": 1})
        log = re.get_evaluation_log()
        assert len(log) >= 1
        assert log[0]["rule"] == "r1"

    def test_error_handling(self):
        def bad_action(ctx):
            raise ValueError("boom")
        re = self._make()
        re.add_rule("bad", lambda ctx: True, bad_action)
        results = re.evaluate({})
        assert len(results) == 1
        assert not results[0]["fired"]
        assert "boom" in results[0]["error"]

    def test_stats(self):
        re = self._make()
        re.add_rule("r1", lambda ctx: True, lambda ctx: None, group="g1")
        re.add_rule("r2", lambda ctx: True, lambda ctx: None, group="g2")
        re.disable_rule("r2")
        re.evaluate({})
        stats = re.get_stats()
        assert stats["total_rules"] == 2
        assert stats["enabled"] == 1
        assert stats["groups"] == 2


# ═══════════════════════════════════════════════════════════════════════════
# MCP HANDLERS — Phase 17
# ═══════════════════════════════════════════════════════════════════════════

class TestMCPHandlersPhase17:
    def test_mesh_services(self):
        from src.mcp_server import handle_mesh_services
        result = asyncio.run(handle_mesh_services({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_mesh_names(self):
        from src.mcp_server import handle_mesh_names
        result = asyncio.run(handle_mesh_names({}))
        data = json.loads(result[0].text)
        assert "services" in data

    def test_mesh_stats(self):
        from src.mcp_server import handle_mesh_stats
        result = asyncio.run(handle_mesh_stats({}))
        data = json.loads(result[0].text)
        assert "total_instances" in data

    def test_cfgvault_namespaces(self):
        from src.mcp_server import handle_cfgvault_namespaces
        result = asyncio.run(handle_cfgvault_namespaces({}))
        data = json.loads(result[0].text)
        assert "namespaces" in data

    def test_cfgvault_keys(self):
        from src.mcp_server import handle_cfgvault_keys
        result = asyncio.run(handle_cfgvault_keys({"namespace": "default"}))
        data = json.loads(result[0].text)
        assert "keys" in data

    def test_cfgvault_stats(self):
        from src.mcp_server import handle_cfgvault_stats
        result = asyncio.run(handle_cfgvault_stats({}))
        data = json.loads(result[0].text)
        assert "total_secrets" in data

    def test_rules_list(self):
        from src.mcp_server import handle_rules_list
        result = asyncio.run(handle_rules_list({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_rules_groups(self):
        from src.mcp_server import handle_rules_groups
        result = asyncio.run(handle_rules_groups({}))
        data = json.loads(result[0].text)
        assert "groups" in data

    def test_rules_stats(self):
        from src.mcp_server import handle_rules_stats
        result = asyncio.run(handle_rules_stats({}))
        data = json.loads(result[0].text)
        assert "total_rules" in data


# ═══════════════════════════════════════════════════════════════════════════
# TOOL COUNT PHASE 17
# ═══════════════════════════════════════════════════════════════════════════

class TestToolCountPhase17:
    def test_tool_count_at_least_238(self):
        """229 + 3 mesh + 3 vault + 3 rules = 238."""
        from src.mcp_server import TOOL_DEFINITIONS
        assert len(TOOL_DEFINITIONS) >= 238, f"Expected >= 238 tools, got {len(TOOL_DEFINITIONS)}"

    def test_no_duplicate_tool_names(self):
        from src.mcp_server import TOOL_DEFINITIONS
        names = [t[0] for t in TOOL_DEFINITIONS]
        dupes = [n for n in names if names.count(n) > 1]
        assert len(names) == len(set(names)), f"Duplicate tools: {set(dupes)}"
