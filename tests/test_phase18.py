"""Phase 18 Tests — Retry Policy, Message Broker, Command Registry, MCP Handlers."""

import asyncio
import json
import pytest


# ═══════════════════════════════════════════════════════════════════════════
# RETRY POLICY
# ═══════════════════════════════════════════════════════════════════════════

class TestRetryPolicy:
    @staticmethod
    def _make():
        from src.retry_policy import RetryPolicyManager
        return RetryPolicyManager()

    def test_singleton_exists(self):
        from src.retry_policy import retry_manager
        assert retry_manager is not None

    def test_default_policies(self):
        rm = self._make()
        policies = rm.list_policies()
        names = [p["name"] for p in policies]
        assert "default" in names
        assert "aggressive" in names
        assert "gentle" in names

    def test_register(self):
        from src.retry_policy import BackoffType
        rm = self._make()
        p = rm.register("custom", max_attempts=10, backoff=BackoffType.LINEAR)
        assert p.max_attempts == 10

    def test_remove(self):
        rm = self._make()
        assert rm.remove("gentle")
        assert not rm.remove("gentle")

    def test_get_delay_exponential(self):
        from src.retry_policy import RetryPolicy, BackoffType
        p = RetryPolicy(name="t", backoff=BackoffType.EXPONENTIAL, base_delay=1.0, jitter=False)
        assert p.get_delay(1) == 1.0
        assert p.get_delay(2) == 2.0
        assert p.get_delay(3) == 4.0

    def test_get_delay_linear(self):
        from src.retry_policy import RetryPolicy, BackoffType
        p = RetryPolicy(name="t", backoff=BackoffType.LINEAR, base_delay=2.0, jitter=False)
        assert p.get_delay(1) == 2.0
        assert p.get_delay(3) == 6.0

    def test_get_delay_fixed(self):
        from src.retry_policy import RetryPolicy, BackoffType
        p = RetryPolicy(name="t", backoff=BackoffType.FIXED, base_delay=5.0, jitter=False)
        assert p.get_delay(1) == 5.0
        assert p.get_delay(5) == 5.0

    def test_max_delay_cap(self):
        from src.retry_policy import RetryPolicy, BackoffType
        p = RetryPolicy(name="t", backoff=BackoffType.EXPONENTIAL, base_delay=10.0, max_delay=20.0, jitter=False)
        assert p.get_delay(10) == 20.0

    def test_execute_success(self):
        rm = self._make()
        result = rm.execute_no_wait(lambda: 42)
        assert result.success
        assert result.result == 42
        assert result.attempts == 1

    def test_execute_retry_then_success(self):
        rm = self._make()
        call_count = [0]
        def flaky():
            call_count[0] += 1
            if call_count[0] < 3:
                raise ValueError("fail")
            return "ok"
        result = rm.execute_no_wait(flaky)
        assert result.success
        assert result.attempts == 3

    def test_execute_all_fail(self):
        rm = self._make()
        def always_fail():
            raise ValueError("nope")
        result = rm.execute_no_wait(always_fail)
        assert not result.success
        assert result.attempts == 3
        assert "nope" in result.last_error

    def test_history(self):
        rm = self._make()
        rm.execute_no_wait(lambda: 1)
        history = rm.get_history()
        assert len(history) >= 1

    def test_stats(self):
        rm = self._make()
        rm.execute_no_wait(lambda: 1)
        stats = rm.get_stats()
        assert stats["total_policies"] >= 3
        assert stats["total_executions"] >= 1


# ═══════════════════════════════════════════════════════════════════════════
# MESSAGE BROKER
# ═══════════════════════════════════════════════════════════════════════════

class TestMessageBroker:
    @staticmethod
    def _make():
        from src.message_broker import MessageBroker
        return MessageBroker()

    def test_singleton_exists(self):
        from src.message_broker import message_broker
        assert message_broker is not None

    def test_subscribe_and_publish(self):
        mb = self._make()
        received = []
        mb.subscribe("orders", lambda msg: received.append(msg.payload))
        mb.publish("orders", {"id": 1})
        assert len(received) == 1
        assert received[0]["id"] == 1

    def test_multiple_subscribers(self):
        mb = self._make()
        r1, r2 = [], []
        mb.subscribe("t", lambda m: r1.append(1))
        mb.subscribe("t", lambda m: r2.append(1))
        mb.publish("t", {})
        assert len(r1) == 1
        assert len(r2) == 1

    def test_unsubscribe(self):
        mb = self._make()
        received = []
        sid = mb.subscribe("t", lambda m: received.append(1))
        mb.unsubscribe("t", sid)
        mb.publish("t", {})
        assert len(received) == 0

    def test_wildcard_subscriber(self):
        mb = self._make()
        received = []
        mb.subscribe("*", lambda m: received.append(m.topic))
        mb.publish("orders", {})
        mb.publish("events", {})
        assert len(received) == 2

    def test_list_topics(self):
        mb = self._make()
        mb.subscribe("a", lambda m: None)
        mb.subscribe("b", lambda m: None)
        topics = mb.list_topics()
        assert "a" in topics
        assert "b" in topics

    def test_subscriber_count(self):
        mb = self._make()
        mb.subscribe("t", lambda m: None)
        mb.subscribe("t", lambda m: None)
        assert mb.subscriber_count("t") == 2

    def test_dead_letter_queue(self):
        mb = self._make()
        def bad_handler(msg):
            raise ValueError("crash")
        mb.subscribe("t", bad_handler)
        mb.publish("t", {"x": 1})
        dlq = mb.get_dlq()
        assert len(dlq) == 1
        assert "crash" in dlq[0]["error"]

    def test_clear_dlq(self):
        mb = self._make()
        mb.subscribe("t", lambda m: (_ for _ in ()).throw(ValueError("x")))
        mb.publish("t", {})
        assert mb.clear_dlq() >= 1
        assert len(mb.get_dlq()) == 0

    def test_message_history(self):
        mb = self._make()
        mb.publish("t", {"a": 1})
        mb.publish("t", {"a": 2})
        msgs = mb.get_messages(topic="t")
        assert len(msgs) == 2

    def test_delivered_count(self):
        mb = self._make()
        mb.subscribe("t", lambda m: None)
        msg = mb.publish("t", {})
        assert msg.delivered == 1

    def test_stats(self):
        mb = self._make()
        mb.subscribe("t", lambda m: None)
        mb.publish("t", {})
        stats = mb.get_stats()
        assert stats["topics"] >= 1
        assert stats["total_messages"] >= 1


# ═══════════════════════════════════════════════════════════════════════════
# COMMAND REGISTRY
# ═══════════════════════════════════════════════════════════════════════════

class TestCommandRegistry:
    @staticmethod
    def _make():
        from src.command_registry import CommandRegistry
        return CommandRegistry()

    def test_singleton_exists(self):
        from src.command_registry import command_registry
        assert command_registry is not None

    def test_register_and_list(self):
        cr = self._make()
        cr.register("greet", lambda args: f"Hello {args.get('name', 'world')}")
        cmds = cr.list_commands()
        assert len(cmds) == 1
        assert cmds[0]["name"] == "greet"

    def test_unregister(self):
        cr = self._make()
        cr.register("temp", lambda a: None)
        assert cr.unregister("temp")
        assert not cr.unregister("temp")

    def test_execute(self):
        cr = self._make()
        cr.register("add", lambda a: a.get("x", 0) + a.get("y", 0))
        result = cr.execute("add", {"x": 3, "y": 5})
        assert result["success"]
        assert result["result"] == 8

    def test_execute_not_found(self):
        cr = self._make()
        result = cr.execute("nope")
        assert not result["success"]

    def test_execute_disabled(self):
        cr = self._make()
        cr.register("cmd", lambda a: "ok")
        cr.disable("cmd")
        result = cr.execute("cmd")
        assert not result["success"]

    def test_alias(self):
        cr = self._make()
        cr.register("hello", lambda a: "hi", aliases=["hi", "hey"])
        assert cr.get("hi") is not None
        assert cr.get("hey").name == "hello"

    def test_execute_via_alias(self):
        cr = self._make()
        cr.register("greet", lambda a: "ok", aliases=["g"])
        result = cr.execute("g")
        assert result["success"]

    def test_categories(self):
        cr = self._make()
        cr.register("a", lambda a: None, category="system")
        cr.register("b", lambda a: None, category="trading")
        cats = cr.list_categories()
        assert "system" in cats
        assert "trading" in cats

    def test_list_by_category(self):
        cr = self._make()
        cr.register("a", lambda a: None, category="system")
        cr.register("b", lambda a: None, category="trading")
        sys_cmds = cr.list_commands(category="system")
        assert len(sys_cmds) == 1

    def test_exec_count(self):
        cr = self._make()
        cr.register("cmd", lambda a: None)
        cr.execute("cmd")
        cr.execute("cmd")
        assert cr.get("cmd").exec_count == 2

    def test_error_handling(self):
        def bad_cmd(a):
            raise RuntimeError("oops")
        cr = self._make()
        cr.register("bad", bad_cmd)
        result = cr.execute("bad")
        assert not result["success"]
        assert "oops" in result["error"]

    def test_history(self):
        cr = self._make()
        cr.register("cmd", lambda a: None)
        cr.execute("cmd")
        history = cr.get_history()
        assert len(history) >= 1

    def test_enable_disable(self):
        cr = self._make()
        cr.register("cmd", lambda a: None)
        cr.disable("cmd")
        assert not cr.get("cmd").enabled
        cr.enable("cmd")
        assert cr.get("cmd").enabled

    def test_stats(self):
        cr = self._make()
        cr.register("a", lambda a: None, category="c1", aliases=["aa"])
        cr.register("b", lambda a: None, category="c2")
        cr.execute("a")
        stats = cr.get_stats()
        assert stats["total_commands"] == 2
        assert stats["aliases"] == 1
        assert stats["total_executions"] == 1


# ═══════════════════════════════════════════════════════════════════════════
# MCP HANDLERS — Phase 18
# ═══════════════════════════════════════════════════════════════════════════

class TestMCPHandlersPhase18:
    def test_retrypol_list(self):
        from src.mcp_server import handle_retrypol_list
        result = asyncio.run(handle_retrypol_list({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_retrypol_history(self):
        from src.mcp_server import handle_retrypol_history
        result = asyncio.run(handle_retrypol_history({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_retrypol_stats(self):
        from src.mcp_server import handle_retrypol_stats
        result = asyncio.run(handle_retrypol_stats({}))
        data = json.loads(result[0].text)
        assert "total_policies" in data

    def test_broker_topics(self):
        from src.mcp_server import handle_broker_topics
        result = asyncio.run(handle_broker_topics({}))
        data = json.loads(result[0].text)
        assert "topics" in data

    def test_broker_messages(self):
        from src.mcp_server import handle_broker_messages
        result = asyncio.run(handle_broker_messages({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_broker_stats(self):
        from src.mcp_server import handle_broker_stats
        result = asyncio.run(handle_broker_stats({}))
        data = json.loads(result[0].text)
        assert "topics" in data

    def test_cmdreg_list(self):
        from src.mcp_server import handle_cmdreg_list
        result = asyncio.run(handle_cmdreg_list({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_cmdreg_categories(self):
        from src.mcp_server import handle_cmdreg_categories
        result = asyncio.run(handle_cmdreg_categories({}))
        data = json.loads(result[0].text)
        assert "categories" in data

    def test_cmdreg_stats(self):
        from src.mcp_server import handle_cmdreg_stats
        result = asyncio.run(handle_cmdreg_stats({}))
        data = json.loads(result[0].text)
        assert "total_commands" in data


# ═══════════════════════════════════════════════════════════════════════════
# TOOL COUNT PHASE 18
# ═══════════════════════════════════════════════════════════════════════════

class TestToolCountPhase18:
    def test_tool_count_at_least_247(self):
        """238 + 3 retry + 3 broker + 3 cmdreg = 247."""
        from src.mcp_server import TOOL_DEFINITIONS
        assert len(TOOL_DEFINITIONS) >= 247, f"Expected >= 247 tools, got {len(TOOL_DEFINITIONS)}"

    def test_no_duplicate_tool_names(self):
        from src.mcp_server import TOOL_DEFINITIONS
        names = [t[0] for t in TOOL_DEFINITIONS]
        dupes = [n for n in names if names.count(n) > 1]
        assert len(names) == len(set(names)), f"Duplicate tools: {set(dupes)}"
