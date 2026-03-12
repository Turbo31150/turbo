"""Tests for src/queue_manager.py — Priority task queue.

Covers: QueueTask, QueueManager (register_handler, enqueue, process_next,
get_task, list_tasks, cancel, get_stats), queue_manager singleton.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.queue_manager import QueueTask, QueueManager, queue_manager


# ===========================================================================
# QueueTask
# ===========================================================================

class TestQueueTask:
    def test_defaults(self):
        t = QueueTask(task_id="abc", name="test")
        assert t.priority == 5
        assert t.status == "pending"
        assert t.max_retries == 2

    def test_ordering(self):
        a = QueueTask(task_id="a", name="a", priority=1)
        b = QueueTask(task_id="b", name="b", priority=5)
        assert a < b


# ===========================================================================
# QueueManager — enqueue & process
# ===========================================================================

class TestEnqueueProcess:
    def test_enqueue(self):
        qm = QueueManager()
        task = qm.enqueue("build", priority=3)
        assert task.status == "pending"
        assert task.name == "build"

    def test_process_with_handler(self):
        qm = QueueManager()
        qm.register_handler("build", lambda meta: "built!")
        qm.enqueue("build")
        result = qm.process_next()
        assert result is not None
        assert result.status == "completed"
        assert result.result == "built!"

    def test_process_no_handler(self):
        qm = QueueManager()
        qm.enqueue("unknown_task")
        result = qm.process_next()
        assert result is not None
        assert result.status == "failed"
        assert "No handler" in result.error

    def test_process_empty_queue(self):
        qm = QueueManager()
        assert qm.process_next() is None

    def test_priority_ordering(self):
        qm = QueueManager()
        results = []
        qm.register_handler("task", lambda meta: results.append(meta.get("id")))
        qm.enqueue("task", priority=5, metadata={"id": "low"})
        qm.enqueue("task", priority=1, metadata={"id": "high"})
        qm.process_next()
        qm.process_next()
        assert results == ["high", "low"]

    def test_handler_exception_retries(self):
        qm = QueueManager()
        counter = {"n": 0}
        def flaky(meta):
            counter["n"] += 1
            if counter["n"] < 3:
                raise ValueError("fail")
            return "ok"
        qm.register_handler("flaky", flaky)
        qm.enqueue("flaky", max_retries=3)
        # First attempt: fails, retries=1
        r1 = qm.process_next()
        assert r1.status == "pending"  # re-enqueued
        # Second attempt: fails, retries=2
        r2 = qm.process_next()
        assert r2.status == "pending"
        # Third attempt: succeeds
        r3 = qm.process_next()
        assert r3.status == "completed"

    def test_max_concurrent(self):
        qm = QueueManager(max_concurrent=1)
        qm.register_handler("task", lambda m: "ok")
        qm.enqueue("task")
        qm.enqueue("task")
        # Simulate running count at max
        qm._running_count = 1
        assert qm.process_next() is None


# ===========================================================================
# QueueManager — get_task & list_tasks
# ===========================================================================

class TestGetList:
    def test_get_task(self):
        qm = QueueManager()
        task = qm.enqueue("test")
        result = qm.get_task(task.task_id)
        assert result is not None
        assert result["name"] == "test"

    def test_get_nonexistent(self):
        qm = QueueManager()
        assert qm.get_task("nope") is None

    def test_list_tasks(self):
        qm = QueueManager()
        qm.enqueue("a")
        qm.enqueue("b")
        tasks = qm.list_tasks()
        assert len(tasks) == 2

    def test_list_tasks_filter(self):
        qm = QueueManager()
        qm.register_handler("ok", lambda m: "done")
        qm.enqueue("ok")
        qm.enqueue("ok")
        qm.process_next()
        completed = qm.list_tasks(status="completed")
        pending = qm.list_tasks(status="pending")
        assert len(completed) == 1
        assert len(pending) == 1


# ===========================================================================
# QueueManager — cancel
# ===========================================================================

class TestCancel:
    def test_cancel_pending(self):
        qm = QueueManager()
        task = qm.enqueue("test")
        assert qm.cancel(task.task_id) is True
        assert qm.get_task(task.task_id)["status"] == "failed"

    def test_cancel_nonexistent(self):
        qm = QueueManager()
        assert qm.cancel("nope") is False


# ===========================================================================
# QueueManager — stats
# ===========================================================================

class TestStats:
    def test_stats_empty(self):
        qm = QueueManager()
        stats = qm.get_stats()
        assert stats["total_tasks"] == 0
        assert stats["pending"] == 0

    def test_stats(self):
        qm = QueueManager()
        qm.register_handler("x", lambda m: "ok")
        qm.enqueue("x")
        qm.enqueue("x")
        qm.process_next()
        stats = qm.get_stats()
        assert stats["total_tasks"] == 2
        assert stats["completed"] == 1
        assert stats["pending"] == 1


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert queue_manager is not None
        assert isinstance(queue_manager, QueueManager)
