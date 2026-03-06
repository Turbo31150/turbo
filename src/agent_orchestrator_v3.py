"""JARVIS Agent Orchestrator v3 — Multi-pipeline coordination with inter-agent communication.

Orchestrates complex workflows:
  - Parallel dispatch across multiple patterns
  - Pipeline chaining with result passing
  - Conditional routing based on intermediate results
  - Aggregate consensus from multiple agents
  - Budget-aware execution (token limits, time limits)

Usage:
    from src.agent_orchestrator_v3 import Orchestrator
    orch = Orchestrator()
    result = await orch.execute("Analyse ce code et propose des optimisations", budget_s=30)
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

import httpx

from src.adaptive_router import AdaptiveRouter, get_router
from src.agent_monitor import get_monitor
from src.pattern_agents import PatternAgentRegistry, AgentResult, NODES

logger = logging.getLogger("jarvis.orchestrator_v3")


@dataclass
class StepResult:
    """Result from a single orchestration step."""
    step_name: str
    pattern: str
    node: str
    content: str
    latency_ms: float
    ok: bool
    quality: float = 0.0
    metadata: dict = field(default_factory=dict)


@dataclass
class OrchestratorResult:
    """Result from the full orchestration."""
    steps: list[StepResult]
    final_content: str
    total_latency_ms: float
    strategy_used: str
    patterns_used: list[str]
    nodes_used: list[str]
    ok: bool
    metadata: dict = field(default_factory=dict)

    @property
    def summary(self) -> str:
        nodes = ", ".join(set(self.nodes_used))
        patterns = ", ".join(set(self.patterns_used))
        return (f"{len(self.steps)} steps | {self.total_latency_ms:.0f}ms | "
                f"nodes: {nodes} | patterns: {patterns}")


@dataclass
class OrchestratorStep:
    """Definition of an orchestration step."""
    name: str
    pattern: str
    prompt_template: str       # Can reference {prev_content}, {original_prompt}
    condition: Optional[Callable[[list[StepResult]], bool]] = None
    parallel_with: list[str] = field(default_factory=list)  # Step names to run in parallel
    node_override: Optional[str] = None
    strategy_override: Optional[str] = None
    max_tokens: int = 1024
    timeout_s: float = 120  # Dynamic timeout handled by pattern_agents._calc_timeout


# ── Pre-built orchestration workflows ─────────────────────────────────────

WORKFLOWS = {
    "auto": [],  # Dynamic — orchestrator decides
    "deep-analysis": [
        OrchestratorStep("classify", "classifier", "Classifie cette tache: {original_prompt}", max_tokens=256),
        OrchestratorStep("analyze", "analysis", "Analyse en profondeur: {original_prompt}", max_tokens=2048),
        OrchestratorStep("verify", "reasoning", "Verifie cette analyse:\nQuestion: {original_prompt}\nAnalyse: {prev_content}", max_tokens=1024),
    ],
    "code-generate": [
        OrchestratorStep("plan", "reasoning", "Planifie l'implementation: {original_prompt}", max_tokens=512),
        OrchestratorStep("code", "code", "Implemente selon ce plan:\nPlan: {prev_content}\nDemande: {original_prompt}", max_tokens=2048),
        OrchestratorStep("review", "security", "Revue securite de ce code:\n{prev_content}", max_tokens=1024),
    ],
    "consensus-3": [
        OrchestratorStep("agent1", "code", "{original_prompt}", node_override="M1"),
        OrchestratorStep("agent2", "code", "{original_prompt}", node_override="OL1",
                         parallel_with=["agent1"]),
        OrchestratorStep("agent3", "code", "{original_prompt}", node_override="M2",
                         parallel_with=["agent1", "agent2"]),
    ],
    "quick-verify": [
        OrchestratorStep("answer", "simple", "{original_prompt}", max_tokens=512),
        OrchestratorStep("check", "reasoning", "Cette reponse est-elle correcte?\nQ: {original_prompt}\nR: {prev_content}",
                         max_tokens=256),
    ],
    "trading-full": [
        OrchestratorStep("technical", "trading", "Analyse technique: {original_prompt}", max_tokens=1024),
        OrchestratorStep("risk", "math", "Calcul de risque pour: {original_prompt}\nAnalyse: {prev_content}", max_tokens=512),
        OrchestratorStep("decision", "reasoning", "Decision trading basee sur:\nTechnique: {prev_content}\nDemande: {original_prompt}", max_tokens=512),
    ],
    "security-audit": [
        OrchestratorStep("scan", "security", "Audit securite: {original_prompt}", max_tokens=2048),
        OrchestratorStep("code_review", "code", "Revue code des vulnerabilites:\n{prev_content}", max_tokens=1024,
                         parallel_with=["scan"]),
        OrchestratorStep("report", "analysis", "Rapport final securite:\nScan: {prev_content}\nDemande: {original_prompt}", max_tokens=2048),
    ],
}


class Orchestrator:
    """Multi-pipeline orchestrator with adaptive routing."""

    def __init__(self):
        self.registry = PatternAgentRegistry()
        self.router = get_router()
        self.monitor = get_monitor()

    async def execute(self, prompt: str, workflow: str = "auto",
                      budget_s: float = 120, max_steps: int = 10) -> OrchestratorResult:
        """Execute an orchestration workflow."""
        t0 = time.perf_counter()

        if workflow == "auto":
            workflow = self._auto_select_workflow(prompt)

        steps_def = WORKFLOWS.get(workflow, WORKFLOWS["auto"])
        if not steps_def:
            # Auto mode: single dispatch
            return await self._execute_auto(prompt, budget_s)

        results = []
        step_results = {}  # name -> StepResult

        # Group parallel steps
        parallel_groups = self._build_parallel_groups(steps_def)

        for group in parallel_groups:
            elapsed = (time.perf_counter() - t0) * 1000
            if elapsed > budget_s * 1000:
                logger.warning(f"Budget exhausted ({elapsed:.0f}ms > {budget_s * 1000}ms)")
                break

            if len(group) == 1:
                # Sequential step
                step = group[0]
                if step.condition and not step.condition(results):
                    continue

                prompt_filled = self._fill_template(step.prompt_template, prompt, results)
                node = step.node_override or self.router.pick_node(step.pattern, prompt_filled)

                sr = await self._execute_step(step, prompt_filled, node)
                results.append(sr)
                step_results[step.name] = sr
            else:
                # Parallel steps
                tasks = []
                for step in group:
                    prompt_filled = self._fill_template(step.prompt_template, prompt, results)
                    node = step.node_override or self.router.pick_node(step.pattern, prompt_filled)
                    tasks.append(self._execute_step(step, prompt_filled, node))

                parallel_results = await asyncio.gather(*tasks)
                for step, sr in zip(group, parallel_results):
                    results.append(sr)
                    step_results[step.name] = sr

        total_ms = (time.perf_counter() - t0) * 1000

        # Build final content: last successful step or best quality
        ok_results = [r for r in results if r.ok]
        if ok_results:
            final = max(ok_results, key=lambda r: r.quality)
        elif results:
            final = results[-1]
        else:
            final = StepResult("empty", "", "", "No steps executed", 0, False)

        return OrchestratorResult(
            steps=results,
            final_content=final.content,
            total_latency_ms=total_ms,
            strategy_used=workflow,
            patterns_used=[r.pattern for r in results],
            nodes_used=[r.node for r in results],
            ok=any(r.ok for r in results),
            metadata={"budget_s": budget_s, "steps_executed": len(results)},
        )

    async def execute_consensus(self, prompt: str, nodes: list[str] = None,
                                 min_agree: int = 2) -> OrchestratorResult:
        """Execute consensus across N nodes, return weighted best."""
        t0 = time.perf_counter()
        if not nodes:
            nodes = self.router.pick_nodes("reasoning", count=3)

        async with httpx.AsyncClient() as client:
            tasks = []
            for node in nodes:
                agent = self.registry.agents.get("reasoning") or list(self.registry.agents.values())[0]
                tasks.append(agent._call_node(client, node, prompt))

            results = await asyncio.gather(*tasks, return_exceptions=True)

        step_results = []
        for node, r in zip(nodes, results):
            if isinstance(r, Exception):
                step_results.append(StepResult(f"consensus_{node}", "reasoning", node, "", 0, False))
            else:
                step_results.append(StepResult(
                    f"consensus_{node}", "reasoning", r.node,
                    r.content, r.latency_ms, r.ok, r.quality_score,
                ))
                # Record to adaptive router
                self.router.record(node, "reasoning", r.ok, r.latency_ms, r.quality_score)

        ok = [r for r in step_results if r.ok]
        total_ms = (time.perf_counter() - t0) * 1000

        if len(ok) >= min_agree:
            # Weighted selection: pick best quality * node weight
            for r in ok:
                w = NODES.get(r.node, {}).get("weight", 1.0)
                r.quality *= w
            best = max(ok, key=lambda r: r.quality)
            final = best.content
        elif ok:
            final = ok[0].content
        else:
            final = "Consensus failed — no successful responses"

        return OrchestratorResult(
            steps=step_results,
            final_content=final,
            total_latency_ms=total_ms,
            strategy_used="consensus",
            patterns_used=["reasoning"],
            nodes_used=nodes,
            ok=bool(ok),
            metadata={"min_agree": min_agree, "agreed": len(ok)},
        )

    async def execute_race(self, prompt: str, pattern: str = "code",
                           count: int = 3) -> OrchestratorResult:
        """Race N nodes, return fastest successful response."""
        t0 = time.perf_counter()
        nodes = self.router.pick_nodes(pattern, count=count)

        async with httpx.AsyncClient() as client:
            agent = self.registry.agents.get(pattern) or list(self.registry.agents.values())[0]
            tasks = [agent._call_node(client, n, prompt) for n in nodes]

            # Dynamic timeout based on pattern complexity
            race_timeout = agent._calc_timeout(nodes[0], prompt) if nodes else 120
            done, pending = await asyncio.wait(
                [asyncio.create_task(t) for t in tasks],
                return_when=asyncio.FIRST_COMPLETED,
                timeout=race_timeout,
            )

        step_results = []
        winner = None

        for task in done:
            try:
                r = task.result()
                sr = StepResult(f"race_{r.node}", pattern, r.node, r.content, r.latency_ms, r.ok, r.quality_score)
                step_results.append(sr)
                self.router.record(r.node, pattern, r.ok, r.latency_ms, r.quality_score)
                if r.ok and winner is None:
                    winner = sr
            except Exception:
                pass

        # Cancel pending
        for task in pending:
            task.cancel()

        total_ms = (time.perf_counter() - t0) * 1000

        return OrchestratorResult(
            steps=step_results,
            final_content=winner.content if winner else "Race failed",
            total_latency_ms=total_ms,
            strategy_used="race",
            patterns_used=[pattern],
            nodes_used=nodes,
            ok=winner is not None,
            metadata={"raced_nodes": nodes, "winner": winner.node if winner else None},
        )

    async def _execute_auto(self, prompt: str, budget_s: float) -> OrchestratorResult:
        """Auto mode: classify then dispatch."""
        t0 = time.perf_counter()
        pattern = self.registry.classify(prompt)
        node = self.router.pick_node(pattern, prompt)

        self.router.acquire(node)
        try:
            result = await self.registry.dispatch(pattern, prompt)
        finally:
            self.router.release(node)

        # Record
        self.router.record(node, pattern, result.ok, result.latency_ms, result.quality_score)
        self.monitor.record_dispatch(pattern, result.node, result.strategy, result.latency_ms, result.ok, result.quality_score)

        total_ms = (time.perf_counter() - t0) * 1000
        sr = StepResult("auto", pattern, result.node, result.content, result.latency_ms, result.ok, result.quality_score)

        return OrchestratorResult(
            steps=[sr],
            final_content=result.content,
            total_latency_ms=total_ms,
            strategy_used="auto",
            patterns_used=[pattern],
            nodes_used=[result.node],
            ok=result.ok,
        )

    async def _execute_step(self, step: OrchestratorStep, prompt: str, node: str) -> StepResult:
        """Execute a single orchestration step."""
        self.router.acquire(node)
        try:
            result = await self.registry.dispatch(step.pattern, prompt)
        finally:
            self.router.release(node)

        # Record
        self.router.record(node, step.pattern, result.ok, result.latency_ms, result.quality_score)
        self.monitor.record_dispatch(step.pattern, result.node, result.strategy, result.latency_ms, result.ok, result.quality_score)

        return StepResult(
            step_name=step.name,
            pattern=step.pattern,
            node=result.node,
            content=result.content,
            latency_ms=result.latency_ms,
            ok=result.ok,
            quality=result.quality_score,
        )

    def _auto_select_workflow(self, prompt: str) -> str:
        """Select best workflow based on prompt analysis."""
        prompt_lower = prompt.lower()

        # Pattern keywords -> workflow mapping
        if any(w in prompt_lower for w in ["securite", "audit", "vulnerability", "owasp", "injection"]):
            return "security-audit"
        if any(w in prompt_lower for w in ["trading", "btc", "eth", "rsi", "macd", "position"]):
            return "trading-full"
        if any(w in prompt_lower for w in ["ecris", "code", "fonction", "implemente", "script"]):
            return "code-generate"
        if any(w in prompt_lower for w in ["analyse", "compare", "benchmark", "rapport"]):
            return "deep-analysis"
        if any(w in prompt_lower for w in ["consensus", "avis", "vote", "opinion"]):
            return "consensus-3"
        # Default: quick verify for short prompts, deep analysis for long ones
        if len(prompt) < 50:
            return "quick-verify"
        return "deep-analysis"

    def _fill_template(self, template: str, original: str, prev_results: list[StepResult]) -> str:
        """Fill prompt template with context from previous steps."""
        content = prev_results[-1].content if prev_results else ""
        return template.replace("{original_prompt}", original).replace("{prev_content}", content[:2000])

    def _build_parallel_groups(self, steps: list[OrchestratorStep]) -> list[list[OrchestratorStep]]:
        """Group steps into parallel execution groups."""
        groups = []
        current_group = []
        grouped_names = set()

        for step in steps:
            if step.name in grouped_names:
                continue

            if step.parallel_with:
                # Find all parallel peers
                group = [step]
                grouped_names.add(step.name)
                for peer_name in step.parallel_with:
                    for s in steps:
                        if s.name == peer_name and s.name not in grouped_names:
                            group.append(s)
                            grouped_names.add(s.name)
                if current_group:
                    groups.append(current_group)
                    current_group = []
                groups.append(group)
            else:
                if current_group and any(s.parallel_with for s in current_group):
                    groups.append(current_group)
                    current_group = [step]
                else:
                    current_group.append(step)
                grouped_names.add(step.name)

        if current_group:
            groups.append(current_group)

        # If no parallel groups found, each step is its own group (sequential)
        if not groups:
            groups = [[s] for s in steps]

        return groups

    def list_workflows(self) -> dict:
        """List available workflows with descriptions."""
        return {
            name: {
                "steps": len(steps),
                "patterns": list(set(s.pattern for s in steps)),
                "parallel": any(s.parallel_with for s in steps),
            }
            for name, steps in WORKFLOWS.items()
            if steps  # Skip 'auto'
        }

    async def close(self):
        await self.registry.close()
