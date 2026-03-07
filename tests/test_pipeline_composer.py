"""Tests for src/pipeline_composer.py — Multi-agent pipeline composition.

Covers: PipelineStep, PipelineResult, PipelineComposer (add_step, run),
pre-built pipelines (code_review, smart_qa, trading, architecture, devops),
PIPELINES registry, run_pipeline.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

with patch("src.pattern_agents.PatternAgentRegistry"):
    from src.pipeline_composer import (
        PipelineStep, PipelineResult, PipelineComposer,
        code_review_pipeline, smart_qa_pipeline, trading_analysis_pipeline,
        architecture_design_pipeline, devops_deploy_pipeline,
        PIPELINES, run_pipeline,
    )


# ===========================================================================
# Dataclasses
# ===========================================================================

class TestPipelineStep:
    def test_defaults(self):
        s = PipelineStep(name="gen", pattern="code")
        assert s.prompt_template == "{input}"
        assert s.condition is None
        assert s.max_retries == 1
        assert s.timeout_s == 60


class TestPipelineResult:
    def test_defaults(self):
        r = PipelineResult(steps=[], final_output="done", total_ms=100, ok=True)
        assert r.pipeline_name == ""


# ===========================================================================
# PipelineComposer — add_step
# ===========================================================================

class TestAddStep:
    def test_add_step(self):
        with patch("src.pipeline_composer.PatternAgentRegistry"):
            pipe = PipelineComposer()
        pipe.add_step("gen", "code")
        assert len(pipe.steps) == 1
        assert pipe.steps[0].name == "gen"
        assert pipe.steps[0].pattern == "code"

    def test_chaining(self):
        with patch("src.pipeline_composer.PatternAgentRegistry"):
            pipe = PipelineComposer()
        result = pipe.add_step("a", "code").add_step("b", "security")
        assert len(pipe.steps) == 2
        assert result is pipe


# ===========================================================================
# PipelineComposer — run
# ===========================================================================

class TestRun:
    @pytest.mark.asyncio
    async def test_sequential_success(self):
        with patch("src.pipeline_composer.PatternAgentRegistry"):
            pipe = PipelineComposer()
        pipe.add_step("gen", "code")
        pipe.add_step("verify", "security")

        mock_result = MagicMock()
        mock_result.ok = True
        mock_result.content = "generated code"
        mock_result.node = "M1"
        mock_result.latency_ms = 500
        mock_result.tokens = 100
        mock_result.quality_score = 0.9
        mock_result.error = ""
        pipe.registry.dispatch = AsyncMock(return_value=mock_result)

        result = await pipe.run("Write hello world")
        assert result.ok is True
        assert len(result.steps) == 2
        assert result.final_output == "generated code"
        assert result.total_ms > 0

    @pytest.mark.asyncio
    async def test_failure_stops_pipeline(self):
        with patch("src.pipeline_composer.PatternAgentRegistry"):
            pipe = PipelineComposer()
        pipe.add_step("gen", "code")
        pipe.add_step("verify", "security")

        mock_result = MagicMock()
        mock_result.ok = False
        mock_result.content = ""
        mock_result.error = "timeout"
        mock_result.node = "M1"
        mock_result.latency_ms = 30000
        mock_result.tokens = 0
        mock_result.quality_score = 0
        pipe.registry.dispatch = AsyncMock(return_value=mock_result)

        result = await pipe.run("test")
        assert result.ok is False
        assert "failed" in result.final_output.lower()
        assert len(result.steps) == 1  # stopped after first step

    @pytest.mark.asyncio
    async def test_condition_skip(self):
        with patch("src.pipeline_composer.PatternAgentRegistry"):
            pipe = PipelineComposer()
        pipe.add_step("gen", "code")
        pipe.add_step("optional", "security", condition=lambda r: r.quality_score > 0.5)

        # First step succeeds with low quality
        mock_result = MagicMock()
        mock_result.ok = True
        mock_result.content = "output"
        mock_result.node = "M1"
        mock_result.latency_ms = 100
        mock_result.tokens = 50
        mock_result.quality_score = 0.3
        mock_result.error = ""
        pipe.registry.dispatch = AsyncMock(return_value=mock_result)

        result = await pipe.run("test")
        assert result.ok is True
        assert len(result.steps) == 2
        assert result.steps[1].get("skipped") is True

    @pytest.mark.asyncio
    async def test_prompt_template(self):
        with patch("src.pipeline_composer.PatternAgentRegistry"):
            pipe = PipelineComposer()
        pipe.add_step("gen", "code", prompt_template="Audit: {input}\nOriginal: {original}")

        mock_result = MagicMock()
        mock_result.ok = True
        mock_result.content = "result"
        mock_result.node = "M1"
        mock_result.latency_ms = 100
        mock_result.tokens = 50
        mock_result.quality_score = 0.9
        mock_result.error = ""
        pipe.registry.dispatch = AsyncMock(return_value=mock_result)

        await pipe.run("my prompt")
        call_args = pipe.registry.dispatch.call_args
        prompt = call_args[0][1]
        assert "Audit: my prompt" in prompt
        assert "Original: my prompt" in prompt

    @pytest.mark.asyncio
    async def test_retry_on_failure(self):
        with patch("src.pipeline_composer.PatternAgentRegistry"):
            pipe = PipelineComposer()
        pipe.add_step("gen", "code", max_retries=3)

        call_count = [0]
        async def mock_dispatch(pattern, prompt):
            call_count[0] += 1
            r = MagicMock()
            r.node = "M1"
            r.latency_ms = 100
            r.tokens = 50
            r.quality_score = 0.9
            if call_count[0] < 3:
                r.ok = False
                r.content = ""
                r.error = "retry"
            else:
                r.ok = True
                r.content = "success after retry"
                r.error = ""
            return r

        pipe.registry.dispatch = mock_dispatch
        result = await pipe.run("test")
        assert result.ok is True
        assert call_count[0] == 3


# ===========================================================================
# Pre-built pipelines
# ===========================================================================

class TestPrebuiltPipelines:
    def test_code_review(self):
        with patch("src.pipeline_composer.PatternAgentRegistry"):
            pipe = code_review_pipeline()
        assert pipe.name == "code-review"
        assert len(pipe.steps) == 3

    def test_smart_qa(self):
        with patch("src.pipeline_composer.PatternAgentRegistry"):
            pipe = smart_qa_pipeline()
        assert pipe.name == "smart-qa"
        assert len(pipe.steps) == 3

    def test_trading_analysis(self):
        with patch("src.pipeline_composer.PatternAgentRegistry"):
            pipe = trading_analysis_pipeline()
        assert pipe.name == "trading-analysis"
        assert len(pipe.steps) == 3

    def test_architecture_design(self):
        with patch("src.pipeline_composer.PatternAgentRegistry"):
            pipe = architecture_design_pipeline()
        assert pipe.name == "architecture-design"
        assert len(pipe.steps) == 4

    def test_devops_deploy(self):
        with patch("src.pipeline_composer.PatternAgentRegistry"):
            pipe = devops_deploy_pipeline()
        assert pipe.name == "devops-deploy"
        assert len(pipe.steps) == 3


# ===========================================================================
# PIPELINES registry & run_pipeline
# ===========================================================================

class TestPipelinesRegistry:
    def test_all_registered(self):
        assert "code-review" in PIPELINES
        assert "smart-qa" in PIPELINES
        assert "trading-analysis" in PIPELINES
        assert "architecture-design" in PIPELINES
        assert "devops-deploy" in PIPELINES
        assert len(PIPELINES) == 5

    @pytest.mark.asyncio
    async def test_run_unknown_pipeline(self):
        result = await run_pipeline("nonexistent", "test")
        assert result.ok is False
        assert "Unknown pipeline" in result.final_output

    @pytest.mark.asyncio
    async def test_run_pipeline_success(self):
        mock_result = MagicMock()
        mock_result.ok = True
        mock_result.content = "output"
        mock_result.node = "M1"
        mock_result.latency_ms = 100
        mock_result.tokens = 50
        mock_result.quality_score = 0.9
        mock_result.error = ""

        with patch("src.pipeline_composer.PatternAgentRegistry") as MockReg:
            mock_instance = MagicMock()
            mock_instance.dispatch = AsyncMock(return_value=mock_result)
            mock_instance.close = AsyncMock()
            MockReg.return_value = mock_instance
            result = await run_pipeline("code-review", "test prompt")
        assert result.ok is True
        assert result.pipeline_name == "code-review"
