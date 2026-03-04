"""Phase 13 Tests — Session Manager V2, Queue Manager, API Gateway, MCP Handlers."""

import asyncio
import json
import tempfile
import time
from pathlib import Path
import pytest


# ═══════════════════════════════════════════════════════════════════════════
# SESSION MANAGER V2
# ═══════════════════════════════════════════════════════════════════════════

class TestSessionManagerV2:
    @staticmethod
    def _make():
        from src.session_manager_v2 import SessionManagerV2
        return SessionManagerV2(store_path=Path(tempfile.mkdtemp()) / "sess.json")

    def test_singleton_exists(self):
        from src.session_manager_v2 import session_manager_v2
        assert session_manager_v2 is not None

    def test_create_session(self):
        sm = self._make()
        s = sm.create("user1")
        assert s.owner == "user1"
        assert s.status == "active"
        assert s.session_id

    def test_get_session(self):
        sm = self._make()
        s = sm.create("user2")
        got = sm.get(s.session_id)
        assert got is not None
        assert got.owner == "user2"

    def test_get_nonexistent(self):
        sm = self._make()
        assert sm.get("no-such-id") is None

    def test_touch(self):
        sm = self._make()
        s = sm.create("user3")
        assert sm.touch(s.session_id)
        got = sm.get(s.session_id)
        assert got.activity_count == 1

    def test_touch_closed(self):
        sm = self._make()
        s = sm.create("user4")
        sm.close(s.session_id)
        assert not sm.touch(s.session_id)

    def test_close(self):
        sm = self._make()
        s = sm.create("user5")
        assert sm.close(s.session_id)
        got = sm.get(s.session_id)
        assert got.status == "closed"

    def test_timeout_expiry(self):
        sm = self._make()
        s = sm.create("user6", timeout_s=0.01)
        time.sleep(0.02)
        got = sm.get(s.session_id)
        assert got.status == "expired"

    def test_cleanup_expired(self):
        sm = self._make()
        sm.create("user7", timeout_s=0.01)
        sm.create("user8", timeout_s=3600)
        time.sleep(0.02)
        count = sm.cleanup_expired()
        assert count >= 1

    def test_list_sessions(self):
        sm = self._make()
        sm.create("alice")
        sm.create("bob")
        sessions = sm.list_sessions()
        assert len(sessions) == 2

    def test_list_filter_owner(self):
        sm = self._make()
        sm.create("alice")
        sm.create("bob")
        sessions = sm.list_sessions(owner="alice")
        assert len(sessions) == 1

    def test_list_filter_status(self):
        sm = self._make()
        s = sm.create("user")
        sm.close(s.session_id)
        sm.create("user2")
        sessions = sm.list_sessions(status="active")
        assert len(sessions) == 1

    def test_tags(self):
        sm = self._make()
        s = sm.create("user", tags=["admin", "test"])
        got = sm.get(s.session_id)
        assert "admin" in got.tags

    def test_metadata(self):
        sm = self._make()
        s = sm.create("user", metadata={"ip": "127.0.0.1"})
        got = sm.get(s.session_id)
        assert got.metadata["ip"] == "127.0.0.1"

    def test_persistence(self):
        path = Path(tempfile.mkdtemp()) / "persist_sess.json"
        from src.session_manager_v2 import SessionManagerV2
        sm1 = SessionManagerV2(store_path=path)
        s = sm1.create("persist_user")
        sm2 = SessionManagerV2(store_path=path)
        sessions = sm2.list_sessions()
        assert len(sessions) == 1
        assert sessions[0]["owner"] == "persist_user"

    def test_stats(self):
        sm = self._make()
        sm.create("u1")
        s = sm.create("u2")
        sm.close(s.session_id)
        stats = sm.get_stats()
        assert stats["total_sessions"] == 2
        assert stats["active"] == 1
        assert stats["closed"] == 1


# ═══════════════════════════════════════════════════════════════════════════
# QUEUE MANAGER
# ═══════════════════════════════════════════════════════════════════════════

class TestQueueManager:
    @staticmethod
    def _make():
        from src.queue_manager import QueueManager
        return QueueManager(max_concurrent=2)

    def test_singleton_exists(self):
        from src.queue_manager import queue_manager
        assert queue_manager is not None

    def test_enqueue(self):
        qm = self._make()
        task = qm.enqueue("test_job")
        assert task.status == "pending"
        assert task.task_id

    def test_process_with_handler(self):
        qm = self._make()
        qm.register_handler("echo", lambda data: data.get("msg", "ok"))
        qm.enqueue("echo", metadata={"msg": "hello"})
        result = qm.process_next()
        assert result.status == "completed"
        assert result.result == "hello"

    def test_process_no_handler(self):
        qm = self._make()
        qm.enqueue("unknown_job")
        result = qm.process_next()
        assert result.status == "failed"
        assert "No handler" in result.error

    def test_priority_ordering(self):
        qm = self._make()
        qm.register_handler("p_job", lambda d: d.get("p"))
        qm.enqueue("p_job", priority=5, metadata={"p": "low"})
        qm.enqueue("p_job", priority=1, metadata={"p": "high"})
        result = qm.process_next()
        assert result.result == "high"  # priority 1 first

    def test_retry_on_failure(self):
        qm = self._make()
        call_count = [0]
        def failing_handler(data):
            call_count[0] += 1
            if call_count[0] < 3:
                raise ValueError("fail")
            return "success"
        qm.register_handler("retry_job", failing_handler)
        qm.enqueue("retry_job", max_retries=3)
        # First attempt fails, retried
        r1 = qm.process_next()
        assert r1.status == "pending"  # retried
        r2 = qm.process_next()
        assert r2.status == "pending"  # retried again
        r3 = qm.process_next()
        assert r3.status == "completed"

    def test_max_retries_exceeded(self):
        qm = self._make()
        def always_fail(data):
            raise ValueError("boom")
        qm.register_handler("always_fail", always_fail)
        qm.enqueue("always_fail", max_retries=1)
        result = qm.process_next()  # retries=1 >= max_retries=1 → failed immediately
        assert result is not None
        assert result.status == "failed"
        assert "boom" in result.error

    def test_cancel(self):
        qm = self._make()
        task = qm.enqueue("cancel_me")
        assert qm.cancel(task.task_id)
        assert qm.get_task(task.task_id)["status"] == "failed"

    def test_list_tasks(self):
        qm = self._make()
        qm.enqueue("a")
        qm.enqueue("b")
        tasks = qm.list_tasks()
        assert len(tasks) == 2

    def test_list_filter(self):
        qm = self._make()
        qm.register_handler("done", lambda d: "ok")
        qm.enqueue("done")
        qm.process_next()
        qm.enqueue("pending_task")
        pending = qm.list_tasks(status="pending")
        assert len(pending) == 1

    def test_get_task(self):
        qm = self._make()
        task = qm.enqueue("detail")
        got = qm.get_task(task.task_id)
        assert got["name"] == "detail"

    def test_max_concurrent(self):
        qm = self._make()  # max 2
        qm.register_handler("slow", lambda d: "ok")
        for _ in range(5):
            qm.enqueue("slow")
        stats = qm.get_stats()
        assert stats["total_tasks"] == 5

    def test_stats(self):
        qm = self._make()
        qm.enqueue("stat_job")
        stats = qm.get_stats()
        assert stats["total_tasks"] == 1
        assert stats["pending"] == 1


# ═══════════════════════════════════════════════════════════════════════════
# API GATEWAY
# ═══════════════════════════════════════════════════════════════════════════

class TestApiGateway:
    @staticmethod
    def _make():
        from src.api_gateway import ApiGateway
        return ApiGateway(global_rate_limit=100, window_s=60.0)

    def test_singleton_exists(self):
        from src.api_gateway import api_gateway
        assert api_gateway is not None

    def test_register_route(self):
        gw = self._make()
        gw.register_route("/api/test", "test_svc", handler=lambda d: {"ok": True})
        routes = gw.get_routes()
        assert len(routes) == 1

    def test_request_success(self):
        gw = self._make()
        gw.register_route("/api/echo", "echo_svc", handler=lambda d: d)
        result = gw.request("/api/echo", client_id="c1", data={"msg": "hi"})
        assert result["status"] == 200
        assert result["data"]["msg"] == "hi"

    def test_request_not_found(self):
        gw = self._make()
        result = gw.request("/api/nope", client_id="c1")
        assert result["status"] == 404

    def test_rate_limit(self):
        gw = self._make()
        gw.register_route("/api/limited", "svc", handler=lambda d: "ok", rate_limit=3)
        for _ in range(3):
            gw.request("/api/limited", client_id="c1")
        result = gw.request("/api/limited", client_id="c1")
        assert result["status"] == 429

    def test_different_clients_independent(self):
        gw = self._make()
        gw.register_route("/api/multi", "svc", handler=lambda d: "ok", rate_limit=2)
        gw.request("/api/multi", client_id="a")
        gw.request("/api/multi", client_id="a")
        # Client "a" exhausted, but "b" is fresh
        result = gw.request("/api/multi", client_id="b")
        assert result["status"] == 200

    def test_handler_error(self):
        gw = self._make()
        def err_handler(d):
            raise ValueError("oops")
        gw.register_route("/api/err", "err_svc", handler=err_handler)
        result = gw.request("/api/err", client_id="c1")
        assert result["status"] == 500

    def test_remove_route(self):
        gw = self._make()
        gw.register_route("/api/rm", "svc")
        assert gw.remove_route("/api/rm")
        assert not gw.remove_route("/api/rm")

    def test_get_clients(self):
        gw = self._make()
        gw.register_route("/api/cl", "svc", handler=lambda d: "ok")
        gw.request("/api/cl", client_id="client_x")
        clients = gw.get_clients()
        assert len(clients) == 1
        assert clients[0]["client_id"] == "client_x"

    def test_request_log(self):
        gw = self._make()
        gw.register_route("/api/log", "svc", handler=lambda d: "ok")
        gw.request("/api/log", client_id="c1")
        log = gw.get_request_log()
        assert len(log) == 1
        assert log[0]["path"] == "/api/log"

    def test_stats(self):
        gw = self._make()
        gw.register_route("/api/s", "svc", handler=lambda d: "ok")
        gw.request("/api/s", client_id="c1")
        stats = gw.get_stats()
        assert stats["total_routes"] == 1
        assert stats["total_requests"] == 1


# ═══════════════════════════════════════════════════════════════════════════
# MCP HANDLERS — Phase 13
# ═══════════════════════════════════════════════════════════════════════════

class TestMCPHandlersPhase13:
    def test_session_v2_list(self):
        from src.mcp_server import handle_session_v2_list
        result = asyncio.run(handle_session_v2_list({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_session_v2_create(self):
        from src.mcp_server import handle_session_v2_create
        result = asyncio.run(handle_session_v2_create({"owner": "test_user"}))
        data = json.loads(result[0].text)
        assert "session_id" in data

    def test_session_v2_stats(self):
        from src.mcp_server import handle_session_v2_stats
        result = asyncio.run(handle_session_v2_stats({}))
        data = json.loads(result[0].text)
        assert "total_sessions" in data

    def test_queue_list(self):
        from src.mcp_server import handle_queue_list
        result = asyncio.run(handle_queue_list({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_queue_stats(self):
        from src.mcp_server import handle_queue_stats
        result = asyncio.run(handle_queue_stats({}))
        data = json.loads(result[0].text)
        assert "total_tasks" in data

    def test_apigw_routes(self):
        from src.mcp_server import handle_apigw_routes
        result = asyncio.run(handle_apigw_routes({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_apigw_clients(self):
        from src.mcp_server import handle_apigw_clients
        result = asyncio.run(handle_apigw_clients({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_apigw_stats(self):
        from src.mcp_server import handle_apigw_stats
        result = asyncio.run(handle_apigw_stats({}))
        data = json.loads(result[0].text)
        assert "total_routes" in data


# ═══════════════════════════════════════════════════════════════════════════
# TOOL COUNT PHASE 13
# ═══════════════════════════════════════════════════════════════════════════

class TestToolCountPhase13:
    def test_tool_count_at_least_202(self):
        """194 + 3 session_v2 + 2 queue + 3 apigw = 202."""
        from src.mcp_server import TOOL_DEFINITIONS
        assert len(TOOL_DEFINITIONS) >= 202, f"Expected >= 202 tools, got {len(TOOL_DEFINITIONS)}"

    def test_no_duplicate_tool_names(self):
        from src.mcp_server import TOOL_DEFINITIONS
        names = [t[0] for t in TOOL_DEFINITIONS]
        dupes = [n for n in names if names.count(n) > 1]
        assert len(names) == len(set(names)), f"Duplicate tools: {set(dupes)}"
