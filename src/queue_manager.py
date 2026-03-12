"""Queue Manager — Async task queue with priority.

Priority-based task queue for long-running operations.
Supports workers, status tracking, and retry on failure.
Thread-safe.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field, asdict
from heapq import heappush, heappop
from typing import Any, Callable

logger = logging.getLogger("jarvis.queue_manager")


@dataclass
class QueueTask:
    task_id: str
    name: str
    priority: int = 5  # 1=highest, 10=lowest
    status: str = "pending"  # pending, running, completed, failed
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    completed_at: float | None = None
    result: Any = None
    error: str | None = None
    retries: int = 0
    max_retries: int = 2
    metadata: dict = field(default_factory=dict)

    def __lt__(self, other):
        return self.priority < other.priority


class QueueManager:
    """Priority task queue manager."""

    def __init__(self, max_concurrent: int = 3):
        self._queue: list[tuple[int, float, QueueTask]] = []  # heap: (priority, ts, task)
        self._tasks: dict[str, QueueTask] = {}
        self._handlers: dict[str, Callable] = {}
        self._lock = threading.Lock()
        self._max_concurrent = max_concurrent
        self._running_count = 0

    def register_handler(self, name: str, handler: Callable) -> None:
        """Register a handler function for a task name."""
        self._handlers[name] = handler

    def enqueue(
        self,
        name: str,
        priority: int = 5,
        metadata: dict | None = None,
        max_retries: int = 2,
    ) -> QueueTask:
        with self._lock:
            tid = str(uuid.uuid4())[:10]
            task = QueueTask(
                task_id=tid, name=name, priority=priority,
                metadata=metadata or {}, max_retries=max_retries,
            )
            self._tasks[tid] = task
            heappush(self._queue, (priority, task.created_at, task))
            return task

    def process_next(self) -> QueueTask | None:
        """Process the next task in queue. Returns the task or None."""
        with self._lock:
            if self._running_count >= self._max_concurrent:
                return None
            # Find next pending task
            task = None
            temp = []
            while self._queue:
                item = heappop(self._queue)
                t = item[2]
                if t.status == "pending":
                    task = t
                    break
                temp.append(item)
            for item in temp:
                heappush(self._queue, item)

            if not task:
                return None

            task.status = "running"
            task.started_at = time.time()
            self._running_count += 1

        # Execute outside lock
        handler = self._handlers.get(task.name)
        if handler:
            try:
                result = handler(task.metadata)
                with self._lock:
                    task.status = "completed"
                    task.result = result
                    task.completed_at = time.time()
                    self._running_count -= 1
            except Exception as e:
                with self._lock:
                    task.retries += 1
                    self._running_count -= 1
                    if task.retries >= task.max_retries:
                        task.status = "failed"
                        task.error = str(e)
                        task.completed_at = time.time()
                    else:
                        task.status = "pending"
                        task.started_at = None
                        heappush(self._queue, (task.priority, task.created_at, task))
        else:
            with self._lock:
                task.status = "failed"
                task.error = f"No handler for '{task.name}'"
                task.completed_at = time.time()
                self._running_count -= 1

        return task

    def get_task(self, task_id: str) -> dict | None:
        task = self._tasks.get(task_id)
        return asdict(task) if task else None

    def list_tasks(self, status: str | None = None) -> list[dict]:
        tasks = list(self._tasks.values())
        if status:
            tasks = [t for t in tasks if t.status == status]
        return [asdict(t) for t in tasks]

    def cancel(self, task_id: str) -> bool:
        with self._lock:
            task = self._tasks.get(task_id)
            if task and task.status == "pending":
                task.status = "failed"
                task.error = "cancelled"
                return True
            return False

    def get_stats(self) -> dict:
        tasks = list(self._tasks.values())
        return {
            "total_tasks": len(tasks),
            "pending": sum(1 for t in tasks if t.status == "pending"),
            "running": sum(1 for t in tasks if t.status == "running"),
            "completed": sum(1 for t in tasks if t.status == "completed"),
            "failed": sum(1 for t in tasks if t.status == "failed"),
            "queue_size": len(self._queue),
            "max_concurrent": self._max_concurrent,
            "handlers": list(self._handlers.keys()),
        }


# ── Singleton ────────────────────────────────────────────────────────────────
queue_manager = QueueManager()
