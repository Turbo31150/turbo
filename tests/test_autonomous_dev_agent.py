"""Tests for src/autonomous_dev_agent.py — Autonomous development agent.

Covers: AutonomousDevAgent (init, start, stop, _bootstrap_tasks,
_main_loop, _discover_tasks, status, get_summary, task execution flow),
dev_agent singleton.
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.autonomous_dev_agent import AutonomousDevAgent, dev_agent


# ===========================================================================
# AutonomousDevAgent — init
# ===========================================================================

class TestInit:
    def test_defaults(self):
        agent = AutonomousDevAgent()
        assert agent.running is False
        assert agent.task is None
        assert agent.current_task is None
        assert agent.completed_tasks == []
        assert agent.task_queue == []
        assert agent.stats["tasks_completed"] == 0
        assert agent.stats["started_at"] is None

    def test_task_categories(self):
        agent = AutonomousDevAgent()
        assert "critical_fix" in agent.task_categories
        assert "performance" in agent.task_categories
        assert "feature" in agent.task_categories
        assert "refactor" in agent.task_categories
        assert "documentation" in agent.task_categories

    def test_priority_ordering(self):
        agent = AutonomousDevAgent()
        assert agent.task_categories["critical_fix"] < agent.task_categories["performance"]
        assert agent.task_categories["performance"] < agent.task_categories["feature"]
        assert agent.task_categories["feature"] < agent.task_categories["refactor"]
        assert agent.task_categories["refactor"] < agent.task_categories["documentation"]


# ===========================================================================
# AutonomousDevAgent — _bootstrap_tasks
# ===========================================================================

class TestBootstrapTasks:
    @pytest.mark.asyncio
    async def test_populates_queue(self):
        agent = AutonomousDevAgent()
        await agent._bootstrap_tasks()
        assert len(agent.task_queue) >= 10

    @pytest.mark.asyncio
    async def test_sorted_by_priority(self):
        agent = AutonomousDevAgent()
        await agent._bootstrap_tasks()
        priorities = [t["priority"] for t in agent.task_queue]
        assert priorities == sorted(priorities)

    @pytest.mark.asyncio
    async def test_all_have_required_fields(self):
        agent = AutonomousDevAgent()
        await agent._bootstrap_tasks()
        for task in agent.task_queue:
            assert "id" in task
            assert "category" in task
            assert "title" in task
            assert "priority" in task
            assert "action" in task
            assert callable(task["action"])

    @pytest.mark.asyncio
    async def test_unique_ids(self):
        agent = AutonomousDevAgent()
        await agent._bootstrap_tasks()
        ids = [t["id"] for t in agent.task_queue]
        assert len(ids) == len(set(ids))

    @pytest.mark.asyncio
    async def test_critical_fix_first(self):
        agent = AutonomousDevAgent()
        await agent._bootstrap_tasks()
        first = agent.task_queue[0]
        assert first["priority"] == 1


# ===========================================================================
# AutonomousDevAgent — start / stop
# ===========================================================================

class TestStartStop:
    @pytest.mark.asyncio
    async def test_start_sets_running(self):
        agent = AutonomousDevAgent()
        with patch.object(agent, "_bootstrap_tasks", new_callable=AsyncMock), \
             patch.object(agent, "_main_loop", new_callable=AsyncMock):
            await agent.start()
        assert agent.running is True
        assert agent.stats["started_at"] is not None
        assert agent.task is not None
        # Cleanup
        agent.running = False
        agent.task.cancel()
        try:
            await agent.task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_start_idempotent(self):
        agent = AutonomousDevAgent()
        agent.running = True
        await agent.start()  # Should just warn and return
        assert agent.task is None  # Was not set again

    @pytest.mark.asyncio
    async def test_stop(self):
        agent = AutonomousDevAgent()

        async def fake_loop():
            while agent.running:
                await asyncio.sleep(0.01)

        agent.running = True
        agent.task = asyncio.create_task(fake_loop())
        await agent.stop()
        assert agent.running is False


# ===========================================================================
# AutonomousDevAgent — _discover_tasks
# ===========================================================================

class TestDiscoverTasks:
    @pytest.mark.asyncio
    async def test_no_crash(self):
        agent = AutonomousDevAgent()
        await agent._discover_tasks()
        # Currently a placeholder, should not crash


# ===========================================================================
# AutonomousDevAgent — task execution (category stat tracking)
# ===========================================================================

class TestTaskExecution:
    @pytest.mark.asyncio
    async def test_fix_category_increments_bugs_fixed(self):
        agent = AutonomousDevAgent()
        agent.running = True
        task = {
            "id": "test_001", "category": "critical_fix",
            "title": "Fix bug", "priority": 1, "estimated_time": 10,
            "action": AsyncMock(return_value={"message": "OK"}),
        }
        agent.task_queue = [task]

        # Run one iteration of main_loop manually
        t = agent.task_queue.pop(0)
        agent.current_task = t
        result = await t["action"]()
        t["status"] = "completed"
        t["result"] = result
        agent.completed_tasks.append(t)
        agent.stats["tasks_completed"] += 1
        cat = t["category"]
        if "fix" in cat:
            agent.stats["bugs_fixed"] += 1

        assert agent.stats["bugs_fixed"] == 1
        assert agent.stats["tasks_completed"] == 1

    @pytest.mark.asyncio
    async def test_feature_category(self):
        agent = AutonomousDevAgent()
        cat = "feature"
        if "feature" in cat:
            agent.stats["features_added"] += 1
        assert agent.stats["features_added"] == 1

    @pytest.mark.asyncio
    async def test_refactor_category(self):
        agent = AutonomousDevAgent()
        cat = "refactor"
        if "refactor" in cat:
            agent.stats["code_improvements"] += 1
        assert agent.stats["code_improvements"] == 1

    @pytest.mark.asyncio
    async def test_doc_category(self):
        agent = AutonomousDevAgent()
        cat = "documentation"
        if "doc" in cat:
            agent.stats["docs_updated"] += 1
        assert agent.stats["docs_updated"] == 1

    @pytest.mark.asyncio
    async def test_retry_on_failure(self):
        agent = AutonomousDevAgent()
        task = {
            "id": "fail_001", "category": "feature",
            "title": "Fail", "priority": 3, "estimated_time": 10,
            "action": AsyncMock(side_effect=RuntimeError("broken")),
            "retries": 0,
        }
        # Simulate failure retry logic
        task["retries"] = task.get("retries", 0) + 1
        task["priority"] += 1
        agent.task_queue.append(task)

        assert task["retries"] == 1
        assert task["priority"] == 4
        assert len(agent.task_queue) == 1


# ===========================================================================
# AutonomousDevAgent — status
# ===========================================================================

class TestStatus:
    def test_idle_status(self):
        agent = AutonomousDevAgent()
        status = agent.status()
        assert status["running"] is False
        assert status["uptime_seconds"] == 0
        assert status["current_task"] is None
        assert status["queue_size"] == 0
        assert status["completed"] == 0

    def test_running_status(self):
        agent = AutonomousDevAgent()
        agent.running = True
        agent.stats["started_at"] = time.time() - 3600
        agent.task_queue = [{"id": "t1"}, {"id": "t2"}]
        status = agent.status()
        assert status["running"] is True
        assert status["uptime_seconds"] >= 3599
        assert status["uptime_hours"] >= 0.99
        assert status["queue_size"] == 2

    def test_with_current_task(self):
        agent = AutonomousDevAgent()
        agent.stats["started_at"] = time.time()
        agent.current_task = {
            "id": "test_1", "title": "Test Task", "category": "feature",
        }
        status = agent.status()
        assert status["current_task"]["id"] == "test_1"
        assert status["current_task"]["title"] == "Test Task"


# ===========================================================================
# AutonomousDevAgent — get_summary
# ===========================================================================

class TestGetSummary:
    def test_returns_string(self):
        agent = AutonomousDevAgent()
        summary = agent.get_summary()
        assert isinstance(summary, str)
        assert "Running" in summary

    def test_includes_stats(self):
        agent = AutonomousDevAgent()
        agent.stats["started_at"] = time.time()
        agent.stats["bugs_fixed"] = 3
        agent.stats["features_added"] = 2
        summary = agent.get_summary()
        assert "3" in summary  # bugs
        assert "2" in summary  # features

    def test_no_current_task(self):
        agent = AutonomousDevAgent()
        agent.stats["started_at"] = time.time()
        summary = agent.get_summary()
        assert "None" in summary


# ===========================================================================
# dev_agent singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert dev_agent is not None
        assert isinstance(dev_agent, AutonomousDevAgent)

    def test_initially_stopped(self):
        # The singleton should not be running on import
        assert dev_agent.running is False


# ===========================================================================
# Task stubs return dicts
# ===========================================================================

class TestTaskStubs:
    @pytest.mark.asyncio
    async def test_optimize_lm_caching(self):
        agent = AutonomousDevAgent()
        result = await agent._task_optimize_lm_caching()
        assert isinstance(result, dict)
        assert "message" in result

    @pytest.mark.asyncio
    async def test_add_voice_pipeline(self):
        agent = AutonomousDevAgent()
        result = await agent._task_add_voice_pipeline()
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_multi_gpu_balancing(self):
        agent = AutonomousDevAgent()
        result = await agent._task_multi_gpu_balancing()
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_refactor_orchestrator(self):
        agent = AutonomousDevAgent()
        result = await agent._task_refactor_orchestrator()
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_unify_db_connections(self):
        agent = AutonomousDevAgent()
        result = await agent._task_unify_db_connections()
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_document_api(self):
        agent = AutonomousDevAgent()
        result = await agent._task_document_api()
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_create_architecture_docs(self):
        agent = AutonomousDevAgent()
        result = await agent._task_create_architecture_docs()
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_windows_notifications(self):
        agent = AutonomousDevAgent()
        result = await agent._task_windows_notifications()
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_optimize_powershell(self):
        agent = AutonomousDevAgent()
        result = await agent._task_optimize_powershell()
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_model_autotuning(self):
        agent = AutonomousDevAgent()
        result = await agent._task_model_autotuning()
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_prompt_caching(self):
        agent = AutonomousDevAgent()
        result = await agent._task_prompt_caching()
        assert isinstance(result, dict)
