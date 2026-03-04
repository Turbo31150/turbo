"""Phase 8 Tests — Rate Limiter, Task Scheduler, Health Dashboard, MCP Handlers."""

import asyncio
import json
import tempfile
import time
from pathlib import Path
import pytest


# ═══════════════════════════════════════════════════════════════════════════
# RATE LIMITER
# ═══════════════════════════════════════════════════════════════════════════

class TestRateLimiter:
    @staticmethod
    def _make():
        from src.rate_limiter import RateLimiter
        return RateLimiter(default_rps=10.0, default_burst=20.0)

    def test_singleton_exists(self):
        from src.rate_limiter import rate_limiter
        assert rate_limiter is not None

    def test_allow_within_burst(self):
        rl = self._make()
        for _ in range(20):
            assert rl.allow("M1")

    def test_deny_after_burst(self):
        rl = self._make()
        for _ in range(20):
            rl.allow("M1")
        assert not rl.allow("M1")

    def test_wait_time(self):
        rl = self._make()
        for _ in range(20):
            rl.allow("M1")
        wt = rl.wait_time("M1")
        assert wt > 0

    def test_configure_node(self):
        rl = self._make()
        rl.configure_node("M2", rps=5.0, burst=10.0)
        for _ in range(10):
            assert rl.allow("M2")
        assert not rl.allow("M2")

    def test_node_stats(self):
        rl = self._make()
        rl.allow("M1")
        stats = rl.get_node_stats("M1")
        assert stats["node"] == "M1"
        assert stats["total_allowed"] == 1
        assert stats["total_denied"] == 0

    def test_all_stats(self):
        rl = self._make()
        rl.allow("M1")
        rl.allow("M2")
        stats = rl.get_all_stats()
        assert "M1" in stats["nodes"]
        assert "M2" in stats["nodes"]
        assert stats["total_allowed"] == 2

    def test_reset_node(self):
        rl = self._make()
        for _ in range(20):
            rl.allow("M1")
        assert not rl.allow("M1")
        rl.reset_node("M1")
        assert rl.allow("M1")

    def test_reset_all(self):
        rl = self._make()
        rl.allow("M1")
        rl.allow("M2")
        rl.reset_all()
        assert rl.get_all_stats()["nodes"] == {}

    def test_cost(self):
        rl = self._make()
        assert rl.allow("M1", cost=15.0)
        assert rl.allow("M1", cost=5.0)
        assert not rl.allow("M1", cost=1.0)


# ═══════════════════════════════════════════════════════════════════════════
# TASK SCHEDULER
# ═══════════════════════════════════════════════════════════════════════════

class TestTaskScheduler:
    @staticmethod
    def _make():
        from src.task_scheduler import TaskScheduler
        tmpdir = tempfile.mkdtemp()
        return TaskScheduler(db_path=Path(tmpdir) / "test_sched.db")

    def test_singleton_exists(self):
        from src.task_scheduler import task_scheduler
        assert task_scheduler is not None

    def test_add_job(self):
        ts = self._make()
        job_id = ts.add_job("test_job", "noop", 60)
        assert isinstance(job_id, str)
        assert len(job_id) == 12

    def test_list_jobs(self):
        ts = self._make()
        ts.add_job("j1", "a", 10)
        ts.add_job("j2", "b", 20)
        jobs = ts.list_jobs()
        assert len(jobs) == 2

    def test_get_job(self):
        ts = self._make()
        jid = ts.add_job("mytest", "act", 30)
        job = ts.get_job(jid)
        assert job is not None
        assert job["name"] == "mytest"

    def test_remove_job(self):
        ts = self._make()
        jid = ts.add_job("temp", "act", 10)
        assert ts.remove_job(jid)
        assert ts.get_job(jid) is None

    def test_enable_disable(self):
        ts = self._make()
        jid = ts.add_job("j", "a", 10)
        ts.enable_job(jid, False)
        job = ts.get_job(jid)
        assert job["enabled"] == 0

    def test_tick_executes_due(self):
        ts = self._make()
        results = []

        async def handler(params):
            results.append(params)
            return "done"

        ts.register_handler("test_act", handler)
        ts.add_job("tick_test", "test_act", 0, params={"x": 1})  # interval=0 → always due
        count = asyncio.run(ts.tick())
        assert count == 1
        assert len(results) == 1
        assert results[0] == {"x": 1}

    def test_one_shot(self):
        ts = self._make()

        async def handler(params):
            return "ok"

        ts.register_handler("once", handler)
        jid = ts.add_job("once_job", "once", 0, one_shot=True)
        asyncio.run(ts.tick())
        job = ts.get_job(jid)
        assert job["enabled"] == 0  # disabled after one run

    def test_stats(self):
        ts = self._make()
        ts.add_job("s", "a", 10)
        stats = ts.get_stats()
        assert stats["total_jobs"] == 1
        assert stats["enabled_jobs"] == 1
        assert "registered_handlers" in stats

    def test_missing_handler(self):
        ts = self._make()
        ts.add_job("bad", "nonexistent_action", 0)
        count = asyncio.run(ts.tick())
        assert count == 1
        job = ts.list_jobs()[0]
        assert "No handler" in job["last_error"]


# ═══════════════════════════════════════════════════════════════════════════
# HEALTH DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════

class TestHealthDashboard:
    def test_singleton_exists(self):
        from src.health_dashboard import health_dashboard
        assert health_dashboard is not None

    def test_collect_structure(self):
        from src.health_dashboard import HealthDashboard
        hd = HealthDashboard()
        report = hd.collect()
        assert "ts" in report
        assert "subsystems" in report
        assert "overall_health" in report
        assert "status" in report
        assert "problems" in report
        assert report["status"] in ("healthy", "degraded", "critical")

    def test_collect_subsystems(self):
        from src.health_dashboard import HealthDashboard
        hd = HealthDashboard()
        report = hd.collect()
        expected = {"diagnostics", "metrics", "alerts", "scheduler", "rate_limiter", "config", "audit", "event_bus"}
        assert expected.issubset(set(report["subsystems"].keys()))

    def test_summary_before_collect(self):
        from src.health_dashboard import HealthDashboard
        hd = HealthDashboard()
        summary = hd.get_summary()
        assert summary["status"] == "unknown"

    def test_summary_after_collect(self):
        from src.health_dashboard import HealthDashboard
        hd = HealthDashboard()
        hd.collect()
        summary = hd.get_summary()
        assert summary["status"] != "unknown"
        assert "overall_health" in summary
        assert "subsystems_ok" in summary

    def test_history(self):
        from src.health_dashboard import HealthDashboard
        hd = HealthDashboard()
        hd.collect()
        hd.collect()
        history = hd.get_history()
        assert len(history) == 2
        assert "health" in history[0]

    def test_overall_health_range(self):
        from src.health_dashboard import HealthDashboard
        hd = HealthDashboard()
        report = hd.collect()
        assert 0 <= report["overall_health"] <= 100


# ═══════════════════════════════════════════════════════════════════════════
# MCP HANDLERS — Phase 8
# ═══════════════════════════════════════════════════════════════════════════

class TestMCPHandlersPhase8:
    def test_ratelimit_check(self):
        from src.mcp_server import handle_ratelimit_check
        result = asyncio.run(handle_ratelimit_check({"node": "M1"}))
        data = json.loads(result[0].text)
        assert "allowed" in data

    def test_ratelimit_stats(self):
        from src.mcp_server import handle_ratelimit_stats
        result = asyncio.run(handle_ratelimit_stats({}))
        data = json.loads(result[0].text)
        assert "nodes" in data

    def test_ratelimit_configure(self):
        from src.mcp_server import handle_ratelimit_configure
        result = asyncio.run(handle_ratelimit_configure({"node": "TEST", "rps": "5", "burst": "10"}))
        assert "configured" in result[0].text.lower()

    def test_scheduler_list(self):
        from src.mcp_server import handle_scheduler_list
        result = asyncio.run(handle_scheduler_list({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_scheduler_add(self):
        from src.mcp_server import handle_scheduler_add
        result = asyncio.run(handle_scheduler_add({"name": "test", "action": "noop", "interval_s": "60"}))
        assert "added" in result[0].text.lower()

    def test_scheduler_stats(self):
        from src.mcp_server import handle_scheduler_stats
        result = asyncio.run(handle_scheduler_stats({}))
        data = json.loads(result[0].text)
        assert "total_jobs" in data

    def test_health_full(self):
        from src.mcp_server import handle_health_full
        result = asyncio.run(handle_health_full({}))
        data = json.loads(result[0].text)
        assert "subsystems" in data
        assert "overall_health" in data

    def test_health_summary(self):
        from src.mcp_server import handle_health_summary
        result = asyncio.run(handle_health_summary({}))
        data = json.loads(result[0].text)
        assert "status" in data

    def test_health_history(self):
        from src.mcp_server import handle_health_history
        result = asyncio.run(handle_health_history({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)


# ═══════════════════════════════════════════════════════════════════════════
# TOOL COUNT PHASE 8
# ═══════════════════════════════════════════════════════════════════════════

class TestToolCountPhase8:
    def test_tool_count_at_least_159(self):
        """149 + 3 ratelimit + 4 scheduler + 3 health = 159."""
        from src.mcp_server import TOOL_DEFINITIONS
        assert len(TOOL_DEFINITIONS) >= 159, f"Expected >= 159 tools, got {len(TOOL_DEFINITIONS)}"

    def test_no_duplicate_tool_names(self):
        from src.mcp_server import TOOL_DEFINITIONS
        names = [t[0] for t in TOOL_DEFINITIONS]
        dupes = [n for n in names if names.count(n) > 1]
        assert len(names) == len(set(names)), f"Duplicate tools: {set(dupes)}"
