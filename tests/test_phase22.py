"""Phase 22 Tests — Email Sender, System Profiler, Context Manager, MCP Handlers."""

import asyncio
import json
import pytest


# ═══════════════════════════════════════════════════════════════════════════
# EMAIL SENDER
# ═══════════════════════════════════════════════════════════════════════════

class TestEmailSender:
    @staticmethod
    def _make():
        from src.email_sender import EmailSender
        return EmailSender()

    def test_singleton_exists(self):
        from src.email_sender import email_sender
        assert email_sender is not None

    def test_create_draft(self):
        es = self._make()
        msg = es.create(to=["test@example.com"], subject="Hello", body="World")
        assert msg.subject == "Hello"
        assert msg.status.value == "draft"

    def test_list_messages(self):
        es = self._make()
        es.create(to=["a@b.com"], subject="A", body="a")
        es.create(to=["c@d.com"], subject="B", body="b")
        assert len(es.list_messages()) == 2

    def test_list_by_status(self):
        es = self._make()
        es.create(to=["a@b.com"], subject="A", body="a")
        msgs = es.list_messages(status="draft")
        assert len(msgs) == 1

    def test_add_template(self):
        es = self._make()
        t = es.add_template("welcome", "Welcome {{name}}", "Hello {{name}}!")
        assert t.name == "welcome"
        assert len(es.list_templates()) == 1

    def test_remove_template(self):
        es = self._make()
        es.add_template("tmp", "s", "b")
        assert es.remove_template("tmp")
        assert not es.remove_template("tmp")

    def test_create_from_template(self):
        es = self._make()
        es.add_template("greet", "Hi {{name}}", "Hello {{name}}, welcome!")
        msg = es.create_from_template("greet", to=["x@y.com"], variables={"name": "Alice"})
        assert msg is not None
        assert "Alice" in msg.body
        assert "Alice" in msg.subject

    def test_send_unconfigured(self):
        es = self._make()
        msg = es.create(to=["a@b.com"], subject="S", body="B")
        result = es.send(msg.msg_id)
        assert not result["success"]
        assert "not configured" in result["error"]

    def test_send_with_transport(self):
        es = self._make()
        sent = []
        es.set_transport(lambda msg, cfg: (sent.append(msg.subject), True)[1])
        msg = es.create(to=["a@b.com"], subject="Test", body="Body")
        result = es.send(msg.msg_id)
        assert result["success"]
        assert len(sent) == 1
        assert es.get(msg.msg_id).status.value == "sent"

    def test_send_already_sent(self):
        es = self._make()
        es.set_transport(lambda m, c: True)
        msg = es.create(to=["a@b.com"], subject="S", body="B")
        es.send(msg.msg_id)
        result = es.send(msg.msg_id)
        assert not result["success"]

    def test_queue_send(self):
        es = self._make()
        es.set_transport(lambda m, c: True)
        result = es.queue_send(to=["a@b.com"], subject="Quick", body="Fast")
        assert result["success"]

    def test_transport_error(self):
        es = self._make()
        es.set_transport(lambda m, c: (_ for _ in ()).throw(ConnectionError("fail")))
        msg = es.create(to=["a@b.com"], subject="S", body="B")
        result = es.send(msg.msg_id)
        assert not result["success"]

    def test_history(self):
        es = self._make()
        es.set_transport(lambda m, c: True)
        es.queue_send(to=["a@b.com"], subject="S", body="B")
        h = es.get_history()
        assert len(h) >= 1

    def test_configure(self):
        es = self._make()
        es.configure(host="smtp.test.com", port=587, from_address="me@test.com")
        assert es.is_configured()

    def test_stats(self):
        es = self._make()
        es.set_transport(lambda m, c: True)
        es.create(to=["a@b.com"], subject="Draft", body="B")
        es.queue_send(to=["b@c.com"], subject="Sent", body="B")
        stats = es.get_stats()
        assert stats["total_messages"] == 2
        assert stats["total_sent"] == 1


# ═══════════════════════════════════════════════════════════════════════════
# SYSTEM PROFILER
# ═══════════════════════════════════════════════════════════════════════════

class TestSystemProfiler:
    @staticmethod
    def _make():
        from src.system_profiler import SystemProfiler
        return SystemProfiler()

    def test_singleton_exists(self):
        from src.system_profiler import system_profiler
        assert system_profiler is not None

    def test_capture(self):
        sp = self._make()
        profile = sp.capture("test")
        assert profile.name == "test"
        assert profile.cpu["cores"] > 0

    def test_list_profiles(self):
        sp = self._make()
        sp.capture("a", tags=["prod"])
        sp.capture("b", tags=["dev"])
        assert len(sp.list_profiles()) == 2
        assert len(sp.list_profiles(tag="prod")) == 1

    def test_get(self):
        sp = self._make()
        p = sp.capture("t")
        assert sp.get(p.profile_id) is not None

    def test_compare(self):
        sp = self._make()
        a = sp.capture("a")
        b = sp.capture("b")
        diff = sp.compare(a.profile_id, b.profile_id)
        assert "cpu_same" in diff

    def test_benchmark_cpu(self):
        sp = self._make()
        result = sp.run_benchmark("cpu_basic")
        assert result.score > 0
        assert result.name == "cpu_basic"

    def test_benchmark_memory(self):
        sp = self._make()
        result = sp.run_benchmark("memory_basic")
        assert result.score > 0

    def test_benchmark_io(self):
        sp = self._make()
        result = sp.run_benchmark("io_basic")
        assert result.score > 0

    def test_list_benchmarks(self):
        sp = self._make()
        sp.run_benchmark("cpu_basic")
        bs = sp.list_benchmarks()
        assert len(bs) >= 1

    def test_os_info(self):
        sp = self._make()
        p = sp.capture("os_test")
        assert p.os_info["system"] == "Windows"

    def test_stats(self):
        sp = self._make()
        sp.capture("t")
        sp.run_benchmark("cpu_basic")
        stats = sp.get_stats()
        assert stats["total_profiles"] == 1
        assert stats["total_benchmarks"] == 1


# ═══════════════════════════════════════════════════════════════════════════
# CONTEXT MANAGER
# ═══════════════════════════════════════════════════════════════════════════

class TestContextManager:
    @staticmethod
    def _make():
        from src.context_manager import ContextManager
        return ContextManager()

    def test_singleton_exists(self):
        from src.context_manager import context_manager
        assert context_manager is not None

    def test_create(self):
        cm = self._make()
        ctx = cm.create("test")
        assert ctx.name == "test"

    def test_delete(self):
        cm = self._make()
        ctx = cm.create("del")
        assert cm.delete(ctx.context_id)
        assert not cm.delete(ctx.context_id)

    def test_set_get_var(self):
        cm = self._make()
        ctx = cm.create("vars")
        cm.set_var(ctx.context_id, "name", "Alice")
        assert cm.get_var(ctx.context_id, "name") == "Alice"

    def test_get_var_default(self):
        cm = self._make()
        ctx = cm.create("t")
        assert cm.get_var(ctx.context_id, "missing", "default") == "default"

    def test_delete_var(self):
        cm = self._make()
        ctx = cm.create("t")
        cm.set_var(ctx.context_id, "x", 1)
        assert cm.delete_var(ctx.context_id, "x")
        assert cm.get_var(ctx.context_id, "x") is None

    def test_parent_inheritance(self):
        cm = self._make()
        parent = cm.create("parent", variables={"color": "blue"})
        child = cm.create("child", parent_id=parent.context_id)
        assert cm.get_var(child.context_id, "color") == "blue"

    def test_get_all_vars_with_parents(self):
        cm = self._make()
        parent = cm.create("p", variables={"a": 1})
        child = cm.create("c", parent_id=parent.context_id, variables={"b": 2})
        all_vars = cm.get_all_vars(child.context_id, include_parents=True)
        assert all_vars["a"] == 1
        assert all_vars["b"] == 2

    def test_create_child(self):
        cm = self._make()
        parent = cm.create("p", variables={"x": 10})
        child = cm.create_child(parent.context_id, "child")
        assert child is not None
        assert child.variables.get("x") == 10

    def test_merge(self):
        cm = self._make()
        a = cm.create("a", variables={"x": 1})
        b = cm.create("b", variables={"y": 2})
        assert cm.merge(a.context_id, b.context_id)
        assert cm.get_var(b.context_id, "x") == 1

    def test_freeze_unfreeze(self):
        cm = self._make()
        ctx = cm.create("f")
        cm.freeze(ctx.context_id)
        assert not cm.set_var(ctx.context_id, "x", 1)
        cm.unfreeze(ctx.context_id)
        assert cm.set_var(ctx.context_id, "x", 1)

    def test_snapshot(self):
        cm = self._make()
        ctx = cm.create("snap", variables={"a": 1})
        snap = cm.snapshot(ctx.context_id)
        assert snap is not None
        assert snap["variables"]["a"] == 1

    def test_list_contexts(self):
        cm = self._make()
        # Root + 2 new
        cm.create("a", tags=["prod"])
        cm.create("b", tags=["dev"])
        assert len(cm.list_contexts()) >= 3  # root + a + b
        assert len(cm.list_contexts(tag="prod")) == 1

    def test_events(self):
        cm = self._make()
        ctx = cm.create("ev")
        cm.set_var(ctx.context_id, "x", 1)
        events = cm.get_events(context_id=ctx.context_id)
        assert len(events) >= 2  # created + updated

    def test_stats(self):
        cm = self._make()
        cm.create("t", variables={"a": 1, "b": 2})
        stats = cm.get_stats()
        assert stats["total_contexts"] >= 2  # root + t
        assert stats["total_variables"] >= 2


# ═══════════════════════════════════════════════════════════════════════════
# MCP HANDLERS — Phase 22
# ═══════════════════════════════════════════════════════════════════════════

class TestMCPHandlersPhase22:
    def test_emailsend_list(self):
        from src.mcp_server import handle_emailsend_list
        result = asyncio.run(handle_emailsend_list({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_emailsend_templates(self):
        from src.mcp_server import handle_emailsend_templates
        result = asyncio.run(handle_emailsend_templates({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_emailsend_stats(self):
        from src.mcp_server import handle_emailsend_stats
        result = asyncio.run(handle_emailsend_stats({}))
        data = json.loads(result[0].text)
        assert "total_messages" in data

    def test_sysprof_profiles(self):
        from src.mcp_server import handle_sysprof_profiles
        result = asyncio.run(handle_sysprof_profiles({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_sysprof_benchmarks(self):
        from src.mcp_server import handle_sysprof_benchmarks
        result = asyncio.run(handle_sysprof_benchmarks({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_sysprof_stats(self):
        from src.mcp_server import handle_sysprof_stats
        result = asyncio.run(handle_sysprof_stats({}))
        data = json.loads(result[0].text)
        assert "total_profiles" in data

    def test_ctxmgr_list(self):
        from src.mcp_server import handle_ctxmgr_list
        result = asyncio.run(handle_ctxmgr_list({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_ctxmgr_events(self):
        from src.mcp_server import handle_ctxmgr_events
        result = asyncio.run(handle_ctxmgr_events({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_ctxmgr_stats(self):
        from src.mcp_server import handle_ctxmgr_stats
        result = asyncio.run(handle_ctxmgr_stats({}))
        data = json.loads(result[0].text)
        assert "total_contexts" in data


# ═══════════════════════════════════════════════════════════════════════════
# TOOL COUNT PHASE 22
# ═══════════════════════════════════════════════════════════════════════════

class TestToolCountPhase22:
    def test_tool_count_at_least_312(self):
        """303 + 3 emailsend + 3 sysprof + 3 ctxmgr = 312."""
        from src.mcp_server import TOOL_DEFINITIONS
        assert len(TOOL_DEFINITIONS) >= 312, f"Expected >= 312 tools, got {len(TOOL_DEFINITIONS)}"

    def test_no_duplicate_tool_names(self):
        from src.mcp_server import TOOL_DEFINITIONS
        names = [t[0] for t in TOOL_DEFINITIONS]
        dupes = [n for n in names if names.count(n) > 1]
        assert len(names) == len(set(names)), f"Duplicate tools: {set(dupes)}"
