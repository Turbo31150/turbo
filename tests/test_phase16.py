"""Phase 16 Tests — Event Store, Webhook Manager, Health Probe, MCP Handlers."""

import asyncio
import json
import time
import pytest


# ═══════════════════════════════════════════════════════════════════════════
# EVENT STORE
# ═══════════════════════════════════════════════════════════════════════════

class TestEventStore:
    @staticmethod
    def _make():
        from src.event_store import EventStore
        return EventStore(max_events=100)

    def test_singleton_exists(self):
        from src.event_store import event_store
        assert event_store is not None

    def test_append_and_get_stream(self):
        es = self._make()
        es.append("orders", "order_created", {"id": 1})
        events = es.get_stream("orders")
        assert len(events) == 1
        assert events[0].event_type == "order_created"

    def test_versioning(self):
        es = self._make()
        e1 = es.append("s1", "a")
        e2 = es.append("s1", "b")
        assert e1.version == 1
        assert e2.version == 2

    def test_get_all(self):
        es = self._make()
        es.append("s1", "a")
        es.append("s2", "b")
        assert len(es.get_all()) == 2

    def test_get_by_type(self):
        es = self._make()
        es.append("s1", "click")
        es.append("s1", "view")
        es.append("s2", "click")
        assert len(es.get_by_type("click")) == 2

    def test_count(self):
        es = self._make()
        es.append("s1", "a")
        es.append("s1", "b")
        es.append("s2", "c")
        assert es.count("s1") == 2
        assert es.count() == 3

    def test_streams(self):
        es = self._make()
        es.append("alpha", "a")
        es.append("beta", "b")
        assert "alpha" in es.streams()
        assert "beta" in es.streams()

    def test_snapshot(self):
        es = self._make()
        es.append("s1", "a")
        snap = es.save_snapshot("s1", {"total": 10})
        assert snap.version == 1
        assert es.get_snapshot("s1").state["total"] == 10

    def test_replay(self):
        es = self._make()
        es.append("counter", "inc", {"amount": 5})
        es.append("counter", "inc", {"amount": 3})
        es.append("counter", "dec", {"amount": 2})

        def reducer(state, event):
            if event.event_type == "inc":
                state["val"] = state.get("val", 0) + event.data.get("amount", 0)
            elif event.event_type == "dec":
                state["val"] = state.get("val", 0) - event.data.get("amount", 0)
            return state

        result = es.replay("counter", reducer)
        assert result["val"] == 6

    def test_replay_with_snapshot(self):
        es = self._make()
        es.append("s1", "inc", {"v": 1})
        es.save_snapshot("s1", {"val": 100})
        es.append("s1", "inc", {"v": 5})

        def reducer(state, event):
            state["val"] = state.get("val", 0) + event.data.get("v", 0)
            return state

        result = es.replay("s1", reducer)
        assert result["val"] == 105  # snapshot 100 + event 5

    def test_projection(self):
        es = self._make()

        def counter_proj(state, event):
            state["count"] = state.get("count", 0) + 1
            return state

        es.register_projection("counter", counter_proj)
        es.append("s1", "a")
        es.append("s1", "b")
        result = es.project("counter", "s1")
        assert result["count"] == 2

    def test_subscribe(self):
        es = self._make()
        received = []
        es.subscribe("s1", lambda e: received.append(e))
        es.append("s1", "test")
        assert len(received) == 1

    def test_subscribe_wildcard(self):
        es = self._make()
        received = []
        es.subscribe("*", lambda e: received.append(e))
        es.append("any_stream", "test")
        assert len(received) == 1

    def test_unsubscribe(self):
        es = self._make()
        received = []
        es.subscribe("s1", lambda e: received.append(e))
        es.unsubscribe("s1")
        es.append("s1", "test")
        assert len(received) == 0

    def test_rotation(self):
        es = self._make()  # max 100
        for i in range(150):
            es.append("rot", "evt", {"i": i})
        assert es.count() <= 100

    def test_stats(self):
        es = self._make()
        es.append("s1", "a")
        es.append("s2", "b")
        stats = es.get_stats()
        assert stats["total_events"] == 2
        assert stats["streams"] == 2


# ═══════════════════════════════════════════════════════════════════════════
# WEBHOOK MANAGER
# ═══════════════════════════════════════════════════════════════════════════

class TestWebhookManager:
    @staticmethod
    def _make():
        from src.webhook_manager import WebhookManager
        return WebhookManager()

    def test_singleton_exists(self):
        from src.webhook_manager import webhook_manager
        assert webhook_manager is not None

    def test_register(self):
        wm = self._make()
        ep = wm.register("hook1", "https://example.com/hook")
        assert ep.name == "hook1"

    def test_list_endpoints(self):
        wm = self._make()
        wm.register("h1", "https://a.com")
        wm.register("h2", "https://b.com")
        assert len(wm.list_endpoints()) == 2

    def test_unregister(self):
        wm = self._make()
        wm.register("temp", "https://x.com")
        assert wm.unregister("temp")
        assert not wm.unregister("temp")

    def test_set_active(self):
        wm = self._make()
        wm.register("h1", "https://a.com")
        assert wm.set_active("h1", False)
        assert not wm.get_endpoint("h1").active

    def test_sign_and_verify(self):
        from src.webhook_manager import WebhookManager
        payload = {"event": "test", "data": 123}
        sig = WebhookManager.sign_payload(payload, "secret123")
        assert WebhookManager.verify_signature(payload, "secret123", sig)
        assert not WebhookManager.verify_signature(payload, "wrong", sig)

    def test_dispatch_with_transport(self):
        wm = self._make()
        wm.register("h1", "https://a.com", events=["user.created"])
        wm.set_transport(lambda url, payload, headers: (200, "ok"))
        records = wm.dispatch("user.created", {"user": "alice"})
        assert len(records) == 1
        assert records[0].status == "success"

    def test_dispatch_event_filter(self):
        wm = self._make()
        wm.register("h1", "https://a.com", events=["user.created"])
        wm.set_transport(lambda url, payload, headers: (200, "ok"))
        records = wm.dispatch("order.placed", {"id": 1})
        assert len(records) == 0  # h1 not subscribed to order.placed

    def test_dispatch_all_events(self):
        wm = self._make()
        wm.register("h1", "https://a.com")  # no filter = all events
        wm.set_transport(lambda url, payload, headers: (200, "ok"))
        records = wm.dispatch("anything", {"x": 1})
        assert len(records) == 1

    def test_dispatch_retry_failure(self):
        wm = self._make()
        wm.register("h1", "https://a.com", max_retries=2)

        def fail_transport(url, payload, headers):
            return (500, "error")

        wm.set_transport(fail_transport)
        records = wm.dispatch("test", {})
        assert records[0].status == "failed"
        assert records[0].attempts == 2

    def test_dispatch_inactive_skipped(self):
        wm = self._make()
        wm.register("h1", "https://a.com")
        wm.set_active("h1", False)
        wm.set_transport(lambda u, p, h: (200, "ok"))
        records = wm.dispatch("test", {})
        assert len(records) == 0

    def test_history(self):
        wm = self._make()
        wm.register("h1", "https://a.com")
        wm.set_transport(lambda u, p, h: (200, "ok"))
        wm.dispatch("test", {})
        history = wm.get_history()
        assert len(history) == 1
        assert history[0]["status"] == "success"

    def test_history_filter(self):
        wm = self._make()
        wm.register("h1", "https://a.com")
        wm.register("h2", "https://b.com")
        wm.set_transport(lambda u, p, h: (200, "ok"))
        wm.dispatch("test", {})
        assert len(wm.get_history(webhook_name="h1")) == 1
        assert len(wm.get_history(webhook_name="h2")) == 1

    def test_stats(self):
        wm = self._make()
        wm.register("h1", "https://a.com")
        wm.set_transport(lambda u, p, h: (200, "ok"))
        wm.dispatch("test", {})
        stats = wm.get_stats()
        assert stats["endpoints"] == 1
        assert stats["successful"] == 1
        assert stats["success_rate"] == 100.0


# ═══════════════════════════════════════════════════════════════════════════
# HEALTH PROBE
# ═══════════════════════════════════════════════════════════════════════════

class TestHealthProbe:
    @staticmethod
    def _make():
        from src.health_probe import HealthProbe
        return HealthProbe()

    def test_singleton_exists(self):
        from src.health_probe import health_probe
        assert health_probe is not None

    def test_register_and_list(self):
        hp = self._make()
        hp.register("db", lambda: True)
        probes = hp.list_probes()
        assert len(probes) == 1
        assert probes[0]["name"] == "db"

    def test_unregister(self):
        hp = self._make()
        hp.register("temp", lambda: True)
        assert hp.unregister("temp")
        assert not hp.unregister("temp")

    def test_run_check_healthy(self):
        hp = self._make()
        hp.register("ok_check", lambda: True)
        r = hp.run_check("ok_check")
        assert r.status.value == "healthy"

    def test_run_check_ok_string(self):
        hp = self._make()
        hp.register("ok_str", lambda: "ok")
        r = hp.run_check("ok_str")
        assert r.status.value == "healthy"

    def test_run_check_degraded(self):
        hp = self._make()
        hp.register("slow", lambda: "high latency", critical=False)
        r = hp.run_check("slow")
        assert r.status.value == "degraded"

    def test_run_check_unhealthy_critical(self):
        hp = self._make()
        hp.register("dead", lambda: False, critical=True)
        r = hp.run_check("dead")
        assert r.status.value == "unhealthy"

    def test_run_check_exception(self):
        def boom():
            raise ConnectionError("timeout")
        hp = self._make()
        hp.register("fail", boom, critical=True)
        r = hp.run_check("fail")
        assert r.status.value == "unhealthy"
        assert "timeout" in r.message

    def test_run_check_nonexistent(self):
        hp = self._make()
        assert hp.run_check("nope") is None

    def test_run_all(self):
        hp = self._make()
        hp.register("a", lambda: True)
        hp.register("b", lambda: True)
        results = hp.run_all()
        assert len(results) == 2

    def test_overall_healthy(self):
        from src.health_probe import HealthStatus
        hp = self._make()
        hp.register("a", lambda: True)
        hp.register("b", lambda: True)
        hp.run_all()
        assert hp.overall_status() == HealthStatus.HEALTHY

    def test_overall_unhealthy(self):
        from src.health_probe import HealthStatus
        hp = self._make()
        hp.register("ok", lambda: True)
        hp.register("bad", lambda: False, critical=True)
        hp.run_all()
        assert hp.overall_status() == HealthStatus.UNHEALTHY

    def test_overall_degraded(self):
        from src.health_probe import HealthStatus
        hp = self._make()
        hp.register("ok", lambda: True)
        hp.register("slow", lambda: "warn", critical=False)
        hp.run_all()
        assert hp.overall_status() == HealthStatus.DEGRADED

    def test_overall_unknown_no_probes(self):
        from src.health_probe import HealthStatus
        hp = self._make()
        assert hp.overall_status() == HealthStatus.UNKNOWN

    def test_history(self):
        hp = self._make()
        hp.register("h", lambda: True)
        hp.run_check("h")
        hp.run_check("h")
        history = hp.get_history()
        assert len(history) == 2

    def test_history_filter(self):
        hp = self._make()
        hp.register("a", lambda: True)
        hp.register("b", lambda: True)
        hp.run_all()
        assert len(hp.get_history(name="a")) == 1

    def test_latency_measured(self):
        hp = self._make()
        hp.register("lat", lambda: True)
        r = hp.run_check("lat")
        assert r.latency_ms >= 0

    def test_stats(self):
        hp = self._make()
        hp.register("a", lambda: True, critical=True)
        hp.register("b", lambda: True, critical=False)
        hp.run_all()
        stats = hp.get_stats()
        assert stats["total_probes"] == 2
        assert stats["critical_probes"] == 1
        assert stats["total_checks"] == 2
        assert stats["healthy"] == 2


# ═══════════════════════════════════════════════════════════════════════════
# MCP HANDLERS — Phase 16
# ═══════════════════════════════════════════════════════════════════════════

class TestMCPHandlersPhase16:
    def test_evstore_streams(self):
        from src.mcp_server import handle_evstore_streams
        result = asyncio.run(handle_evstore_streams({}))
        data = json.loads(result[0].text)
        assert "streams" in data

    def test_evstore_events(self):
        from src.mcp_server import handle_evstore_events
        result = asyncio.run(handle_evstore_events({"limit": "10"}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_evstore_stats(self):
        from src.mcp_server import handle_evstore_stats
        result = asyncio.run(handle_evstore_stats({}))
        data = json.loads(result[0].text)
        assert "total_events" in data

    def test_webhook_list(self):
        from src.mcp_server import handle_webhook_list
        result = asyncio.run(handle_webhook_list({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_webhook_history(self):
        from src.mcp_server import handle_webhook_history
        result = asyncio.run(handle_webhook_history({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_webhook_stats(self):
        from src.mcp_server import handle_webhook_stats
        result = asyncio.run(handle_webhook_stats({}))
        data = json.loads(result[0].text)
        assert "endpoints" in data

    def test_hprobe_list(self):
        from src.mcp_server import handle_hprobe_list
        result = asyncio.run(handle_hprobe_list({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_hprobe_run(self):
        from src.mcp_server import handle_hprobe_run
        result = asyncio.run(handle_hprobe_run({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_hprobe_stats(self):
        from src.mcp_server import handle_hprobe_stats
        result = asyncio.run(handle_hprobe_stats({}))
        data = json.loads(result[0].text)
        assert "total_probes" in data


# ═══════════════════════════════════════════════════════════════════════════
# TOOL COUNT PHASE 16
# ═══════════════════════════════════════════════════════════════════════════

class TestToolCountPhase16:
    def test_tool_count_at_least_229(self):
        """220 + 3 evstore + 3 webhook + 3 hprobe = 229."""
        from src.mcp_server import TOOL_DEFINITIONS
        assert len(TOOL_DEFINITIONS) >= 229, f"Expected >= 229 tools, got {len(TOOL_DEFINITIONS)}"

    def test_no_duplicate_tool_names(self):
        from src.mcp_server import TOOL_DEFINITIONS
        names = [t[0] for t in TOOL_DEFINITIONS]
        dupes = [n for n in names if names.count(n) > 1]
        assert len(names) == len(set(names)), f"Duplicate tools: {set(dupes)}"
