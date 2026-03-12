"""JARVIS Agent Task Planner — Decomposes complex tasks into sub-steps with agent assignment.

Given a complex prompt, the planner:
  1. Classifies overall complexity (nano→xl)
  2. Decomposes into ordered sub-tasks
  3. Assigns optimal agent + node per sub-task
  4. Estimates time and resource budget
  5. Generates an execution plan (sequential/parallel/mixed)

Usage:
    from src.agent_task_planner import TaskPlanner
    planner = TaskPlanner()
    plan = planner.plan("Cree une API REST securisee avec tests")
    result = await planner.execute_plan(plan)
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Optional

from src.pattern_agents import PatternAgentRegistry


__all__ = [
    "PlanResult",
    "SubTask",
    "TaskPlan",
    "TaskPlanner",
]

logger = logging.getLogger("jarvis.task_planner")


@dataclass
class SubTask:
    """A single sub-task in a plan."""
    id: int
    name: str
    description: str
    pattern: str           # Which pattern agent handles this
    estimated_ms: int      # Estimated time
    depends_on: list[int] = field(default_factory=list)  # IDs of dependencies
    parallel_group: int = 0  # Steps in same group run in parallel
    priority: int = 1
    result: Optional[str] = None
    ok: bool = False
    actual_ms: float = 0


@dataclass
class TaskPlan:
    """A complete execution plan."""
    original_prompt: str
    complexity: str         # nano, micro, small, medium, large, xl
    sub_tasks: list[SubTask]
    total_estimated_ms: int
    parallel_groups: int
    sequential_steps: int

    @property
    def summary(self) -> str:
        return (f"{len(self.sub_tasks)} sub-tasks | "
                f"complexity={self.complexity} | "
                f"{self.parallel_groups} parallel groups | "
                f"~{self.total_estimated_ms}ms estimated")


@dataclass
class PlanResult:
    """Result of executing a plan."""
    plan: TaskPlan
    results: list[SubTask]
    total_ms: float
    ok: bool
    final_output: str
    steps_ok: int
    steps_total: int

    @property
    def summary(self) -> str:
        return (f"{self.steps_ok}/{self.steps_total} OK | "
                f"{self.total_ms:.0f}ms | "
                f"complexity={self.plan.complexity}")


# Task decomposition patterns
DECOMPOSITION_RULES = [
    # (keywords, sub-tasks template)
    {
        "keywords": ["api", "rest", "endpoint", "serveur"],
        "name": "API Development",
        "steps": [
            ("plan", "reasoning", "Planifie l'architecture de l'API: endpoints, modeles, middleware"),
            ("code", "code", "Implemente les endpoints de l'API"),
            ("security", "security", "Revue securite: authentification, validation, injection"),
            ("test", "code", "Ecris les tests unitaires pour l'API"),
        ],
    },
    {
        "keywords": ["analyse", "compare", "benchmark", "rapport"],
        "name": "Analysis",
        "steps": [
            ("research", "analysis", "Analyse les donnees et identifie les points cles"),
            ("compare", "reasoning", "Compare les options et evalue les trade-offs"),
            ("report", "creative", "Redige le rapport final avec recommandations"),
        ],
    },
    {
        "keywords": ["trading", "position", "signal", "crypto"],
        "name": "Trading Analysis",
        "steps": [
            ("technical", "trading", "Analyse technique: indicateurs, tendances, supports/resistances"),
            ("risk", "math", "Calcul de risque: position sizing, stop loss, take profit"),
            ("decision", "reasoning", "Decision finale avec niveau de confiance"),
        ],
    },
    {
        "keywords": ["securite", "audit", "vulnerability", "owasp"],
        "name": "Security Audit",
        "steps": [
            ("scan", "security", "Scan des vulnerabilites connues"),
            ("code_review", "code", "Revue de code pour failles de securite"),
            ("report", "analysis", "Rapport d'audit avec recommandations et priorites"),
        ],
    },
    {
        "keywords": ["architecture", "design", "microservice", "scalable"],
        "name": "Architecture Design",
        "steps": [
            ("requirements", "analysis", "Analyse des besoins et contraintes"),
            ("design", "reasoning", "Design de l'architecture: composants, flux, patterns"),
            ("validation", "security", "Validation securite et performance"),
            ("documentation", "creative", "Documentation et diagrammes"),
        ],
    },
    {
        "keywords": ["deploy", "ci", "cd", "docker", "kubernetes"],
        "name": "DevOps Pipeline",
        "steps": [
            ("dockerfile", "code", "Creation du Dockerfile et configs"),
            ("cicd", "devops", "Configuration CI/CD pipeline"),
            ("monitoring", "system", "Setup monitoring et alerting"),
        ],
    },
]


class TaskPlanner:
    """Decomposes complex tasks into executable sub-plans."""

    COMPLEXITY_THRESHOLDS = {
        "nano": 20,     # < 20 chars
        "micro": 50,    # < 50 chars
        "small": 100,   # < 100 chars
        "medium": 200,  # < 200 chars
        "large": 500,   # < 500 chars
        "xl": float("inf"),
    }

    def __init__(self):
        self.registry = PatternAgentRegistry()

    def plan(self, prompt: str) -> TaskPlan:
        """Create an execution plan for a complex task."""
        complexity = self._assess_complexity(prompt)
        sub_tasks = self._decompose(prompt, complexity)

        # Assign parallel groups
        self._assign_groups(sub_tasks)

        total_est = sum(t.estimated_ms for t in sub_tasks)
        parallel_groups = max(t.parallel_group for t in sub_tasks) + 1 if sub_tasks else 0
        sequential = len(set(t.parallel_group for t in sub_tasks))

        return TaskPlan(
            original_prompt=prompt,
            complexity=complexity,
            sub_tasks=sub_tasks,
            total_estimated_ms=total_est,
            parallel_groups=parallel_groups,
            sequential_steps=sequential,
        )

    async def execute_plan(self, plan: TaskPlan) -> PlanResult:
        """Execute a task plan."""
        t0 = time.perf_counter()

        if not plan.sub_tasks:
            # Simple task — dispatch directly
            pattern = self.registry.classify(plan.original_prompt)
            result = await self.registry.dispatch(pattern, plan.original_prompt)
            st = SubTask(0, "direct", plan.original_prompt, pattern, 0)
            st.result = result.content
            st.ok = result.ok
            st.actual_ms = result.latency_ms
            return PlanResult(
                plan=plan, results=[st], total_ms=result.latency_ms,
                ok=result.ok, final_output=result.content,
                steps_ok=1 if result.ok else 0, steps_total=1,
            )

        # Group sub-tasks by parallel group
        groups = {}
        for st in plan.sub_tasks:
            groups.setdefault(st.parallel_group, []).append(st)

        results = []
        prev_content = plan.original_prompt

        for group_id in sorted(groups.keys()):
            group = groups[group_id]
            tasks = []

            for st in group:
                # Build prompt with context from previous steps
                enriched = self._enrich_prompt(st, plan.original_prompt, prev_content, results)
                tasks.append(self._execute_subtask(st, enriched))

            group_results = await asyncio.gather(*tasks)
            results.extend(group_results)

            # Update prev_content with successful results
            ok_results = [r for r in group_results if r.ok and r.result]
            if ok_results:
                prev_content = ok_results[-1].result

        total_ms = (time.perf_counter() - t0) * 1000
        steps_ok = sum(1 for r in results if r.ok)

        # Final output: combine or use last
        ok_all = [r for r in results if r.ok and r.result]
        final = ok_all[-1].result if ok_all else "Plan execution failed"

        return PlanResult(
            plan=plan, results=results, total_ms=total_ms,
            ok=steps_ok > 0, final_output=final,
            steps_ok=steps_ok, steps_total=len(results),
        )

    async def _execute_subtask(self, st: SubTask, prompt: str) -> SubTask:
        """Execute a single sub-task."""
        t0 = time.perf_counter()
        try:
            result = await self.registry.dispatch(st.pattern, prompt)
            st.result = result.content
            st.ok = result.ok
            st.actual_ms = (time.perf_counter() - t0) * 1000
        except Exception as e:
            st.ok = False
            st.result = str(e)[:200]
            st.actual_ms = (time.perf_counter() - t0) * 1000
        return st

    def _assess_complexity(self, prompt: str) -> str:
        """Assess prompt complexity."""
        length = len(prompt)
        for level, threshold in self.COMPLEXITY_THRESHOLDS.items():
            if length < threshold:
                return level
        return "xl"

    def _decompose(self, prompt: str, complexity: str) -> list[SubTask]:
        """Decompose a task into sub-tasks."""
        prompt_lower = prompt.lower()

        # Try matching decomposition rules
        for rule in DECOMPOSITION_RULES:
            if any(kw in prompt_lower for kw in rule["keywords"]):
                sub_tasks = []
                for i, (name, pattern, desc) in enumerate(rule["steps"]):
                    est_ms = {"simple": 2000, "code": 8000, "reasoning": 5000,
                              "analysis": 6000, "security": 7000, "trading": 5000,
                              "math": 4000, "creative": 5000, "system": 3000,
                              "devops": 4000}.get(pattern, 5000)
                    sub_tasks.append(SubTask(
                        id=i, name=name, description=desc,
                        pattern=pattern, estimated_ms=est_ms,
                        depends_on=[i-1] if i > 0 else [],
                    ))
                return sub_tasks

        # Default: classify + execute
        if complexity in ("nano", "micro"):
            # Simple task — no decomposition
            return []

        # Medium+ tasks: classify → execute → verify
        pattern = self.registry.classify(prompt)
        return [
            SubTask(0, "classify", "Classify the task", "classifier", 2000),
            SubTask(1, "execute", prompt[:200], pattern, 8000, depends_on=[0]),
            SubTask(2, "verify", "Verify the result", "reasoning", 5000, depends_on=[1]),
        ]

    def _assign_groups(self, sub_tasks: list[SubTask]):
        """Assign parallel groups based on dependencies."""
        for st in sub_tasks:
            if not st.depends_on:
                st.parallel_group = 0
            else:
                max_dep_group = max(
                    (t.parallel_group for t in sub_tasks if t.id in st.depends_on),
                    default=0,
                )
                st.parallel_group = max_dep_group + 1

    def _enrich_prompt(self, st: SubTask, original: str, prev_content: str,
                       completed: list[SubTask]) -> str:
        """Enrich a sub-task prompt with context."""
        parts = [st.description]
        if original != prev_content:
            parts.append(f"\nOriginal request: {original[:300]}")
        if completed:
            ok_prev = [c for c in completed if c.ok and c.result]
            if ok_prev:
                last = ok_prev[-1]
                parts.append(f"\nPrevious step ({last.name}): {last.result[:500]}")
        return "\n".join(parts)

    def plan_to_dict(self, plan: TaskPlan) -> dict:
        """Convert plan to JSON-serializable dict."""
        return {
            "prompt": plan.original_prompt[:200],
            "complexity": plan.complexity,
            "total_estimated_ms": plan.total_estimated_ms,
            "parallel_groups": plan.parallel_groups,
            "sub_tasks": [
                {
                    "id": st.id, "name": st.name,
                    "pattern": st.pattern, "estimated_ms": st.estimated_ms,
                    "depends_on": st.depends_on, "group": st.parallel_group,
                }
                for st in plan.sub_tasks
            ],
            "summary": plan.summary,
        }

    async def close(self):
        await self.registry.close()
