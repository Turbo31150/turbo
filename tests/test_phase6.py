"""Phase 6 Tests — Workflow Engine, Session Manager, Alert Manager, MCP Handlers."""

import asyncio
import json
import tempfile
import time
from pathlib import Path
import pytest


# ═══════════════════════════════════════════════════════════════════════════
# WORKFLOW ENGINE
# ═══════════════════════════════════════════════════════════════════════════

class TestWorkflowEngine:
    @staticmethod
    def _make_engine():
        from src.workflow_engine import WorkflowEngine
        tmpdir = tempfile.mkdtemp()
        return WorkflowEngine(db_path=Path(tmpdir) / "test_wf.db")

    def test_singleton_exists(self):
        from src.workflow_engine import workflow_engine
        assert workflow_engine is not None

    def test_create_and_get(self):
        wf = self._make_engine()
        wf_id = wf.create("test flow", [{"name": "s1", "action": "noop"}])
        assert isinstance(wf_id, str)
        got = wf.get(wf_id)
        assert got is not None
        assert got["name"] == "test flow"
        assert len(got["steps"]) == 1

    def test_list_workflows(self):
        wf = self._make_engine()
        wf.create("a", [])
        wf.create("b", [])
        result = wf.list_workflows()
        assert len(result) == 2

    def test_delete(self):
        wf = self._make_engine()
        wf_id = wf.create("delete me", [])
        assert wf.delete(wf_id)
        assert wf.get(wf_id) is None
        assert not wf.delete("nope")

    def test_execute_noop(self):
        wf = self._make_engine()
        wf_id = wf.create("noop flow", [
            {"name": "step1", "action": "noop"},
            {"name": "step2", "action": "noop", "depends_on": ["step1"]},
        ])
        run_id = asyncio.run(wf.execute(wf_id))
        run = wf.get_run(run_id)
        assert run is not None
        assert run["status"] == "completed"
        assert "step1" in run["step_results"]
        assert "step2" in run["step_results"]

    def test_execute_with_condition_skip(self):
        wf = self._make_engine()
        wf_id = wf.create("cond flow", [
            {"name": "s1", "action": "noop"},
            {"name": "s2", "action": "noop", "condition": "mode==prod"},
        ], variables={"mode": "dev"})
        run_id = asyncio.run(wf.execute(wf_id))
        run = wf.get_run(run_id)
        assert run["step_results"]["s2"].get("skipped")

    def test_execute_nonexistent(self):
        wf = self._make_engine()
        with pytest.raises(ValueError):
            asyncio.run(wf.execute("nope"))

    def test_list_runs(self):
        wf = self._make_engine()
        wf_id = wf.create("runs test", [{"name": "s1", "action": "noop"}])
        asyncio.run(wf.execute(wf_id))
        asyncio.run(wf.execute(wf_id))
        runs = wf.list_runs(wf_id)
        assert len(runs) == 2

    def test_stats(self):
        wf = self._make_engine()
        wf.create("a", [])
        stats = wf.get_stats()
        assert stats["total_workflows"] == 1
        assert stats["total_runs"] == 0


# ═══════════════════════════════════════════════════════════════════════════
# SESSION MANAGER
# ═══════════════════════════════════════════════════════════════════════════

class TestSessionManager:
    @staticmethod
    def _make_manager():
        from src.session_manager import SessionManager
        tmpdir = tempfile.mkdtemp()
        return SessionManager(db_path=Path(tmpdir) / "test_sess.db")

    def test_singleton_exists(self):
        from src.session_manager import session_manager
        assert session_manager is not None

    def test_create_and_get(self):
        sm = self._make_manager()
        sid = sm.create("test")
        ctx = sm.get_context(sid)
        assert ctx is not None
        assert ctx["source"] == "test"

    def test_set_preference(self):
        sm = self._make_manager()
        sid = sm.create("test")
        sm.set_preference(sid, "theme", "dark")
        val = sm.get_preference(sid, "theme")
        assert val == "dark"
        assert sm.get_preference(sid, "nonexistent", "default") == "default"

    def test_record_command(self):
        sm = self._make_manager()
        sid = sm.create("test")
        sm.record_command(sid, "/cluster-check")
        sm.record_command(sid, "/gpu-status")
        ctx = sm.get_context(sid)
        assert len(ctx["last_commands"]) == 2
        assert ctx["last_commands"][0]["cmd"] == "/cluster-check"

    def test_set_active_conversation(self):
        sm = self._make_manager()
        sid = sm.create("test")
        sm.set_active_conversation(sid, "conv123")
        ctx = sm.get_context(sid)
        assert ctx["active_conversation"] == "conv123"

    def test_set_preferred_node(self):
        sm = self._make_manager()
        sid = sm.create("test")
        sm.set_preferred_node(sid, "M1")
        ctx = sm.get_context(sid)
        assert ctx["preferred_node"] == "M1"

    def test_list_sessions(self):
        sm = self._make_manager()
        sm.create("a")
        sm.create("b")
        sessions = sm.list_sessions()
        assert len(sessions) == 2

    def test_delete(self):
        sm = self._make_manager()
        sid = sm.create("del")
        assert sm.delete(sid)
        assert sm.get_context(sid) is None
        assert not sm.delete("nope")

    def test_cleanup(self):
        sm = self._make_manager()
        sid = sm.create("old")
        import sqlite3
        with sqlite3.connect(str(sm._db_path)) as conn:
            conn.execute("UPDATE sessions SET last_active = 0 WHERE id = ?", (sid,))
        cleaned = sm.cleanup(inactive_hours=1)
        assert cleaned == 1

    def test_stats(self):
        sm = self._make_manager()
        sm.create("electron")
        stats = sm.get_stats()
        assert stats["total_sessions"] == 1
        assert "electron" in stats["by_source"]

    def test_get_nonexistent(self):
        sm = self._make_manager()
        assert sm.get_context("nope") is None
        assert sm.get_preference("nope", "x") is None


# ═══════════════════════════════════════════════════════════════════════════
# ALERT MANAGER
# ═══════════════════════════════════════════════════════════════════════════

class TestAlertManager:
    def test_singleton_exists(self):
        from src.alert_manager import alert_manager
        assert alert_manager is not None

    def test_fire_and_get_active(self):
        from src.alert_manager import AlertManager
        am = AlertManager()
        ok = asyncio.run(am.fire("test_alert", "Test message", level="warning", source="test"))
        assert ok is True
        active = am.get_active()
        assert len(active) == 1
        assert active[0]["key"] == "test_alert"

    def test_dedup_same_key(self):
        from src.alert_manager import AlertManager
        am = AlertManager()
        am._cooldown_s = 0
        asyncio.run(am.fire("dup", "msg1", level="info"))
        asyncio.run(am.fire("dup", "msg2", level="info"))
        active = am.get_active()
        assert len(active) == 1
        assert active[0]["count"] == 2

    def test_acknowledge(self):
        from src.alert_manager import AlertManager
        am = AlertManager()
        asyncio.run(am.fire("ack_test", "msg"))
        assert am.acknowledge("ack_test")
        active = am.get_active()
        assert active[0]["acknowledged"]
        assert not am.acknowledge("nonexistent")

    def test_resolve(self):
        from src.alert_manager import AlertManager
        am = AlertManager()
        asyncio.run(am.fire("res_test", "msg"))
        assert am.resolve("res_test")
        active = am.get_active()
        assert len(active) == 0
        assert not am.resolve("nope")

    def test_escalation(self):
        from src.alert_manager import AlertManager
        am = AlertManager()
        am._cooldown_s = 0
        am._escalation_rules = {"info": 3}
        for i in range(4):
            asyncio.run(am.fire("esc", f"msg {i}", level="info"))
        active = am.get_active()
        assert active[0]["level"] == "warning"  # escalated from info

    def test_cooldown(self):
        from src.alert_manager import AlertManager
        am = AlertManager()
        am._cooldown_s = 9999
        ok1 = asyncio.run(am.fire("cool", "msg", source="s1"))
        ok2 = asyncio.run(am.fire("cool", "msg", source="s1"))
        assert ok1 is True
        assert ok2 is False

    def test_get_all(self):
        from src.alert_manager import AlertManager
        am = AlertManager()
        am._cooldown_s = 0
        asyncio.run(am.fire("a1", "msg1"))
        asyncio.run(am.fire("a2", "msg2"))
        all_alerts = am.get_all()
        assert len(all_alerts) == 2

    def test_history(self):
        from src.alert_manager import AlertManager
        am = AlertManager()
        asyncio.run(am.fire("h1", "msg"))
        history = am.get_history()
        assert len(history) == 1

    def test_stats(self):
        from src.alert_manager import AlertManager
        am = AlertManager()
        asyncio.run(am.fire("s1", "msg", level="warning"))
        stats = am.get_stats()
        assert stats["total_alerts"] == 1
        assert stats["active_alerts"] == 1
        assert "warning" in stats["by_level"]

    def test_clear_resolved(self):
        from src.alert_manager import AlertManager
        am = AlertManager()
        asyncio.run(am.fire("cr1", "msg"))
        am.resolve("cr1")
        cleared = am.clear_resolved()
        assert cleared == 1
        assert len(am.get_all()) == 0

    def test_level_filter(self):
        from src.alert_manager import AlertManager
        am = AlertManager()
        am._cooldown_s = 0
        asyncio.run(am.fire("w1", "warning", level="warning"))
        asyncio.run(am.fire("i1", "info", level="info"))
        warnings = am.get_active(level="warning")
        assert len(warnings) == 1


# ═══════════════════════════════════════════════════════════════════════════
# MCP HANDLERS — Phase 6
# ═══════════════════════════════════════════════════════════════════════════

class TestMCPHandlersPhase6:
    def test_workflow_create(self):
        from src.mcp_server import handle_workflow_create
        result = asyncio.run(handle_workflow_create({
            "name": "test", "steps": json.dumps([{"name": "s1", "action": "noop"}]),
        }))
        assert "created" in result[0].text.lower()

    def test_workflow_list(self):
        from src.mcp_server import handle_workflow_list
        result = asyncio.run(handle_workflow_list({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_workflow_stats(self):
        from src.mcp_server import handle_workflow_stats
        result = asyncio.run(handle_workflow_stats({}))
        data = json.loads(result[0].text)
        assert "total_workflows" in data

    def test_session_create(self):
        from src.mcp_server import handle_session_create
        result = asyncio.run(handle_session_create({"source": "test"}))
        assert "created" in result[0].text.lower()

    def test_session_list(self):
        from src.mcp_server import handle_session_list
        result = asyncio.run(handle_session_list({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_session_stats(self):
        from src.mcp_server import handle_session_stats
        result = asyncio.run(handle_session_stats({}))
        data = json.loads(result[0].text)
        assert "total_sessions" in data

    def test_alert_fire(self):
        from src.mcp_server import handle_alert_fire
        result = asyncio.run(handle_alert_fire({
            "key": "mcp_test", "message": "test alert", "level": "info", "source": "test",
        }))
        assert "fired" in result[0].text.lower()

    def test_alert_active(self):
        from src.mcp_server import handle_alert_active
        result = asyncio.run(handle_alert_active({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_alert_stats(self):
        from src.mcp_server import handle_alert_stats
        result = asyncio.run(handle_alert_stats({}))
        data = json.loads(result[0].text)
        assert "total_alerts" in data


# ═══════════════════════════════════════════════════════════════════════════
# TOOL COUNT PHASE 6
# ═══════════════════════════════════════════════════════════════════════════

class TestToolCountPhase6:
    def test_tool_count_at_least_139(self):
        """126 + 4 workflow + 4 session + 5 alert = 139."""
        from src.mcp_server import TOOL_DEFINITIONS
        assert len(TOOL_DEFINITIONS) >= 139, f"Expected >= 139 tools, got {len(TOOL_DEFINITIONS)}"

    def test_no_duplicate_tool_names(self):
        from src.mcp_server import TOOL_DEFINITIONS
        names = [t[0] for t in TOOL_DEFINITIONS]
        dupes = [n for n in names if names.count(n) > 1]
        assert len(names) == len(set(names)), f"Duplicate tools: {set(dupes)}"
