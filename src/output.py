"""JARVIS structured JSON output formatter."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class JarvisMeta:
    version: str = "10.6"
    current_engine: str = "CLAUDE"
    mode: str = "DUAL_CORE"


@dataclass
class Summary:
    goal: str = ""
    consensus_score: float = 0.0


@dataclass
class PlanStep:
    id: str = ""
    action: str = ""
    executor: str = "CLAUDE"
    command_to_run: str | None = None


@dataclass
class EngineInteraction:
    cross_check_required: bool = False
    instruction_for_other_engine: str = ""


@dataclass
class FinalDecision:
    decision: str = ""
    rationale: str = ""


@dataclass
class FileAction:
    path: str = ""
    operation: str = "READ"  # READ | WRITE


@dataclass
class TerminalAction:
    cmd: str = ""


@dataclass
class ActionsRequired:
    filesystem: list[FileAction] = field(default_factory=list)
    terminal: list[TerminalAction] = field(default_factory=list)


@dataclass
class JarvisOutput:
    jarvis_meta: JarvisMeta = field(default_factory=JarvisMeta)
    summary: Summary = field(default_factory=Summary)
    plan: list[PlanStep] = field(default_factory=list)
    engine_interaction: EngineInteraction = field(default_factory=EngineInteraction)
    final_decision: FinalDecision = field(default_factory=FinalDecision)
    actions_required: ActionsRequired = field(default_factory=ActionsRequired)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, ensure_ascii=False)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# JSON Schema for OutputFormat validation
JARVIS_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "jarvis_meta": {
            "type": "object",
            "properties": {
                "version": {"type": "string"},
                "current_engine": {"type": "string", "enum": ["CLAUDE", "GEMINI", "AUTO"]},
                "mode": {"type": "string"},
            },
            "required": ["version", "current_engine", "mode"],
        },
        "summary": {
            "type": "object",
            "properties": {
                "goal": {"type": "string"},
                "consensus_score": {"type": "number", "minimum": 0, "maximum": 1},
            },
            "required": ["goal", "consensus_score"],
        },
        "plan": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "action": {"type": "string"},
                    "executor": {"type": "string"},
                    "command_to_run": {"type": ["string", "null"]},
                },
                "required": ["id", "action", "executor"],
            },
        },
        "engine_interaction": {
            "type": "object",
            "properties": {
                "cross_check_required": {"type": "boolean"},
                "instruction_for_other_engine": {"type": "string"},
            },
        },
        "final_decision": {
            "type": "object",
            "properties": {
                "decision": {"type": "string"},
                "rationale": {"type": "string"},
            },
            "required": ["decision", "rationale"],
        },
        "actions_required": {
            "type": "object",
            "properties": {
                "filesystem": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "operation": {"type": "string", "enum": ["READ", "WRITE"]},
                        },
                    },
                },
                "terminal": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {"cmd": {"type": "string"}},
                    },
                },
            },
        },
    },
    "required": ["jarvis_meta", "summary", "plan", "final_decision"],
}
