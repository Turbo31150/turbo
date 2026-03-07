"""Tests for src/task_scheduler.py — Cron-like persistent job scheduling.

Covers: ScheduledJob, TaskScheduler (register_handler, add_job, remove_job,
enable_job, list_jobs, get_job, _get_due_jobs, run_job, tick, start, stop,
get_stats), task_scheduler singleton.
Uses tmp_path SQLite DB for isolation. Async tests for run_job/tick/start/stop.
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.task_scheduler import ScheduledJob, TaskScheduler, task_scheduler


# ===========================================================================
# Dataclass
# ===========================================================================

class TestScheduledJob:
    def test_defaults(self):
        j = ScheduledJob(job_id="j1", name="test", interval_s=60,
                         action="check", params={})
        assert j.enabled is True
        assert j.one_shot is False
        assert j.last_run == 0.0
        assert j.run_count == 0
        assert j.last_result == ""
        assert j.last_error == ""


# ===========================================================================
# TaskScheduler — job CRUD
# ===========================================================================

class TestJobCrud:
    def test_add_job(self, tmp_path):
        ts = TaskScheduler(db_path=tmp_path / "sched.db")
        job_id = ts.add_job("health", "health_check", interval_s=300)
        assert len(job_id) == 12
        jobs = ts.list_jobs()
        assert len(jobs) == 1
        assert jobs[0]["name"] == "health"

    def test_add_job_with_params(self, tmp_path):
        ts = TaskScheduler(db_path=tmp_path / "sched.db")
        job_id = ts.add_job("task", "run", interval_s=60, params={"key": "val"})
        job = ts.get_job(job_id)
        assert '"key"' in job["params"]

    def test_add_one_shot(self, tmp_path):
        ts = TaskScheduler(db_path=tmp_path / "sched.db")
        job_id = ts.add_job("once", "action", interval_s=0, one_shot=True)
        job = ts.get_job(job_id)
        assert job["one_shot"] == 1

    def test_remove_job(self, tmp_path):
        ts = TaskScheduler(db_path=tmp_path / "sched.db")
        job_id = ts.add_job("temp", "action", interval_s=60)
        assert ts.remove_job(job_id) is True
        assert ts.remove_job(job_id) is False

    def test_enable_disable_job(self, tmp_path):
        ts = TaskScheduler(db_path=tmp_path / "sched.db")
        job_id = ts.add_job("test", "action", interval_s=60)
        assert ts.enable_job(job_id, False) is True
        job = ts.get_job(job_id)
        assert job["enabled"] == 0
        assert ts.enable_job(job_id, True) is True

    def test_enable_nonexistent(self, tmp_path):
        ts = TaskScheduler(db_path=tmp_path / "sched.db")
        assert ts.enable_job("nope") is False

    def test_get_job(self, tmp_path):
        ts = TaskScheduler(db_path=tmp_path / "sched.db")
        job_id = ts.add_job("test", "action", interval_s=60)
        job = ts.get_job(job_id)
        assert job is not None
        assert job["name"] == "test"

    def test_get_job_nonexistent(self, tmp_path):
        ts = TaskScheduler(db_path=tmp_path / "sched.db")
        assert ts.get_job("nope") is None

    def test_list_jobs_empty(self, tmp_path):
        ts = TaskScheduler(db_path=tmp_path / "sched.db")
        assert ts.list_jobs() == []

    def test_list_jobs_multiple(self, tmp_path):
        ts = TaskScheduler(db_path=tmp_path / "sched.db")
        ts.add_job("a", "action", interval_s=60)
        ts.add_job("b", "action", interval_s=120)
        assert len(ts.list_jobs()) == 2


# ===========================================================================
# TaskScheduler — handler registration
# ===========================================================================

class TestHandlers:
    def test_register_handler(self, tmp_path):
        ts = TaskScheduler(db_path=tmp_path / "sched.db")
        handler = AsyncMock(return_value="done")
        ts.register_handler("check", handler)
        assert "check" in ts._handlers


# ===========================================================================
# TaskScheduler — due jobs
# ===========================================================================

class TestDueJobs:
    def test_get_due_jobs(self, tmp_path):
        ts = TaskScheduler(db_path=tmp_path / "sched.db")
        # Job with interval 0 and last_run 0 should be immediately due
        ts.add_job("due", "action", interval_s=0)
        due = ts._get_due_jobs()
        assert len(due) == 1
        assert due[0].name == "due"

    def test_not_due_yet(self, tmp_path):
        ts = TaskScheduler(db_path=tmp_path / "sched.db")
        job_id = ts.add_job("future", "action", interval_s=9999)
        # Set last_run to now
        import sqlite3
        with sqlite3.connect(str(tmp_path / "sched.db")) as conn:
            conn.execute("UPDATE jobs SET last_run=? WHERE job_id=?", (time.time(), job_id))
        due = ts._get_due_jobs()
        assert len(due) == 0

    def test_disabled_not_due(self, tmp_path):
        ts = TaskScheduler(db_path=tmp_path / "sched.db")
        ts.add_job("disabled", "action", interval_s=0, enabled=False)
        due = ts._get_due_jobs()
        assert len(due) == 0


# ===========================================================================
# TaskScheduler — run_job (async)
# ===========================================================================

class TestRunJob:
    @pytest.mark.asyncio
    async def test_run_job_success(self, tmp_path):
        ts = TaskScheduler(db_path=tmp_path / "sched.db")
        handler = AsyncMock(return_value="result_ok")
        ts.register_handler("check", handler)
        job_id = ts.add_job("test", "check", interval_s=60, params={"x": 1})
        due = ts._get_due_jobs()
        result = await ts.run_job(due[0])
        assert result == "result_ok"
        handler.assert_called_once_with({"x": 1})
        # Check DB updated
        job = ts.get_job(job_id)
        assert job["run_count"] == 1
        assert job["last_result"] == "result_ok"

    @pytest.mark.asyncio
    async def test_run_job_no_handler(self, tmp_path):
        ts = TaskScheduler(db_path=tmp_path / "sched.db")
        job_id = ts.add_job("test", "unknown_action", interval_s=60)
        due = ts._get_due_jobs()
        result = await ts.run_job(due[0])
        assert "No handler" in result

    @pytest.mark.asyncio
    async def test_run_job_handler_exception(self, tmp_path):
        ts = TaskScheduler(db_path=tmp_path / "sched.db")
        handler = AsyncMock(side_effect=ValueError("boom"))
        ts.register_handler("fail", handler)
        job_id = ts.add_job("test", "fail", interval_s=60)
        due = ts._get_due_jobs()
        result = await ts.run_job(due[0])
        assert "ValueError" in result
        job = ts.get_job(job_id)
        assert "boom" in job["last_error"]

    @pytest.mark.asyncio
    async def test_run_one_shot_disables(self, tmp_path):
        ts = TaskScheduler(db_path=tmp_path / "sched.db")
        handler = AsyncMock(return_value="done")
        ts.register_handler("once", handler)
        job_id = ts.add_job("test", "once", interval_s=0, one_shot=True)
        due = ts._get_due_jobs()
        await ts.run_job(due[0])
        job = ts.get_job(job_id)
        assert job["enabled"] == 0


# ===========================================================================
# TaskScheduler — tick (async)
# ===========================================================================

class TestTick:
    @pytest.mark.asyncio
    async def test_tick_executes_due(self, tmp_path):
        ts = TaskScheduler(db_path=tmp_path / "sched.db")
        handler = AsyncMock(return_value="ok")
        ts.register_handler("check", handler)
        ts.add_job("test", "check", interval_s=0)
        count = await ts.tick()
        assert count == 1
        handler.assert_called_once()

    @pytest.mark.asyncio
    async def test_tick_nothing_due(self, tmp_path):
        ts = TaskScheduler(db_path=tmp_path / "sched.db")
        count = await ts.tick()
        assert count == 0


# ===========================================================================
# TaskScheduler — start / stop (async)
# ===========================================================================

class TestStartStop:
    @pytest.mark.asyncio
    async def test_start_stop(self, tmp_path):
        ts = TaskScheduler(db_path=tmp_path / "sched.db")
        assert ts.running is False
        await ts.start(check_interval=0.1)
        assert ts.running is True
        await asyncio.sleep(0.2)
        await ts.stop()
        assert ts.running is False

    @pytest.mark.asyncio
    async def test_double_start(self, tmp_path):
        ts = TaskScheduler(db_path=tmp_path / "sched.db")
        await ts.start(check_interval=0.1)
        await ts.start(check_interval=0.1)  # should not create second task
        assert ts.running is True
        await ts.stop()


# ===========================================================================
# TaskScheduler — stats
# ===========================================================================

class TestStats:
    def test_stats(self, tmp_path):
        ts = TaskScheduler(db_path=tmp_path / "sched.db")
        ts.add_job("a", "check", interval_s=60)
        ts.add_job("b", "check", interval_s=120, enabled=False)
        handler = AsyncMock()
        ts.register_handler("check", handler)
        stats = ts.get_stats()
        assert stats["total_jobs"] == 2
        assert stats["enabled_jobs"] == 1
        assert "check" in stats["registered_handlers"]
        assert stats["running"] is False

    def test_stats_empty(self, tmp_path):
        ts = TaskScheduler(db_path=tmp_path / "sched.db")
        stats = ts.get_stats()
        assert stats["total_jobs"] == 0


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert task_scheduler is not None
        assert isinstance(task_scheduler, TaskScheduler)
