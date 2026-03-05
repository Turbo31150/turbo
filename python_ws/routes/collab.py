"""Collab REST routes — Claude Code <-> Perplexity task bridge.

Endpoints:
    POST   /collab/tasks          — Create a task
    GET    /collab/tasks          — List tasks (optional ?status=pending)
    GET    /collab/tasks/{id}     — Get one task
    POST   /collab/tasks/{id}/claim    — Claim (start working)
    POST   /collab/tasks/{id}/complete — Mark done with result
    POST   /collab/tasks/{id}/cancel   — Cancel
    GET    /collab/stats          — Queue stats
    GET    /collab/next           — Get next pending task for Perplexity
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

_turbo = str(Path(__file__).resolve().parent.parent.parent)
if _turbo not in sys.path:
    sys.path.insert(0, _turbo)

from src.collab_bridge import (
    create_task, get_pending_tasks, claim_task,
    complete_task, get_task, list_tasks, cancel_task, stats,
)

collab_router = APIRouter(prefix="/collab", tags=["collab"])


class TaskCreate(BaseModel):
    title: str
    description: str = ""
    category: str = "general"
    priority: str = "medium"
    assigned_to: str = "perplexity"
    created_by: str = "claude_code"
    actions: list[dict[str, Any]] | None = None
    expected_output: str = ""


class TaskComplete(BaseModel):
    result: str
    success: bool = True


@collab_router.post("/tasks")
async def api_create_task(body: TaskCreate):
    return create_task(**body.model_dump())


@collab_router.get("/tasks")
async def api_list_tasks(status: str | None = None, limit: int = 20):
    return list_tasks(status=status, limit=limit)


@collab_router.get("/tasks/{task_id}")
async def api_get_task(task_id: str):
    t = get_task(task_id)
    if not t:
        raise HTTPException(404, f"Task {task_id} not found")
    return t


@collab_router.get("/next")
async def api_next_task():
    pending = get_pending_tasks("perplexity")
    if not pending:
        return {"message": "No pending tasks", "task": None}
    return {"task": pending[0]}


@collab_router.post("/tasks/{task_id}/claim")
async def api_claim_task(task_id: str):
    t = claim_task(task_id)
    if not t:
        raise HTTPException(404, f"Task {task_id} not found or already claimed")
    return t


@collab_router.post("/tasks/{task_id}/complete")
async def api_complete_task(task_id: str, body: TaskComplete):
    t = complete_task(task_id, body.result, body.success)
    if not t:
        raise HTTPException(404, f"Task {task_id} not found")
    return t


@collab_router.post("/tasks/{task_id}/cancel")
async def api_cancel_task(task_id: str):
    t = cancel_task(task_id)
    if not t:
        raise HTTPException(404, f"Task {task_id} not found")
    return t


@collab_router.get("/stats")
async def api_stats():
    return stats()
