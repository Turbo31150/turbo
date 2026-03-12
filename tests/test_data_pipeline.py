"""Tests for src/data_pipeline.py — ETL pipeline manager.

Covers: PipelineStage, PipelineRun, Pipeline (add_stage, execute, to_dict),
DataPipelineManager (create, get, delete, list_pipelines, run, get_history,
get_stats), data_pipeline singleton.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data_pipeline import (
    PipelineStage, PipelineRun, Pipeline, DataPipelineManager, data_pipeline,
)


# ===========================================================================
# Dataclasses
# ===========================================================================

class TestDataclasses:
    def test_pipeline_stage(self):
        ps = PipelineStage(name="extract", func=lambda d: d)
        assert ps.stage_type == "transform"

    def test_pipeline_run(self):
        pr = PipelineRun(run_id="abc", pipeline_name="test")
        assert pr.status == "pending"
        assert pr.output == {}


# ===========================================================================
# Pipeline — add_stage & execute
# ===========================================================================

class TestPipeline:
    def test_add_stage_chaining(self):
        p = Pipeline("test")
        p.add_stage("a", func=lambda d: d).add_stage("b", func=lambda d: d)
        assert len(p.stages) == 2

    @pytest.mark.asyncio
    async def test_execute_sync_stages(self):
        p = Pipeline("test")
        p.add_stage("double", func=lambda d: {"val": d.get("val", 0) * 2})
        p.add_stage("add_one", func=lambda d: {"val": d["val"] + 1})
        run = await p.execute({"val": 5})
        assert run.status == "completed"
        assert run.output["val"] == 11
        assert run.stages_completed == 2

    @pytest.mark.asyncio
    async def test_execute_async_stage(self):
        async def async_transform(data):
            return {"result": data.get("x", 0) + 10}

        p = Pipeline("async_test")
        p.add_stage("async_add", func=async_transform)
        run = await p.execute({"x": 5})
        assert run.status == "completed"
        assert run.output["result"] == 15

    @pytest.mark.asyncio
    async def test_execute_stage_failure(self):
        def bad_stage(data):
            raise ValueError("stage error")

        p = Pipeline("fail_test")
        p.add_stage("ok", func=lambda d: d)
        p.add_stage("bad", func=bad_stage)
        run = await p.execute({})
        assert run.status == "failed"
        assert "bad" in run.error
        assert run.stages_completed == 1

    @pytest.mark.asyncio
    async def test_execute_non_dict_result(self):
        p = Pipeline("non_dict")
        p.add_stage("returns_list", func=lambda d: [1, 2, 3])
        run = await p.execute({})
        assert run.status == "completed"
        assert run.output == {"result": [1, 2, 3]}

    def test_to_dict(self):
        p = Pipeline("info", description="desc")
        p.add_stage("s1", func=lambda d: d, stage_type="extract")
        d = p.to_dict()
        assert d["name"] == "info"
        assert d["description"] == "desc"
        assert len(d["stages"]) == 1
        assert d["stages"][0]["type"] == "extract"


# ===========================================================================
# DataPipelineManager — CRUD
# ===========================================================================

class TestManagerCRUD:
    def test_create(self):
        m = DataPipelineManager()
        p = m.create("etl", "my pipeline")
        assert p.name == "etl"
        assert m.get("etl") is not None

    def test_get_nonexistent(self):
        m = DataPipelineManager()
        assert m.get("nope") is None

    def test_delete(self):
        m = DataPipelineManager()
        m.create("temp")
        assert m.delete("temp") is True
        assert m.delete("temp") is False

    def test_list_pipelines(self):
        m = DataPipelineManager()
        m.create("a")
        m.create("b")
        lst = m.list_pipelines()
        assert len(lst) == 2


# ===========================================================================
# DataPipelineManager — run
# ===========================================================================

class TestManagerRun:
    @pytest.mark.asyncio
    async def test_run_success(self):
        m = DataPipelineManager()
        p = m.create("simple")
        p.add_stage("pass", func=lambda d: {"done": True})
        run = await m.run("simple")
        assert run.status == "completed"

    @pytest.mark.asyncio
    async def test_run_nonexistent(self):
        m = DataPipelineManager()
        with pytest.raises(KeyError):
            await m.run("nope")

    @pytest.mark.asyncio
    async def test_run_records_history(self):
        m = DataPipelineManager()
        p = m.create("hist")
        p.add_stage("x", func=lambda d: d)
        await m.run("hist")
        history = m.get_history()
        assert len(history) == 1
        assert history[0]["status"] == "completed"


# ===========================================================================
# DataPipelineManager — stats
# ===========================================================================

class TestManagerStats:
    def test_stats_empty(self):
        m = DataPipelineManager()
        stats = m.get_stats()
        assert stats["total_pipelines"] == 0
        assert stats["total_runs"] == 0

    @pytest.mark.asyncio
    async def test_stats_after_runs(self):
        m = DataPipelineManager()
        p = m.create("s")
        p.add_stage("ok", func=lambda d: d)
        await m.run("s")
        stats = m.get_stats()
        assert stats["total_runs"] == 1
        assert stats["completed_runs"] == 1
        assert stats["success_rate"] == 100.0


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert data_pipeline is not None
        assert isinstance(data_pipeline, DataPipelineManager)
