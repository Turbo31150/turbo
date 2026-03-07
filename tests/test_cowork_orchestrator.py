"""Tests for src/cowork_orchestrator.py — Cowork development orchestrator.

Covers: CoworkOrchestrator (init, stop, _get_next_tasks, _assign_agents,
_validate_result, _extract_file_paths, _extract_review_score, status,
_log_status), cowork_orchestrator singleton.
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.cowork_orchestrator import CoworkOrchestrator, cowork_orchestrator
from src.cowork_master_config import (
    DevelopmentTask, TaskPriority, TaskCategory, AgentRole,
    AVAILABLE_AGENTS, COWORK_CONFIG, DEVELOPMENT_QUEUE,
)


# ===========================================================================
# CoworkOrchestrator — init
# ===========================================================================

class TestInit:
    def test_defaults(self):
        orch = CoworkOrchestrator()
        assert orch.running is False
        assert orch.start_time is None
        assert len(orch.task_queue) == len(DEVELOPMENT_QUEUE)
        assert orch.active_tasks == {}
        assert orch.completed_tasks == []
        assert orch.failed_tasks == []
        assert orch.stats["tasks_completed"] == 0

    def test_agents_status_all_idle(self):
        orch = CoworkOrchestrator()
        for name in AVAILABLE_AGENTS:
            assert orch.agents_status[name] == "idle"

    def test_agents_status_count(self):
        orch = CoworkOrchestrator()
        assert len(orch.agents_status) == len(AVAILABLE_AGENTS)


# ===========================================================================
# CoworkOrchestrator — stop
# ===========================================================================

class TestStop:
    @pytest.mark.asyncio
    async def test_stop(self):
        orch = CoworkOrchestrator()
        orch.running = True
        await orch.stop()
        assert orch.running is False

    @pytest.mark.asyncio
    async def test_stop_idempotent(self):
        orch = CoworkOrchestrator()
        await orch.stop()
        await orch.stop()
        assert orch.running is False


# ===========================================================================
# CoworkOrchestrator — _get_next_tasks
# ===========================================================================

class TestGetNextTasks:
    def test_no_slots(self):
        orch = CoworkOrchestrator()
        # Fill active_tasks to max
        for i in range(COWORK_CONFIG["max_parallel_tasks"]):
            orch.active_tasks[f"task_{i}"] = MagicMock()
        tasks = orch._get_next_tasks()
        assert tasks == []

    def test_picks_pending_only(self):
        orch = CoworkOrchestrator()
        orch.task_queue = [
            DevelopmentTask(
                id="T-A", title="Done", description="D",
                category=TaskCategory.BUGFIX, priority=TaskPriority.CRITICAL,
                required_agents=[AgentRole.CODER], estimated_duration_min=10,
                status="completed",
            ),
            DevelopmentTask(
                id="T-B", title="Pending", description="D",
                category=TaskCategory.BUGFIX, priority=TaskPriority.HIGH,
                required_agents=[AgentRole.CODER], estimated_duration_min=10,
            ),
        ]
        tasks = orch._get_next_tasks()
        assert len(tasks) == 1
        assert tasks[0].id == "T-B"

    def test_checks_dependencies(self):
        orch = CoworkOrchestrator()
        orch.task_queue = [
            DevelopmentTask(
                id="T-A", title="Blocked", description="D",
                category=TaskCategory.FEATURE, priority=TaskPriority.CRITICAL,
                required_agents=[AgentRole.CODER], estimated_duration_min=10,
                dependencies=["T-MISSING"],
            ),
            DevelopmentTask(
                id="T-B", title="Free", description="D",
                category=TaskCategory.FEATURE, priority=TaskPriority.HIGH,
                required_agents=[AgentRole.CODER], estimated_duration_min=10,
            ),
        ]
        tasks = orch._get_next_tasks()
        assert len(tasks) == 1
        assert tasks[0].id == "T-B"

    def test_deps_met(self):
        orch = CoworkOrchestrator()
        dep = DevelopmentTask(
            id="T-DEP", title="Dep", description="D",
            category=TaskCategory.BUGFIX, priority=TaskPriority.CRITICAL,
            required_agents=[AgentRole.CODER], estimated_duration_min=10,
        )
        orch.completed_tasks.append(dep)
        orch.task_queue = [
            DevelopmentTask(
                id="T-A", title="Has dep", description="D",
                category=TaskCategory.FEATURE, priority=TaskPriority.HIGH,
                required_agents=[AgentRole.CODER], estimated_duration_min=10,
                dependencies=["T-DEP"],
            ),
        ]
        tasks = orch._get_next_tasks()
        assert len(tasks) == 1
        assert tasks[0].id == "T-A"

    def test_sorted_by_priority(self):
        orch = CoworkOrchestrator()
        orch.task_queue = [
            DevelopmentTask(
                id="LOW", title="Low", description="D",
                category=TaskCategory.DOCUMENTATION, priority=TaskPriority.LOW,
                required_agents=[AgentRole.DOCUMENTER], estimated_duration_min=10,
            ),
            DevelopmentTask(
                id="CRIT", title="Critical", description="D",
                category=TaskCategory.BUGFIX, priority=TaskPriority.CRITICAL,
                required_agents=[AgentRole.CODER], estimated_duration_min=10,
            ),
            DevelopmentTask(
                id="MED", title="Medium", description="D",
                category=TaskCategory.TESTING, priority=TaskPriority.MEDIUM,
                required_agents=[AgentRole.TESTER], estimated_duration_min=10,
            ),
        ]
        tasks = orch._get_next_tasks()
        assert tasks[0].id == "CRIT"

    def test_limits_to_max_parallel(self):
        orch = CoworkOrchestrator()
        max_p = COWORK_CONFIG["max_parallel_tasks"]
        orch.task_queue = [
            DevelopmentTask(
                id=f"T-{i}", title=f"T{i}", description="D",
                category=TaskCategory.TESTING, priority=TaskPriority.MEDIUM,
                required_agents=[AgentRole.TESTER], estimated_duration_min=10,
            )
            for i in range(max_p + 5)
        ]
        tasks = orch._get_next_tasks()
        assert len(tasks) == max_p


# ===========================================================================
# CoworkOrchestrator — _assign_agents
# ===========================================================================

class TestAssignAgents:
    def test_assigns_available(self):
        orch = CoworkOrchestrator()
        task = DevelopmentTask(
            id="T-1", title="T", description="D",
            category=TaskCategory.BUGFIX, priority=TaskPriority.HIGH,
            required_agents=[AgentRole.CODER], estimated_duration_min=10,
        )
        assigned = orch._assign_agents(task)
        assert AgentRole.CODER in assigned
        agent_name = assigned[AgentRole.CODER]["name"]
        assert orch.agents_status[agent_name] == "busy"

    def test_no_agent_for_role(self):
        orch = CoworkOrchestrator()
        # Mark all agents as busy
        for name in orch.agents_status:
            orch.agents_status[name] = "busy"
        task = DevelopmentTask(
            id="T-2", title="T", description="D",
            category=TaskCategory.BUGFIX, priority=TaskPriority.HIGH,
            required_agents=[AgentRole.CODER], estimated_duration_min=10,
        )
        assigned = orch._assign_agents(task)
        assert AgentRole.CODER not in assigned

    def test_multi_role(self):
        orch = CoworkOrchestrator()
        task = DevelopmentTask(
            id="T-3", title="T", description="D",
            category=TaskCategory.FEATURE, priority=TaskPriority.HIGH,
            required_agents=[AgentRole.ARCHITECT, AgentRole.CODER],
            estimated_duration_min=30,
        )
        assigned = orch._assign_agents(task)
        # Should assign at least some roles
        assert len(assigned) >= 1


# ===========================================================================
# CoworkOrchestrator — _validate_result
# ===========================================================================

class TestValidateResult:
    @pytest.mark.asyncio
    async def test_valid(self):
        orch = CoworkOrchestrator()
        task = MagicMock()
        result = {"code_review_score": 85.0, "tests_passed": True}
        assert await orch._validate_result(task, result) is True

    @pytest.mark.asyncio
    async def test_low_review_score(self):
        orch = CoworkOrchestrator()
        task = MagicMock()
        result = {"code_review_score": 50.0, "tests_passed": True}
        assert await orch._validate_result(task, result) is False

    @pytest.mark.asyncio
    async def test_tests_failed(self):
        orch = CoworkOrchestrator()
        task = MagicMock()
        result = {"code_review_score": 90.0, "tests_passed": False}
        assert await orch._validate_result(task, result) is False


# ===========================================================================
# CoworkOrchestrator — _extract_file_paths
# ===========================================================================

class TestExtractFilePaths:
    def test_finds_paths(self):
        orch = CoworkOrchestrator()
        code = "Created F:/BUREAU/turbo/src/new_module.py and F:/BUREAU/turbo/src/utils/helper.py"
        paths = orch._extract_file_paths(code)
        assert "F:/BUREAU/turbo/src/new_module.py" in paths

    def test_no_paths(self):
        orch = CoworkOrchestrator()
        paths = orch._extract_file_paths("No paths here")
        assert paths == []

    def test_deduplicates(self):
        orch = CoworkOrchestrator()
        code = "F:/BUREAU/turbo/src/mod.py and F:/BUREAU/turbo/src/mod.py again"
        paths = orch._extract_file_paths(code)
        assert len(paths) == 1


# ===========================================================================
# CoworkOrchestrator — _extract_review_score
# ===========================================================================

class TestExtractReviewScore:
    def test_finds_score(self):
        orch = CoworkOrchestrator()
        review = "Overall score: 85 out of 100"
        assert orch._extract_review_score(review) == 85.0

    def test_score_colon(self):
        orch = CoworkOrchestrator()
        review = "Score:92"
        assert orch._extract_review_score(review) == 92.0

    def test_no_score_default(self):
        orch = CoworkOrchestrator()
        review = "This code looks great!"
        assert orch._extract_review_score(review) == 75.0

    def test_case_insensitive(self):
        orch = CoworkOrchestrator()
        review = "SCORE: 88"
        assert orch._extract_review_score(review) == 88.0


# ===========================================================================
# CoworkOrchestrator — status
# ===========================================================================

class TestStatus:
    def test_idle(self):
        orch = CoworkOrchestrator()
        status = orch.status()
        assert status["running"] is False
        assert status["active_tasks"] == 0
        assert status["agents_idle"] == len(AVAILABLE_AGENTS)
        assert status["agents_busy"] == 0

    def test_with_activity(self):
        orch = CoworkOrchestrator()
        orch.running = True
        orch.stats["uptime_hours"] = 2.5
        orch.stats["tasks_completed"] = 5
        orch.active_tasks["T-1"] = MagicMock()
        # Mark one agent as busy
        first_agent = list(orch.agents_status.keys())[0]
        orch.agents_status[first_agent] = "busy"

        status = orch.status()
        assert status["running"] is True
        assert status["uptime_hours"] == 2.5
        assert status["active_tasks"] == 1
        assert status["agents_busy"] == 1
        assert status["agents_idle"] == len(AVAILABLE_AGENTS) - 1


# ===========================================================================
# CoworkOrchestrator — _log_status
# ===========================================================================

class TestLogStatus:
    def test_does_not_crash(self):
        orch = CoworkOrchestrator()
        orch._log_status()  # Should not raise


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert cowork_orchestrator is not None
        assert isinstance(cowork_orchestrator, CoworkOrchestrator)

    def test_has_queue(self):
        # Fresh singleton should have the development queue
        assert len(cowork_orchestrator.task_queue) > 0
