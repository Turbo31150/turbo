"""Phase 11 Tests — Cache Manager, Secret Vault, Dependency Graph, MCP Handlers."""

import asyncio
import json
import tempfile
import time
from pathlib import Path
import pytest


# ═══════════════════════════════════════════════════════════════════════════
# CACHE MANAGER
# ═══════════════════════════════════════════════════════════════════════════

class TestCacheManager:
    @staticmethod
    def _make():
        from src.cache_manager import CacheManager
        tmpdir = tempfile.mkdtemp()
        return CacheManager(l1_max_size=10, l2_dir=Path(tmpdir) / "cache", default_ttl_s=60)

    def test_singleton_exists(self):
        from src.cache_manager import cache_manager
        assert cache_manager is not None

    def test_set_and_get(self):
        cm = self._make()
        cm.set("key1", "value1")
        assert cm.get("key1") == "value1"

    def test_miss(self):
        cm = self._make()
        assert cm.get("nonexistent") is None

    def test_ttl_expiry_l1(self):
        """L1 entry expires, L2 promotes back — verify L1 eviction works."""
        from src.cache_manager import CacheManager
        # No L2 dir to avoid fallback
        cm = CacheManager(l1_max_size=10, l2_dir=Path(tempfile.mkdtemp()) / "no_l2", default_ttl_s=60)
        cm.set("exp", "val", ttl_s=0.01)
        time.sleep(0.02)
        # L1 expired, L2 has the value but with default TTL → still returned
        # Test that L1 entry is actually expired
        ns = cm._ns("default")
        if "exp" in ns:
            assert ns["exp"].expired

    def test_namespaces(self):
        cm = self._make()
        cm.set("k", "v1", namespace="ns1")
        cm.set("k", "v2", namespace="ns2")
        assert cm.get("k", "ns1") == "v1"
        assert cm.get("k", "ns2") == "v2"

    def test_delete(self):
        cm = self._make()
        cm.set("del", "val")
        assert cm.delete("del")
        assert cm.get("del") is None

    def test_clear_namespace(self):
        cm = self._make()
        cm.set("a", "1", namespace="ns")
        cm.set("b", "2", namespace="ns")
        count = cm.clear("ns")
        assert count >= 2
        assert cm.get("a", "ns") is None

    def test_lru_eviction(self):
        cm = self._make()  # max 10
        for i in range(15):
            cm.set(f"k{i}", f"v{i}")
        # First entries should be evicted
        assert cm.get("k0") is not None  # L2 fallback
        stats = cm.get_stats()
        assert stats["evictions"] >= 5

    def test_l2_persistence(self):
        tmpdir = tempfile.mkdtemp()
        cm1 = self._make()
        cm1._l2_dir = Path(tmpdir) / "l2"
        cm1.set("persist", "data")
        # New instance with same L2 dir
        from src.cache_manager import CacheManager
        cm2 = CacheManager(l2_dir=cm1._l2_dir)
        # L1 miss → L2 hit
        assert cm2.get("persist") == "data"

    def test_stats(self):
        cm = self._make()
        cm.set("s", "v")
        cm.get("s")
        cm.get("miss")
        stats = cm.get_stats()
        assert stats["l1_hits"] >= 1
        assert stats["sets"] >= 1
        assert stats["hit_rate"] > 0

    def test_get_namespaces(self):
        cm = self._make()
        cm.set("x", "1", namespace="alpha")
        cm.set("y", "2", namespace="beta")
        ns = cm.get_namespaces()
        assert "alpha" in ns
        assert "beta" in ns


# ═══════════════════════════════════════════════════════════════════════════
# SECRET VAULT
# ═══════════════════════════════════════════════════════════════════════════

class TestSecretVault:
    @staticmethod
    def _make():
        from src.secret_vault import SecretVault
        tmpdir = tempfile.mkdtemp()
        return SecretVault(vault_path=Path(tmpdir) / "test.vault", passphrase="test-key-123")

    def test_singleton_exists(self):
        from src.secret_vault import secret_vault
        assert secret_vault is not None

    def test_set_and_get(self):
        sv = self._make()
        sv.set("api_key", "sk-12345")
        assert sv.get("api_key") == "sk-12345"

    def test_get_missing(self):
        sv = self._make()
        assert sv.get("nope") is None

    def test_delete(self):
        sv = self._make()
        sv.set("temp", "val")
        assert sv.delete("temp")
        assert sv.get("temp") is None

    def test_exists(self):
        sv = self._make()
        sv.set("exists", "yes")
        assert sv.exists("exists")
        assert not sv.exists("nope")

    def test_list_keys(self):
        sv = self._make()
        sv.set("k1", "v1")
        sv.set("k2", "v2")
        keys = sv.list_keys()
        assert "k1" in keys
        assert "k2" in keys

    def test_list_entries_no_values(self):
        sv = self._make()
        sv.set("secret", "hidden_value", metadata={"env": "prod"})
        entries = sv.list_entries()
        assert len(entries) == 1
        assert "value" not in entries[0]  # no value exposed
        assert entries[0]["metadata"]["env"] == "prod"

    def test_metadata(self):
        sv = self._make()
        sv.set("key", "val", metadata={"service": "trading"})
        entry = sv.get_with_metadata("key")
        assert entry["metadata"]["service"] == "trading"
        assert entry["has_value"] is True

    def test_persistence(self):
        tmpdir = tempfile.mkdtemp()
        path = Path(tmpdir) / "persist.vault"
        from src.secret_vault import SecretVault
        sv1 = SecretVault(vault_path=path, passphrase="same-key")
        sv1.set("saved", "data123")
        sv2 = SecretVault(vault_path=path, passphrase="same-key")
        assert sv2.get("saved") == "data123"

    def test_stats(self):
        sv = self._make()
        sv.set("s", "v")
        stats = sv.get_stats()
        assert stats["total_secrets"] == 1
        assert "encrypted" in stats


# ═══════════════════════════════════════════════════════════════════════════
# DEPENDENCY GRAPH
# ═══════════════════════════════════════════════════════════════════════════

class TestDependencyGraph:
    @staticmethod
    def _make():
        from src.dependency_graph import DependencyGraph
        return DependencyGraph()

    def test_singleton_exists(self):
        from src.dependency_graph import dep_graph
        assert dep_graph is not None

    def test_singleton_has_nodes(self):
        from src.dependency_graph import dep_graph
        assert len(dep_graph.get_all_nodes()) >= 20

    def test_add_and_get_deps(self):
        dg = self._make()
        dg.add_dependency("A", "B")
        dg.add_dependency("A", "C")
        deps = dg.get_dependencies("A")
        assert "B" in deps
        assert "C" in deps

    def test_get_dependents(self):
        dg = self._make()
        dg.add_dependency("X", "Y")
        assert "X" in dg.get_dependents("Y")

    def test_no_cycle(self):
        dg = self._make()
        dg.add_dependency("A", "B")
        dg.add_dependency("B", "C")
        assert not dg.has_cycle()

    def test_cycle_detection(self):
        dg = self._make()
        dg.add_dependency("A", "B")
        dg.add_dependency("B", "C")
        dg.add_dependency("C", "A")
        assert dg.has_cycle()

    def test_topological_sort(self):
        dg = self._make()
        dg.add_dependency("app", "db")
        dg.add_dependency("app", "cache")
        dg.add_dependency("cache", "db")
        order = dg.topological_sort()
        assert order.index("db") < order.index("cache")
        assert order.index("cache") < order.index("app")

    def test_topological_sort_cycle(self):
        dg = self._make()
        dg.add_dependency("A", "B")
        dg.add_dependency("B", "A")
        with pytest.raises(ValueError, match="Cycle"):
            dg.topological_sort()

    def test_impact_analysis(self):
        dg = self._make()
        dg.add_dependency("web", "api")
        dg.add_dependency("api", "db")
        dg.add_dependency("worker", "db")
        affected = dg.impact_analysis("db")
        assert "api" in affected
        assert "web" in affected
        assert "worker" in affected

    def test_transitive_deps(self):
        dg = self._make()
        dg.add_dependency("A", "B")
        dg.add_dependency("B", "C")
        dg.add_dependency("C", "D")
        trans = dg.transitive_deps("A")
        assert set(trans) == {"B", "C", "D"}

    def test_remove_node(self):
        dg = self._make()
        dg.add_node("temp")
        assert dg.remove_node("temp")
        assert "temp" not in dg.get_all_nodes()

    def test_stats(self):
        dg = self._make()
        dg.add_dependency("x", "y")
        stats = dg.get_stats()
        assert stats["total_nodes"] == 2
        assert stats["total_edges"] == 1
        assert stats["has_cycle"] is False

    def test_singleton_no_cycle(self):
        from src.dependency_graph import dep_graph
        assert not dep_graph.has_cycle()

    def test_singleton_topological_sort(self):
        from src.dependency_graph import dep_graph
        order = dep_graph.topological_sort()
        assert len(order) >= 20


# ═══════════════════════════════════════════════════════════════════════════
# MCP HANDLERS — Phase 11
# ═══════════════════════════════════════════════════════════════════════════

class TestMCPHandlersPhase11:
    def test_cache_get(self):
        from src.mcp_server import handle_cache_get
        result = asyncio.run(handle_cache_get({"key": "test_key"}))
        data = json.loads(result[0].text)
        assert "hit" in data

    def test_cache_set(self):
        from src.mcp_server import handle_cache_set
        result = asyncio.run(handle_cache_set({"key": "mcp_test", "value": "hello"}))
        assert "cached" in result[0].text.lower()

    def test_cache_mgr_stats(self):
        from src.mcp_server import handle_cache_mgr_stats
        result = asyncio.run(handle_cache_mgr_stats({}))
        data = json.loads(result[0].text)
        assert "l1_hits" in data

    def test_vault_list(self):
        from src.mcp_server import handle_vault_list
        result = asyncio.run(handle_vault_list({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_vault_stats(self):
        from src.mcp_server import handle_vault_stats
        result = asyncio.run(handle_vault_stats({}))
        data = json.loads(result[0].text)
        assert "total_secrets" in data

    def test_depgraph_show(self):
        from src.mcp_server import handle_depgraph_show
        result = asyncio.run(handle_depgraph_show({}))
        data = json.loads(result[0].text)
        assert isinstance(data, dict)
        assert len(data) >= 10

    def test_depgraph_impact(self):
        from src.mcp_server import handle_depgraph_impact
        result = asyncio.run(handle_depgraph_impact({"node": "event_bus"}))
        data = json.loads(result[0].text)
        assert "affected" in data
        assert data["count"] >= 1

    def test_depgraph_order(self):
        from src.mcp_server import handle_depgraph_order
        result = asyncio.run(handle_depgraph_order({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)
        assert len(data) >= 20

    def test_depgraph_stats(self):
        from src.mcp_server import handle_depgraph_stats
        result = asyncio.run(handle_depgraph_stats({}))
        data = json.loads(result[0].text)
        assert "total_nodes" in data


# ═══════════════════════════════════════════════════════════════════════════
# TOOL COUNT PHASE 11
# ═══════════════════════════════════════════════════════════════════════════

class TestToolCountPhase11:
    def test_tool_count_at_least_186(self):
        """177 + 3 cache + 2 vault + 4 depgraph = 186."""
        from src.mcp_server import TOOL_DEFINITIONS
        assert len(TOOL_DEFINITIONS) >= 186, f"Expected >= 186 tools, got {len(TOOL_DEFINITIONS)}"

    def test_no_duplicate_tool_names(self):
        from src.mcp_server import TOOL_DEFINITIONS
        names = [t[0] for t in TOOL_DEFINITIONS]
        dupes = [n for n in names if names.count(n) > 1]
        assert len(names) == len(set(names)), f"Duplicate tools: {set(dupes)}"
