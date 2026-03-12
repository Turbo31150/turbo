"""Tests for src/task_queue.py — Priority-based async task queue.

Covers: TaskStatus enum, QueuedTask (defaults, to_dict), TaskQueue (_init_db,
enqueue, cancel, get_task, list_pending, list_recent, get_stats, process_next,
_get_best_node, cleanup, _update_task, _row_to_task), task_queue singleton.
"""

from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.task_queue import TaskStatus, QueuedTask, TaskQueue, task_queue


# ===========================================================================
# TaskStatus
# ===========================================================================

class TestTaskStatus:
    def test_values(self):
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.RUNNING.value == "running"
        assert TaskStatus.DONE.value == "done"
        assert TaskStatus.FAILED.value == "failed"
        assert TaskStatus.CANCELLED.value == "cancelled"

    def test_is_string(self):
        assert isinstance(TaskStatus.PENDING, str)
        assert TaskStatus.PENDING == "pending"


# ===========================================================================
# QueuedTask
# ===========================================================================

class TestQueuedTask:
    def test_defaults(self):
        t = QueuedTask(id="abc", prompt="do something")
        assert t.task_type == "code"
        assert t.priority == 5
        assert t.status == TaskStatus.PENDING
        assert t.node == ""
        assert t.result == ""
        assert t.error == ""
        assert t.retries == 0
        assert t.max_retries == 2
        assert t.timeout_s == 120.0
        assert t.created_at > 0
        assert t.started_at == 0.0
        assert t.finished_at == 0.0

    def test_to_dict_fields(self):
        t = QueuedTask(id="x1", prompt="test prompt", task_type="math",
                       priority=8, status=TaskStatus.DONE, node="M1",
                       result="42", retries=1)
        d = t.to_dict()
        assert d["id"] == "x1"
        assert d["task_type"] == "math"
        assert d["priority"] == 8
        assert d["status"] == "done"
        assert d["node"] == "M1"
        assert d["result"] == "42"
        assert d["retries"] == 1

    def test_to_dict_truncates_prompt(self):
        t = QueuedTask(id="x", prompt="a" * 500)
        d = t.to_dict()
        assert len(d["prompt"]) == 200

    def test_to_dict_truncates_result(self):
        t = QueuedTask(id="x", prompt="q", result="r" * 1000)
        d = t.to_dict()
        assert len(d["result"]) == 500


# ===========================================================================
# TaskQueue — init
# ===========================================================================

class TestInit:
    def test_creates_db(self):
        f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        db_path = Path(f.name)
        f.close()
        tq = TaskQueue(db_path=db_path)
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        conn.close()
        assert "tasks" in tables
        # tempfile cleanup skipped (Windows file locking)


# ===========================================================================
# TaskQueue — enqueue / get_task / cancel
# ===========================================================================

class TestEnqueueGetCancel:
    def _make_queue(self):
        f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        db_path = Path(f.name)
        f.close()
        return TaskQueue(db_path=db_path), db_path

    def test_enqueue_returns_id(self):
        tq, db = self._make_queue()
        tid = tq.enqueue("test prompt")
        assert isinstance(tid, str)
        assert len(tid) == 8
        # tempfile cleanup skipped (Windows file locking)

    def test_enqueue_with_options(self):
        tq, db = self._make_queue()
        tid = tq.enqueue("math problem", task_type="math", priority=9,
                         max_retries=5, timeout_s=60.0)
        task = tq.get_task(tid)
        assert task is not None
        assert task.task_type == "math"
        assert task.priority == 9
        assert task.max_retries == 5
        assert task.timeout_s == 60.0
        # tempfile cleanup skipped (Windows file locking)

    def test_get_task_existing(self):
        tq, db = self._make_queue()
        tid = tq.enqueue("hello")
        task = tq.get_task(tid)
        assert task is not None
        assert task.prompt == "hello"
        assert task.status == TaskStatus.PENDING
        # tempfile cleanup skipped (Windows file locking)

    def test_get_task_nonexistent(self):
        tq, db = self._make_queue()
        assert tq.get_task("nope") is None
        # tempfile cleanup skipped (Windows file locking)

    def test_cancel_pending(self):
        tq, db = self._make_queue()
        tid = tq.enqueue("to cancel")
        assert tq.cancel(tid) is True
        task = tq.get_task(tid)
        assert task.status == TaskStatus.CANCELLED
        # tempfile cleanup skipped (Windows file locking)

    def test_cancel_nonexistent(self):
        tq, db = self._make_queue()
        assert tq.cancel("nope") is False
        # tempfile cleanup skipped (Windows file locking)

    def test_cancel_already_cancelled(self):
        tq, db = self._make_queue()
        tid = tq.enqueue("test")
        tq.cancel(tid)
        assert tq.cancel(tid) is False  # already cancelled
        # tempfile cleanup skipped (Windows file locking)


# ===========================================================================
# TaskQueue — list_pending / list_recent
# ===========================================================================

class TestListMethods:
    def _make_queue(self):
        f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        db_path = Path(f.name)
        f.close()
        return TaskQueue(db_path=db_path), db_path

    def test_list_pending_empty(self):
        tq, db = self._make_queue()
        assert tq.list_pending() == []
        # tempfile cleanup skipped (Windows file locking)

    def test_list_pending_ordered_by_priority(self):
        tq, db = self._make_queue()
        tq.enqueue("low", priority=1)
        tq.enqueue("high", priority=10)
        tq.enqueue("mid", priority=5)
        result = tq.list_pending()
        assert len(result) == 3
        assert result[0]["priority"] == 10
        assert result[1]["priority"] == 5
        assert result[2]["priority"] == 1
        # tempfile cleanup skipped (Windows file locking)

    def test_list_pending_limit(self):
        tq, db = self._make_queue()
        for i in range(5):
            tq.enqueue(f"task{i}")
        result = tq.list_pending(limit=2)
        assert len(result) == 2
        # tempfile cleanup skipped (Windows file locking)

    def test_list_recent_empty(self):
        tq, db = self._make_queue()
        assert tq.list_recent() == []
        # tempfile cleanup skipped (Windows file locking)

    def test_list_recent_shows_done_and_failed(self):
        tq, db = self._make_queue()
        import sqlite3
        tid1 = tq.enqueue("done task")
        tid2 = tq.enqueue("failed task")
        # Manually update status
        conn = sqlite3.connect(str(db))
        conn.execute("UPDATE tasks SET status='done', finished_at=? WHERE id=?",
                     (time.time(), tid1))
        conn.execute("UPDATE tasks SET status='failed', finished_at=? WHERE id=?",
                     (time.time(), tid2))
        conn.commit()
        conn.close()
        result = tq.list_recent()
        assert len(result) == 2
        # tempfile cleanup skipped (Windows file locking)


# ===========================================================================
# TaskQueue — get_stats
# ===========================================================================

class TestGetStats:
    def _make_queue(self):
        f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        db_path = Path(f.name)
        f.close()
        return TaskQueue(db_path=db_path), db_path

    def test_empty(self):
        tq, db = self._make_queue()
        stats = tq.get_stats()
        assert stats["total"] == 0
        assert stats["by_status"] == {}
        assert stats["processing"] is False
        # tempfile cleanup skipped (Windows file locking)

    def test_with_data(self):
        tq, db = self._make_queue()
        tq.enqueue("a")
        tq.enqueue("b")
        tid = tq.enqueue("c")
        tq.cancel(tid)
        stats = tq.get_stats()
        assert stats["total"] == 3
        assert stats["by_status"]["pending"] == 2
        assert stats["by_status"]["cancelled"] == 1
        # tempfile cleanup skipped (Windows file locking)


# ===========================================================================
# TaskQueue — cleanup
# ===========================================================================

class TestCleanup:
    def _make_queue(self):
        f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        db_path = Path(f.name)
        f.close()
        return TaskQueue(db_path=db_path), db_path

    def test_cleanup_old_tasks(self):
        tq, db = self._make_queue()
        import sqlite3
        old_time = time.time() - (10 * 86400)  # 10 days ago
        tq.enqueue("old task")
        conn = sqlite3.connect(str(db))
        conn.execute("UPDATE tasks SET status='done', finished_at=?", (old_time,))
        conn.commit()
        conn.close()
        removed = tq.cleanup(days=7)
        assert removed == 1
        # tempfile cleanup skipped (Windows file locking)

    def test_cleanup_keeps_recent(self):
        tq, db = self._make_queue()
        import sqlite3
        recent_time = time.time() - 3600  # 1 hour ago
        tq.enqueue("recent task")
        conn = sqlite3.connect(str(db))
        conn.execute("UPDATE tasks SET status='done', finished_at=?", (recent_time,))
        conn.commit()
        conn.close()
        removed = tq.cleanup(days=7)
        assert removed == 0
        # tempfile cleanup skipped (Windows file locking)

    def test_cleanup_ignores_pending(self):
        tq, db = self._make_queue()
        tq.enqueue("still pending")
        removed = tq.cleanup(days=0)
        assert removed == 0  # pending tasks not cleaned
        # tempfile cleanup skipped (Windows file locking)


# ===========================================================================
# TaskQueue — _get_best_node
# ===========================================================================

class TestGetBestNode:
    def _make_queue(self):
        f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        db_path = Path(f.name)
        f.close()
        return TaskQueue(db_path=db_path), db_path

    def test_fallback_to_m1(self):
        tq, db = self._make_queue()
        with patch.dict("sys.modules", {"src.orchestrator_v2": MagicMock()}):
            # Force import error
            with patch("src.task_queue.TaskQueue._get_best_node",
                       wraps=tq._get_best_node):
                node = tq._get_best_node("unknown_type")
        assert node == "M1"
        # tempfile cleanup skipped (Windows file locking)

    def test_exception_returns_m1(self):
        tq, db = self._make_queue()
        # _get_best_node catches all exceptions and returns M1
        with patch("builtins.__import__", side_effect=ImportError("no module")):
            node = tq._get_best_node("code")
        assert node == "M1"
        # tempfile cleanup skipped (Windows file locking)


# ===========================================================================
# TaskQueue — process_next
# ===========================================================================

class TestProcessNext:
    def _make_queue(self):
        f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        db_path = Path(f.name)
        f.close()
        return TaskQueue(db_path=db_path), db_path

    @pytest.mark.asyncio
    async def test_empty_queue(self):
        tq, db = self._make_queue()
        result = await tq.process_next()
        assert result is None
        # tempfile cleanup skipped (Windows file locking)

    @pytest.mark.asyncio
    async def test_success(self):
        tq, db = self._make_queue()
        tid = tq.enqueue("test task", task_type="code")
        with patch.object(tq, "_get_best_node", return_value="M1"), \
             patch.object(tq, "_execute_on_node", new_callable=AsyncMock,
                          return_value="result text"), \
             patch.object(tq, "_record_call"):
            result = await tq.process_next()
        assert result is not None
        assert result["status"] == "done"
        assert result["node"] == "M1"
        assert result["result"] == "result text"
        # tempfile cleanup skipped (Windows file locking)

    @pytest.mark.asyncio
    async def test_failure_retries(self):
        tq, db = self._make_queue()
        tid = tq.enqueue("fail task", max_retries=2)
        with patch.object(tq, "_get_best_node", return_value="M1"), \
             patch.object(tq, "_execute_on_node", new_callable=AsyncMock,
                          side_effect=Exception("node error")), \
             patch.object(tq, "_record_call"):
            result = await tq.process_next()
        assert result is not None
        assert result["status"] == "pending"  # retried
        assert result["retries"] == 1
        # tempfile cleanup skipped (Windows file locking)

    @pytest.mark.asyncio
    async def test_failure_exhausted_retries(self):
        tq, db = self._make_queue()
        tid = tq.enqueue("fail task", max_retries=0)
        with patch.object(tq, "_get_best_node", return_value="M1"), \
             patch.object(tq, "_execute_on_node", new_callable=AsyncMock,
                          side_effect=Exception("boom")), \
             patch.object(tq, "_record_call"):
            result = await tq.process_next()
        assert result["status"] == "failed"
        # tempfile cleanup skipped (Windows file locking)

    @pytest.mark.asyncio
    async def test_picks_highest_priority(self):
        tq, db = self._make_queue()
        tq.enqueue("low priority", priority=1)
        tq.enqueue("high priority", priority=10)
        with patch.object(tq, "_get_best_node", return_value="M1"), \
             patch.object(tq, "_execute_on_node", new_callable=AsyncMock,
                          return_value="done"), \
             patch.object(tq, "_record_call"):
            result = await tq.process_next()
        # Should pick the high priority task
        assert "high priority" in result["prompt"]
        # tempfile cleanup skipped (Windows file locking)


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert task_queue is not None
        assert isinstance(task_queue, TaskQueue)
