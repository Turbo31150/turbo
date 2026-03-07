"""Tests for src/cowork_master_config.py — Cowork master configuration.

Covers: TaskPriority, TaskCategory, AgentRole enums,
DevelopmentTask dataclass, AVAILABLE_AGENTS, DEVELOPMENT_QUEUE,
COWORK_CONFIG.
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.cowork_master_config import (
    TaskPriority, TaskCategory, AgentRole,
    DevelopmentTask, AVAILABLE_AGENTS, DEVELOPMENT_QUEUE, COWORK_CONFIG,
)


# ===========================================================================
# TaskPriority
# ===========================================================================

class TestTaskPriority:
    def test_values(self):
        assert TaskPriority.CRITICAL.value == 1
        assert TaskPriority.HIGH.value == 2
        assert TaskPriority.MEDIUM.value == 3
        assert TaskPriority.LOW.value == 4

    def test_ordering(self):
        assert TaskPriority.CRITICAL.value < TaskPriority.HIGH.value
        assert TaskPriority.HIGH.value < TaskPriority.MEDIUM.value
        assert TaskPriority.MEDIUM.value < TaskPriority.LOW.value

    def test_member_count(self):
        assert len(TaskPriority) == 4


# ===========================================================================
# TaskCategory
# ===========================================================================

class TestTaskCategory:
    def test_values(self):
        expected = {"bugfix", "feature", "optimization", "refactor",
                    "testing", "documentation", "infrastructure", "security"}
        actual = {c.value for c in TaskCategory}
        assert actual == expected

    def test_member_count(self):
        assert len(TaskCategory) == 8


# ===========================================================================
# AgentRole
# ===========================================================================

class TestAgentRole:
    def test_values(self):
        expected = {"architect", "coder", "reviewer", "tester",
                    "optimizer", "documenter"}
        actual = {r.value for r in AgentRole}
        assert actual == expected

    def test_member_count(self):
        assert len(AgentRole) == 6


# ===========================================================================
# DevelopmentTask
# ===========================================================================

class TestDevelopmentTask:
    def test_defaults(self):
        task = DevelopmentTask(
            id="T-001", title="Test", description="Desc",
            category=TaskCategory.BUGFIX, priority=TaskPriority.HIGH,
            required_agents=[AgentRole.CODER],
            estimated_duration_min=30,
        )
        assert task.status == "pending"
        assert task.dependencies == []
        assert task.assigned_to is None
        assert task.started_at is None
        assert task.completed_at is None
        assert task.result == {}
        assert task.error is None
        assert isinstance(task.created_at, datetime)

    def test_with_dependencies(self):
        task = DevelopmentTask(
            id="T-002", title="Dep", description="With deps",
            category=TaskCategory.FEATURE, priority=TaskPriority.MEDIUM,
            required_agents=[AgentRole.ARCHITECT, AgentRole.CODER],
            estimated_duration_min=90,
            dependencies=["T-001"],
        )
        assert task.dependencies == ["T-001"]
        assert len(task.required_agents) == 2

    def test_status_mutation(self):
        task = DevelopmentTask(
            id="T-003", title="M", description="D",
            category=TaskCategory.TESTING, priority=TaskPriority.LOW,
            required_agents=[AgentRole.TESTER], estimated_duration_min=10,
        )
        task.status = "in_progress"
        assert task.status == "in_progress"
        task.assigned_to = "coder_m2"
        assert task.assigned_to == "coder_m2"


# ===========================================================================
# AVAILABLE_AGENTS
# ===========================================================================

class TestAvailableAgents:
    def test_not_empty(self):
        assert len(AVAILABLE_AGENTS) >= 6

    def test_all_have_role(self):
        for name, info in AVAILABLE_AGENTS.items():
            assert "role" in info, f"{name}: missing role"
            assert isinstance(info["role"], AgentRole)

    def test_all_have_specialties(self):
        for name, info in AVAILABLE_AGENTS.items():
            assert "specialties" in info, f"{name}: missing specialties"
            assert len(info["specialties"]) >= 1

    def test_covers_all_roles(self):
        roles_present = {info["role"] for info in AVAILABLE_AGENTS.values()}
        for role in AgentRole:
            assert role in roles_present, f"No agent with role {role.value}"

    def test_lm_studio_agents_have_node(self):
        for name, info in AVAILABLE_AGENTS.items():
            if "node" in info:
                assert info["node"].startswith("http")

    def test_known_agents(self):
        assert "architect_m1" in AVAILABLE_AGENTS
        assert "coder_m2" in AVAILABLE_AGENTS
        assert "reviewer_m3" in AVAILABLE_AGENTS


# ===========================================================================
# DEVELOPMENT_QUEUE
# ===========================================================================

class TestDevelopmentQueue:
    def test_has_tasks(self):
        assert len(DEVELOPMENT_QUEUE) >= 20

    def test_all_are_tasks(self):
        for task in DEVELOPMENT_QUEUE:
            assert isinstance(task, DevelopmentTask)

    def test_unique_ids(self):
        ids = [t.id for t in DEVELOPMENT_QUEUE]
        assert len(ids) == len(set(ids)), "Duplicate task IDs found"

    def test_ids_format(self):
        for task in DEVELOPMENT_QUEUE:
            assert task.id.startswith("DEV-"), f"Bad ID format: {task.id}"

    def test_valid_priorities(self):
        for task in DEVELOPMENT_QUEUE:
            assert isinstance(task.priority, TaskPriority)

    def test_valid_categories(self):
        for task in DEVELOPMENT_QUEUE:
            assert isinstance(task.category, TaskCategory)

    def test_required_agents_not_empty(self):
        for task in DEVELOPMENT_QUEUE:
            assert len(task.required_agents) >= 1, f"{task.id}: no required agents"

    def test_estimated_duration_positive(self):
        for task in DEVELOPMENT_QUEUE:
            assert task.estimated_duration_min > 0, f"{task.id}: zero duration"

    def test_dependencies_reference_valid_ids(self):
        all_ids = {t.id for t in DEVELOPMENT_QUEUE}
        for task in DEVELOPMENT_QUEUE:
            for dep in task.dependencies:
                assert dep in all_ids, f"{task.id} depends on unknown {dep}"

    def test_has_critical_tasks(self):
        critical = [t for t in DEVELOPMENT_QUEUE if t.priority == TaskPriority.CRITICAL]
        assert len(critical) >= 1

    def test_has_multiple_categories(self):
        categories = {t.category for t in DEVELOPMENT_QUEUE}
        assert len(categories) >= 5

    def test_all_statuses_pending(self):
        for task in DEVELOPMENT_QUEUE:
            assert task.status == "pending"

    def test_phases_coverage(self):
        # Ensure tasks span multiple phases (IDs spread out)
        ids_nums = [int(t.id.split("-")[1]) for t in DEVELOPMENT_QUEUE]
        assert max(ids_nums) >= 20


# ===========================================================================
# COWORK_CONFIG
# ===========================================================================

class TestCoworkConfig:
    def test_is_dict(self):
        assert isinstance(COWORK_CONFIG, dict)

    def test_timing_keys(self):
        assert "task_poll_interval_sec" in COWORK_CONFIG
        assert "max_parallel_tasks" in COWORK_CONFIG
        assert "agent_timeout_min" in COWORK_CONFIG

    def test_quality_gates(self):
        assert COWORK_CONFIG["require_code_review"] is True
        assert COWORK_CONFIG["require_tests"] is True
        assert 0 < COWORK_CONFIG["min_test_coverage"] <= 1.0

    def test_git_config(self):
        assert "auto_commit" in COWORK_CONFIG
        assert "commit_prefix" in COWORK_CONFIG
        assert "branch_pattern" in COWORK_CONFIG
        assert "{task_id}" in COWORK_CONFIG["branch_pattern"]

    def test_notification_config(self):
        assert COWORK_CONFIG["notify_on_task_complete"] is True
        assert COWORK_CONFIG["notify_on_task_failed"] is True
        assert isinstance(COWORK_CONFIG["notification_channels"], list)

    def test_reasonable_values(self):
        assert COWORK_CONFIG["task_poll_interval_sec"] > 0
        assert COWORK_CONFIG["max_parallel_tasks"] >= 1
        assert COWORK_CONFIG["agent_timeout_min"] >= 1
