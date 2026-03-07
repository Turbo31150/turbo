"""Phase 4 Tests — Orchestrator V2, Autonomous Loop, REST API, MCP Handlers, Service."""

import asyncio
import json
import time
import pytest


# ═══════════════════════════════════════════════════════════════════════════
# ORCHESTRATOR V2 — Advanced Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestOrchestratorV2Advanced:
    def test_routing_matrix_all_types(self):
        from src.orchestrator_v2 import ROUTING_MATRIX
        expected_types = {"code", "review", "reasoning", "voice", "trading", "system", "simple", "archi", "web"}
        assert expected_types == set(ROUTING_MATRIX.keys())

    def test_routing_matrix_weights(self):
        from src.orchestrator_v2 import ROUTING_MATRIX
        for task_type, entries in ROUTING_MATRIX.items():
            for node, weight in entries:
                assert isinstance(node, str)
                assert 0.5 <= weight <= 2.0, f"{task_type}/{node}: weight {weight} out of range"

    def test_record_call_updates_stats(self):
        from src.orchestrator_v2 import OrchestratorV2
        orch = OrchestratorV2()
        orch.record_call("test_node", latency_ms=50.0, success=True, tokens=100)
        stats = orch.get_node_stats()
        assert "test_node" in stats
        assert stats["test_node"]["total_calls"] == 1
        assert stats["test_node"]["success_rate"] == 1.0
        assert stats["test_node"]["total_tokens"] == 100

    def test_record_call_failure(self):
        from src.orchestrator_v2 import OrchestratorV2
        orch = OrchestratorV2()
        orch.record_call("fail_node", latency_ms=500.0, success=False)
        stats = orch.get_node_stats()
        assert stats["fail_node"]["success_rate"] == 0.0

    def test_weighted_score_positive(self):
        from src.orchestrator_v2 import OrchestratorV2
        orch = OrchestratorV2()
        orch.record_call("M1", latency_ms=50.0, success=True)
        score = orch.weighted_score("M1", "code")
        assert score > 0

    def test_get_best_node(self):
        from src.orchestrator_v2 import OrchestratorV2
        orch = OrchestratorV2()
        orch.record_call("M1", latency_ms=50.0, success=True)
        orch.record_call("M2", latency_ms=500.0, success=True)
        best = orch.get_best_node(["M1", "M2"], "code")
        assert best is not None

    def test_get_best_node_empty(self):
        from src.orchestrator_v2 import OrchestratorV2
        orch = OrchestratorV2()
        assert orch.get_best_node([], "code") is None

    def test_fallback_chain_returns_list(self):
        from src.orchestrator_v2 import OrchestratorV2
        orch = OrchestratorV2()
        chain = orch.fallback_chain("code")
        assert isinstance(chain, list)
        assert len(chain) > 0

    def test_fallback_chain_excludes(self):
        from src.orchestrator_v2 import OrchestratorV2
        orch = OrchestratorV2()
        chain = orch.fallback_chain("code", exclude={"M1"})
        assert "M1" not in chain

    def test_budget_report(self):
        from src.orchestrator_v2 import OrchestratorV2
        orch = OrchestratorV2()
        orch.record_call("M1", latency_ms=50.0, success=True, tokens=200)
        report = orch.get_budget_report()
        assert report["total_tokens"] == 200
        assert report["total_calls"] == 1
        assert "M1" in report["tokens_by_node"]

    def test_reset_budget(self):
        from src.orchestrator_v2 import OrchestratorV2
        orch = OrchestratorV2()
        orch.record_call("M1", latency_ms=50.0, success=True, tokens=500)
        orch.reset_budget()
        report = orch.get_budget_report()
        assert report["total_tokens"] == 0

    def test_health_check_returns_int(self):
        from src.orchestrator_v2 import OrchestratorV2
        orch = OrchestratorV2()
        score = orch.health_check()
        assert isinstance(score, int)
        assert 0 <= score <= 100

    def test_dashboard_keys(self):
        from src.orchestrator_v2 import OrchestratorV2
        orch = OrchestratorV2()
        dash = orch.get_dashboard()
        expected_keys = {"observability", "drift", "auto_tune", "health_score", "node_stats", "budget"}
        assert expected_keys.issubset(set(dash.keys()))

    def test_get_alerts_returns_list(self):
        from src.orchestrator_v2 import OrchestratorV2
        orch = OrchestratorV2()
        alerts = orch.get_alerts()
        assert isinstance(alerts, list)


# ═══════════════════════════════════════════════════════════════════════════
# AUTONOMOUS LOOP
# ═══════════════════════════════════════════════════════════════════════════

class TestAutonomousLoop:
    def test_singleton_exists(self):
        from src.autonomous_loop import autonomous_loop
        assert autonomous_loop is not None

    def test_initial_state(self):
        from src.autonomous_loop import AutonomousLoop
        loop = AutonomousLoop()
        assert not loop.is_running
        assert len(loop._tasks) >= 13  # 9 base + auto_develop + brain_auto_learn + improve_cycle + predict_next_actions + extras

    def test_builtin_tasks_registered(self):
        from src.autonomous_loop import AutonomousLoop
        loop = AutonomousLoop()
        expected = {"health_check", "gpu_monitor", "drift_reroute", "budget_alert", "auto_tune_sample", "self_heal", "db_backup", "weekly_cleanup", "proactive_suggest", "auto_develop", "brain_auto_learn", "improve_cycle", "predict_next_actions"}
        assert expected.issubset(set(loop._tasks.keys()))

    def test_register_custom_task(self):
        from src.autonomous_loop import AutonomousLoop
        loop = AutonomousLoop()

        async def my_task():
            return {"ok": True}

        loop.register("custom", my_task, interval_s=10.0)
        assert "custom" in loop._tasks
        assert loop._tasks["custom"].interval_s == 10.0

    def test_unregister_task(self):
        from src.autonomous_loop import AutonomousLoop
        loop = AutonomousLoop()
        loop.unregister("health_check")
        assert "health_check" not in loop._tasks

    def test_enable_disable(self):
        from src.autonomous_loop import AutonomousLoop
        loop = AutonomousLoop()
        loop.enable("health_check", False)
        assert not loop._tasks["health_check"].enabled
        loop.enable("health_check", True)
        assert loop._tasks["health_check"].enabled

    def test_get_status_structure(self):
        from src.autonomous_loop import AutonomousLoop
        loop = AutonomousLoop()
        status = loop.get_status()
        assert "running" in status
        assert "tasks" in status
        assert "event_count" in status
        assert isinstance(status["tasks"], dict)

    def test_get_events_empty(self):
        from src.autonomous_loop import AutonomousLoop
        loop = AutonomousLoop()
        events = loop.get_events()
        assert isinstance(events, list)
        assert len(events) == 0

    def test_log_event_ring_buffer(self):
        from src.autonomous_loop import AutonomousLoop
        loop = AutonomousLoop()
        loop._max_log = 5
        for i in range(10):
            loop._log_event("test", "info", f"msg {i}")
        assert len(loop._event_log) == 5
        assert loop._event_log[0]["message"] == "msg 5"

    def test_run_task_success(self):
        from src.autonomous_loop import AutonomousLoop, AutonomousTask

        async def ok_task():
            return {"status": "ok"}

        loop = AutonomousLoop()
        task = AutonomousTask(name="test", fn=ok_task)
        result = asyncio.run(loop._run_task(task))
        assert result == {"status": "ok"}
        assert task.run_count == 1
        assert task.fail_count == 0

    def test_run_task_failure(self):
        from src.autonomous_loop import AutonomousLoop, AutonomousTask

        async def fail_task():
            raise RuntimeError("boom")

        loop = AutonomousLoop()
        task = AutonomousTask(name="fail", fn=fail_task)
        with pytest.raises(RuntimeError):
            asyncio.run(loop._run_task(task))
        assert task.fail_count == 1


# ═══════════════════════════════════════════════════════════════════════════
# MCP HANDLERS ORCHESTRATOR V2
# ═══════════════════════════════════════════════════════════════════════════

class TestMCPHandlersOrchV2:
    def test_orch_dashboard(self):
        from src.mcp_server import handle_orch_dashboard
        result = asyncio.run(handle_orch_dashboard({}))
        assert len(result) == 1
        data = json.loads(result[0].text)
        assert "health_score" in data

    def test_orch_node_stats(self):
        from src.mcp_server import handle_orch_node_stats
        result = asyncio.run(handle_orch_node_stats({}))
        assert len(result) == 1
        data = json.loads(result[0].text)
        assert isinstance(data, dict)

    def test_orch_budget(self):
        from src.mcp_server import handle_orch_budget
        result = asyncio.run(handle_orch_budget({}))
        data = json.loads(result[0].text)
        assert "total_tokens" in data

    def test_orch_fallback(self):
        from src.mcp_server import handle_orch_fallback
        result = asyncio.run(handle_orch_fallback({"task_type": "code"}))
        data = json.loads(result[0].text)
        assert "chain" in data
        assert isinstance(data["chain"], list)

    def test_orch_best_node(self):
        from src.mcp_server import handle_orch_best_node
        result = asyncio.run(handle_orch_best_node({"task_type": "code"}))
        data = json.loads(result[0].text)
        assert "best" in data
        assert "scores" in data

    def test_orch_record_call(self):
        from src.mcp_server import handle_orch_record_call
        result = asyncio.run(handle_orch_record_call({
            "node": "test_mcp",
            "latency_ms": 42,
            "success": True,
            "tokens": 100,
        }))
        assert "Recorded" in result[0].text

    def test_orch_health(self):
        from src.mcp_server import handle_orch_health
        result = asyncio.run(handle_orch_health({}))
        data = json.loads(result[0].text)
        assert "health_score" in data
        assert isinstance(data["alerts"], list)

    def test_orch_routing_matrix(self):
        from src.mcp_server import handle_orch_routing_matrix
        result = asyncio.run(handle_orch_routing_matrix({}))
        data = json.loads(result[0].text)
        assert "code" in data
        assert isinstance(data["code"], list)

    def test_orch_reset_budget(self):
        from src.mcp_server import handle_orch_reset_budget
        result = asyncio.run(handle_orch_reset_budget({}))
        assert "reset" in result[0].text.lower()


# ═══════════════════════════════════════════════════════════════════════════
# TOOL REGISTRY COUNT
# ═══════════════════════════════════════════════════════════════════════════

class TestToolRegistry:
    def test_tool_count_at_least_96(self):
        """Verify we have at least 96 MCP tools (87 base + 9 orch_v2)."""
        from src.mcp_server import TOOL_DEFINITIONS
        assert len(TOOL_DEFINITIONS) >= 96, f"Expected >= 96 tools, got {len(TOOL_DEFINITIONS)}"

    def test_no_duplicate_tool_names(self):
        from src.mcp_server import TOOL_DEFINITIONS
        names = [t[0] for t in TOOL_DEFINITIONS]
        assert len(names) == len(set(names)), f"Duplicate tools: {[n for n in names if names.count(n) > 1]}"

    def test_all_handlers_callable(self):
        from src.mcp_server import TOOL_DEFINITIONS
        for name, desc, schema, handler in TOOL_DEFINITIONS:
            assert callable(handler), f"Tool {name} handler not callable"


# ═══════════════════════════════════════════════════════════════════════════
# WINDOWS SERVICE
# ═══════════════════════════════════════════════════════════════════════════

class TestWindowsService:
    def test_service_script_exists(self):
        from pathlib import Path
        script = Path("F:/BUREAU/turbo/scripts/jarvis_service.py")
        assert script.exists()

    def test_service_importable(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "jarvis_service", "F:/BUREAU/turbo/scripts/jarvis_service.py"
        )
        assert spec is not None


# ═══════════════════════════════════════════════════════════════════════════
# DOMINO EXECUTOR V2 — Extended
# ═══════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════
# NOTIFIER
# ═══════════════════════════════════════════════════════════════════════════

class TestNotifier:
    def test_singleton_exists(self):
        from src.notifier import notifier
        assert notifier is not None

    def test_info_notification(self):
        from src.notifier import Notifier
        n = Notifier()
        ok = asyncio.run(n.info("test message", source="test"))
        assert ok is True

    def test_history(self):
        from src.notifier import Notifier
        n = Notifier()
        asyncio.run(n.info("msg 1"))
        asyncio.run(n.warn("msg 2"))
        history = n.get_history()
        assert len(history) == 2
        assert history[0]["level"] == "info"
        assert history[1]["level"] == "warning"

    def test_stats(self):
        from src.notifier import Notifier
        n = Notifier()
        asyncio.run(n.info("x"))
        stats = n.get_stats()
        assert stats["total"] == 1
        assert "info" in stats["by_level"]

    def test_cooldown(self):
        from src.notifier import Notifier
        n = Notifier()
        n._cooldown_s = 9999  # long cooldown
        ok1 = asyncio.run(n.warn("same msg"))
        ok2 = asyncio.run(n.warn("same msg"))
        assert ok1 is True
        assert ok2 is False  # rate-limited


# ═══════════════════════════════════════════════════════════════════════════
# TASK QUEUE
# ═══════════════════════════════════════════════════════════════════════════

class TestTaskQueue:
    """Task queue tests use in-memory-like temp paths (no cleanup needed on Windows)."""

    @staticmethod
    def _make_queue():
        import tempfile
        from pathlib import Path
        from src.task_queue import TaskQueue
        tmpdir = tempfile.mkdtemp()
        return TaskQueue(db_path=Path(tmpdir) / "test_tq.db")

    def test_enqueue_and_list(self):
        q = self._make_queue()
        q.enqueue("test prompt", task_type="code", priority=5)
        pending = q.list_pending()
        assert len(pending) == 1
        assert pending[0]["prompt"] == "test prompt"

    def test_cancel(self):
        q = self._make_queue()
        tid = q.enqueue("cancel me")
        assert q.cancel(tid) is True
        assert q.cancel("nonexistent") is False

    def test_stats(self):
        q = self._make_queue()
        q.enqueue("a")
        q.enqueue("b")
        stats = q.get_stats()
        assert stats["total"] == 2
        assert stats["by_status"]["pending"] == 2

    def test_priority_order(self):
        q = self._make_queue()
        q.enqueue("low", priority=1)
        q.enqueue("high", priority=10)
        q.enqueue("mid", priority=5)
        pending = q.list_pending()
        assert pending[0]["priority"] == 10
        assert pending[-1]["priority"] == 1

    def test_get_task(self):
        q = self._make_queue()
        tid = q.enqueue("get me")
        task = q.get_task(tid)
        assert task is not None
        assert task.prompt == "get me"
        assert q.get_task("nope") is None


# ═══════════════════════════════════════════════════════════════════════════
# SELF-HEALING
# ═══════════════════════════════════════════════════════════════════════════

class TestSelfHealing:
    def test_self_heal_registered(self):
        from src.autonomous_loop import AutonomousLoop
        loop = AutonomousLoop()
        assert "self_heal" in loop._tasks
        assert loop._tasks["self_heal"].interval_s == 90.0

    def test_builtin_count_updated(self):
        from src.autonomous_loop import AutonomousLoop
        loop = AutonomousLoop()
        assert len(loop._tasks) == 13  # 9 base + 4 new autonomous tasks


# ═══════════════════════════════════════════════════════════════════════════
# MCP TOOL COUNT
# ═══════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════
# CRON SCHEDULER
# ═══════════════════════════════════════════════════════════════════════════

class TestCronScheduler:
    def test_cron_matches_any(self):
        from src.autonomous_loop import CronSchedule
        c = CronSchedule()  # all None = always matches
        assert c.matches_now()

    def test_cron_weekday_filter(self):
        from src.autonomous_loop import CronSchedule
        from datetime import datetime
        today = datetime.now().weekday()
        c_yes = CronSchedule(weekdays=[today])
        c_no = CronSchedule(weekdays=[(today + 1) % 7])
        assert c_yes.matches_now()
        assert not c_no.matches_now()

    def test_cron_hour_filter(self):
        from src.autonomous_loop import CronSchedule
        from datetime import datetime
        now_hour = datetime.now().hour
        c_yes = CronSchedule(hour=now_hour)
        c_no = CronSchedule(hour=(now_hour + 1) % 24)
        assert c_yes.matches_now()
        assert not c_no.matches_now()

    def test_cron_tasks_registered(self):
        from src.autonomous_loop import AutonomousLoop
        loop = AutonomousLoop()
        assert "db_backup" in loop._tasks
        assert "weekly_cleanup" in loop._tasks
        assert loop._tasks["db_backup"].cron is not None
        assert loop._tasks["weekly_cleanup"].cron is not None

    def test_total_tasks_count(self):
        from src.autonomous_loop import AutonomousLoop
        loop = AutonomousLoop()
        assert len(loop._tasks) == 13  # 9 base + 4 new autonomous tasks


# ═══════════════════════════════════════════════════════════════════════════
# AGENT MEMORY
# ═══════════════════════════════════════════════════════════════════════════

class TestAgentMemory:
    @staticmethod
    def _make_memory():
        import tempfile
        from pathlib import Path
        from src.agent_memory import AgentMemory
        tmpdir = tempfile.mkdtemp()
        return AgentMemory(db_path=Path(tmpdir) / "test_mem.db")

    def test_remember_and_recall(self):
        mem = self._make_memory()
        mem.remember("Python est un langage de programmation", category="tech")
        mem.remember("Le trading requiert de la discipline", category="trading")
        mem.remember("Java est aussi un langage", category="tech")
        results = mem.recall("langage programmation", min_similarity=0.01)
        assert len(results) > 0
        assert results[0]["category"] == "tech"

    def test_forget(self):
        mem = self._make_memory()
        mid = mem.remember("delete me")
        assert mem.forget(mid) is True
        assert mem.forget(999) is False

    def test_list_all(self):
        mem = self._make_memory()
        mem.remember("a")
        mem.remember("b")
        all_mems = mem.list_all()
        assert len(all_mems) == 2

    def test_stats(self):
        mem = self._make_memory()
        mem.remember("x", category="test")
        stats = mem.get_stats()
        assert stats["total"] == 1
        assert "test" in stats["categories"]

    def test_category_filter(self):
        mem = self._make_memory()
        mem.remember("tech stuff", category="tech")
        mem.remember("personal stuff", category="personal")
        tech = mem.list_all(category="tech")
        assert len(tech) == 1
        assert tech[0]["category"] == "tech"

    def test_cleanup(self):
        mem = self._make_memory()
        # Low importance memory
        mid = mem.remember("old stuff", importance=0.1)
        # Manually backdate created_at
        import sqlite3
        with sqlite3.connect(str(mem._db_path)) as conn:
            conn.execute("UPDATE memories SET created_at = 0 WHERE id = ?", (mid,))
        cleaned = mem.cleanup(max_age_days=1)
        assert cleaned >= 1


# ═══════════════════════════════════════════════════════════════════════════
# MCP MEMORY HANDLERS
# ═══════════════════════════════════════════════════════════════════════════

class TestMCPMemoryHandlers:
    def test_memory_remember(self):
        from src.mcp_server import handle_memory_remember
        result = asyncio.run(handle_memory_remember({"content": "test memory", "category": "test"}))
        assert "stored" in result[0].text.lower()

    def test_memory_recall(self):
        from src.mcp_server import handle_memory_recall
        result = asyncio.run(handle_memory_recall({"query": "test"}))
        assert len(result) == 1

    def test_memory_list(self):
        from src.mcp_server import handle_memory_list
        result = asyncio.run(handle_memory_list({}))
        assert len(result) == 1


class TestToolCountV2:
    def test_tool_count_at_least_110(self):
        """96 base + 4 task_queue + 3 notif + 3 autonomous + 4 memory = 110."""
        from src.mcp_server import TOOL_DEFINITIONS
        assert len(TOOL_DEFINITIONS) >= 110, f"Expected >= 110 tools, got {len(TOOL_DEFINITIONS)}"


class TestDominoV2Extended:
    def test_orchestrator_fallback_function(self):
        from src.domino_executor import _get_orchestrator_fallback
        chain = _get_orchestrator_fallback("code")
        assert isinstance(chain, list)
        assert len(chain) > 0

    def test_orchestrator_fallback_with_exclude(self):
        from src.domino_executor import _get_orchestrator_fallback
        chain = _get_orchestrator_fallback("code", exclude={"M1"})
        assert "M1" not in chain


# ═══════════════════════════════════════════════════════════════════════════
# VAGUE 4 — PROACTIVE AGENT
# ═══════════════════════════════════════════════════════════════════════════

class TestProactiveAgent:
    def test_singleton_exists(self):
        from src.proactive_agent import proactive_agent
        assert proactive_agent is not None

    def test_analyze_returns_list(self):
        from src.proactive_agent import ProactiveAgent
        pa = ProactiveAgent()
        results = asyncio.run(pa.analyze())
        assert isinstance(results, list)

    def test_dismiss(self):
        from src.proactive_agent import ProactiveAgent
        pa = ProactiveAgent()
        pa.dismiss("test_key")
        assert "test_key" in pa._dismissed

    def test_get_last(self):
        from src.proactive_agent import ProactiveAgent
        pa = ProactiveAgent()
        assert pa.get_last() == []
        asyncio.run(pa.analyze())
        assert isinstance(pa.get_last(), list)

    def test_cooldown(self):
        from src.proactive_agent import ProactiveAgent
        pa = ProactiveAgent()
        pa._cooldown_s = 0  # disable cooldown for test
        s1 = asyncio.run(pa.analyze())
        s2 = asyncio.run(pa.analyze())
        assert isinstance(s1, list)
        assert isinstance(s2, list)

    def test_stats(self):
        from src.proactive_agent import ProactiveAgent
        pa = ProactiveAgent()
        stats = pa.get_stats()
        assert "last_suggestions_count" in stats
        assert "dismissed_count" in stats

    def test_time_suggestions_static(self):
        from src.proactive_agent import ProactiveAgent
        from datetime import datetime
        suggestions = ProactiveAgent._time_suggestions(datetime(2026, 3, 4, 23, 10))
        assert any(s["key"] == "night_backup" for s in suggestions)

    def test_proactive_registered_in_loop(self):
        from src.autonomous_loop import AutonomousLoop
        loop = AutonomousLoop()
        assert "proactive_suggest" in loop._tasks
        assert loop._tasks["proactive_suggest"].interval_s == 600.0


# ═══════════════════════════════════════════════════════════════════════════
# VAGUE 4 — CONVERSATION STORE
# ═══════════════════════════════════════════════════════════════════════════

class TestConversationStore:
    @staticmethod
    def _make_store():
        import tempfile
        from pathlib import Path
        from src.conversation_store import ConversationStore
        tmpdir = tempfile.mkdtemp()
        return ConversationStore(db_path=Path(tmpdir) / "test_conv.db")

    def test_create_conversation(self):
        cs = self._make_store()
        conv_id = cs.create("Test conv", source="test")
        assert isinstance(conv_id, str)
        assert len(conv_id) == 8

    def test_add_turn_and_get(self):
        cs = self._make_store()
        cid = cs.create("Turn test")
        tid = cs.add_turn(cid, "M1", "hello", "world", latency_ms=50, tokens=10)
        assert isinstance(tid, int)
        conv = cs.get_conversation(cid)
        assert conv is not None
        assert conv["turn_count"] == 1
        assert conv["total_tokens"] == 10
        assert len(conv["turns"]) == 1
        assert conv["turns"][0]["prompt"] == "hello"

    def test_list_conversations(self):
        cs = self._make_store()
        cs.create("A")
        cs.create("B")
        convs = cs.list_conversations(limit=10)
        assert len(convs) == 2

    def test_search_turns(self):
        cs = self._make_store()
        cid = cs.create("Search test")
        cs.add_turn(cid, "M1", "fix the Python bug", "Fixed it")
        cs.add_turn(cid, "M2", "deploy code", "Deployed")
        results = cs.search_turns("Python")
        assert len(results) == 1
        assert "Python" in results[0]["prompt"]

    def test_get_node_history(self):
        cs = self._make_store()
        cid = cs.create("Node test")
        cs.add_turn(cid, "M1", "a", "b")
        cs.add_turn(cid, "M2", "c", "d")
        cs.add_turn(cid, "M1", "e", "f")
        m1_turns = cs.get_node_history("M1")
        assert len(m1_turns) == 2

    def test_stats(self):
        cs = self._make_store()
        cid = cs.create("Stats test")
        cs.add_turn(cid, "M1", "q", "r", tokens=100, latency_ms=50)
        stats = cs.get_stats()
        assert stats["total_conversations"] == 1
        assert stats["total_turns"] == 1
        assert stats["total_tokens"] == 100
        assert "M1" in stats["by_node"]

    def test_get_nonexistent(self):
        cs = self._make_store()
        assert cs.get_conversation("nope") is None

    def test_cleanup(self):
        cs = self._make_store()
        cid = cs.create("Old conv")
        # Backdate the conversation
        import sqlite3
        with sqlite3.connect(str(cs._db_path)) as conn:
            conn.execute("UPDATE conversations SET updated_at = 0 WHERE id = ?", (cid,))
        cleaned = cs.cleanup(days=1)
        assert cleaned == 1


# ═══════════════════════════════════════════════════════════════════════════
# VAGUE 4 — LOAD BALANCER
# ═══════════════════════════════════════════════════════════════════════════

class TestLoadBalancer:
    def test_singleton_exists(self):
        from src.load_balancer import load_balancer
        assert load_balancer is not None

    def test_pick_returns_string(self):
        from src.load_balancer import LoadBalancer
        lb = LoadBalancer()
        node = lb.pick("code")
        assert isinstance(node, str)
        assert len(node) > 0

    def test_pick_excludes(self):
        from src.load_balancer import LoadBalancer
        lb = LoadBalancer()
        node = lb.pick("code", exclude={"M1", "M2", "M3"})
        assert node not in {"M1", "M2", "M3"}

    def test_release(self):
        from src.load_balancer import LoadBalancer
        lb = LoadBalancer()
        node = lb.pick("code")
        lb.release(node)
        assert lb._active[node] == 0

    def test_report_success(self):
        from src.load_balancer import LoadBalancer
        lb = LoadBalancer()
        node = lb.pick("code")
        lb.report(node, 100.0, True, 50)
        assert lb._active[node] == 0

    def test_report_failure_tracks(self):
        from src.load_balancer import LoadBalancer
        lb = LoadBalancer()
        node = lb.pick("code")
        lb.report(node, 500.0, False)
        assert len(lb._recent_failures[node]) == 1

    def test_circuit_breaker(self):
        from src.load_balancer import LoadBalancer
        lb = LoadBalancer()
        lb._failure_threshold = 2
        lb._recent_failures["BAD_NODE"] = [time.time(), time.time()]
        status = lb.get_status()
        if "BAD_NODE" in status["nodes"]:
            assert status["nodes"]["BAD_NODE"]["circuit_broken"]

    def test_get_status(self):
        from src.load_balancer import LoadBalancer
        lb = LoadBalancer()
        lb.pick("code")
        status = lb.get_status()
        assert "nodes" in status
        assert "max_concurrent" in status
        assert "failure_threshold" in status

    def test_reset(self):
        from src.load_balancer import LoadBalancer
        lb = LoadBalancer()
        lb.pick("code")
        lb.reset()
        assert len(lb._counters) == 0
        assert len(lb._active) == 0


# ═══════════════════════════════════════════════════════════════════════════
# VAGUE 4 — MCP HANDLERS (new modules)
# ═══════════════════════════════════════════════════════════════════════════

class TestMCPHandlersVague4:
    def test_handle_conv_list(self):
        from src.mcp_server import handle_conv_list
        result = asyncio.run(handle_conv_list({}))
        assert len(result) == 1

    def test_handle_conv_stats(self):
        from src.mcp_server import handle_conv_stats
        result = asyncio.run(handle_conv_stats({}))
        data = json.loads(result[0].text)
        assert "total_conversations" in data

    def test_handle_lb_status(self):
        from src.mcp_server import handle_lb_status
        result = asyncio.run(handle_lb_status({}))
        data = json.loads(result[0].text)
        assert "nodes" in data

    def test_handle_lb_pick(self):
        from src.mcp_server import handle_lb_pick
        result = asyncio.run(handle_lb_pick({"task_type": "code"}))
        data = json.loads(result[0].text)
        assert "selected_node" in data

    def test_handle_proactive_analyze(self):
        from src.mcp_server import handle_proactive_analyze
        result = asyncio.run(handle_proactive_analyze({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_handle_proactive_dismiss(self):
        from src.mcp_server import handle_proactive_dismiss
        result = asyncio.run(handle_proactive_dismiss({"key": "test_dismiss"}))
        assert "dismissed" in result[0].text.lower()


# ═══════════════════════════════════════════════════════════════════════════
# VAGUE 4 — TOOL COUNT FINAL
# ═══════════════════════════════════════════════════════════════════════════

class TestToolCountVague4:
    def test_tool_count_at_least_118(self):
        """110 base + 4 conv + 2 lb + 2 proactive = 118."""
        from src.mcp_server import TOOL_DEFINITIONS
        assert len(TOOL_DEFINITIONS) >= 118, f"Expected >= 118 tools, got {len(TOOL_DEFINITIONS)}"
