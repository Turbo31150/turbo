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
        assert len(tasks) >= 140
        ids = [t.id for t in tasks]
        assert "health_cluster" in ids
        assert "backup_databases" in ids
        assert "audit_code" in ids
        assert "daily_pipeline" in ids
        assert "trading_scan" in ids

    def test_phase3_tasks_exist(self):
        to.create_default_tasks()
        ids = [t.id for t in to.load_tasks()]
        for tid in ["metrics_collector", "orch_self_health", "metrics_cleanup",
                     "ws_server_health", "cluster_failover", "error_rate_monitor",
                     "dashboard_export", "parallel_cluster_ping", "memory_guard"]:
            assert tid in ids, f"Missing task: {tid}"

    def test_autonomy_tasks_exist(self):
        to.create_default_tasks()
        ids = [t.id for t in to.load_tasks()]
        for tid in ["autonomy_cycle", "autonomy_heal", "autonomy_trends", "autonomy_optimize"]:
            assert tid in ids, f"Missing autonomy task: {tid}"

    def test_evolution_tasks_exist(self):
        to.create_default_tasks()
        ids = [t.id for t in to.load_tasks()]
        for tid in ["error_anticipator", "auto_debugger", "cluster_load_balance",
                     "code_evolution_scan", "test_evolution", "cluster_benchmark",
                     "failure_learner", "node_exerciser", "dependency_health",
                     "log_anomaly_detector", "perf_regression", "cluster_knowledge_sync",
                     "smart_scheduler", "cluster_code_review", "resource_predictor"]:
            assert tid in ids, f"Missing evolution task: {tid}"

    def test_autonomic_tasks_exist(self):
        to.create_default_tasks()
        ids = [t.id for t in to.load_tasks()]
        for tid in ["security_scanner", "db_vacuum_optimize", "gpu_thermal_predictor",
                     "auto_recovery", "dead_code_detector", "config_drift_detector",
                     "api_latency_tracker", "self_documenter", "failover_drill",
                     "orphan_data_cleaner", "canary_heartbeat", "cluster_utilization",
                     "auto_changelog", "circuit_breaker", "continuous_test_runner",
                     "disk_fill_predictor", "model_quality_monitor", "process_tree_monitor",
                     "dependency_freshness", "cluster_work_generator"]:
            assert tid in ids, f"Missing autonomic task: {tid}"

    def test_cognitive_tasks_exist(self):
        to.create_default_tasks()
        ids = [t.id for t in to.load_tasks()]
        for tid in ["error_correlator", "auto_test_generator", "prompt_optimizer",
                     "entropy_monitor", "memory_leak_detector", "task_dependency_optimizer",
                     "cluster_cross_validator", "import_syntax_healer", "performance_profiler",
                     "alert_aggregator", "evolution_fitness", "node_warmup",
                     "auto_rollback_sentinel", "knowledge_base_builder", "saturation_balancer"]:
            assert tid in ids, f"Missing cognitive task: {tid}"

    def test_self_evolving_tasks_exist(self):
        to.create_default_tasks()
        ids = [t.id for t in to.load_tasks()]
        for tid in ["task_auto_tuner", "task_retirement", "inter_node_teaching",
                     "code_complexity_tracker", "ab_task_tester", "data_pipeline_validator",
                     "service_mesh_mapper", "daily_insight_generator", "error_deduplicator",
                     "git_activity_intelligence", "cluster_feedback_loop", "dynamic_priority",
                     "self_benchmark", "model_arbitrage", "evolution_report_card"]:
            assert tid in ids, f"Missing self-evolving task: {tid}"

    def test_predictive_tasks_exist(self):
        to.create_default_tasks()
        ids = [t.id for t in to.load_tasks()]
        for tid in ["predictive_failure", "watchdog_watchdog", "external_connectivity",
                     "log_intelligence", "backup_restore_test", "task_chain_optimizer",
                     "auto_fix_engine", "capacity_planner", "node_latency_matrix",
                     "autonomous_code_reviewer", "task_value_scorer", "cluster_consensus_solver",
                     "schema_drift_monitor", "execution_heatmap", "system_genome"]:
            assert tid in ids, f"Missing predictive task: {tid}"


class TestEscalation:
    def test_escalation_increments(self):
        to.save_task(to.TaskDef(id="esc1", name="Esc", task_type="quick",
                                 action="python", payload={"code": "print('x')"}))
        for _ in range(4):
            to.process_escalation("esc1", "failed")
        conn = to.get_db()
        row = conn.execute("SELECT consecutive_fails FROM task_escalation WHERE task_id='esc1'").fetchone()
        conn.close()
        assert row[0] == 4

    def test_escalation_resets_on_success(self):
        to.save_task(to.TaskDef(id="esc2", name="Esc2", task_type="quick",
                                 action="python", payload={"code": "print('x')"}))
        to.process_escalation("esc2", "failed")
        to.process_escalation("esc2", "failed")
        to.process_escalation("esc2", "completed")
        conn = to.get_db()
        row = conn.execute("SELECT consecutive_fails FROM task_escalation WHERE task_id='esc2'").fetchone()
        conn.close()
        assert row[0] == 0


class TestParallelExecutor:
    def test_parallel_execution(self):
        tasks = [
            to.TaskDef(id=f"par{i}", name=f"Par{i}", task_type="quick",
                       action="python", payload={"code": f"print('task{i}')"})
            for i in range(3)
        ]
        results = to.execute_parallel(tasks, max_workers=3)
        assert len(results) == 3
        assert all(r.status == "completed" for r in results)


class TestMetrics:
    def test_record_and_retrieve(self):
        to.record_metric("test_metric", 42.5)
        to.record_metric("test_metric", 43.0)
        # Direct query since get_metrics_summary uses datetime('now') which is UTC in sqlite
        conn = to.get_db()
        rows = conn.execute("SELECT metric_value FROM task_metrics WHERE metric_name='test_metric' ORDER BY id").fetchall()
        conn.close()
        assert len(rows) == 2
        assert rows[0][0] == 42.5
        assert rows[1][0] == 43.0


class TestExtendedBranch:
    def test_branch_port_open(self):
        task = to.TaskDef(
            id="port1", name="Port", task_type="quick", action="branch",
            payload={
                "condition": {"type": "port_open", "host": "127.0.0.1", "port": 99999},
                "branches": {
                    "open": {"action": "python", "payload": {"code": "print('open')"}},
                    "closed": {"action": "python", "payload": {"code": "print('closed')"}},
                    "error": {"action": "python", "payload": {"code": "print('error')"}},
                },
            })
        result = to.execute_branch(task)
        assert result.status == "completed"
        # Port 99999 is invalid, returns either "closed" or "error"
        assert any(x in result.output for x in ("closed", "error"))

    def test_branch_env_var(self):
        os.environ["TEST_ORCH_VAR"] = "hello"
        task = to.TaskDef(
            id="env1", name="Env", task_type="quick", action="branch",
            payload={
                "condition": {"type": "env_var", "var": "TEST_ORCH_VAR"},
                "branches": {
                    "set": {"action": "python", "payload": {"code": "print('is set')"}},
                    "unset": {"action": "python", "payload": {"code": "print('not set')"}},
                },
            })
        result = to.execute_branch(task)
        assert result.status == "completed"
        assert "is set" in result.output
        del os.environ["TEST_ORCH_VAR"]

    def test_branch_recent_task_status(self):
        to.save_task(to.TaskDef(id="ref1", name="Ref", task_type="quick",
                                 action="python", payload={"code": "print('ok')"}))
        to.record_run(to.TaskResult("ref1", "completed", output="done"))
        task = to.TaskDef(
            id="rts1", name="RecentStatus", task_type="quick", action="branch",
            payload={
                "condition": {"type": "recent_task_status", "task_id": "ref1"},
                "branches": {
                    "completed": {"action": "python", "payload": {"code": "print('was ok')"}},
                    "failed": {"action": "python", "payload": {"code": "print('was bad')"}},
                    "never_run": {"action": "python", "payload": {"code": "print('never')"}},
                },
            })
        result = to.execute_branch(task)
        assert result.status == "completed"
        assert "was ok" in result.output


class TestResourceCheck:
    def test_always_passes_for_simple_task(self):
        task = to.TaskDef(id="res1", name="Simple", task_type="quick",
                          action="python", payload={"code": "print('ok')"})
        ok, reason = to.check_resource_availability(task)
        assert ok

class TestSelfCheck:
    def test_self_check_returns_healthy(self):
        result = to.orchestrator_self_check()
        assert result["status"] in ("healthy", "degraded")
        assert "db_size_mb" in result

class TestDashboardExport:
    def test_export_has_fields(self):
        to.create_default_tasks()
        data = to.export_dashboard_data()
        assert "task_count" in data
        assert data["task_count"] >= 140
        assert "tasks" in data
        assert "recent_runs" in data
        assert "metrics" in data
