"""Data Pipeline — ETL for cluster data processing.

Configurable stages: extract, transform, load.
Supports chaining multiple stages into pipelines.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine


__all__ = [
    "DataPipelineManager",
    "Pipeline",
    "PipelineRun",
    "PipelineStage",
]

logger = logging.getLogger("jarvis.data_pipeline")

StageFunc = Callable[[dict], Coroutine[Any, Any, dict] | dict]


@dataclass
class PipelineStage:
    name: str
    func: StageFunc
    stage_type: str = "transform"  # extract, transform, load
    description: str = ""


@dataclass
class PipelineRun:
    run_id: str
    pipeline_name: str
    status: str = "pending"  # pending, running, completed, failed
    started_at: float = 0.0
    finished_at: float = 0.0
    stages_completed: int = 0
    total_stages: int = 0
    error: str = ""
    output: dict = field(default_factory=dict)


class Pipeline:
    """A named pipeline with ordered stages."""

    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
        self.stages: list[PipelineStage] = []
        self.created_at = time.time()

    def add_stage(
        self,
        name: str,
        func: StageFunc,
        stage_type: str = "transform",
        description: str = "",
    ) -> "Pipeline":
        self.stages.append(PipelineStage(
            name=name, func=func, stage_type=stage_type, description=description,
        ))
        return self

    async def execute(self, initial_data: dict | None = None) -> PipelineRun:
        """Execute all stages in order. Each stage receives output of previous."""
        run = PipelineRun(
            run_id=uuid.uuid4().hex[:12],
            pipeline_name=self.name,
            status="running",
            started_at=time.time(),
            total_stages=len(self.stages),
        )
        data = dict(initial_data or {})

        for stage in self.stages:
            try:
                result = stage.func(data)
                if asyncio.iscoroutine(result):
                    data = await result
                else:
                    data = result
                if not isinstance(data, dict):
                    data = {"result": data}
                run.stages_completed += 1
            except Exception as e:
                run.status = "failed"
                run.error = f"Stage '{stage.name}': {e}"
                run.finished_at = time.time()
                logger.warning("Pipeline %s stage %s failed: %s", self.name, stage.name, e)
                return run

        run.status = "completed"
        run.finished_at = time.time()
        run.output = data
        return run

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "stages": [
                {"name": s.name, "type": s.stage_type, "description": s.description}
                for s in self.stages
            ],
            "created_at": self.created_at,
        }


class DataPipelineManager:
    """Manages named pipelines and their execution history."""

    def __init__(self):
        self._pipelines: dict[str, Pipeline] = {}
        self._history: list[dict] = []
        self._max_history = 200

    def create(self, name: str, description: str = "") -> Pipeline:
        """Create a new pipeline."""
        pipeline = Pipeline(name, description)
        self._pipelines[name] = pipeline
        return pipeline

    def get(self, name: str) -> Pipeline | None:
        return self._pipelines.get(name)

    def delete(self, name: str) -> bool:
        return self._pipelines.pop(name, None) is not None

    def list_pipelines(self) -> list[dict]:
        return [p.to_dict() for p in self._pipelines.values()]

    async def run(self, name: str, initial_data: dict | None = None) -> PipelineRun:
        """Execute a named pipeline."""
        pipeline = self._pipelines.get(name)
        if not pipeline:
            raise KeyError(f"Pipeline '{name}' not found")
        result = await pipeline.execute(initial_data)
        self._history.append({
            "run_id": result.run_id,
            "pipeline": result.pipeline_name,
            "status": result.status,
            "stages_completed": result.stages_completed,
            "total_stages": result.total_stages,
            "duration_ms": round((result.finished_at - result.started_at) * 1000),
            "error": result.error,
            "ts": result.finished_at,
        })
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]
        return result

    def get_history(self, limit: int = 50) -> list[dict]:
        return self._history[-limit:]

    def get_stats(self) -> dict:
        completed = sum(1 for h in self._history if h["status"] == "completed")
        failed = sum(1 for h in self._history if h["status"] == "failed")
        return {
            "total_pipelines": len(self._pipelines),
            "total_runs": len(self._history),
            "completed_runs": completed,
            "failed_runs": failed,
            "success_rate": round(completed / max(1, len(self._history)) * 100, 1),
        }


# ── Singleton ────────────────────────────────────────────────────────────────
data_pipeline = DataPipelineManager()
