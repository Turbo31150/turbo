"""Phase 10 Tests — Retry Manager, Data Pipeline, Service Registry, MCP Handlers."""

import asyncio
import json
import time
import pytest


# ═══════════════════════════════════════════════════════════════════════════
# RETRY MANAGER
# ═══════════════════════════════════════════════════════════════════════════

class TestRetryManager:
    @staticmethod
    def _make():
        from src.retry_manager import RetryManager, RetryConfig
        return RetryManager(default_config=RetryConfig(
            max_retries=2, base_delay_s=0.01, max_delay_s=0.05, jitter=False,
        ))

    def test_singleton_exists(self):
        from src.retry_manager import retry_manager
        assert retry_manager is not None

    def test_success_no_retry(self):
        rm = self._make()
        call_count = 0

        async def ok():
            nonlocal call_count
            call_count += 1
            return "done"

        result = asyncio.run(rm.execute(ok, name="test_ok"))
        assert result == "done"
        assert call_count == 1

    def test_retry_on_failure(self):
        rm = self._make()
        attempts = []

        async def flaky():
            attempts.append(1)
            if len(attempts) < 3:
                raise ValueError("fail")
            return "recovered"

        result = asyncio.run(rm.execute(flaky, name="test_flaky"))
        assert result == "recovered"
        assert len(attempts) == 3

    def test_all_retries_exhausted(self):
        rm = self._make()

        async def always_fail():
            raise RuntimeError("permanent")

        with pytest.raises(RuntimeError, match="permanent"):
            asyncio.run(rm.execute(always_fail, name="test_fail"))

    def test_circuit_breaker_opens(self):
        rm = self._make()
        rm.configure_breaker("cb_test", failure_threshold=3, reset_timeout_s=0.1)

        async def fail():
            raise ValueError("x")

        # 1 call = 1 initial + 2 retries = 3 failures → breaker opens
        try:
            asyncio.run(rm.execute(fail, name="cb_test"))
        except (ValueError, RuntimeError):
            pass

        breaker = rm.get_breaker("cb_test")
        assert breaker.state == "open"

    def test_circuit_breaker_half_open(self):
        from src.retry_manager import CircuitBreaker
        cb = CircuitBreaker(failure_threshold=2, reset_timeout_s=0.01)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == "open"
        time.sleep(0.02)
        assert cb.state == "half_open"

    def test_sync_execute(self):
        rm = self._make()

        def sync_ok():
            return 42

        result = rm.execute_sync(sync_ok, name="sync_test")
        assert result == 42

    def test_stats(self):
        rm = self._make()

        async def ok():
            return True

        asyncio.run(rm.execute(ok, name="stat_test"))
        stats = rm.get_stats()
        assert stats["total_successes"] >= 1
        assert "breakers" in stats

    def test_reset_all(self):
        rm = self._make()

        async def fail():
            raise ValueError("x")

        try:
            asyncio.run(rm.execute(fail, name="reset_test"))
        except ValueError:
            pass

        rm.reset_all()
        stats = rm.get_stats()
        assert stats["total_retries"] == 0


# ═══════════════════════════════════════════════════════════════════════════
# DATA PIPELINE
# ═══════════════════════════════════════════════════════════════════════════

class TestDataPipeline:
    @staticmethod
    def _make():
        from src.data_pipeline import DataPipelineManager
        return DataPipelineManager()

    def test_singleton_exists(self):
        from src.data_pipeline import data_pipeline
        assert data_pipeline is not None

    def test_create_pipeline(self):
        dp = self._make()
        pipe = dp.create("test_pipe", "A test pipeline")
        assert pipe.name == "test_pipe"

    def test_list_pipelines(self):
        dp = self._make()
        dp.create("p1")
        dp.create("p2")
        assert len(dp.list_pipelines()) == 2

    def test_delete_pipeline(self):
        dp = self._make()
        dp.create("temp")
        assert dp.delete("temp")
        assert dp.get("temp") is None

    def test_execute_pipeline(self):
        dp = self._make()
        pipe = dp.create("exec_test")
        pipe.add_stage("double", lambda d: {"value": d.get("value", 0) * 2})
        pipe.add_stage("add10", lambda d: {"value": d.get("value", 0) + 10})
        run = asyncio.run(dp.run("exec_test", {"value": 5}))
        assert run.status == "completed"
        assert run.output["value"] == 20  # 5*2=10, 10+10=20

    def test_execute_async_stage(self):
        dp = self._make()
        pipe = dp.create("async_test")

        async def async_stage(data):
            return {"result": data.get("x", 0) + 1}

        pipe.add_stage("async_step", async_stage)
        run = asyncio.run(dp.run("async_test", {"x": 41}))
        assert run.status == "completed"
        assert run.output["result"] == 42

    def test_failed_stage(self):
        dp = self._make()
        pipe = dp.create("fail_test")
        pipe.add_stage("boom", lambda d: (_ for _ in ()).throw(ValueError("bad")))
        run = asyncio.run(dp.run("fail_test"))
        assert run.status == "failed"
        assert "bad" in run.error

    def test_history(self):
        dp = self._make()
        pipe = dp.create("hist")
        pipe.add_stage("noop", lambda d: d)
        asyncio.run(dp.run("hist"))
        assert len(dp.get_history()) == 1

    def test_stats(self):
        dp = self._make()
        pipe = dp.create("stat")
        pipe.add_stage("noop", lambda d: d)
        asyncio.run(dp.run("stat"))
        stats = dp.get_stats()
        assert stats["total_pipelines"] == 1
        assert stats["completed_runs"] == 1

    def test_pipeline_not_found(self):
        dp = self._make()
        with pytest.raises(KeyError):
            asyncio.run(dp.run("nonexistent"))


# ═══════════════════════════════════════════════════════════════════════════
# SERVICE REGISTRY
# ═══════════════════════════════════════════════════════════════════════════

class TestServiceRegistry:
    @staticmethod
    def _make():
        from src.service_registry import ServiceRegistry
        return ServiceRegistry()

    def test_singleton_exists(self):
        from src.service_registry import service_registry
        assert service_registry is not None

    def test_register(self):
        sr = self._make()
        entry = sr.register("m1", "http://127.0.0.1:1234", "lm_studio")
        assert entry.name == "m1"
        assert entry.url == "http://127.0.0.1:1234"

    def test_deregister(self):
        sr = self._make()
        sr.register("temp", "http://localhost")
        assert sr.deregister("temp")
        assert sr.get("temp") is None

    def test_heartbeat(self):
        sr = self._make()
        sr.register("hb", "http://localhost")
        assert sr.heartbeat("hb", "healthy")
        entry = sr.get("hb")
        assert entry.health_status == "healthy"
        assert entry.heartbeat_count == 1  # only heartbeat call counts

    def test_heartbeat_unknown(self):
        sr = self._make()
        assert not sr.heartbeat("nonexistent")

    def test_find_by_type(self):
        sr = self._make()
        sr.register("s1", "http://a", "lm_studio")
        sr.register("s2", "http://b", "ollama")
        sr.register("s3", "http://c", "lm_studio")
        results = sr.find(service_type="lm_studio")
        assert len(results) == 2

    def test_find_healthy_only(self):
        sr = self._make()
        sr.register("h1", "http://a")
        sr.heartbeat("h1", "healthy")
        sr.register("h2", "http://b")
        sr.heartbeat("h2", "unhealthy")
        results = sr.find(healthy_only=True)
        assert len(results) == 1

    def test_is_alive(self):
        sr = self._make()
        entry = sr.register("alive", "http://a", ttl_s=0.01)
        assert entry.is_alive
        time.sleep(0.02)
        assert not entry.is_alive

    def test_cleanup_stale(self):
        sr = self._make()
        sr.register("stale", "http://a", ttl_s=0.01)
        time.sleep(0.02)
        removed = sr.cleanup_stale()
        assert removed == 1
        assert sr.get("stale") is None

    def test_list_services(self):
        sr = self._make()
        sr.register("ls1", "http://a")
        services = sr.list_services()
        assert len(services) == 1
        assert services[0]["name"] == "ls1"

    def test_stats(self):
        sr = self._make()
        sr.register("st1", "http://a", "typeA")
        stats = sr.get_stats()
        assert stats["total_services"] == 1
        assert "typeA" in stats["types"]

    def test_update_existing(self):
        sr = self._make()
        sr.register("upd", "http://old")
        sr.register("upd", "http://new")
        assert sr.get("upd").url == "http://new"


# ═══════════════════════════════════════════════════════════════════════════
# MCP HANDLERS — Phase 10
# ═══════════════════════════════════════════════════════════════════════════

class TestMCPHandlersPhase10:
    def test_retry_stats(self):
        from src.mcp_server import handle_retry_stats
        result = asyncio.run(handle_retry_stats({}))
        data = json.loads(result[0].text)
        assert "total_retries" in data

    def test_retry_reset(self):
        from src.mcp_server import handle_retry_reset
        result = asyncio.run(handle_retry_reset({}))
        assert "reset" in result[0].text.lower()

    def test_pipeline_list(self):
        from src.mcp_server import handle_pipeline_list
        result = asyncio.run(handle_pipeline_list({}))
        data = json.loads(result[0].text)
        assert isinstance(data, dict) and "pipelines" in data

    def test_pipeline_stats(self):
        from src.mcp_server import handle_pipeline_stats
        result = asyncio.run(handle_pipeline_stats({}))
        data = json.loads(result[0].text)
        assert "total_pipelines" in data

    def test_service_register(self):
        from src.mcp_server import handle_service_register
        result = asyncio.run(handle_service_register({"name": "test_svc", "url": "http://test"}))
        assert "registered" in result[0].text.lower()

    def test_service_list(self):
        from src.mcp_server import handle_service_list
        result = asyncio.run(handle_service_list({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_service_heartbeat(self):
        from src.mcp_server import handle_service_heartbeat
        result = asyncio.run(handle_service_heartbeat({"name": "test_svc"}))
        assert "ok" in result[0].text.lower() or "fail" in result[0].text.lower()

    def test_service_stats(self):
        from src.mcp_server import handle_service_stats
        result = asyncio.run(handle_service_stats({}))
        data = json.loads(result[0].text)
        assert "total_services" in data


# ═══════════════════════════════════════════════════════════════════════════
# TOOL COUNT PHASE 10
# ═══════════════════════════════════════════════════════════════════════════

class TestToolCountPhase10:
    def test_tool_count_at_least_177(self):
        """168 + 2 retry + 3 pipeline + 4 service = 177."""
        from src.mcp_server import TOOL_DEFINITIONS
        assert len(TOOL_DEFINITIONS) >= 177, f"Expected >= 177 tools, got {len(TOOL_DEFINITIONS)}"

    def test_no_duplicate_tool_names(self):
        from src.mcp_server import TOOL_DEFINITIONS
        names = [t[0] for t in TOOL_DEFINITIONS]
        dupes = [n for n in names if names.count(n) > 1]
        assert len(names) == len(set(names)), f"Duplicate tools: {set(dupes)}"
