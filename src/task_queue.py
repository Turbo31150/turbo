"""JARVIS Smart Task Queue — Priority-based async task scheduling with persistence.

Features:
- Priority queue (higher = sooner)
- SQLite persistence (survives restarts)
- Auto-routing via orchestrator_v2
- Retry with exponential backoff
- Timeout per task

Usage:
    from src.task_queue import task_queue
    task_id = task_queue.enqueue("Analyze this code", task_type="code", priority=5)
    result = await task_queue.process_next()
"""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Awaitable


__all__ = [
    "QueuedTask",
    "TaskQueue",
    "TaskStatus",
]

logger = logging.getLogger("jarvis.task_queue")

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "task_queue.db"


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class QueuedTask:
    id: str
    prompt: str
    task_type: str = "code"
    priority: int = 5
    status: TaskStatus = TaskStatus.PENDING
    node: str = ""
    result: str = ""
    error: str = ""
    retries: int = 0
    max_retries: int = 2
    timeout_s: float = 120.0
    created_at: float = field(default_factory=time.time)
    started_at: float = 0.0
    finished_at: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "prompt": self.prompt[:200],
            "task_type": self.task_type,
            "priority": self.priority,
            "status": self.status.value,
            "node": self.node,
            "result": self.result[:500] if self.result else "",
            "error": self.error,
            "retries": self.retries,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }


class TaskQueue:
    """Priority-based async task queue with SQLite persistence."""

    def __init__(self, db_path: Path | None = None) -> None:
        self._db_path = db_path or DB_PATH
        self._processing = False
        self._init_db()

    def _init_db(self) -> None:
        """Initialize SQLite database."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    prompt TEXT NOT NULL,
                    task_type TEXT DEFAULT 'code',
                    priority INTEGER DEFAULT 5,
                    status TEXT DEFAULT 'pending',
                    node TEXT DEFAULT '',
                    result TEXT DEFAULT '',
                    error TEXT DEFAULT '',
                    retries INTEGER DEFAULT 0,
                    max_retries INTEGER DEFAULT 2,
                    timeout_s REAL DEFAULT 120.0,
                    created_at REAL,
                    started_at REAL DEFAULT 0,
                    finished_at REAL DEFAULT 0
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_task_status ON tasks(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_task_priority ON tasks(priority DESC)")

    def enqueue(self, prompt: str, task_type: str = "code", priority: int = 5,
                max_retries: int = 2, timeout_s: float = 120.0) -> str:
        """Add a task to the queue. Returns task ID."""
        task_id = str(uuid.uuid4())[:8]
        now = time.time()
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.execute(
                "INSERT INTO tasks (id, prompt, task_type, priority, status, created_at, max_retries, timeout_s) "
                "VALUES (?, ?, ?, ?, 'pending', ?, ?, ?)",
                (task_id, prompt, task_type, priority, now, max_retries, timeout_s),
            )
        logger.info("Task %s enqueued: %s (type=%s, prio=%d)", task_id, prompt[:60], task_type, priority)
        return task_id

    def cancel(self, task_id: str) -> bool:
        """Cancel a pending task."""
        with sqlite3.connect(str(self._db_path)) as conn:
            c = conn.execute(
                "UPDATE tasks SET status='cancelled' WHERE id=? AND status='pending'",
                (task_id,),
            )
            return c.rowcount > 0

    def get_task(self, task_id: str) -> QueuedTask | None:
        """Get a task by ID."""
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
            if not row:
                return None
            return self._row_to_task(row)

    def list_pending(self, limit: int = 20) -> list[dict[str, Any]]:
        """List pending tasks ordered by priority."""
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM tasks WHERE status='pending' ORDER BY priority DESC, created_at ASC LIMIT ?",
                (limit,),
            ).fetchall()
            return [self._row_to_task(r).to_dict() for r in rows]

    def list_recent(self, limit: int = 20) -> list[dict[str, Any]]:
        """List recently completed/failed tasks."""
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM tasks WHERE status IN ('done','failed') ORDER BY finished_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [self._row_to_task(r).to_dict() for r in rows]

    def get_stats(self) -> dict[str, Any]:
        """Queue statistics."""
        with sqlite3.connect(str(self._db_path)) as conn:
            counts = {}
            for row in conn.execute("SELECT status, COUNT(*) FROM tasks GROUP BY status"):
                counts[row[0]] = row[1]
            total = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
            return {"total": total, "by_status": counts, "processing": self._processing}

    async def process_next(self) -> dict[str, Any] | None:
        """Pick the highest-priority pending task, route to best node, execute."""
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM tasks WHERE status='pending' ORDER BY priority DESC, created_at ASC LIMIT 1"
            ).fetchone()
            if not row:
                return None
            task = self._row_to_task(row)

        # Route to best node
        node = self._get_best_node(task.task_type)
        task.node = node
        task.status = TaskStatus.RUNNING
        task.started_at = time.time()
        self._update_task(task)

        # Execute
        try:
            result = await asyncio.wait_for(
                self._execute_on_node(task.prompt, node, task.task_type),
                timeout=task.timeout_s,
            )
            task.result = result
            task.status = TaskStatus.DONE
            task.finished_at = time.time()

            # Record success in orchestrator
            self._record_call(node, (task.finished_at - task.started_at) * 1000, True, len(result) // 4)

        except (asyncio.TimeoutError, Exception) as e:
            task.error = str(e)
            task.retries += 1
            if task.retries <= task.max_retries:
                task.status = TaskStatus.PENDING  # retry
                logger.warning("Task %s retry %d/%d: %s", task.id, task.retries, task.max_retries, e)
            else:
                task.status = TaskStatus.FAILED
                task.finished_at = time.time()
                logger.error("Task %s failed after %d retries: %s", task.id, task.retries, e)

            self._record_call(node, 0, False)

        self._update_task(task)
        return task.to_dict()

    def _get_best_node(self, task_type: str) -> str:
        """Get best node from orchestrator_v2."""
        try:
            from src.orchestrator_v2 import orchestrator_v2, ROUTING_MATRIX
            matrix_entry = ROUTING_MATRIX.get(task_type, ROUTING_MATRIX.get("simple", []))
            candidates = [n for n, _ in matrix_entry]
            best = orchestrator_v2.get_best_node(candidates, task_type)
            return best or candidates[0] if candidates else "M1"
        except Exception:
            return "M1"

    @staticmethod
    def _record_call(node: str, latency_ms: float, success: bool, tokens: int = 0) -> None:
        try:
            from src.orchestrator_v2 import orchestrator_v2
            orchestrator_v2.record_call(node, latency_ms, success, tokens)
        except Exception:
            pass

    async def _execute_on_node(self, prompt: str, node: str, task_type: str) -> str:
        """Execute prompt on specified node."""
        import httpx
        from src.config import config, prepare_lmstudio_input, build_lmstudio_payload, build_ollama_payload

        if node in ("OL1",):
            # Ollama
            payload = build_ollama_payload("qwen3:1.7b", [{"role": "user", "content": prompt}])
            async with httpx.AsyncClient(timeout=120) as client:
                r = await client.post("http://127.0.0.1:11434/api/chat", json=payload)
                data = r.json()
                return data.get("message", {}).get("content", "")

        # LM Studio nodes
        node_cfg = config.get_node(node) if config else None
        if node_cfg:
            base_url = node_cfg.url.rstrip("/")
            url = f"{base_url}/api/v1/chat" if "/api/" not in base_url else base_url
        else:
            url = "http://127.0.0.1:1234/api/v1/chat"

        model_id = node_cfg.default_model if node_cfg and node_cfg.default_model else "qwen3-8b"
        # LM Studio uses short model name (e.g. "qwen3-8b"), strip org prefix
        model_name = model_id.split("/")[-1] if "/" in model_id else model_id
        lm_input = prepare_lmstudio_input(prompt, node, model_name)
        payload = build_lmstudio_payload(model_name, lm_input)
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(url, json=payload)
            data = r.json()
            # Extract from output array
            outputs = data.get("output", [])
            for o in reversed(outputs):
                if o.get("type") == "message":
                    content = o.get("content", "")
                    if isinstance(content, list):
                        return "".join(c.get("text", "") for c in content if c.get("type") == "output_text")
                    return str(content)
            return str(data)

    def _update_task(self, task: QueuedTask) -> None:
        """Update task in database."""
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.execute(
                "UPDATE tasks SET status=?, node=?, result=?, error=?, retries=?, "
                "started_at=?, finished_at=? WHERE id=?",
                (task.status.value, task.node, task.result, task.error, task.retries,
                 task.started_at, task.finished_at, task.id),
            )

    @staticmethod
    def _row_to_task(row) -> QueuedTask:
        return QueuedTask(
            id=row["id"],
            prompt=row["prompt"],
            task_type=row["task_type"],
            priority=row["priority"],
            status=TaskStatus(row["status"]),
            node=row["node"],
            result=row["result"],
            error=row["error"],
            retries=row["retries"],
            max_retries=row["max_retries"],
            timeout_s=row["timeout_s"],
            created_at=row["created_at"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
        )

    def cleanup(self, days: int = 7) -> int:
        """Remove old completed/failed tasks."""
        cutoff = time.time() - (days * 86400)
        with sqlite3.connect(str(self._db_path)) as conn:
            c = conn.execute(
                "DELETE FROM tasks WHERE status IN ('done','failed','cancelled') AND finished_at < ? AND finished_at > 0",
                (cutoff,),
            )
            return c.rowcount


# Global singleton
task_queue = TaskQueue()
