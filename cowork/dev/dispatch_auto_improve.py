#!/usr/bin/env python3
"""Dispatch Auto-Improver — Self-improving dispatch loop.

Combines:
  1. Quality gate auto-tune (relax strict thresholds)
  2. Self-improvement analysis (detect bad patterns, suggest route shifts)
  3. Strategy auto-optimize (switch strategies based on historical data)
  4. Quick benchmark (validate improvements)

Designed to run as a cron every 30min for continuous improvement.

Usage:
    python dev/dispatch_auto_improve.py --once
    python dev/dispatch_auto_improve.py --help
"""

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

# Fix Windows cp1252 encoding
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


async def run_improvement_cycle():
    results = {"timestamp": time.strftime("%Y-%m-%d %H:%M:%S"), "steps": []}

    # Step 1: Quality gate auto-tune
    try:
        from src.quality_gate import get_gate
        gate = get_gate()
        tune_result = gate.auto_tune_from_data(min_samples=5)
        results["steps"].append({
            "step": "quality_gate_auto_tune",
            "changes": tune_result,
            "ok": "error" not in tune_result,
        })
    except Exception as e:
        results["steps"].append({"step": "quality_gate_auto_tune", "error": str(e), "ok": False})

    # Step 2: Self-improvement analysis + auto-apply
    try:
        from src.self_improvement import get_improver
        imp = get_improver()
        suggestions = imp.suggest_improvements()
        applied = imp.apply_improvements(auto=True, max_actions=5)
        results["steps"].append({
            "step": "self_improvement",
            "suggestions": len(suggestions),
            "applied": len(applied),
            "details": [{"type": a.get("action_type", "?"), "target": a.get("target", "?")} for a in applied[:5]],
            "ok": True,
        })
    except Exception as e:
        results["steps"].append({"step": "self_improvement", "error": str(e), "ok": False})

    # Step 3: Strategy auto-optimize
    try:
        from src.pattern_agents import PatternAgentRegistry
        reg = PatternAgentRegistry()
        changes = reg.auto_optimize_strategies()
        results["steps"].append({
            "step": "strategy_auto_optimize",
            "changes": changes,
            "ok": "error" not in changes,
        })
    except Exception as e:
        results["steps"].append({"step": "strategy_auto_optimize", "error": str(e), "ok": False})

    # Step 4: Quick benchmark (5 critical patterns)
    try:
        import httpx
        from src.pattern_agents import PatternAgentRegistry
        reg = PatternAgentRegistry()
        bench_prompts = {
            "architecture": "Design un systeme event-driven",
            "security": "Audit: query = f'SELECT * FROM users WHERE id={uid}'",
            "analysis": "Compare REST vs GraphQL vs gRPC",
            "code": "Ecris un parser CSV en Python avec gestion d'erreurs",
            "reasoning": "Prouve que la racine de 2 est irrationnelle",
        }
        bench_results = []
        async with httpx.AsyncClient() as client:
            for pat, prompt in bench_prompts.items():
                agent = reg.agents.get(pat)
                if agent:
                    try:
                        r = await agent.execute(client, prompt)
                        bench_results.append({"pattern": pat, "ok": r.ok, "node": r.node, "ms": round(r.latency_ms)})
                    except Exception as e:
                        bench_results.append({"pattern": pat, "ok": False, "error": str(e)[:80]})

        ok = sum(1 for r in bench_results if r.get("ok"))
        results["steps"].append({
            "step": "quick_benchmark",
            "ok_count": ok,
            "total": len(bench_results),
            "rate": f"{ok/max(1,len(bench_results))*100:.0f}%",
            "results": bench_results,
            "ok": ok == len(bench_results),
        })
    except Exception as e:
        results["steps"].append({"step": "quick_benchmark", "error": str(e), "ok": False})

    # Summary
    all_ok = all(s.get("ok", False) for s in results["steps"])
    results["overall_ok"] = all_ok
    results["steps_ok"] = sum(1 for s in results["steps"] if s.get("ok", False))
    results["steps_total"] = len(results["steps"])

    print(json.dumps(results, ensure_ascii=False, indent=2))
    return results


def main():
    parser = argparse.ArgumentParser(description="Dispatch auto-improvement cycle")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument("--json", action="store_true", help="JSON output only")
    args = parser.parse_args()

    asyncio.run(run_improvement_cycle())


if __name__ == "__main__":
    main()
