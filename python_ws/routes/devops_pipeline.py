"""DevOps Pipeline REST API — connects Electron UI to pipeline_engine.py.

Endpoints:
    GET  /devops/pipelines          — List all pipelines
    GET  /devops/pipelines/{id}     — Pipeline details + sections
    POST /devops/pipelines/run      — Launch a new pipeline
    POST /devops/pipelines/{id}/resume — Resume incomplete pipeline
    GET  /devops/cache              — Cache statistics
    GET  /devops/templates          — List reusable templates
    GET  /devops/status             — Engine health summary
"""

from __future__ import annotations

import asyncio
import logging
import sqlite3
import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger("jarvis.devops_pipeline")

_turbo_root = Path(__file__).resolve().parent.parent.parent
_scripts_dir = _turbo_root / "scripts"
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))

DB_PATH = _turbo_root / "data" / "pipeline.db"

devops_pipeline_router = APIRouter(tags=["devops-pipeline"])


# ── Helpers ──────────────────────────────────────────────────────────────

def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _ensure_db():
    """Create tables if they don't exist (idempotent)."""
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS pipeline_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prompt_hash TEXT UNIQUE,
            prompt TEXT,
            response TEXT,
            provider TEXT,
            category TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            hits INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS pipelines (
            id TEXT PRIMARY KEY,
            name TEXT,
            original_prompt TEXT,
            status TEXT DEFAULT 'pending',
            total_sections INTEGER DEFAULT 0,
            completed_sections INTEGER DEFAULT 0,
            result TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS pipeline_sections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pipeline_id TEXT REFERENCES pipelines(id),
            section_idx INTEGER,
            section_type TEXT,
            prompt TEXT,
            response TEXT,
            provider TEXT,
            status TEXT DEFAULT 'pending',
            latency_ms REAL DEFAULT 0,
            from_cache INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS pipeline_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            pattern TEXT,
            section_types TEXT,
            description TEXT,
            usage_count INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        );
    """)
    conn.close()


_ensure_db()


# ── Models ───────────────────────────────────────────────────────────────

class PipelineRunRequest(BaseModel):
    prompt: str
    name: str = ""
    circulate_passes: int = 2


class PipelineResumeRequest(BaseModel):
    pass  # no body needed, ID is in path


# ── Background execution tracker ─────────────────────────────────────────

_running_pipelines: dict[str, dict] = {}  # id -> {"status": ..., "progress": ...}


async def _run_pipeline_bg(prompt: str, name: str, passes: int):
    """Run pipeline in background thread."""
    try:
        from pipeline_engine import (
            _init_db, decompose_task,
            execute_pipeline, save_as_template, send_telegram,
            Pipeline, _find_similar_pipeline,
        )

        def _execute():
            conn = _init_db()

            # Check for similar existing pipeline
            similar = _find_similar_pipeline(conn, prompt)
            if similar and similar.result:
                conn.close()
                return {"reused": True, "pipeline_id": similar.id, "result": similar.result[:3000]}

            # Decompose
            p_name = name or prompt[:40].replace(" ", "-")
            sections = decompose_task(prompt, conn)

            pipeline = Pipeline(
                name=p_name,
                original_prompt=prompt,
                sections=sections,
            )

            _running_pipelines[pipeline.id] = {"status": "running", "progress": 0}

            pipeline = execute_pipeline(pipeline, conn)
            save_as_template(conn, pipeline)

            # Send result to Telegram
            if pipeline.result:
                try:
                    send_telegram(f"Pipeline '{p_name}' termine:\n{pipeline.result[:500]}")
                except Exception:
                    pass

            conn.close()
            return {
                "pipeline_id": pipeline.id,
                "status": pipeline.status,
                "sections_ok": sum(1 for s in pipeline.sections if s.status in ("completed", "cached")),
                "total": len(pipeline.sections),
                "result": (pipeline.result or "")[:3000],
            }

        result = await asyncio.to_thread(_execute)
        pid = result.get("pipeline_id", "")
        if pid in _running_pipelines:
            _running_pipelines[pid]["status"] = result.get("status", "completed")
        return result

    except Exception as exc:
        logger.exception("Pipeline execution failed")
        return {"error": str(exc)}


# ── Endpoints ────────────────────────────────────────────────────────────

@devops_pipeline_router.get("/devops/pipelines")
async def api_devops_list_pipelines(limit: int = 50):
    """List all pipelines from pipeline.db."""
    conn = _get_conn()
    try:
        rows = conn.execute("""
            SELECT id, name, original_prompt, status, total_sections,
                   completed_sections, created_at, updated_at
            FROM pipelines ORDER BY created_at DESC LIMIT ?
        """, (limit,)).fetchall()

        pipelines = []
        for r in rows:
            pipelines.append({
                "id": r["id"],
                "name": r["name"],
                "prompt": (r["original_prompt"] or "")[:200],
                "status": r["status"],
                "total": r["total_sections"],
                "completed": r["completed_sections"],
                "created": r["created_at"],
                "updated": r["updated_at"],
            })

        # Add running pipelines not yet in DB
        for pid, info in _running_pipelines.items():
            if not any(p["id"] == pid for p in pipelines):
                pipelines.insert(0, {
                    "id": pid, "name": "Running...", "prompt": "",
                    "status": info["status"], "total": 0, "completed": 0,
                    "created": "", "updated": "",
                })

        return {"pipelines": pipelines, "total": len(pipelines)}
    finally:
        conn.close()


@devops_pipeline_router.get("/devops/pipelines/{pipeline_id}")
async def api_devops_pipeline_detail(pipeline_id: str):
    """Get pipeline details with all sections."""
    conn = _get_conn()
    try:
        row = conn.execute("SELECT * FROM pipelines WHERE id = ?", (pipeline_id,)).fetchone()
        if not row:
            raise HTTPException(404, f"Pipeline {pipeline_id} not found")

        sections = conn.execute("""
            SELECT section_idx, section_type, prompt, response, provider,
                   status, latency_ms, from_cache, created_at
            FROM pipeline_sections
            WHERE pipeline_id = ? ORDER BY section_idx
        """, (pipeline_id,)).fetchall()

        return {
            "id": row["id"],
            "name": row["name"],
            "prompt": row["original_prompt"],
            "status": row["status"],
            "total": row["total_sections"],
            "completed": row["completed_sections"],
            "result": row["result"],
            "created": row["created_at"],
            "updated": row["updated_at"],
            "sections": [{
                "idx": s["section_idx"],
                "type": s["section_type"],
                "prompt": s["prompt"],
                "response": s["response"],
                "provider": s["provider"],
                "status": s["status"],
                "latency_ms": round(s["latency_ms"] or 0),
                "cached": bool(s["from_cache"]),
                "created": s["created_at"],
            } for s in sections],
        }
    finally:
        conn.close()


@devops_pipeline_router.post("/devops/pipelines/run")
async def api_devops_run_pipeline(req: PipelineRunRequest):
    """Launch a new DevOps pipeline (runs in background)."""
    if not req.prompt.strip():
        raise HTTPException(400, "prompt required")

    # Fire-and-forget in background
    task = asyncio.create_task(_run_pipeline_bg(req.prompt, req.name, req.circulate_passes))

    return {"ok": True, "message": "Pipeline started", "prompt": req.prompt[:100]}


@devops_pipeline_router.post("/devops/pipelines/{pipeline_id}/resume")
async def api_devops_resume_pipeline(pipeline_id: str):
    """Resume an incomplete/failed pipeline."""
    conn = _get_conn()
    try:
        row = conn.execute("SELECT id, status FROM pipelines WHERE id = ?", (pipeline_id,)).fetchone()
        if not row:
            raise HTTPException(404, f"Pipeline {pipeline_id} not found")
        if row["status"] == "completed":
            return {"ok": True, "message": "Pipeline already completed", "id": pipeline_id}
    finally:
        conn.close()

    async def _resume():
        try:
            from pipeline_engine import resume_pipeline as pe_resume, _init_db
            def _do():
                c = _init_db()
                result = pe_resume(c, pipeline_id)
                c.close()
                return result
            return await asyncio.to_thread(_do)
        except Exception as exc:
            logger.exception("Resume failed")

    asyncio.create_task(_resume())
    return {"ok": True, "message": f"Resuming pipeline {pipeline_id}"}


@devops_pipeline_router.get("/devops/cache")
async def api_devops_cache_stats():
    """Cache statistics from pipeline.db."""
    conn = _get_conn()
    try:
        total = conn.execute("SELECT COUNT(*) as c FROM pipeline_cache").fetchone()["c"]
        hits = conn.execute("SELECT COALESCE(SUM(hits), 0) as h FROM pipeline_cache").fetchone()["h"]
        top_cats = conn.execute(
            "SELECT category, COUNT(*) as c FROM pipeline_cache GROUP BY category ORDER BY c DESC LIMIT 10"
        ).fetchall()
        recent = conn.execute(
            "SELECT prompt, provider, category, hits, created_at FROM pipeline_cache ORDER BY created_at DESC LIMIT 10"
        ).fetchall()

        return {
            "total_entries": total,
            "total_hits": hits,
            "top_categories": {r["category"]: r["c"] for r in top_cats},
            "recent": [{
                "prompt": (r["prompt"] or "")[:100],
                "provider": r["provider"],
                "category": r["category"],
                "hits": r["hits"],
                "created": r["created_at"],
            } for r in recent],
        }
    finally:
        conn.close()


@devops_pipeline_router.get("/devops/templates")
async def api_devops_templates():
    """List reusable pipeline templates."""
    conn = _get_conn()
    try:
        rows = conn.execute("""
            SELECT name, pattern, section_types, description, usage_count, created_at
            FROM pipeline_templates ORDER BY usage_count DESC LIMIT 30
        """).fetchall()
        return {"templates": [{
            "name": r["name"],
            "pattern": (r["pattern"] or "")[:150],
            "section_types": r["section_types"],
            "description": r["description"],
            "usage_count": r["usage_count"],
            "created": r["created_at"],
        } for r in rows]}
    finally:
        conn.close()


@devops_pipeline_router.get("/devops/status")
async def api_devops_status():
    """Overall pipeline engine health."""
    conn = _get_conn()
    try:
        total = conn.execute("SELECT COUNT(*) as c FROM pipelines").fetchone()["c"]
        completed = conn.execute("SELECT COUNT(*) as c FROM pipelines WHERE status='completed'").fetchone()["c"]
        running = conn.execute("SELECT COUNT(*) as c FROM pipelines WHERE status='running'").fetchone()["c"]
        failed = conn.execute("SELECT COUNT(*) as c FROM pipelines WHERE status='failed'").fetchone()["c"]
        cache_entries = conn.execute("SELECT COUNT(*) as c FROM pipeline_cache").fetchone()["c"]
        templates = conn.execute("SELECT COUNT(*) as c FROM pipeline_templates").fetchone()["c"]
        sections_ok = conn.execute(
            "SELECT COUNT(*) as c FROM pipeline_sections WHERE status IN ('completed','cached')"
        ).fetchone()["c"]
        sections_total = conn.execute("SELECT COUNT(*) as c FROM pipeline_sections").fetchone()["c"]

        return {
            "pipelines": {"total": total, "completed": completed, "running": running + len(_running_pipelines), "failed": failed},
            "sections": {"completed": sections_ok, "total": sections_total},
            "cache": {"entries": cache_entries},
            "templates": {"count": templates},
        }
    finally:
        conn.close()


@devops_pipeline_router.delete("/devops/pipelines/{pipeline_id}")
async def api_devops_delete_pipeline(pipeline_id: str):
    """Delete a pipeline and its sections."""
    conn = _get_conn()
    try:
        conn.execute("DELETE FROM pipeline_sections WHERE pipeline_id = ?", (pipeline_id,))
        conn.execute("DELETE FROM pipelines WHERE id = ?", (pipeline_id,))
        conn.commit()
        return {"ok": True, "deleted": pipeline_id}
    finally:
        conn.close()
