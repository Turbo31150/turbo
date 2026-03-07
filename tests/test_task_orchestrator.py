"""Tests for task_orchestrator.py."""

import json
import os
import sqlite3
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import task_orchestrator as to


@pytest.fixture(autouse=True)
def temp_db(tmp_path):
    """Use temp DB for each test."""
    db_path = str(tmp_path / "test_orch.db")
    to.DB_PATH = db_path
    to.init_db()
    yield db_path


class TestScheduleParser:
    def test_every_minutes(self):
        result = to.calculate_next_run("every:5m")
        from datetime import datetime, timedelta
        expected = datetime.now() + timedelta(minutes=5)
        parsed = datetime.fromisoformat(result)
        assert abs((parsed - expected).total_seconds()) < 2

    def test_every_hours(self):
        result = to.calculate_next_run("every:2h")
        from datetime import datetime, timedelta
        parsed = datetime.fromisoformat(result)
        expected = datetime.now() + timedelta(hours=2)
        assert abs((parsed - expected).total_seconds()) < 2

    def test_daily(self):
        result = to.calculate_next_run("daily:03:00")
        parsed = to.datetime.fromisoformat(result)
        assert parsed.hour == 3
        assert parsed.minute == 0

    def test_weekly(self):
        result = to.calculate_next_run("weekly:mon:09:00")
        parsed = to.datetime.fromisoformat(result)
        assert parsed.hour == 9
        assert parsed.weekday() == 0  # Monday

    def test_hourly(self):
        result = to.calculate_next_run("hourly")
        parsed = to.datetime.fromisoformat(result)
        assert (parsed - to.datetime.now()).total_seconds() > 3500


class TestTaskCRUD:
    def test_save_and_load(self):
        task = to.TaskDef(id="test1", name="Test Task", task_type="quick",
                          action="python", payload={"code": "print('hi')"})
        to.save_task(task)
        tasks = to.load_tasks()
        assert len(tasks) >= 1
        found = [t for t in tasks if t.id == "test1"]
        assert len(found) == 1
        assert found[0].name == "Test Task"

    def test_save_with_schedule(self):
        task = to.TaskDef(id="sched1", name="Scheduled", task_type="health",
                          action="python", schedule="every:10m",
                          payload={"code": "print('ok')"})
        to.save_task(task)
        conn = to.get_db()
        row = conn.execute("SELECT next_run FROM task_schedule WHERE task_id='sched1'").fetchone()
        conn.close()
        assert row is not None
        assert row[0] is not None

    def test_dependencies(self):
        t1 = to.TaskDef(id="dep1", name="Dep1", task_type="quick", action="python",
                         payload={"code": "print('dep1')"})
        t2 = to.TaskDef(id="dep2", name="Dep2", task_type="quick", action="python",
                         payload={"code": "print('dep2')"}, depends_on=["dep1"])
        to.save_task(t1)
        to.save_task(t2)

        # dep2 should not be ready (dep1 hasn't run)
        assert not to.check_dependencies(t2)

        # Record dep1 as completed
        to.record_run(to.TaskResult("dep1", "completed", output="done"))
        assert to.check_dependencies(t2)


class TestExecutors:
    def test_execute_python(self):
        task = to.TaskDef(id="py1", name="Python", task_type="quick", action="python",
                          payload={"code": "print('hello world')"})
        result = to.execute_python(task)
        assert result.status == "completed"
        assert "hello world" in result.output

    def test_execute_python_failure(self):
        task = to.TaskDef(id="py2", name="Fail", task_type="quick", action="python",
                          payload={"code": "raise ValueError('boom')"})
        result = to.execute_python(task)
        assert result.status == "failed"

    def test_execute_python_timeout(self):
        task = to.TaskDef(id="py3", name="Slow", task_type="quick", action="python",
                          payload={"code": "import time; time.sleep(10)"},
                          timeout_s=1)
        result = to.execute_python(task)
        assert result.status == "failed"
        assert "Timeout" in result.error

    def test_execute_branch_time(self):
        task = to.TaskDef(
            id="br1", name="Branch", task_type="quick", action="branch",
            payload={
                "condition": {"type": "time"},
                "branches": {
                    "business_hours": {"action": "python", "payload": {"code": "print('work')"}},
                    "off_hours": {"action": "python", "payload": {"code": "print('sleep')"}},
                },
            })
        result = to.execute_branch(task)
        assert result.status == "completed"
        assert result.output.strip() in ("work", "sleep")

    def test_execute_branch_file_exists(self):
        task = to.TaskDef(
            id="br2", name="Branch File", task_type="quick", action="branch",
            payload={
                "condition": {"type": "file_exists", "path": "pyproject.toml"},
                "branches": {
                    "exists": {"action": "python", "payload": {"code": "print('found')"}},
                    "missing": {"action": "python", "payload": {"code": "print('not found')"}},
                },
            })
        result = to.execute_branch(task)
        assert result.status == "completed"
        assert "found" in result.output

    def test_execute_pipeline(self):
        task = to.TaskDef(
            id="pipe1", name="Pipeline", task_type="pipeline", action="pipeline",
            payload={"steps": [
                {"action": "python", "payload": {"code": "print('step1')"}},
                {"action": "python", "payload": {"code": "print('step2')"}},
            ]})
        result = to.execute_pipeline(task)
        assert result.status == "completed"
        output = json.loads(result.output)
        assert len(output) == 2
        assert all(s["status"] == "completed" for s in output)

    def test_execute_pipeline_failure_stops(self):
        task = to.TaskDef(
            id="pipe2", name="Fail Pipeline", task_type="pipeline", action="pipeline",
            payload={"steps": [
                {"action": "python", "payload": {"code": "print('ok')"}, "required": True},
                {"action": "python", "payload": {"code": "raise Exception('boom')"}, "required": True},
                {"action": "python", "payload": {"code": "print('never')"}},
            ]},
            branch_on={"failed": "stop"})
        result = to.execute_pipeline(task)
        assert result.status == "failed"


class TestRouting:
    def test_routing_table_coverage(self):
        """All task types should have routing entries."""
        for tt in ["code", "bugfix", "review", "reasoning", "quick", "audit", "backup"]:
            assert tt in to.ROUTING_TABLE

    def test_smart_dispatch_fallback(self):
        """If preferred nodes are down, should try fallbacks."""
        with patch.object(to, "check_node_health", return_value=False):
            node, ok, resp = to.smart_dispatch("code", "test")
            assert not ok
            assert node == "none"


class TestRecordRun:
    def test_record_and_retrieve(self):
        to.save_task(to.TaskDef(id="rec1", name="Rec", task_type="quick",
                                 action="python", schedule="every:1h",
                                 payload={"code": "print('ok')"}))
        to.record_run(to.TaskResult("rec1", "completed", output="done", duration_ms=123))
        conn = to.get_db()
        row = conn.execute("SELECT status, duration_ms FROM task_runs WHERE task_id='rec1'").fetchone()
        conn.close()
        assert row[0] == "completed"
        assert row[1] == 123


class TestDefaultTasks:
    def test_create_defaults(self):
        to.create_default_tasks()
        tasks = to.load_tasks()
        assert len(tasks) >= 10
        ids = [t.id for t in tasks]
        assert "health_cluster" in ids
        assert "backup_databases" in ids
        assert "audit_code" in ids
        assert "daily_pipeline" in ids
        assert "trading_scan" in ids
