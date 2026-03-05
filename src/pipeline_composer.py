"""JARVIS Pipeline Composer — Chain multiple pattern agents in sequence.

Compose complex workflows from simple agents:
  - Sequential: A -> B -> C (each uses output of previous)
  - Parallel: A + B -> merge -> C
  - Conditional: classify -> route to branch
  - Loop: repeat until quality threshold

Usage:
    from src.pipeline_composer import PipelineComposer
    pipe = PipelineComposer()
    pipe.add_step("classify", "classifier")
    pipe.add_step("execute", "code")
    pipe.add_step("verify", "security")
    result = await pipe.run("Ecris un parser JSON securise")
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Optional, Callable

from src.pattern_agents import PatternAgentRegistry, AgentResult

logger = logging.getLogger("jarvis.pipeline")


@dataclass
class PipelineStep:
    name: str
    pattern: str  # agent pattern type
    prompt_template: str = "{input}"  # {input} = previous output, {original} = original prompt
    condition: Optional[Callable[[AgentResult], bool]] = None  # skip if False
    max_retries: int = 1
    timeout_s: float = 60


@dataclass
class PipelineResult:
    steps: list[dict]
    final_output: str
    total_ms: float
    ok: bool
    pipeline_name: str = ""


class PipelineComposer:
    """Compose multi-agent pipelines."""

    def __init__(self):
        self.steps: list[PipelineStep] = []
        self.registry = PatternAgentRegistry()
        self.name = ""

    def add_step(self, name: str, pattern: str, prompt_template: str = "{input}",
                 condition: Optional[Callable] = None, max_retries: int = 1) -> "PipelineComposer":
        self.steps.append(PipelineStep(
            name=name, pattern=pattern, prompt_template=prompt_template,
            condition=condition, max_retries=max_retries,
        ))
        return self

    async def run(self, original_prompt: str) -> PipelineResult:
        """Execute the pipeline sequentially."""
        t_start = time.perf_counter()
        results = []
        current_input = original_prompt

        for step in self.steps:
            # Check condition
            if step.condition and results:
                last_result = results[-1].get("agent_result")
                if last_result and not step.condition(last_result):
                    results.append({
                        "step": step.name, "pattern": step.pattern,
                        "skipped": True, "reason": "condition not met",
                    })
                    continue

            # Build prompt
            prompt = step.prompt_template.replace("{input}", current_input[:2000])
            prompt = prompt.replace("{original}", original_prompt[:1000])

            # Execute with retries
            for attempt in range(step.max_retries):
                result = await self.registry.dispatch(step.pattern, prompt)
                if result.ok:
                    break

            step_info = {
                "step": step.name,
                "pattern": step.pattern,
                "node": result.node,
                "latency_ms": round(result.latency_ms),
                "tokens": result.tokens,
                "quality": result.quality_score,
                "ok": result.ok,
                "output_preview": result.content[:200] if result.ok else result.error[:100],
                "agent_result": result,
            }
            results.append(step_info)

            if result.ok:
                current_input = result.content
            else:
                # Pipeline fails on first error
                total_ms = (time.perf_counter() - t_start) * 1000
                return PipelineResult(
                    steps=[{k: v for k, v in s.items() if k != "agent_result"} for s in results],
                    final_output=f"Pipeline failed at step '{step.name}': {result.error}",
                    total_ms=total_ms, ok=False, pipeline_name=self.name,
                )

        total_ms = (time.perf_counter() - t_start) * 1000
        return PipelineResult(
            steps=[{k: v for k, v in s.items() if k != "agent_result"} for s in results],
            final_output=current_input,
            total_ms=total_ms, ok=True, pipeline_name=self.name,
        )

    async def close(self):
        await self.registry.close()


# ── Pre-built Pipelines ────────────────────────────────────────────────────

def code_review_pipeline() -> PipelineComposer:
    """Code -> Security Audit -> Architecture Review."""
    pipe = PipelineComposer()
    pipe.name = "code-review"
    pipe.add_step("generate", "code", "{input}")
    pipe.add_step("security", "security",
                  "Audite ce code pour vulnerabilites OWASP:\n{input}")
    pipe.add_step("review", "analysis",
                  "Analyse la qualite de ce code et propose des ameliorations:\n{input}")
    return pipe


def smart_qa_pipeline() -> PipelineComposer:
    """Classify -> Route to best agent -> Verify."""
    pipe = PipelineComposer()
    pipe.name = "smart-qa"
    pipe.add_step("classify", "classifier",
                  "Classifie cette demande et identifie le type: {input}")
    pipe.add_step("answer", "analysis", "{original}")
    pipe.add_step("verify", "reasoning",
                  "Verifie cette reponse. Si correcte dis 'VALIDE'. Sinon corrige:\nQuestion: {original}\nReponse: {input}")
    return pipe


def trading_analysis_pipeline() -> PipelineComposer:
    """Technical Analysis -> Risk Assessment -> Decision."""
    pipe = PipelineComposer()
    pipe.name = "trading-analysis"
    pipe.add_step("technical", "trading",
                  "Analyse technique detaillee: {input}")
    pipe.add_step("risk", "math",
                  "Calcule le risk/reward et les probabilites pour:\n{input}")
    pipe.add_step("decision", "analysis",
                  "Resume l'analyse et donne une recommandation (BUY/SELL/HOLD) avec score de confiance:\n{input}")
    return pipe


def architecture_design_pipeline() -> PipelineComposer:
    """Requirements -> Architecture -> Security Audit -> Code Skeleton."""
    pipe = PipelineComposer()
    pipe.name = "architecture-design"
    pipe.add_step("requirements", "analysis",
                  "Analyse les besoins et contraintes:\n{input}")
    pipe.add_step("design", "architecture",
                  "Design l'architecture complete basee sur ces besoins:\n{input}")
    pipe.add_step("security", "security",
                  "Audite cette architecture pour failles de securite:\n{input}")
    pipe.add_step("skeleton", "code",
                  "Genere le squelette de code Python pour cette architecture:\n{input}")
    return pipe


def devops_deploy_pipeline() -> PipelineComposer:
    """Code -> Docker -> CI/CD -> Monitoring."""
    pipe = PipelineComposer()
    pipe.name = "devops-deploy"
    pipe.add_step("dockerfile", "devops",
                  "Ecris un Dockerfile multi-stage pour:\n{input}")
    pipe.add_step("ci", "devops",
                  "Ecris un workflow GitHub Actions CI/CD pour ce projet:\n{input}")
    pipe.add_step("monitoring", "system",
                  "Ecris un script de health check et monitoring pour:\n{input}")
    return pipe


# Registry of pre-built pipelines
PIPELINES = {
    "code-review": code_review_pipeline,
    "smart-qa": smart_qa_pipeline,
    "trading-analysis": trading_analysis_pipeline,
    "architecture-design": architecture_design_pipeline,
    "devops-deploy": devops_deploy_pipeline,
}


async def run_pipeline(name: str, prompt: str) -> PipelineResult:
    """Run a named pre-built pipeline."""
    factory = PIPELINES.get(name)
    if not factory:
        return PipelineResult(
            steps=[], final_output=f"Unknown pipeline: {name}. Available: {list(PIPELINES.keys())}",
            total_ms=0, ok=False, pipeline_name=name,
        )
    pipe = factory()
    result = await pipe.run(prompt)
    await pipe.close()
    return result


# CLI
async def _main():
    import sys
    if len(sys.argv) < 3:
        print(f"Usage: pipeline_composer.py <pipeline> <prompt>")
        print(f"Pipelines: {list(PIPELINES.keys())}")
        return

    name = sys.argv[1]
    prompt = " ".join(sys.argv[2:])
    result = await run_pipeline(name, prompt)

    print(f"\n{'='*60}")
    print(f"Pipeline: {result.pipeline_name}")
    print(f"OK: {result.ok} | Total: {result.total_ms:.0f}ms")
    print(f"Steps: {len(result.steps)}")
    for s in result.steps:
        status = "SKIP" if s.get("skipped") else ("OK" if s.get("ok") else "FAIL")
        print(f"  [{status}] {s['step']} ({s.get('pattern','?')}) {s.get('latency_ms',0)}ms Q={s.get('quality',0):.2f}")
    print(f"\nOutput:\n{result.final_output[:500]}")

if __name__ == "__main__":
    asyncio.run(_main())
