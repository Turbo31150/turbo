"""Tests for src/cron_manager.py — Periodic task execution with cron-like scheduling.

Covers: ScheduleType, CronJob (next_run_in), CronExecution, CronManager (add_job,
remove_job, enable, disable, get, run_job, check_and_run_due, list_jobs, list_groups,
get_executions, get_stats), cron_manager singleton.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.cron_manager import (
    ScheduleType, CronJob, CronExecution, CronManager, cron_manager,
)


# ===========================================================================
# Enums & Dataclasses
# ===========================================================================

class TestScheduleType:
    def test_values(self):
        assert ScheduleType.INTERVAL.value == "interval"
        assert ScheduleType.DAILY.value == "daily"
        assert ScheduleType.WEEKLY.value == "weekly"


class TestCronJob:
    def test_defaults(self):
        j = CronJob(name="test", schedule_type=ScheduleType.INTERVAL)
        assert j.interval_seconds == 60.0
        assert j.group == "default"
        assert j.enabled is True
        assert j.run_count == 0
        assert j.last_run is None

    def test_next_run_in_no_last(self):
        j = CronJob(name="test", schedule_type=ScheduleType.INTERVAL)
        assert j.next_run_in is None

    def test_next_run_in_with_last(self):
        j = CronJob(name="test", schedule_type=ScheduleType.INTERVAL, interval_seconds=60)
        j.last_run = time.time() - 30  # 30s ago
        remaining = j.next_run_in
        assert remaining is not None
        assert 25 <= remaining <= 35

    def test_next_run_in_daily(self):
        j = CronJob(name="test", schedule_type=ScheduleType.DAILY, last_run=time.time())
        assert j.next_run_in is None  # only for interval


class TestCronExecution:
    def test_defaults(self):
        e = CronExecution(name="test")
        assert e.success is True
        assert e.result == ""
        assert e.error == ""
        assert e.timestamp > 0


# ===========================================================================
# CronManager — Job Management
# ===========================================================================

class TestJobManagement:
    def test_add_job(self):
        cm = CronManager()
        job = cm.add_job("test", interval_seconds=30)
        assert job.name == "test"
        assert job.interval_seconds == 30

    def test_remove_job(self):
        cm = CronManager()
        cm.add_job("test")
        assert cm.remove_job("test") is True
        assert cm.remove_job("test") is False

    def test_enable_disable(self):
        cm = CronManager()
        cm.add_job("test")
        assert cm.disable("test") is True
        assert cm.get("test").enabled is False
        assert cm.enable("test") is True
        assert cm.get("test").enabled is True

    def test_enable_nonexistent(self):
        cm = CronManager()
        assert cm.enable("nope") is False
        assert cm.disable("nope") is False

    def test_get(self):
        cm = CronManager()
        cm.add_job("test")
        assert cm.get("test") is not None
        assert cm.get("nope") is None


# ===========================================================================
# CronManager — run_job
# ===========================================================================

class TestRunJob:
    def test_not_found(self):
        cm = CronManager()
        result = cm.run_job("nope")
        assert result["success"] is False
        assert "not found" in result["error"]

    def test_disabled(self):
        cm = CronManager()
        cm.add_job("test")
        cm.disable("test")
        result = cm.run_job("test")
        assert result["success"] is False
        assert "disabled" in result["error"]

    def test_success(self):
        cm = CronManager()
        cm.add_job("test", callback=lambda: "hello")
        result = cm.run_job("test")
        assert result["success"] is True
        assert result["result"] == "hello"
        assert cm.get("test").run_count == 1
        assert cm.get("test").last_run is not None

    def test_callback_error(self):
        cm = CronManager()
        cm.add_job("test", callback=lambda: (_ for _ in ()).throw(ValueError("boom")))
        result = cm.run_job("test")
        assert result["success"] is False
        assert "boom" in result["error"]
        assert cm.get("test").run_count == 1

    def test_no_callback(self):
        cm = CronManager()
        cm.add_job("test")
        result = cm.run_job("test")
        assert result["success"] is True
        assert result["result"] == ""

    def test_records_execution(self):
        cm = CronManager()
        cm.add_job("test", callback=lambda: 42)
        cm.run_job("test")
        execs = cm.get_executions(name="test")
        assert len(execs) == 1
        assert execs[0]["success"] is True


# ===========================================================================
# CronManager — check_and_run_due
# ===========================================================================

class TestCheckAndRunDue:
    def test_no_due_jobs(self):
        cm = CronManager()
        cm.add_job("test", interval_seconds=9999)
        cm.run_job("test")  # set last_run
        executed = cm.check_and_run_due()
        assert executed == []

    def test_due_job_runs(self):
        cm = CronManager()
        cm.add_job("test", callback=lambda: "ok", interval_seconds=0.1)
        # Never run before, so it's due
        executed = cm.check_and_run_due()
        assert "test" in executed

    def test_disabled_skipped(self):
        cm = CronManager()
        cm.add_job("test", interval_seconds=0.1)
        cm.disable("test")
        executed = cm.check_and_run_due()
        assert executed == []


# ===========================================================================
# CronManager — list_jobs / list_groups
# ===========================================================================

class TestListMethods:
    def test_list_jobs(self):
        cm = CronManager()
        cm.add_job("a", group="web")
        cm.add_job("b", group="db")
        result = cm.list_jobs()
        assert len(result) == 2

    def test_list_jobs_filter_group(self):
        cm = CronManager()
        cm.add_job("a", group="web")
        cm.add_job("b", group="db")
        result = cm.list_jobs(group="web")
        assert len(result) == 1
        assert result[0]["name"] == "a"

    def test_list_groups(self):
        cm = CronManager()
        cm.add_job("a", group="web")
        cm.add_job("b", group="db")
        groups = cm.list_groups()
        assert set(groups) == {"web", "db"}


# ===========================================================================
# CronManager — get_executions / get_stats
# ===========================================================================

class TestExecutionsAndStats:
    def test_executions_empty(self):
        cm = CronManager()
        assert cm.get_executions() == []

    def test_executions_filter(self):
        cm = CronManager()
        cm.add_job("a", callback=lambda: 1)
        cm.add_job("b", callback=lambda: 2)
        cm.run_job("a")
        cm.run_job("b")
        cm.run_job("a")
        execs = cm.get_executions(name="a")
        assert len(execs) == 2

    def test_stats_empty(self):
        cm = CronManager()
        stats = cm.get_stats()
        assert stats["total_jobs"] == 0
        assert stats["total_executions"] == 0

    def test_stats_with_data(self):
        cm = CronManager()
        cm.add_job("a", group="web")
        cm.add_job("b", group="db")
        cm.disable("b")
        cm.add_job("c", group="web", callback=lambda: 1)
        cm.run_job("c")
        stats = cm.get_stats()
        assert stats["total_jobs"] == 3
        assert stats["enabled"] == 2
        assert stats["disabled"] == 1
        assert stats["groups"] == 2
        assert stats["total_executions"] == 1


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert cron_manager is not None
        assert isinstance(cron_manager, CronManager)
