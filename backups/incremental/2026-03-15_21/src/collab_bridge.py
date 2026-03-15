"""JARVIS Collab Bridge — Task queue for Claude Code <-> Perplexity collaboration.

SQLite-backed task queue in jarvis.db (table: collab_tasks).
Both AIs interact via REST endpoints or direct function calls.

Flow:
  1. Claude Code creates a task (create_task)
  2. Perplexity picks it up (get_pending_tasks / claim_task)
  3. Perplexity executes and reports result (complete_task)
  4. Claude Code reads the result (get_task)
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any


__all__ = [
    "cancel_task",
    "claim_task",
    "complete_task",
    "create_task",
    "get_pending_tasks",
    "get_task",
    "list_tasks",
    "stats",
]

_DB = Path(__file__).resolve().parent.parent / "data" / "jarvis.db"


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(str(_DB))
    c.row_factory = sqlite3.Row
    return c


def _gen_id() -> str:
    t = time.strftime("%Y%m%d_%H%M%S")
    return f"task_{t}"


def create_task(
    title: str,
    description: str = "",
    category: str = "general",
    priority: str = "medium",
    assigned_to: str = "perplexity",
    created_by: str = "claude_code",
    actions: list[dict] | None = None,
    expected_output: str = "",
    task_id: str | None = None,
) -> dict[str, Any]:
    """Create a new collaboration task."""
    tid = task_id or _gen_id()
    with _conn() as conn:
        conn.execute(
            """INSERT INTO collab_tasks
               (task_id, title, description, category, priority, status,
                assigned_to, created_by, actions, expected_output, created_at)
               VALUES (?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?)""",
            (
                tid, title, description, category, priority,
                assigned_to, created_by,
                json.dumps(actions or [], ensure_ascii=False),
                expected_output, time.time(),
            ),
        )
    return {"task_id": tid, "status": "pending", "title": title}


def get_pending_tasks(assigned_to: str = "perplexity") -> list[dict]:
    """Get all pending tasks for a given assignee."""
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM collab_tasks WHERE status='pending' AND assigned_to=? ORDER BY id",
            (assigned_to,),
        ).fetchall()
    return [dict(r) for r in rows]


def claim_task(task_id: str, worker: str = "perplexity") -> dict | None:
    """Mark a task as in_progress."""
    with _conn() as conn:
        conn.execute(
            "UPDATE collab_tasks SET status='in_progress', started_at=? WHERE task_id=? AND status='pending'",
            (time.time(), task_id),
        )
        row = conn.execute("SELECT * FROM collab_tasks WHERE task_id=?", (task_id,)).fetchone()
    return dict(row) if row else None


def complete_task(task_id: str, result: str, success: bool = True) -> dict | None:
    """Mark a task as completed with result."""
    status = "completed" if success else "failed"
    with _conn() as conn:
        conn.execute(
            "UPDATE collab_tasks SET status=?, result=?, completed_at=? WHERE task_id=?",
            (status, result, time.time(), task_id),
        )
        row = conn.execute("SELECT * FROM collab_tasks WHERE task_id=?", (task_id,)).fetchone()
    return dict(row) if row else None


def get_task(task_id: str) -> dict | None:
    """Get a task by ID."""
    with _conn() as conn:
        row = conn.execute("SELECT * FROM collab_tasks WHERE task_id=?", (task_id,)).fetchone()
    return dict(row) if row else None


def list_tasks(status: str | None = None, limit: int = 20) -> list[dict]:
    """List tasks, optionally filtered by status."""
    q = "SELECT * FROM collab_tasks"
    params: list = []
    if status:
        q += " WHERE status=?"
        params.append(status)
    q += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    with _conn() as conn:
        rows = conn.execute(q, params).fetchall()
    return [dict(r) for r in rows]


def cancel_task(task_id: str) -> dict | None:
    """Cancel a pending task."""
    with _conn() as conn:
        conn.execute(
            "UPDATE collab_tasks SET status='cancelled', completed_at=? WHERE task_id=? AND status IN ('pending','in_progress')",
            (time.time(), task_id),
        )
        row = conn.execute("SELECT * FROM collab_tasks WHERE task_id=?", (task_id,)).fetchone()
    return dict(row) if row else None


def stats() -> dict:
    """Get task queue statistics."""
    with _conn() as conn:
        rows = conn.execute(
            "SELECT status, COUNT(*) as cnt FROM collab_tasks GROUP BY status"
        ).fetchall()
    return {r["status"]: r["cnt"] for r in rows}
