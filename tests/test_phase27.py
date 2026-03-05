"""Phase 27 Tests — Printer Manager, Firewall Controller, Scheduler Manager, MCP Handlers."""

import asyncio
import json
import pytest


# ═══════════════════════════════════════════════════════════════════════════
# PRINTER MANAGER
# ═══════════════════════════════════════════════════════════════════════════

class TestPrinterManager:
    @staticmethod
    def _make():
        from src.printer_manager import PrinterManager
        return PrinterManager()

    def test_singleton_exists(self):
        from src.printer_manager import printer_manager
        assert printer_manager is not None

    def test_get_events_empty(self):
        pm = self._make()
        events = pm.get_events()
        assert isinstance(events, list)
        assert len(events) == 0

    def test_record_event(self):
        pm = self._make()
        pm._record("test", "HP LaserJet", True, "ok")
        events = pm.get_events()
        assert len(events) == 1
        assert events[0]["action"] == "test"
        assert events[0]["printer"] == "HP LaserJet"

    def test_printer_info_dataclass(self):
        from src.printer_manager import PrinterInfo
        p = PrinterInfo(name="HP LaserJet", port="USB001", driver="HP Universal")
        assert p.name == "HP LaserJet"
        assert p.is_default is False

    def test_print_event_dataclass(self):
        from src.printer_manager import PrintEvent
        e = PrintEvent(action="list", printer="Canon")
        assert e.action == "list"
        assert e.success is True

    def test_search_with_mock(self):
        pm = self._make()
        pm.list_printers = lambda: [
            {"name": "HP LaserJet", "port": "USB001"},
            {"name": "Canon PIXMA", "port": "USB002"},
        ]
        results = pm.search("canon")
        assert len(results) == 1
        assert results[0]["name"] == "Canon PIXMA"

    def test_search_no_match(self):
        pm = self._make()
        pm.list_printers = lambda: [{"name": "HP LaserJet"}]
        results = pm.search("Epson")
        assert len(results) == 0

    def test_get_default_with_mock(self):
        pm = self._make()
        pm.list_printers = lambda: [
            {"name": "HP", "is_default": False},
            {"name": "Canon", "is_default": True},
        ]
        default = pm.get_default()
        assert default["name"] == "Canon"

    def test_get_stats_structure(self):
        pm = self._make()
        pm.list_printers = lambda: [{"name": "HP", "is_default": True}]
        stats = pm.get_stats()
        assert "total_printers" in stats
        assert "default_printer" in stats
        assert stats["total_printers"] == 1


# ═══════════════════════════════════════════════════════════════════════════
# FIREWALL CONTROLLER
# ═══════════════════════════════════════════════════════════════════════════

class TestFirewallController:
    @staticmethod
    def _make():
        from src.firewall_controller import FirewallController
        return FirewallController()

    def test_singleton_exists(self):
        from src.firewall_controller import firewall_controller
        assert firewall_controller is not None

    def test_get_events_empty(self):
        fc = self._make()
        events = fc.get_events()
        assert isinstance(events, list)
        assert len(events) == 0

    def test_record_event(self):
        fc = self._make()
        fc._record("test", "AllowHTTP", True, "ok")
        events = fc.get_events()
        assert len(events) == 1
        assert events[0]["rule_name"] == "AllowHTTP"

    def test_firewall_rule_dataclass(self):
        from src.firewall_controller import FirewallRule
        r = FirewallRule(name="AllowHTTP", direction="In", action="Allow")
        assert r.name == "AllowHTTP"
        assert r.protocol == ""

    def test_firewall_event_dataclass(self):
        from src.firewall_controller import FirewallEvent
        e = FirewallEvent(action="list", rule_name="TestRule")
        assert e.action == "list"
        assert e.success is True

    def test_parse_rules(self):
        fc = self._make()
        sample = (
            "Rule Name:                            TestRule\n"
            "Direction:                            In\n"
            "Action:                               Allow\n"
            "Protocol:                             TCP\n"
            "LocalPort:                            80\n"
            "Enabled:                              Yes\n"
            "Profiles:                             Domain\n"
            "---\n"
            "Rule Name:                            BlockAll\n"
            "Direction:                            Out\n"
            "Action:                               Block\n"
        )
        rules = fc._parse_rules(sample)
        assert len(rules) == 2
        assert rules[0]["name"] == "TestRule"
        assert rules[0]["direction"] == "In"
        assert rules[0]["action"] == "Allow"
        assert rules[0]["local_port"] == "80"
        assert rules[1]["name"] == "BlockAll"

    def test_search_rules_with_mock(self):
        fc = self._make()
        fc.list_rules = lambda: [
            {"name": "AllowHTTP", "direction": "In"},
            {"name": "BlockSSH", "direction": "In"},
        ]
        results = fc.search_rules("http")
        assert len(results) == 1

    def test_count_rules_with_mock(self):
        fc = self._make()
        fc.list_rules = lambda: [
            {"name": "R1", "direction": "In"},
            {"name": "R2", "direction": "Out"},
            {"name": "R3", "direction": "In"},
        ]
        counts = fc.count_rules()
        assert counts["inbound"] == 2
        assert counts["outbound"] == 1
        assert counts["total"] == 3


# ═══════════════════════════════════════════════════════════════════════════
# SCHEDULER MANAGER
# ═══════════════════════════════════════════════════════════════════════════

class TestSchedulerManager:
    @staticmethod
    def _make():
        from src.scheduler_manager import SchedulerManager
        return SchedulerManager()

    def test_singleton_exists(self):
        from src.scheduler_manager import scheduler_manager
        assert scheduler_manager is not None

    def test_get_events_empty(self):
        sm = self._make()
        events = sm.get_events()
        assert isinstance(events, list)
        assert len(events) == 0

    def test_record_event(self):
        sm = self._make()
        sm._record("test", "MyTask", True, "ok")
        events = sm.get_events()
        assert len(events) == 1
        assert events[0]["task_name"] == "MyTask"

    def test_scheduled_task_dataclass(self):
        from src.scheduler_manager import ScheduledTask
        t = ScheduledTask(name="Backup", folder="\\Microsoft", status="Ready")
        assert t.name == "Backup"
        assert t.last_result == ""

    def test_scheduler_event_dataclass(self):
        from src.scheduler_manager import SchedulerEvent
        e = SchedulerEvent(action="list", task_name="Cleanup")
        assert e.action == "list"
        assert e.success is True

    def test_get_stats_structure(self):
        sm = self._make()
        stats = sm.get_stats()
        assert "total_events" in stats

    def test_parse_csv(self):
        sm = self._make()
        csv_data = (
            '"TaskName","Status","Next Run Time","Last Run Time","Last Result","Author","Task To Run"\n'
            '"\\MyTask","Ready","10:00:00","09:00:00","0","Admin","cmd.exe"\n'
        )
        tasks = sm._parse_csv(csv_data)
        assert len(tasks) == 1
        assert tasks[0]["name"] == "\\MyTask"
        assert tasks[0]["status"] == "Ready"

    def test_search_tasks_with_mock(self):
        sm = self._make()
        sm.list_tasks = lambda: [
            {"name": "\\Backup", "status": "Ready"},
            {"name": "\\Cleanup", "status": "Disabled"},
        ]
        results = sm.search_tasks("backup")
        assert len(results) == 1

    def test_count_by_status_with_mock(self):
        sm = self._make()
        sm.list_tasks = lambda: [
            {"name": "A", "status": "Ready"},
            {"name": "B", "status": "Ready"},
            {"name": "C", "status": "Disabled"},
        ]
        counts = sm.count_by_status()
        assert counts["Ready"] == 2
        assert counts["Disabled"] == 1


# ═══════════════════════════════════════════════════════════════════════════
# MCP HANDLERS — Phase 27
# ═══════════════════════════════════════════════════════════════════════════

class TestMCPHandlersPhase27:
    def test_prnmgr_events(self):
        from src.mcp_server import handle_prnmgr_events
        result = asyncio.run(handle_prnmgr_events({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_prnmgr_stats(self):
        from src.mcp_server import handle_prnmgr_stats
        result = asyncio.run(handle_prnmgr_stats({}))
        data = json.loads(result[0].text)
        assert "total_printers" in data

    def test_fwctl_events(self):
        from src.mcp_server import handle_fwctl_events
        result = asyncio.run(handle_fwctl_events({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_fwctl_stats(self):
        from src.mcp_server import handle_fwctl_stats
        result = asyncio.run(handle_fwctl_stats({}))
        data = json.loads(result[0].text)
        assert "profiles" in data

    def test_schedmgr_events(self):
        from src.mcp_server import handle_schedmgr_events
        result = asyncio.run(handle_schedmgr_events({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_schedmgr_stats(self):
        from src.mcp_server import handle_schedmgr_stats
        result = asyncio.run(handle_schedmgr_stats({}))
        data = json.loads(result[0].text)
        assert "total_events" in data


# ═══════════════════════════════════════════════════════════════════════════
# TOOL COUNT PHASE 27
# ═══════════════════════════════════════════════════════════════════════════

class TestToolCountPhase27:
    def test_tool_count_at_least_357(self):
        """348 + 3 prnmgr + 3 fwctl + 3 schedmgr = 357."""
        from src.mcp_server import TOOL_DEFINITIONS
        assert len(TOOL_DEFINITIONS) >= 357, f"Expected >= 357 tools, got {len(TOOL_DEFINITIONS)}"

    def test_no_duplicate_tool_names(self):
        from src.mcp_server import TOOL_DEFINITIONS
        names = [t[0] for t in TOOL_DEFINITIONS]
        dupes = [n for n in names if names.count(n) > 1]
        assert len(names) == len(set(names)), f"Duplicate tools: {set(dupes)}"
