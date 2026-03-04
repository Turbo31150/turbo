"""Phase 9 Tests — Plugin Manager, Command Router, Resource Monitor, MCP Handlers."""

import asyncio
import json
import tempfile
from pathlib import Path
import pytest


# ═══════════════════════════════════════════════════════════════════════════
# PLUGIN MANAGER
# ═══════════════════════════════════════════════════════════════════════════

class TestPluginManager:
    @staticmethod
    def _make(tmpdir=None):
        from src.plugin_manager import PluginManager
        d = Path(tmpdir or tempfile.mkdtemp()) / "plugins"
        d.mkdir(parents=True, exist_ok=True)
        return PluginManager(plugins_dir=d)

    def test_singleton_exists(self):
        from src.plugin_manager import plugin_manager
        assert plugin_manager is not None

    def test_discover_empty(self):
        pm = self._make()
        assert pm.discover() == []

    def test_discover_finds_plugin(self):
        pm = self._make()
        p = pm.plugins_dir / "test_plugin"
        p.mkdir()
        (p / "manifest.json").write_text('{"name":"test","version":"1.0","description":"Test plugin"}')
        discovered = pm.discover()
        assert "test_plugin" in discovered

    def test_load_plugin(self):
        pm = self._make()
        p = pm.plugins_dir / "myplugin"
        p.mkdir()
        (p / "manifest.json").write_text('{"name":"myplugin","version":"0.1","description":"desc","author":"me"}')
        info = pm.load("myplugin")
        assert info.name == "myplugin"
        assert info.version == "0.1"
        assert info.enabled is True

    def test_load_missing_plugin(self):
        pm = self._make()
        with pytest.raises(FileNotFoundError):
            pm.load("nonexistent")

    def test_unload_plugin(self):
        pm = self._make()
        p = pm.plugins_dir / "temp"
        p.mkdir()
        (p / "manifest.json").write_text('{"name":"temp","version":"1.0","description":""}')
        pm.load("temp")
        assert pm.unload("temp")
        assert pm.get_plugin("temp") is None

    def test_enable_disable(self):
        pm = self._make()
        p = pm.plugins_dir / "toggle"
        p.mkdir()
        (p / "manifest.json").write_text('{"name":"toggle","version":"1.0","description":""}')
        pm.load("toggle")
        pm.disable("toggle")
        assert pm.get_plugin("toggle").enabled is False
        pm.enable("toggle")
        assert pm.get_plugin("toggle").enabled is True

    def test_list_plugins(self):
        pm = self._make()
        p = pm.plugins_dir / "listed"
        p.mkdir()
        (p / "manifest.json").write_text('{"name":"listed","version":"2.0","description":"d"}')
        pm.load("listed")
        plugins = pm.list_plugins()
        assert len(plugins) == 1
        assert plugins[0]["name"] == "listed"

    def test_stats(self):
        pm = self._make()
        stats = pm.get_stats()
        assert "total_plugins" in stats
        assert "plugins_dir" in stats

    def test_plugin_with_tools(self):
        pm = self._make()
        p = pm.plugins_dir / "tooled"
        p.mkdir()
        (p / "manifest.json").write_text('{"name":"tooled","version":"1.0","description":"","tools":["tool_a","tool_b"]}')
        info = pm.load("tooled")
        assert info.tools == ["tool_a", "tool_b"]


# ═══════════════════════════════════════════════════════════════════════════
# COMMAND ROUTER
# ═══════════════════════════════════════════════════════════════════════════

class TestCommandRouter:
    @staticmethod
    def _make():
        from src.command_router import CommandRouter
        return CommandRouter()

    def test_singleton_exists(self):
        from src.command_router import command_router
        assert command_router is not None

    def test_register_and_match(self):
        cr = self._make()
        cr.register("greet", handler=lambda: None, keywords=["hello", "salut"])
        matches = cr.match("hello world")
        assert len(matches) >= 1
        assert matches[0].route.name == "greet"

    def test_exact_match(self):
        cr = self._make()
        cr.register("status", handler=lambda: None, keywords=["check"])
        matches = cr.match("status")
        assert matches[0].matched_by == "exact"
        assert matches[0].score == 1.0

    def test_pattern_match(self):
        cr = self._make()
        cr.register("search", handler=lambda: None, patterns=[r"cherche\s+(?P<query>.+)"])
        matches = cr.match("cherche Python bug")
        assert len(matches) >= 1
        assert matches[0].captures.get("query") == "Python bug"

    def test_no_match(self):
        cr = self._make()
        cr.register("specific", handler=lambda: None, keywords=["xyz123"])
        result = cr.route("completely unrelated")
        assert result is None

    def test_route_records_history(self):
        cr = self._make()
        cr.register("test", handler=lambda: None, keywords=["test"])
        cr.route("test something")
        assert len(cr.get_history()) == 1

    def test_route_increments_count(self):
        cr = self._make()
        cr.register("counter", handler=lambda: None, keywords=["count"])
        cr.route("count this")
        cr.route("count that")
        routes = cr.get_routes()
        assert routes[0]["call_count"] == 2

    def test_unregister(self):
        cr = self._make()
        cr.register("temp", handler=lambda: None, keywords=["temp"])
        assert cr.unregister("temp")
        assert cr.match("temp") == []

    def test_priority_ordering(self):
        cr = self._make()
        cr.register("low", handler=lambda: None, keywords=["test"], priority=0)
        cr.register("high", handler=lambda: None, keywords=["test"], priority=10)
        matches = cr.match("test")
        # Both match, but equal keyword score → high priority comes first
        assert matches[0].route.name == "high"

    def test_stats(self):
        cr = self._make()
        cr.register("s1", handler=lambda: None, keywords=["a"], category="cat1")
        stats = cr.get_stats()
        assert stats["total_routes"] == 1
        assert "cat1" in stats["categories"]

    def test_get_routes(self):
        cr = self._make()
        cr.register("r1", handler=lambda: None, keywords=["k1"], description="desc1")
        routes = cr.get_routes()
        assert routes[0]["description"] == "desc1"


# ═══════════════════════════════════════════════════════════════════════════
# RESOURCE MONITOR
# ═══════════════════════════════════════════════════════════════════════════

class TestResourceMonitor:
    def test_singleton_exists(self):
        from src.resource_monitor import resource_monitor
        assert resource_monitor is not None

    def test_sample_structure(self):
        from src.resource_monitor import ResourceMonitor
        rm = ResourceMonitor()
        snap = rm.sample()
        assert "ts" in snap
        assert "cpu_percent" in snap
        assert "ram_used_gb" in snap
        assert "gpus" in snap
        assert "disks" in snap

    def test_sample_adds_history(self):
        from src.resource_monitor import ResourceMonitor
        rm = ResourceMonitor()
        rm.sample()
        rm.sample()
        assert len(rm.get_history()) == 2

    def test_get_latest(self):
        from src.resource_monitor import ResourceMonitor
        rm = ResourceMonitor()
        assert rm.get_latest() == {}
        rm.sample()
        assert rm.get_latest() != {}

    def test_thresholds(self):
        from src.resource_monitor import ResourceMonitor
        rm = ResourceMonitor()
        rm.set_threshold("cpu_percent", 50.0)
        assert rm.get_thresholds()["cpu_percent"] == 50.0

    def test_stats(self):
        from src.resource_monitor import ResourceMonitor
        rm = ResourceMonitor()
        rm.sample()
        stats = rm.get_stats()
        assert stats["samples"] == 1
        assert "thresholds" in stats


# ═══════════════════════════════════════════════════════════════════════════
# MCP HANDLERS — Phase 9
# ═══════════════════════════════════════════════════════════════════════════

class TestMCPHandlersPhase9:
    def test_plugin_list(self):
        from src.mcp_server import handle_plugin_list
        result = asyncio.run(handle_plugin_list({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_plugin_discover(self):
        from src.mcp_server import handle_plugin_discover
        result = asyncio.run(handle_plugin_discover({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_plugin_stats(self):
        from src.mcp_server import handle_plugin_stats
        result = asyncio.run(handle_plugin_stats({}))
        data = json.loads(result[0].text)
        assert "total_plugins" in data

    def test_cmd_route(self):
        from src.mcp_server import handle_cmd_route
        result = asyncio.run(handle_cmd_route({"text": "test"}))
        data = json.loads(result[0].text)
        assert "route" in data

    def test_cmd_routes(self):
        from src.mcp_server import handle_cmd_routes
        result = asyncio.run(handle_cmd_routes({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_cmd_stats(self):
        from src.mcp_server import handle_cmd_stats
        result = asyncio.run(handle_cmd_stats({}))
        data = json.loads(result[0].text)
        assert "total_routes" in data

    def test_resource_sample(self):
        from src.mcp_server import handle_resource_sample
        result = asyncio.run(handle_resource_sample({}))
        data = json.loads(result[0].text)
        assert "cpu_percent" in data

    def test_resource_latest(self):
        from src.mcp_server import handle_resource_latest
        result = asyncio.run(handle_resource_latest({}))
        # May return empty dict if no sample taken yet via this singleton
        data = json.loads(result[0].text)
        assert isinstance(data, dict)

    def test_resource_stats(self):
        from src.mcp_server import handle_resource_stats
        result = asyncio.run(handle_resource_stats({}))
        data = json.loads(result[0].text)
        assert "samples" in data


# ═══════════════════════════════════════════════════════════════════════════
# TOOL COUNT PHASE 9
# ═══════════════════════════════════════════════════════════════════════════

class TestToolCountPhase9:
    def test_tool_count_at_least_168(self):
        """159 + 3 plugin + 3 cmd + 3 resource = 168."""
        from src.mcp_server import TOOL_DEFINITIONS
        assert len(TOOL_DEFINITIONS) >= 168, f"Expected >= 168 tools, got {len(TOOL_DEFINITIONS)}"

    def test_no_duplicate_tool_names(self):
        from src.mcp_server import TOOL_DEFINITIONS
        names = [t[0] for t in TOOL_DEFINITIONS]
        dupes = [n for n in names if names.count(n) > 1]
        assert len(names) == len(set(names)), f"Duplicate tools: {set(dupes)}"
