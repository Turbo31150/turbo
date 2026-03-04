"""Task Scheduler — Cron-like persistent job scheduling.

Supports recurring and one-shot jobs with configurable intervals.
Jobs are persisted in SQLite so they survive restarts.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Coroutine

logger = logging.getLogger("jarvis.task_scheduler")

JobFunc = Callable[[dict], Coroutine[Any, Any, Any]]


@dataclass
class ScheduledJob:
    job_id: str
    name: str
    interval_s: float
    action: str
    params: dict
    enabled: bool = True
    one_shot: bool = False
    last_run: float = 0.0
    run_count: int = 0
    last_result: str = ""
    last_error: str = ""


class TaskScheduler:
    """Persistent cron-like scheduler."""

    def __init__(self, db_path: Path | None = None):
        self._db_path = db_path or Path("data/scheduler.db")
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._handlers: dict[str, JobFunc] = {}
        self._running = False
        self._task: asyncio.Task | None = None

    def _init_db(self) -> None:
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                interval_s REAL NOT NULL,
                action TEXT NOT NULL,
                params TEXT DEFAULT '{}',
                enabled INTEGER DEFAULT 1,
                one_shot INTEGER DEFAULT 0,
                last_run REAL DEFAULT 0,
                run_count INTEGER DEFAULT 0,
                last_result TEXT DEFAULT '',
                last_error TEXT DEFAULT '',
                created_at REAL DEFAULT 0
            )""")

    # ── Job registration ─────────────────────────────────────────────────

    def register_handler(self, action: str, handler: JobFunc) -> None:
        """Register a callable for a given action type."""
        self._handlers[action] = handler

    def add_job(
        self,
        name: str,
        action: str,
        interval_s: float,
        params: dict | None = None,
        one_shot: bool = False,
        enabled: bool = True,
    ) -> str:
        """Create a new scheduled job. Returns job_id."""
        job_id = uuid.uuid4().hex[:12]
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.execute(
                "INSERT INTO jobs (job_id,name,action,interval_s,params,one_shot,enabled,created_at) VALUES (?,?,?,?,?,?,?,?)",
                (job_id, name, action, interval_s, json.dumps(params or {}), int(one_shot), int(enabled), time.time()),
            )
        return job_id

    def remove_job(self, job_id: str) -> bool:
        with sqlite3.connect(str(self._db_path)) as conn:
            cur = conn.execute("DELETE FROM jobs WHERE job_id=?", (job_id,))
            return cur.rowcount > 0

    def enable_job(self, job_id: str, enabled: bool = True) -> bool:
        with sqlite3.connect(str(self._db_path)) as conn:
            cur = conn.execute("UPDATE jobs SET enabled=? WHERE job_id=?", (int(enabled), job_id))
            return cur.rowcount > 0

    def list_jobs(self) -> list[dict]:
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM jobs ORDER BY created_at DESC").fetchall()
            return [dict(r) for r in rows]

    def get_job(self, job_id: str) -> dict | None:
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
            return dict(row) if row else None

    # ── Execution ────────────────────────────────────────────────────────

    def _get_due_jobs(self) -> list[ScheduledJob]:
        now = time.time()
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM jobs WHERE enabled=1").fetchall()
            due = []
            for r in rows:
                if now - r["last_run"] >= r["interval_s"]:
                    due.append(ScheduledJob(
                        job_id=r["job_id"], name=r["name"],
                        interval_s=r["interval_s"], action=r["action"],
                        params=json.loads(r["params"]),
                        enabled=bool(r["enabled"]), one_shot=bool(r["one_shot"]),
                        last_run=r["last_run"], run_count=r["run_count"],
                    ))
            return due

    async def run_job(self, job: ScheduledJob) -> str:
        """Execute a single job. Returns result string."""
        handler = self._handlers.get(job.action)
        if not handler:
            err = f"No handler for action '{job.action}'"
            self._update_job_result(job.job_id, error=err)
            return err
        try:
            result = await handler(job.params)
            result_str = str(result) if result else "ok"
            self._update_job_result(job.job_id, result=result_str)
            if job.one_shot:
                self.enable_job(job.job_id, False)
            return result_str
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
            logger.warning("Job %s (%s) failed: %s", job.job_id, job.name, err)
            self._update_job_result(job.job_id, error=err)
            return err

    def _update_job_result(self, job_id: str, result: str = "", error: str = "") -> None:
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.execute(
                "UPDATE jobs SET last_run=?, run_count=run_count+1, last_result=?, last_error=? WHERE job_id=?",
                (time.time(), result, error, job_id),
            )

    async def tick(self) -> int:
        """Check for due jobs and execute them. Returns count executed."""
        due = self._get_due_jobs()
        for job in due:
            await self.run_job(job)
        return len(due)

    # ── Loop control ─────────────────────────────────────────────────────

    async def start(self, check_interval: float = 5.0) -> None:
        """Start the scheduler loop."""
        if self._running:
            return
        self._running = True

        async def _loop():
            while self._running:
                try:
                    await self.tick()
                except Exception as e:
                    logger.error("Scheduler tick error: %s", e)
                await asyncio.sleep(check_interval)

        self._task = asyncio.create_task(_loop())

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    @property
    def running(self) -> bool:
        return self._running

    def get_stats(self) -> dict:
        jobs = self.list_jobs()
        enabled = [j for j in jobs if j.get("enabled")]
        return {
            "total_jobs": len(jobs),
            "enabled_jobs": len(enabled),
            "registered_handlers": list(self._handlers.keys()),
            "running": self._running,
        }


# ── Singleton ────────────────────────────────────────────────────────────────
task_scheduler = TaskScheduler()
