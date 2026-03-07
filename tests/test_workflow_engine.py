"""Tests for src/workflow_engine.py — Multi-step workflow execution.

Covers: WorkflowEngine (_init_db, create, get, list_workflows, delete,
execute, _execute_step, _eval_condition, get_run, list_runs, get_stats),
workflow_engine singleton.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.workflow_engine import WorkflowEngine, workflow_engine


# ===========================================================================
# _eval_condition (static)
# ===========================================================================

class TestEvalCondition:
    def test_simple_equals_true(self):
        assert WorkflowEngine._eval_condition("env == prod", {"env": "prod"}, {}) is True

    def test_simple_equals_false(self):
        assert WorkflowEngine._eval_condition("env == staging", {"env": "prod"}, {}) is False

    def test_quoted_value(self):
        assert WorkflowEngine._eval_condition("x == 'hello'", {"x": "hello"}, {}) is True

    def test_double_quoted_value(self):
        assert WorkflowEngine._eval_condition('x == "world"', {"x": "world"}, {}) is True

    def test_from_step_results(self):
        assert WorkflowEngine._eval_condition("build == ok", {}, {"build": "ok"}) is True

    def test_variables_priority_over_step_results(self):
        assert WorkflowEngine._eval_condition("x == var", {"x": "var"}, {"x": "step"}) is True

    def test_missing_key_empty_string(self):
        assert WorkflowEngine._eval_condition("missing == ''", {}, {}) is True

    def test_no_equals_returns_true(self):
        assert WorkflowEngine._eval_condition("just a string", {}, {}) is True

    def test_exception_returns_true(self):
        assert WorkflowEngine._eval_condition("", {}, {}) is True


# ===========================================================================
# WorkflowEngine — CRUD
# ===========================================================================

class TestCRUD:
    def _make_engine(self):
        f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        db_path = Path(f.name)
        f.close()
        return WorkflowEngine(db_path=db_path), db_path

    def test_create_returns_id(self):
        engine, db_path = self._make_engine()
        wf_id = engine.create("test", steps=[{"name": "a", "action": "noop"}])
        assert isinstance(wf_id, str)
        assert len(wf_id) == 8
        # tempfile cleanup skipped (Windows file locking)

    def test_get_existing(self):
        engine, db_path = self._make_engine()
        wf_id = engine.create("deploy", steps=[
            {"name": "build", "action": "bash", "params": {"cmd": "echo ok"}},
        ], variables={"env": "prod"})
        wf = engine.get(wf_id)
        assert wf is not None
        assert wf["name"] == "deploy"
        assert len(wf["steps"]) == 1
        assert wf["variables"]["env"] == "prod"
        # tempfile cleanup skipped (Windows file locking)

    def test_get_nonexistent(self):
        engine, db_path = self._make_engine()
        assert engine.get("nope") is None
        # tempfile cleanup skipped (Windows file locking)

    def test_list_workflows_empty(self):
        engine, db_path = self._make_engine()
        assert engine.list_workflows() == []
        # tempfile cleanup skipped (Windows file locking)

    def test_list_workflows_with_data(self):
        engine, db_path = self._make_engine()
        engine.create("wf1", steps=[])
        engine.create("wf2", steps=[])
        result = engine.list_workflows()
        assert len(result) == 2
        assert all("id" in r and "name" in r for r in result)
        # tempfile cleanup skipped (Windows file locking)

    def test_list_workflows_limit(self):
        engine, db_path = self._make_engine()
        for i in range(5):
            engine.create(f"wf{i}", steps=[])
        result = engine.list_workflows(limit=3)
        assert len(result) == 3
        # tempfile cleanup skipped (Windows file locking)

    def test_delete_existing(self):
        engine, db_path = self._make_engine()
        wf_id = engine.create("to_delete", steps=[])
        assert engine.delete(wf_id) is True
        assert engine.get(wf_id) is None
        # tempfile cleanup skipped (Windows file locking)

    def test_delete_nonexistent(self):
        engine, db_path = self._make_engine()
        assert engine.delete("nope") is False
        # tempfile cleanup skipped (Windows file locking)


# ===========================================================================
# WorkflowEngine — _execute_step
# ===========================================================================

class TestExecuteStep:
    def _make_engine(self):
        f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        db_path = Path(f.name)
        f.close()
        return WorkflowEngine(db_path=db_path), db_path

    @pytest.mark.asyncio
    async def test_noop(self):
        engine, db_path = self._make_engine()
        result = await engine._execute_step({"action": "noop"}, {})
        assert result["status"] == "ok"
        assert result["output"] == "noop"
        # tempfile cleanup skipped (Windows file locking)

    @pytest.mark.asyncio
    async def test_unknown_action(self):
        engine, db_path = self._make_engine()
        result = await engine._execute_step({"action": "xyz"}, {})
        assert "Unknown action" in result["output"]
        # tempfile cleanup skipped (Windows file locking)

    @pytest.mark.asyncio
    async def test_bash_success(self):
        engine, db_path = self._make_engine()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "hello"
        mock_result.stderr = ""
        with patch("subprocess.run", return_value=mock_result):
            result = await engine._execute_step(
                {"action": "bash", "params": {"cmd": "echo hello"}}, {}
            )
        assert result["status"] == "ok"
        assert result["output"] == "hello"
        # tempfile cleanup skipped (Windows file locking)

    @pytest.mark.asyncio
    async def test_bash_failure(self):
        engine, db_path = self._make_engine()
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "error"
        with patch("subprocess.run", return_value=mock_result):
            result = await engine._execute_step(
                {"action": "bash", "params": {"cmd": "false"}}, {}
            )
        assert result["status"] == "error"
        assert result["returncode"] == 1
        # tempfile cleanup skipped (Windows file locking)

    @pytest.mark.asyncio
    async def test_bash_variable_substitution(self):
        engine, db_path = self._make_engine()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "prod"
        mock_result.stderr = ""
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            await engine._execute_step(
                {"action": "bash", "params": {"cmd": "echo $env"}},
                {"$env": "prod"},
            )
        # Variable should have been substituted (with shlex.quote)
        call_args = mock_run.call_args
        assert "prod" in call_args[0][0] or "prod" in str(call_args)
        # tempfile cleanup skipped (Windows file locking)

    @pytest.mark.asyncio
    async def test_cluster_query_ollama(self):
        engine, db_path = self._make_engine()
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"message": {"content": "test response"}}'
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = await engine._execute_step(
                {"action": "cluster_query", "params": {"node": "OL1", "prompt": "hello"}}, {}
            )
        assert result["status"] == "ok"
        assert result["node"] == "OL1"
        # tempfile cleanup skipped (Windows file locking)

    @pytest.mark.asyncio
    async def test_cluster_query_lmstudio(self):
        engine, db_path = self._make_engine()
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"choices": [{"message": {"content": "answer"}}]}'
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = await engine._execute_step(
                {"action": "cluster_query", "params": {"node": "M1", "prompt": "question"}}, {}
            )
        assert result["status"] == "ok"
        assert "answer" in result["output"]
        # tempfile cleanup skipped (Windows file locking)

    @pytest.mark.asyncio
    async def test_cluster_query_failure(self):
        engine, db_path = self._make_engine()
        with patch("urllib.request.urlopen", side_effect=Exception("timeout")):
            result = await engine._execute_step(
                {"action": "cluster_query", "params": {"node": "M1", "prompt": "x"}}, {}
            )
        assert result["status"] == "error"
        assert "failed" in result["output"]
        # tempfile cleanup skipped (Windows file locking)


# ===========================================================================
# WorkflowEngine — execute
# ===========================================================================

class TestExecute:
    def _make_engine(self):
        f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        db_path = Path(f.name)
        f.close()
        return WorkflowEngine(db_path=db_path), db_path

    @pytest.mark.asyncio
    async def test_not_found(self):
        engine, db_path = self._make_engine()
        with pytest.raises(ValueError, match="not found"):
            await engine.execute("nonexistent")
        # tempfile cleanup skipped (Windows file locking)

    @pytest.mark.asyncio
    async def test_single_noop_step(self):
        engine, db_path = self._make_engine()
        wf_id = engine.create("test", steps=[{"name": "s1", "action": "noop"}])
        run_id = await engine.execute(wf_id)
        run = engine.get_run(run_id)
        assert run is not None
        assert run["status"] == "completed"
        assert "s1" in run["step_results"]
        # tempfile cleanup skipped (Windows file locking)

    @pytest.mark.asyncio
    async def test_sequential_steps(self):
        engine, db_path = self._make_engine()
        wf_id = engine.create("test", steps=[
            {"name": "a", "action": "noop"},
            {"name": "b", "action": "noop", "depends_on": ["a"]},
        ])
        run_id = await engine.execute(wf_id)
        run = engine.get_run(run_id)
        assert run["status"] == "completed"
        assert "a" in run["step_results"]
        assert "b" in run["step_results"]
        # tempfile cleanup skipped (Windows file locking)

    @pytest.mark.asyncio
    async def test_condition_skip(self):
        engine, db_path = self._make_engine()
        wf_id = engine.create("test", steps=[
            {"name": "s1", "action": "noop", "condition": "env == staging"},
        ], variables={"env": "prod"})
        run_id = await engine.execute(wf_id)
        run = engine.get_run(run_id)
        assert run["status"] == "completed"
        assert run["step_results"]["s1"]["skipped"] is True
        # tempfile cleanup skipped (Windows file locking)

    @pytest.mark.asyncio
    async def test_step_failure_stops_workflow(self):
        engine, db_path = self._make_engine()
        wf_id = engine.create("test", steps=[
            {"name": "fail_step", "action": "noop"},
            {"name": "after", "action": "noop", "depends_on": ["fail_step"]},
        ])
        with patch.object(engine, "_execute_step", side_effect=Exception("boom")):
            run_id = await engine.execute(wf_id)
        run = engine.get_run(run_id)
        assert run["status"] == "failed"
        # tempfile cleanup skipped (Windows file locking)

    @pytest.mark.asyncio
    async def test_continue_on_error(self):
        engine, db_path = self._make_engine()
        wf_id = engine.create("test", steps=[
            {"name": "flaky", "action": "noop", "continue_on_error": True},
            {"name": "next", "action": "noop"},
        ])
        call_count = [0]
        async def mock_step(step, vars):
            call_count[0] += 1
            if step["name"] == "flaky":
                raise Exception("flaky error")
            return {"status": "ok", "output": "done"}

        with patch.object(engine, "_execute_step", side_effect=mock_step):
            run_id = await engine.execute(wf_id)
        run = engine.get_run(run_id)
        assert run["status"] == "completed"
        # tempfile cleanup skipped (Windows file locking)

    @pytest.mark.asyncio
    async def test_variable_passing(self):
        engine, db_path = self._make_engine()
        wf_id = engine.create("test", steps=[
            {"name": "s1", "action": "noop"},
        ], variables={"base": "123"})
        run_id = await engine.execute(wf_id, variables={"extra": "456"})
        run = engine.get_run(run_id)
        assert run["variables"]["base"] == "123"
        assert run["variables"]["extra"] == "456"
        # tempfile cleanup skipped (Windows file locking)


# ===========================================================================
# WorkflowEngine — get_run, list_runs, get_stats
# ===========================================================================

class TestRunQueries:
    def _make_engine(self):
        f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        db_path = Path(f.name)
        f.close()
        return WorkflowEngine(db_path=db_path), db_path

    def test_get_run_nonexistent(self):
        engine, db_path = self._make_engine()
        assert engine.get_run("nope") is None
        # tempfile cleanup skipped (Windows file locking)

    @pytest.mark.asyncio
    async def test_list_runs_all(self):
        engine, db_path = self._make_engine()
        wf_id = engine.create("test", steps=[{"name": "a", "action": "noop"}])
        await engine.execute(wf_id)
        await engine.execute(wf_id)
        runs = engine.list_runs()
        assert len(runs) == 2
        # tempfile cleanup skipped (Windows file locking)

    @pytest.mark.asyncio
    async def test_list_runs_by_workflow(self):
        engine, db_path = self._make_engine()
        wf1 = engine.create("wf1", steps=[{"name": "a", "action": "noop"}])
        wf2 = engine.create("wf2", steps=[{"name": "b", "action": "noop"}])
        await engine.execute(wf1)
        await engine.execute(wf2)
        runs = engine.list_runs(workflow_id=wf1)
        assert len(runs) == 1
        # tempfile cleanup skipped (Windows file locking)

    @pytest.mark.asyncio
    async def test_get_stats(self):
        engine, db_path = self._make_engine()
        wf_id = engine.create("test", steps=[{"name": "a", "action": "noop"}])
        await engine.execute(wf_id)
        stats = engine.get_stats()
        assert stats["total_workflows"] == 1
        assert stats["total_runs"] == 1
        assert "completed" in stats["runs_by_status"]
        # tempfile cleanup skipped (Windows file locking)

    def test_get_stats_empty(self):
        engine, db_path = self._make_engine()
        stats = engine.get_stats()
        assert stats["total_workflows"] == 0
        assert stats["total_runs"] == 0
        # tempfile cleanup skipped (Windows file locking)


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert workflow_engine is not None
        assert isinstance(workflow_engine, WorkflowEngine)
