"""Phase 21 Tests — Network Scanner, Cron Manager, App Launcher, MCP Handlers."""

import asyncio
import json
import pytest


# ═══════════════════════════════════════════════════════════════════════════
# NETWORK SCANNER
# ═══════════════════════════════════════════════════════════════════════════

class TestNetworkScanner:
    @staticmethod
    def _make():
        from src.network_scanner import NetworkScanner
        return NetworkScanner()

    def test_singleton_exists(self):
        from src.network_scanner import network_scanner
        assert network_scanner is not None

    def test_default_profiles(self):
        ns = self._make()
        profiles = ns.list_profiles()
        names = [p["name"] for p in profiles]
        assert "cluster" in names
        assert "local" in names

    def test_register_profile(self):
        ns = self._make()
        p = ns.register_profile("custom", targets=["10.0.0.1"], ports=[80])
        assert p.name == "custom"
        assert len(ns.list_profiles()) == 3

    def test_remove_profile(self):
        ns = self._make()
        assert ns.remove_profile("local")
        assert not ns.remove_profile("local")

    def test_ping_localhost(self):
        ns = self._make()
        result = ns.ping("127.0.0.1")
        assert result["ip"] == "127.0.0.1"
        assert result["alive"] is True

    def test_check_port_closed(self):
        ns = self._make()
        result = ns.check_port("127.0.0.1", 59999, timeout_ms=500)
        assert result["port"] == 59999
        assert result["open"] is False

    def test_scan_ports(self):
        ns = self._make()
        results = ns.scan_ports("127.0.0.1", [59998, 59999], timeout_ms=500)
        assert len(results) == 2

    def test_known_hosts(self):
        ns = self._make()
        ns.ping("127.0.0.1")
        hosts = ns.get_known_hosts()
        assert len(hosts) >= 1

    def test_run_profile(self):
        ns = self._make()
        ns.register_profile("test", targets=["127.0.0.1"], scan_type="ping")
        result = ns.run_profile("test")
        assert result is not None
        assert result.hosts_found >= 1

    def test_history(self):
        ns = self._make()
        ns.register_profile("t", targets=["127.0.0.1"], scan_type="ping")
        ns.run_profile("t")
        h = ns.get_history()
        assert len(h) >= 1

    def test_stats(self):
        ns = self._make()
        stats = ns.get_stats()
        assert stats["total_profiles"] >= 2
        assert "profiles" in stats


# ═══════════════════════════════════════════════════════════════════════════
# CRON MANAGER
# ═══════════════════════════════════════════════════════════════════════════

class TestCronManager:
    @staticmethod
    def _make():
        from src.cron_manager import CronManager
        return CronManager()

    def test_singleton_exists(self):
        from src.cron_manager import cron_manager
        assert cron_manager is not None

    def test_add_job(self):
        from src.cron_manager import ScheduleType
        cm = self._make()
        job = cm.add_job("test", schedule_type=ScheduleType.INTERVAL, interval_seconds=60)
        assert job.name == "test"
        assert job.interval_seconds == 60

    def test_remove_job(self):
        cm = self._make()
        cm.add_job("temp")
        assert cm.remove_job("temp")
        assert not cm.remove_job("temp")

    def test_enable_disable(self):
        cm = self._make()
        cm.add_job("cmd")
        cm.disable("cmd")
        assert not cm.get("cmd").enabled
        cm.enable("cmd")
        assert cm.get("cmd").enabled

    def test_run_job(self):
        cm = self._make()
        cm.add_job("counter", callback=lambda: 42)
        result = cm.run_job("counter")
        assert result["success"]
        assert result["result"] == "42"

    def test_run_job_not_found(self):
        cm = self._make()
        result = cm.run_job("nope")
        assert not result["success"]

    def test_run_job_disabled(self):
        cm = self._make()
        cm.add_job("d", callback=lambda: 1)
        cm.disable("d")
        result = cm.run_job("d")
        assert not result["success"]

    def test_run_job_error(self):
        cm = self._make()
        cm.add_job("bad", callback=lambda: 1/0)
        result = cm.run_job("bad")
        assert not result["success"]
        assert "division" in result["error"]

    def test_run_count(self):
        cm = self._make()
        cm.add_job("c", callback=lambda: None)
        cm.run_job("c")
        cm.run_job("c")
        assert cm.get("c").run_count == 2

    def test_check_and_run_due(self):
        cm = self._make()
        cm.add_job("due", callback=lambda: None, interval_seconds=0)
        executed = cm.check_and_run_due()
        assert "due" in executed

    def test_list_jobs(self):
        cm = self._make()
        cm.add_job("a", group="g1")
        cm.add_job("b", group="g2")
        assert len(cm.list_jobs()) == 2
        assert len(cm.list_jobs(group="g1")) == 1

    def test_list_groups(self):
        cm = self._make()
        cm.add_job("a", group="alpha")
        cm.add_job("b", group="beta")
        groups = cm.list_groups()
        assert "alpha" in groups

    def test_executions(self):
        cm = self._make()
        cm.add_job("c", callback=lambda: None)
        cm.run_job("c")
        execs = cm.get_executions()
        assert len(execs) >= 1

    def test_stats(self):
        cm = self._make()
        cm.add_job("a", group="g")
        cm.run_job("a")
        stats = cm.get_stats()
        assert stats["total_jobs"] == 1
        assert stats["total_executions"] == 1


# ═══════════════════════════════════════════════════════════════════════════
# APP LAUNCHER
# ═══════════════════════════════════════════════════════════════════════════

class TestAppLauncher:
    @staticmethod
    def _make():
        from src.app_launcher import AppLauncher
        return AppLauncher()

    def test_singleton_exists(self):
        from src.app_launcher import app_launcher
        assert app_launcher is not None

    def test_register(self):
        al = self._make()
        app = al.register("notepad", "notepad.exe", description="Text editor")
        assert app.name == "notepad"

    def test_unregister(self):
        al = self._make()
        al.register("temp", "temp.exe")
        assert al.unregister("temp")
        assert not al.unregister("temp")

    def test_set_favorite(self):
        al = self._make()
        al.register("fav", "fav.exe")
        assert al.set_favorite("fav", True)
        assert al.get("fav").favorite

    def test_launch(self):
        al = self._make()
        al.register("echo_app", "python", args=["-c", "pass"])
        result = al.launch("echo_app")
        assert result["success"]
        assert result["pid"] is not None

    def test_launch_not_found(self):
        al = self._make()
        result = al.launch("nope")
        assert not result["success"]

    def test_launch_count(self):
        al = self._make()
        al.register("counter", "python", args=["-c", "pass"])
        al.launch("counter")
        al.launch("counter")
        assert al.get("counter").launch_count == 2

    def test_list_apps(self):
        al = self._make()
        al.register("a", "a.exe", group="g1")
        al.register("b", "b.exe", group="g2")
        assert len(al.list_apps()) == 2
        assert len(al.list_apps(group="g1")) == 1

    def test_list_favorites(self):
        al = self._make()
        al.register("fav", "fav.exe", favorite=True)
        al.register("nonfav", "nf.exe")
        favs = al.list_apps(favorites_only=True)
        assert len(favs) == 1

    def test_search(self):
        al = self._make()
        al.register("chrome", "chrome.exe", description="Web browser")
        al.register("notepad", "notepad.exe", description="Text editor")
        results = al.search("browser")
        assert len(results) == 1

    def test_history(self):
        al = self._make()
        al.register("h", "python", args=["-c", "pass"])
        al.launch("h")
        h = al.get_history()
        assert len(h) >= 1

    def test_most_used(self):
        al = self._make()
        al.register("a", "python", args=["-c", "pass"])
        al.register("b", "python", args=["-c", "pass"])
        al.launch("a")
        al.launch("a")
        al.launch("b")
        top = al.get_most_used()
        assert top[0]["name"] == "a"

    def test_list_groups(self):
        al = self._make()
        al.register("a", "a.exe", group="tools")
        groups = al.list_groups()
        assert "tools" in groups

    def test_stats(self):
        al = self._make()
        al.register("a", "python", args=["-c", "pass"], favorite=True, group="g")
        al.launch("a")
        stats = al.get_stats()
        assert stats["total_apps"] == 1
        assert stats["favorites"] == 1
        assert stats["total_launches"] == 1


# ═══════════════════════════════════════════════════════════════════════════
# MCP HANDLERS — Phase 21
# ═══════════════════════════════════════════════════════════════════════════

class TestMCPHandlersPhase21:
    def test_netscan_profiles(self):
        from src.mcp_server import handle_netscan_profiles
        result = asyncio.run(handle_netscan_profiles({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_netscan_history(self):
        from src.mcp_server import handle_netscan_history
        result = asyncio.run(handle_netscan_history({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_netscan_stats(self):
        from src.mcp_server import handle_netscan_stats
        result = asyncio.run(handle_netscan_stats({}))
        data = json.loads(result[0].text)
        assert "total_profiles" in data

    def test_cron_list(self):
        from src.mcp_server import handle_cron_list
        result = asyncio.run(handle_cron_list({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_cron_executions(self):
        from src.mcp_server import handle_cron_executions
        result = asyncio.run(handle_cron_executions({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_cron_stats(self):
        from src.mcp_server import handle_cron_stats
        result = asyncio.run(handle_cron_stats({}))
        data = json.loads(result[0].text)
        assert "total_jobs" in data

    def test_applnch_list(self):
        from src.mcp_server import handle_applnch_list
        result = asyncio.run(handle_applnch_list({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_applnch_history(self):
        from src.mcp_server import handle_applnch_history
        result = asyncio.run(handle_applnch_history({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_applnch_stats(self):
        from src.mcp_server import handle_applnch_stats
        result = asyncio.run(handle_applnch_stats({}))
        data = json.loads(result[0].text)
        assert "total_apps" in data


# ═══════════════════════════════════════════════════════════════════════════
# TOOL COUNT PHASE 21
# ═══════════════════════════════════════════════════════════════════════════

class TestToolCountPhase21:
    def test_tool_count_at_least_274(self):
        """265 + 3 netscan + 3 cron + 3 applnch = 274."""
        from src.mcp_server import TOOL_DEFINITIONS
        assert len(TOOL_DEFINITIONS) >= 274, f"Expected >= 274 tools, got {len(TOOL_DEFINITIONS)}"

    def test_no_duplicate_tool_names(self):
        from src.mcp_server import TOOL_DEFINITIONS
        names = [t[0] for t in TOOL_DEFINITIONS]
        dupes = [n for n in names if names.count(n) > 1]
        assert len(names) == len(set(names)), f"Duplicate tools: {set(dupes)}"
