"""Tests for src/cowork_agent_config.py — Cowork agent and task backlog.

Covers: CoworkTask dataclass, COWORK_BACKLOG, CoworkAgent (init, start,
stop, _pick_next_task, _dependencies_met, _execute_task, status).
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

from src.cowork_agent_config import CoworkTask, CoworkAgent, COWORK_BACKLOG, cowork_agent


# ===========================================================================
# CoworkTask
# ===========================================================================

class TestCoworkTask:
    def test_defaults(self):
        task = CoworkTask(
            id="T-001", title="Test", description="Desc",
            category="test", priority=5, estimated_duration_min=10,
        )
        assert task.status == "pending"
        assert task.dependencies == []
        assert task.result == {}
        assert task.started_at == 0
        assert task.completed_at == 0
        assert task.error == ""

    def test_with_dependencies(self):
        task = CoworkTask(
            id="T-002", title="Dep", description="With deps",
            category="ia", priority=8, estimated_duration_min=30,
            dependencies=["T-001"],
        )
        assert task.dependencies == ["T-001"]

    def test_status_mutation(self):
        task = CoworkTask(
            id="T-003", title="Mut", description="Test",
            category="cluster", priority=3, estimated_duration_min=5,
        )
        task.status = "in_progress"
        assert task.status == "in_progress"
        task.started_at = time.time()
        assert task.started_at > 0


# ===========================================================================
# COWORK_BACKLOG
# ===========================================================================

class TestCoworkBacklog:
    def test_not_empty(self):
        assert len(COWORK_BACKLOG) >= 10

    def test_all_are_tasks(self):
        for task in COWORK_BACKLOG:
            assert isinstance(task, CoworkTask)

    def test_unique_ids(self):
        ids = [t.id for t in COWORK_BACKLOG]
        assert len(ids) == len(set(ids)), "Duplicate task IDs found"

    def test_valid_priorities(self):
        for task in COWORK_BACKLOG:
            assert 1 <= task.priority <= 10, f"{task.id}: priority {task.priority} out of range"

    def test_categories(self):
        categories = {t.category for t in COWORK_BACKLOG}
        assert "windows" in categories
        assert "ia" in categories
        assert "cluster" in categories

    def test_dependencies_reference_valid_ids(self):
        all_ids = {t.id for t in COWORK_BACKLOG}
        for task in COWORK_BACKLOG:
            for dep in task.dependencies:
                assert dep in all_ids, f"{task.id} depends on unknown {dep}"


# ===========================================================================
# CoworkAgent — init
# ===========================================================================

class TestCoworkAgentInit:
    def test_init(self):
        agent = CoworkAgent()
        assert agent.running is False
        assert agent.current_task is None
        assert agent.completed_tasks == []
        assert len(agent.backlog) > 0
        assert agent.stats["tasks_completed"] == 0

    def test_singleton_exists(self):
        assert cowork_agent is not None
        assert isinstance(cowork_agent, CoworkAgent)


# ===========================================================================
# CoworkAgent — _dependencies_met
# ===========================================================================

class TestDependenciesMet:
    def test_no_deps(self):
        agent = CoworkAgent()
        task = CoworkTask(
            id="X-001", title="T", description="D",
            category="test", priority=5, estimated_duration_min=1,
        )
        assert agent._dependencies_met(task) is True

    def test_deps_not_met(self):
        agent = CoworkAgent()
        task = CoworkTask(
            id="X-002", title="T", description="D",
            category="test", priority=5, estimated_duration_min=1,
            dependencies=["X-001"],
        )
        assert agent._dependencies_met(task) is False

    def test_deps_met(self):
        agent = CoworkAgent()
        dep = CoworkTask(
            id="X-001", title="Dep", description="D",
            category="test", priority=5, estimated_duration_min=1,
            status="completed",
        )
        agent.completed_tasks.append(dep)
        task = CoworkTask(
            id="X-002", title="T", description="D",
            category="test", priority=5, estimated_duration_min=1,
            dependencies=["X-001"],
        )
        assert agent._dependencies_met(task) is True


# ===========================================================================
# CoworkAgent — _pick_next_task
# ===========================================================================

class TestPickNextTask:
    def test_picks_highest_priority(self):
        agent = CoworkAgent()
        agent.backlog = [
            CoworkTask(id="A", title="Low", description="D", category="t",
                       priority=3, estimated_duration_min=1),
            CoworkTask(id="B", title="High", description="D", category="t",
                       priority=9, estimated_duration_min=1),
            CoworkTask(id="C", title="Med", description="D", category="t",
                       priority=5, estimated_duration_min=1),
        ]
        task = agent._pick_next_task()
        assert task is not None
        assert task.id == "B"

    def test_skips_non_pending(self):
        agent = CoworkAgent()
        agent.backlog = [
            CoworkTask(id="A", title="Done", description="D", category="t",
                       priority=10, estimated_duration_min=1, status="completed"),
            CoworkTask(id="B", title="Pending", description="D", category="t",
                       priority=5, estimated_duration_min=1),
        ]
        task = agent._pick_next_task()
        assert task.id == "B"

    def test_empty_backlog(self):
        agent = CoworkAgent()
        agent.backlog = []
        assert agent._pick_next_task() is None

    def test_skips_blocked_deps(self):
        agent = CoworkAgent()
        agent.backlog = [
            CoworkTask(id="A", title="Blocked", description="D", category="t",
                       priority=10, estimated_duration_min=1,
                       dependencies=["MISSING"]),
            CoworkTask(id="B", title="Free", description="D", category="t",
                       priority=5, estimated_duration_min=1),
        ]
        task = agent._pick_next_task()
        assert task.id == "B"


# ===========================================================================
# CoworkAgent — _execute_task
# ===========================================================================

class TestExecuteTask:
    @pytest.mark.asyncio
    async def test_success(self):
        agent = CoworkAgent()
        agent.backlog = [
            CoworkTask(id="EX-001", title="Test", description="D",
                       category="test", priority=5, estimated_duration_min=1),
        ]
        task = agent.backlog[0]
        with patch.object(agent, "_call_perplexity_for_task", new_callable=AsyncMock), \
             patch.object(agent, "_emit_completion", new_callable=AsyncMock):
            await agent._execute_task(task)
        assert task.status == "completed"
        assert task.completed_at > 0
        assert agent.stats["tasks_completed"] == 1
        assert len(agent.completed_tasks) == 1

    @pytest.mark.asyncio
    async def test_failure(self):
        agent = CoworkAgent()
        agent.backlog = [
            CoworkTask(id="EX-002", title="Fail", description="D",
                       category="test", priority=5, estimated_duration_min=1),
        ]
        task = agent.backlog[0]
        with patch.object(agent, "_call_perplexity_for_task", new_callable=AsyncMock,
                          side_effect=RuntimeError("broken")):
            await agent._execute_task(task)
        assert task.status == "failed"
        assert "broken" in task.error
        assert agent.stats["tasks_failed"] == 1


# ===========================================================================
# CoworkAgent — status
# ===========================================================================

class TestStatus:
    def test_status_idle(self):
        agent = CoworkAgent()
        status = agent.status()
        assert status["running"] is False
        assert status["current_task"] is None
        assert status["backlog_size"] > 0
        assert status["completed_count"] == 0
        assert "next_tasks" in status
        assert len(status["next_tasks"]) <= 5

    def test_status_with_current_task(self):
        agent = CoworkAgent()
        agent.current_task = CoworkTask(
            id="CUR-001", title="Current", description="D",
            category="test", priority=5, estimated_duration_min=1,
        )
        status = agent.status()
        assert status["current_task"]["id"] == "CUR-001"

    def test_next_tasks_sorted_by_priority(self):
        agent = CoworkAgent()
        status = agent.status()
        priorities = [t["priority"] for t in status["next_tasks"]]
        assert priorities == sorted(priorities, reverse=True)


# ===========================================================================
# CoworkAgent — stop
# ===========================================================================

class TestStop:
    def test_stop(self):
        agent = CoworkAgent()
        agent.running = True
        agent.stop()
        assert agent.running is False

    def test_stop_idempotent(self):
        agent = CoworkAgent()
        agent.stop()
        agent.stop()
        assert agent.running is False
