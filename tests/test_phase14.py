"""Phase 14 Tests — Template Engine, State Machine, Log Aggregator, MCP Handlers."""

import asyncio
import json
import time
import pytest


# ═══════════════════════════════════════════════════════════════════════════
# TEMPLATE ENGINE
# ═══════════════════════════════════════════════════════════════════════════

class TestTemplateEngine:
    @staticmethod
    def _make():
        from src.template_engine import TemplateEngine
        return TemplateEngine()

    def test_singleton_exists(self):
        from src.template_engine import template_engine
        assert template_engine is not None

    def test_simple_variable(self):
        te = self._make()
        result = te.render("Hello {{ name }}!", {"name": "JARVIS"})
        assert result == "Hello JARVIS!"

    def test_multiple_vars(self):
        te = self._make()
        result = te.render("{{ a }} + {{ b }} = {{ c }}", {"a": "1", "b": "2", "c": "3"})
        assert result == "1 + 2 = 3"

    def test_dot_notation(self):
        te = self._make()
        result = te.render("{{ user.name }}", {"user": {"name": "Alice"}})
        assert result == "Alice"

    def test_if_true(self):
        te = self._make()
        result = te.render("{% if show %}visible{% endif %}", {"show": True})
        assert result == "visible"

    def test_if_false(self):
        te = self._make()
        result = te.render("{% if show %}visible{% endif %}", {"show": False})
        assert result == ""

    def test_if_comparison(self):
        te = self._make()
        result = te.render("{% if status == 'ok' %}OK{% endif %}", {"status": "ok"})
        assert result == "OK"

    def test_if_greater(self):
        te = self._make()
        result = te.render("{% if score > 50 %}PASS{% endif %}", {"score": 75})
        assert result == "PASS"

    def test_if_negation(self):
        te = self._make()
        result = te.render("{% if !error %}NO ERROR{% endif %}", {"error": ""})
        assert result == "NO ERROR"

    def test_for_loop(self):
        te = self._make()
        result = te.render("{% for item in items %}{{ item }} {% endfor %}", {"items": ["a", "b", "c"]})
        assert "a" in result
        assert "c" in result

    def test_register_and_render_named(self):
        te = self._make()
        te.register("greet", "Hello {{ name }}!")
        result = te.render_named("greet", {"name": "World"})
        assert result == "Hello World!"

    def test_render_named_missing(self):
        te = self._make()
        assert te.render_named("nope") is None

    def test_unregister(self):
        te = self._make()
        te.register("temp", "test")
        assert te.unregister("temp")
        assert not te.unregister("temp")

    def test_global_var(self):
        te = self._make()
        te.set_global("version", "10.6")
        result = te.render("v{{ version }}")
        assert result == "v10.6"

    def test_list_templates(self):
        te = self._make()
        te.register("a", "template A")
        te.register("b", "template B")
        templates = te.list_templates()
        assert len(templates) == 2

    def test_stats(self):
        te = self._make()
        te.register("s", "test")
        te.render("{{ x }}", {"x": "1"})
        stats = te.get_stats()
        assert stats["total_templates"] == 1
        assert stats["render_count"] >= 1


# ═══════════════════════════════════════════════════════════════════════════
# STATE MACHINE
# ═══════════════════════════════════════════════════════════════════════════

class TestStateMachine:
    @staticmethod
    def _make():
        from src.state_machine import StateMachineManager
        return StateMachineManager()

    def test_singleton_exists(self):
        from src.state_machine import state_machine_mgr
        assert state_machine_mgr is not None

    def test_create_fsm(self):
        mgr = self._make()
        fsm = mgr.create("test_flow", "idle")
        assert fsm.current_state == "idle"

    def test_add_transition_and_trigger(self):
        mgr = self._make()
        fsm = mgr.create("flow1", "idle")
        fsm.add_state("running")
        fsm.add_transition("idle", "running", "start")
        assert fsm.trigger("start")
        assert fsm.current_state == "running"

    def test_invalid_trigger(self):
        mgr = self._make()
        fsm = mgr.create("flow2", "idle")
        assert not fsm.trigger("nonexistent_event")

    def test_guard_blocks(self):
        mgr = self._make()
        fsm = mgr.create("flow3", "idle")
        fsm.add_state("running")
        fsm.add_transition("idle", "running", "start", guard=lambda ctx: ctx.get("ready", False))
        assert not fsm.trigger("start", {"ready": False})
        assert fsm.current_state == "idle"

    def test_guard_allows(self):
        mgr = self._make()
        fsm = mgr.create("flow4", "idle")
        fsm.add_state("running")
        fsm.add_transition("idle", "running", "start", guard=lambda ctx: ctx.get("ready"))
        assert fsm.trigger("start", {"ready": True})
        assert fsm.current_state == "running"

    def test_on_enter_on_exit(self):
        mgr = self._make()
        log = []
        fsm = mgr.create("flow5", "a")
        fsm.add_state("b", on_enter=lambda: log.append("enter_b"))
        fsm._states["a"].on_exit = lambda: log.append("exit_a")
        fsm.add_transition("a", "b", "go")
        fsm.trigger("go")
        assert "exit_a" in log
        assert "enter_b" in log

    def test_history(self):
        mgr = self._make()
        fsm = mgr.create("flow6", "s1")
        fsm.add_state("s2")
        fsm.add_state("s3")
        fsm.add_transition("s1", "s2", "next")
        fsm.add_transition("s2", "s3", "next")
        fsm.trigger("next")
        fsm.trigger("next")
        history = fsm.get_history()
        assert len(history) == 2

    def test_can_trigger(self):
        mgr = self._make()
        fsm = mgr.create("flow7", "idle")
        fsm.add_state("run")
        fsm.add_transition("idle", "run", "start")
        assert fsm.can_trigger("start")
        assert not fsm.can_trigger("stop")

    def test_available_events(self):
        mgr = self._make()
        fsm = mgr.create("flow8", "idle")
        fsm.add_state("run")
        fsm.add_transition("idle", "run", "start")
        fsm.add_transition("idle", "run", "force_start")
        events = fsm.get_available_events()
        assert "start" in events
        assert "force_start" in events

    def test_get_info(self):
        mgr = self._make()
        fsm = mgr.create("info_flow", "init")
        info = fsm.get_info()
        assert info["name"] == "info_flow"
        assert info["current_state"] == "init"

    def test_list_machines(self):
        mgr = self._make()
        mgr.create("m1", "a")
        mgr.create("m2", "b")
        machines = mgr.list_machines()
        assert len(machines) == 2

    def test_delete(self):
        mgr = self._make()
        mgr.create("del_me", "x")
        assert mgr.delete("del_me")
        assert not mgr.delete("del_me")

    def test_stats(self):
        mgr = self._make()
        fsm = mgr.create("stat_flow", "a")
        fsm.add_state("b")
        fsm.add_transition("a", "b", "go")
        stats = mgr.get_stats()
        assert stats["total_machines"] == 1
        assert stats["states_total"] == 2
        assert stats["transitions_total"] == 1


# ═══════════════════════════════════════════════════════════════════════════
# LOG AGGREGATOR
# ═══════════════════════════════════════════════════════════════════════════

class TestLogAggregator:
    @staticmethod
    def _make():
        from src.log_aggregator import LogAggregator
        return LogAggregator(max_entries=100)

    def test_singleton_exists(self):
        from src.log_aggregator import log_aggregator
        assert log_aggregator is not None

    def test_log_and_query(self):
        la = self._make()
        la.log("test message", level="info", source="test")
        results = la.query()
        assert len(results) >= 1
        assert results[0]["message"] == "test message"

    def test_filter_by_level(self):
        la = self._make()
        la.log("info msg", level="info")
        la.log("error msg", level="error")
        results = la.query(level="error")
        assert all(r["level"] == "error" for r in results)

    def test_filter_by_source(self):
        la = self._make()
        la.log("gpu msg", source="gpu")
        la.log("cpu msg", source="cpu")
        results = la.query(source="gpu")
        assert all(r["source"] == "gpu" for r in results)

    def test_search(self):
        la = self._make()
        la.log("temperature high alert")
        la.log("normal operation")
        results = la.query(search="temperature")
        assert len(results) == 1

    def test_since_until(self):
        la = self._make()
        t1 = time.time()
        la.log("before")
        time.sleep(0.02)
        t2 = time.time()
        la.log("after")
        results = la.query(since=t2)
        assert len(results) == 1
        assert results[0]["message"] == "after"

    def test_limit(self):
        la = self._make()
        for i in range(10):
            la.log(f"msg {i}")
        results = la.query(limit=3)
        assert len(results) == 3

    def test_rotation(self):
        la = self._make()  # max 100
        for i in range(150):
            la.log(f"msg {i}")
        results = la.query(limit=200)
        assert len(results) <= 100

    def test_get_sources(self):
        la = self._make()
        la.log("a", source="gpu")
        la.log("b", source="cpu")
        sources = la.get_sources()
        assert "gpu" in sources
        assert "cpu" in sources

    def test_level_counts(self):
        la = self._make()
        la.log("a", level="info")
        la.log("b", level="error")
        la.log("c", level="error")
        counts = la.get_level_counts()
        assert counts["error"] == 2

    def test_clear(self):
        la = self._make()
        la.log("a")
        la.log("b")
        cleared = la.clear()
        assert cleared == 2
        assert len(la.query()) == 0

    def test_clear_by_source(self):
        la = self._make()
        la.log("gpu msg", source="gpu")
        la.log("cpu msg", source="cpu")
        cleared = la.clear(source="gpu")
        assert cleared == 1
        results = la.query()
        assert len(results) == 1

    def test_stats(self):
        la = self._make()
        la.log("s1", source="a", level="info")
        la.log("s2", source="b", level="error")
        stats = la.get_stats()
        assert stats["total_entries"] == 2
        assert stats["sources"] == 2


# ═══════════════════════════════════════════════════════════════════════════
# MCP HANDLERS — Phase 14
# ═══════════════════════════════════════════════════════════════════════════

class TestMCPHandlersPhase14:
    def test_template_list(self):
        from src.mcp_server import handle_template_list
        result = asyncio.run(handle_template_list({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_template_render_missing(self):
        from src.mcp_server import handle_template_render
        result = asyncio.run(handle_template_render({"name": "nope", "context": "{}"}))
        data = json.loads(result[0].text)
        assert "error" in data

    def test_template_stats(self):
        from src.mcp_server import handle_template_stats
        result = asyncio.run(handle_template_stats({}))
        data = json.loads(result[0].text)
        assert "total_templates" in data

    def test_fsm_list(self):
        from src.mcp_server import handle_fsm_list
        result = asyncio.run(handle_fsm_list({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_fsm_stats(self):
        from src.mcp_server import handle_fsm_stats
        result = asyncio.run(handle_fsm_stats({}))
        data = json.loads(result[0].text)
        assert "total_machines" in data

    def test_logagg_query(self):
        from src.mcp_server import handle_logagg_query
        result = asyncio.run(handle_logagg_query({"limit": 10}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_logagg_sources(self):
        from src.mcp_server import handle_logagg_sources
        result = asyncio.run(handle_logagg_sources({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_logagg_stats(self):
        from src.mcp_server import handle_logagg_stats
        result = asyncio.run(handle_logagg_stats({}))
        data = json.loads(result[0].text)
        assert "total_entries" in data


# ═══════════════════════════════════════════════════════════════════════════
# TOOL COUNT PHASE 14
# ═══════════════════════════════════════════════════════════════════════════

class TestToolCountPhase14:
    def test_tool_count_at_least_210(self):
        """202 + 3 template + 2 fsm + 3 logagg = 210."""
        from src.mcp_server import TOOL_DEFINITIONS
        assert len(TOOL_DEFINITIONS) >= 210, f"Expected >= 210 tools, got {len(TOOL_DEFINITIONS)}"

    def test_no_duplicate_tool_names(self):
        from src.mcp_server import TOOL_DEFINITIONS
        names = [t[0] for t in TOOL_DEFINITIONS]
        dupes = [n for n in names if names.count(n) > 1]
        assert len(names) == len(set(names)), f"Duplicate tools: {set(dupes)}"
