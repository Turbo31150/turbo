"""Comprehensive tests for src/collab_bridge.py

Uses an in-memory SQLite database so no real jarvis.db or network access
is ever needed.  Every call to ``_conn()`` is patched to return the shared
in-memory connection that already contains the ``collab_tasks`` schema.
"""

from __future__ import annotations

import json
import sqlite3
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.collab_bridge import (
    _gen_id,
    cancel_task,
    claim_task,
    complete_task,
    create_task,
    get_pending_tasks,
    get_task,
    list_tasks,
    stats,
)

# ---------------------------------------------------------------------------
# Fixtures — in-memory SQLite with the real schema
# ---------------------------------------------------------------------------

_SCHEMA = """\
CREATE TABLE IF NOT EXISTS collab_tasks (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id       TEXT UNIQUE NOT NULL,
    title         TEXT NOT NULL,
    description   TEXT DEFAULT '',
    category      TEXT DEFAULT 'general',
    priority      TEXT DEFAULT 'medium',
    status        TEXT DEFAULT 'pending',
    assigned_to   TEXT DEFAULT 'perplexity',
    created_by    TEXT DEFAULT 'claude_code',
    actions       TEXT DEFAULT '[]',
    expected_output TEXT DEFAULT '',
    result        TEXT DEFAULT NULL,
    created_at    REAL,
    started_at    REAL,
    completed_at  REAL
);
"""


def _make_conn() -> sqlite3.Connection:
    """Return a fresh in-memory connection with the schema already applied."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(_SCHEMA)
    conn.commit()
    return conn


@pytest.fixture(autouse=True)
def _patch_conn():
    """Patch ``_conn`` for every test so it returns the same in-memory db."""
    mem = _make_conn()
    with patch("src.collab_bridge._conn", return_value=mem):
        yield mem
    mem.close()


# ===================================================================
# 1. Import & module-level sanity
# ===================================================================

class TestImports:
    def test_public_functions_exist(self):
        """All expected public functions are importable."""
        for name in (
            "create_task", "get_pending_tasks", "claim_task",
            "complete_task", "get_task", "list_tasks",
            "cancel_task", "stats",
        ):
            assert callable(globals()[name]), f"{name} should be callable"

    def test_gen_id_format(self):
        """_gen_id returns a string starting with 'task_'."""
        tid = _gen_id()
        assert tid.startswith("task_")
        # The rest is a timestamp like 20260306_143500
        parts = tid.replace("task_", "").split("_")
        assert len(parts) == 2
        assert parts[0].isdigit() and len(parts[0]) == 8
        assert parts[1].isdigit() and len(parts[1]) == 6


# ===================================================================
# 2. create_task
# ===================================================================

class TestCreateTask:
    def test_create_minimal(self, _patch_conn):
        """Create a task with only a title; defaults should apply."""
        result = create_task("Do something")
        assert result["status"] == "pending"
        assert result["title"] == "Do something"
        assert result["task_id"].startswith("task_")

    def test_create_with_explicit_id(self, _patch_conn):
        """Caller-supplied task_id is respected."""
        result = create_task("My task", task_id="custom_42")
        assert result["task_id"] == "custom_42"

    def test_create_stores_actions_as_json(self, _patch_conn):
        """The actions list is serialised as JSON in the database."""
        actions = [{"type": "search", "query": "hello"}]
        create_task("Task with actions", actions=actions, task_id="act_1")
        row = get_task("act_1")
        assert row is not None
        stored = json.loads(row["actions"])
        assert stored == actions

    def test_create_all_params(self, _patch_conn):
        """Every parameter is correctly persisted."""
        result = create_task(
            title="Full task",
            description="desc",
            category="code",
            priority="high",
            assigned_to="claude",
            created_by="human",
            actions=[{"a": 1}],
            expected_output="json blob",
            task_id="full_1",
        )
        row = get_task("full_1")
        assert row["description"] == "desc"
        assert row["category"] == "code"
        assert row["priority"] == "high"
        assert row["assigned_to"] == "claude"
        assert row["created_by"] == "human"
        assert row["expected_output"] == "json blob"

    def test_create_duplicate_id_raises(self, _patch_conn):
        """Inserting the same task_id twice should raise IntegrityError."""
        create_task("First", task_id="dup_1")
        with pytest.raises(sqlite3.IntegrityError):
            create_task("Second", task_id="dup_1")


# ===================================================================
# 3. get_task / get_pending_tasks
# ===================================================================

class TestGetTask:
    def test_get_existing(self, _patch_conn):
        create_task("Exist", task_id="ex_1")
        row = get_task("ex_1")
        assert row is not None
        assert row["title"] == "Exist"

    def test_get_nonexistent_returns_none(self, _patch_conn):
        assert get_task("no_such_id") is None

    def test_get_pending_filters_by_assignee(self, _patch_conn):
        create_task("For perp", assigned_to="perplexity", task_id="p1")
        create_task("For claude", assigned_to="claude", task_id="p2")
        pending = get_pending_tasks("perplexity")
        assert len(pending) == 1
        assert pending[0]["task_id"] == "p1"


# ===================================================================
# 4. claim_task
# ===================================================================

class TestClaimTask:
    def test_claim_sets_in_progress(self, _patch_conn):
        create_task("Claimable", task_id="cl_1")
        row = claim_task("cl_1")
        assert row is not None
        assert row["status"] == "in_progress"
        assert row["started_at"] is not None

    def test_claim_already_claimed_no_change(self, _patch_conn):
        """Claiming a task already in_progress leaves it unchanged."""
        create_task("Once", task_id="cl_2")
        claim_task("cl_2")
        # Second claim targets status='pending' which no longer matches
        row = claim_task("cl_2")
        # Row still returned (SELECT has no status filter), status still in_progress
        assert row is not None
        assert row["status"] == "in_progress"

    def test_claim_nonexistent_returns_none(self, _patch_conn):
        assert claim_task("ghost") is None


# ===================================================================
# 5. complete_task
# ===================================================================

class TestCompleteTask:
    def test_complete_success(self, _patch_conn):
        create_task("Completable", task_id="co_1")
        claim_task("co_1")
        row = complete_task("co_1", result="done!", success=True)
        assert row is not None
        assert row["status"] == "completed"
        assert row["result"] == "done!"
        assert row["completed_at"] is not None

    def test_complete_failure(self, _patch_conn):
        create_task("Failing", task_id="co_2")
        row = complete_task("co_2", result="error msg", success=False)
        assert row is not None
        assert row["status"] == "failed"
        assert row["result"] == "error msg"

    def test_complete_nonexistent(self, _patch_conn):
        assert complete_task("nope", "whatever") is None


# ===================================================================
# 6. cancel_task
# ===================================================================

class TestCancelTask:
    def test_cancel_pending(self, _patch_conn):
        create_task("Cancellable", task_id="cn_1")
        row = cancel_task("cn_1")
        assert row is not None
        assert row["status"] == "cancelled"

    def test_cancel_in_progress(self, _patch_conn):
        create_task("Running", task_id="cn_2")
        claim_task("cn_2")
        row = cancel_task("cn_2")
        assert row is not None
        assert row["status"] == "cancelled"

    def test_cancel_already_completed_noop(self, _patch_conn):
        """Cancelling a completed task should not change its status."""
        create_task("Done", task_id="cn_3")
        complete_task("cn_3", "result")
        row = cancel_task("cn_3")
        # The UPDATE WHERE clause excludes 'completed', so status stays
        assert row is not None
        assert row["status"] == "completed"

    def test_cancel_nonexistent(self, _patch_conn):
        assert cancel_task("void") is None


# ===================================================================
# 7. list_tasks
# ===================================================================

class TestListTasks:
    def test_list_all(self, _patch_conn):
        for i in range(5):
            create_task(f"T{i}", task_id=f"lt_{i}")
        result = list_tasks()
        assert len(result) == 5

    def test_list_with_status_filter(self, _patch_conn):
        create_task("A", task_id="ls_1")
        create_task("B", task_id="ls_2")
        claim_task("ls_1")
        pending = list_tasks(status="pending")
        assert len(pending) == 1
        assert pending[0]["task_id"] == "ls_2"

    def test_list_respects_limit(self, _patch_conn):
        for i in range(10):
            create_task(f"T{i}", task_id=f"lim_{i}")
        result = list_tasks(limit=3)
        assert len(result) == 3

    def test_list_empty(self, _patch_conn):
        assert list_tasks() == []


# ===================================================================
# 8. stats
# ===================================================================

class TestStats:
    def test_stats_empty(self, _patch_conn):
        assert stats() == {}

    def test_stats_counts(self, _patch_conn):
        create_task("A", task_id="s1")
        create_task("B", task_id="s2")
        claim_task("s1")
        complete_task("s2", "ok")
        result = stats()
        assert result.get("in_progress") == 1
        assert result.get("completed") == 1


# ===================================================================
# 9. Full workflow (integration-style, still in-memory)
# ===================================================================

class TestFullWorkflow:
    def test_end_to_end(self, _patch_conn):
        """Simulate the complete Claude Code -> Perplexity collaboration flow."""
        # Step 1: Claude Code creates a task
        task = create_task(
            title="Research Python 3.14 features",
            description="Find all new features in Python 3.14",
            category="research",
            priority="high",
            assigned_to="perplexity",
            created_by="claude_code",
            task_id="e2e_1",
        )
        assert task["status"] == "pending"

        # Step 2: Perplexity picks it up
        pending = get_pending_tasks("perplexity")
        assert len(pending) == 1

        # Step 3: Perplexity claims it
        claimed = claim_task("e2e_1")
        assert claimed["status"] == "in_progress"

        # No more pending
        assert get_pending_tasks("perplexity") == []

        # Step 4: Perplexity completes it
        done = complete_task("e2e_1", result="Python 3.14 adds X, Y, Z")
        assert done["status"] == "completed"
        assert "X, Y, Z" in done["result"]

        # Step 5: Claude Code reads the result
        final = get_task("e2e_1")
        assert final["status"] == "completed"
        assert final["result"] == "Python 3.14 adds X, Y, Z"

        # Stats reflect the completed task
        s = stats()
        assert s.get("completed") == 1

    def test_create_and_cancel_flow(self, _patch_conn):
        """Task created, then cancelled before completion."""
        create_task("Throwaway", task_id="flow_c")
        cancel_task("flow_c")
        row = get_task("flow_c")
        assert row["status"] == "cancelled"
        assert stats().get("cancelled") == 1


# ===================================================================
# 10. Edge cases & mocking internals
# ===================================================================

class TestEdgeCases:
    def test_gen_id_called_when_no_task_id(self, _patch_conn):
        """When task_id is None, _gen_id is used."""
        with patch("src.collab_bridge._gen_id", return_value="task_mock_123") as mock_gen:
            result = create_task("Auto ID")
            mock_gen.assert_called_once()
            assert result["task_id"] == "task_mock_123"

    def test_actions_default_empty_list(self, _patch_conn):
        """When actions is None, an empty list is stored."""
        create_task("No actions", task_id="edge_1")
        row = get_task("edge_1")
        assert json.loads(row["actions"]) == []

    def test_unicode_content(self, _patch_conn):
        """Unicode in title/description is handled correctly."""
        create_task(
            title="Tache avec accents et emojis",
            description="Recherche avancee",
            task_id="uni_1",
        )
        row = get_task("uni_1")
        assert row["title"] == "Tache avec accents et emojis"
        assert row["description"] == "Recherche avancee"

    def test_complete_overwrites_previous_result(self, _patch_conn):
        """Calling complete_task twice overwrites the result."""
        create_task("Overwrite", task_id="ow_1")
        complete_task("ow_1", "first")
        complete_task("ow_1", "second")
        row = get_task("ow_1")
        assert row["result"] == "second"
