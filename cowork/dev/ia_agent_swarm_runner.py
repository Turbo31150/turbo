#!/usr/bin/env python3
"""ia_agent_swarm_runner.py — Activate IA agent swarm.

Orchestrates ~50 ia_*.py specialized agents from the cowork/dev directory.
Categories: coders, reasoners, analysts, spawners, optimizers, monitors, utilities.

Usage:
    python ia_agent_swarm_runner.py --once              # Activate all agents once
    python ia_agent_swarm_runner.py --list              # List available agents with categories
    python ia_agent_swarm_runner.py --dry-run           # Show what would run without executing
    python ia_agent_swarm_runner.py --parallel 5        # Run 5 agents simultaneously
    python ia_agent_swarm_runner.py --category coders   # Run only coder agents
    python ia_agent_swarm_runner.py --timeout 90        # Override default 60s timeout
    python ia_agent_swarm_runner.py --json              # Output results as JSON
    python ia_agent_swarm_runner.py --exclude ia_self_improver.py,ia_cost_tracker.py
"""
import argparse
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SELF_NAME = Path(__file__).name

# ---------------------------------------------------------------------------
# Category classification based on script name keywords
# ---------------------------------------------------------------------------
CATEGORY_RULES = {
    "coders": [
        "code_generator", "code_generator_v2", "autonomous_coder",
        "test_generator", "test_writer", "doc_generator", "doc_writer",
    ],
    "reasoners": [
        "chain_of_thought", "chain_of_thought_v2", "hypothesis_tester",
        "debate_engine", "self_critic", "fact_checker",
    ],
    "analysts": [
        "error_analyzer", "anomaly_detector", "inference_profiler",
        "model_benchmarker", "peer_reviewer", "pattern_detector",
    ],
    "optimizers": [
        "meta_optimizer", "prompt_optimizer", "routing_optimizer",
        "weight_calibrator", "self_improver", "context_compressor",
    ],
    "planners": [
        "task_planner", "task_prioritizer", "goal_decomposer",
        "goal_tracker", "curriculum_planner",
    ],
    "spawners": [
        "agent_spawner", "swarm_coordinator", "workload_balancer",
        "ensemble_voter",
    ],
    "knowledge": [
        "knowledge_distiller", "knowledge_graph", "memory_consolidator",
        "transfer_learner", "data_synthesizer",
    ],
    "monitors": [
        "cost_tracker", "capability_tracker", "usage_predictor",
        "feedback_loop", "proactive_agent",
    ],
    "creative": [
        "story_generator", "image_prompt_crafter", "skill_synthesizer",
    ],
    "infrastructure": [
        "model_cache_manager", "experiment_runner", "teacher_student",
    ],
}

# Flatten for reverse lookup: keyword -> category
_KEYWORD_TO_CATEGORY = {}
for cat, keywords in CATEGORY_RULES.items():
    for kw in keywords:
        _KEYWORD_TO_CATEGORY[kw] = cat


def classify_agent(script_name: str) -> str:
    """Return the category for a given ia_*.py script name."""
    # Strip prefix and suffix: ia_code_generator.py -> code_generator
    stem = script_name.replace("ia_", "").replace(".py", "")
    if stem in _KEYWORD_TO_CATEGORY:
        return _KEYWORD_TO_CATEGORY[stem]
    # Fallback heuristic on partial matches
    for kw, cat in _KEYWORD_TO_CATEGORY.items():
        if kw in stem or stem in kw:
            return cat
    return "uncategorized"


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------
def discover_agents(exclude_self: bool = True) -> list[Path]:
    """Find all ia_*.py scripts in SCRIPT_DIR, excluding this runner."""
    agents = sorted(SCRIPT_DIR.glob("ia_*.py"))
    if exclude_self:
        agents = [a for a in agents if a.name != SELF_NAME]
    return agents


def build_agent_registry(agents: list[Path]) -> list[dict]:
    """Build a registry with name, path, and category for each agent."""
    registry = []
    for agent in agents:
        registry.append({
            "name": agent.stem,
            "file": agent.name,
            "path": str(agent),
            "category": classify_agent(agent.name),
        })
    return registry


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------
def run_agent(script: Path, timeout: int = 60) -> dict:
    """Run a single agent script with --once flag. Returns result dict."""
    cmd = [sys.executable, str(script), "--once"]
    start = time.time()
    result = {
        "script": script.name,
        "category": classify_agent(script.name),
        "success": False,
        "returncode": -1,
        "duration_ms": 0,
        "output": "",
        "error": "",
        "status": "unknown",
    }
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(SCRIPT_DIR),
            env={**dict(__import__("os").environ), "PYTHONIOENCODING": "utf-8"},
        )
        elapsed = int((time.time() - start) * 1000)
        result["success"] = proc.returncode == 0
        result["returncode"] = proc.returncode
        result["duration_ms"] = elapsed
        # Keep last 500 chars of stdout/stderr for summary
        result["output"] = (proc.stdout or "")[-500:].strip()
        result["error"] = (proc.stderr or "")[-500:].strip()
        result["status"] = "ok" if proc.returncode == 0 else f"exit({proc.returncode})"
    except subprocess.TimeoutExpired:
        result["duration_ms"] = timeout * 1000
        result["status"] = "TIMEOUT"
        result["error"] = f"Killed after {timeout}s timeout"
    except FileNotFoundError:
        result["status"] = "NOT_FOUND"
        result["error"] = f"Python executable or script not found"
    except PermissionError:
        result["status"] = "PERMISSION_DENIED"
        result["error"] = "Permission denied"
    except Exception as e:
        result["duration_ms"] = int((time.time() - start) * 1000)
        result["status"] = "ERROR"
        result["error"] = str(e)[:500]
    return result


def run_swarm(
    agents: list[Path],
    parallel: int = 3,
    timeout: int = 60,
    dry_run: bool = False,
    verbose: bool = False,
) -> list[dict]:
    """Run all agents with controlled parallelism. Returns list of results."""
    total = len(agents)
    if dry_run:
        results = []
        for i, agent in enumerate(agents, 1):
            cat = classify_agent(agent.name)
            print(f"  [{i:>3}/{total}] [DRY-RUN] {agent.name:<45} ({cat})")
            results.append({
                "script": agent.name,
                "category": cat,
                "success": True,
                "status": "dry-run",
                "duration_ms": 0,
                "output": "",
                "error": "",
            })
        return results

    results = []
    completed = 0
    start_all = time.time()

    print(f"\n  Swarm activation: {total} agents, {parallel} parallel, {timeout}s timeout\n")

    with ThreadPoolExecutor(max_workers=parallel) as executor:
        future_to_agent = {
            executor.submit(run_agent, agent, timeout): agent
            for agent in agents
        }
        for future in as_completed(future_to_agent):
            completed += 1
            res = future.result()
            results.append(res)

            # Status indicator
            if res["success"]:
                tag = "  OK "
            elif res["status"] == "TIMEOUT":
                tag = " T/O "
            else:
                tag = "FAIL "

            elapsed_s = res["duration_ms"] / 1000
            print(
                f"  [{completed:>3}/{total}] [{tag}] "
                f"{res['script']:<45} {elapsed_s:>6.1f}s  ({res['category']})"
            )
            if verbose and res["error"]:
                for line in res["error"].split("\n")[-3:]:
                    print(f"           | {line}")

    total_time = time.time() - start_all
    print(f"\n  Total wall time: {total_time:.1f}s")
    return results


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------
def print_list(registry: list[dict]) -> None:
    """Print the agent registry grouped by category."""
    from collections import defaultdict
    by_cat = defaultdict(list)
    for entry in registry:
        by_cat[entry["category"]].append(entry)

    print(f"\n  IA Agent Swarm — {len(registry)} agents discovered\n")
    print(f"  {'Category':<18} {'Count':>5}   Agents")
    print(f"  {'-'*18} {'-'*5}   {'-'*50}")

    for cat in sorted(by_cat.keys()):
        agents_in_cat = by_cat[cat]
        names = ", ".join(a["name"].replace("ia_", "") for a in agents_in_cat)
        print(f"  {cat:<18} {len(agents_in_cat):>5}   {names}")

    print()


def print_summary(results: list[dict], as_json: bool = False) -> None:
    """Print execution summary."""
    if as_json:
        summary = {
            "timestamp": datetime.now().isoformat(),
            "total": len(results),
            "success": sum(1 for r in results if r["success"]),
            "failed": sum(1 for r in results if not r["success"]),
            "timeout": sum(1 for r in results if r["status"] == "TIMEOUT"),
            "avg_duration_ms": (
                int(sum(r["duration_ms"] for r in results) / len(results))
                if results else 0
            ),
            "results": results,
        }
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return

    total = len(results)
    ok = sum(1 for r in results if r["success"])
    failed = sum(1 for r in results if not r["success"])
    timeouts = sum(1 for r in results if r["status"] == "TIMEOUT")
    avg_ms = int(sum(r["duration_ms"] for r in results) / total) if total else 0
    max_ms = max((r["duration_ms"] for r in results), default=0)
    min_ms = min((r["duration_ms"] for r in results if r["duration_ms"] > 0), default=0)

    print("\n" + "=" * 72)
    print("  SWARM EXECUTION SUMMARY")
    print("=" * 72)
    print(f"  Timestamp : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Total     : {total} agents")
    print(f"  Success   : {ok} ({ok*100//total if total else 0}%)")
    print(f"  Failed    : {failed}")
    print(f"  Timeouts  : {timeouts}")
    print(f"  Avg time  : {avg_ms}ms")
    print(f"  Min/Max   : {min_ms}ms / {max_ms}ms")

    # Per-category breakdown
    from collections import defaultdict
    by_cat = defaultdict(lambda: {"ok": 0, "fail": 0, "total": 0, "ms": 0})
    for r in results:
        cat = r.get("category", "uncategorized")
        by_cat[cat]["total"] += 1
        by_cat[cat]["ms"] += r["duration_ms"]
        if r["success"]:
            by_cat[cat]["ok"] += 1
        else:
            by_cat[cat]["fail"] += 1

    print(f"\n  {'Category':<18} {'OK':>4} {'Fail':>5} {'Total':>6} {'Avg ms':>8}")
    print(f"  {'-'*18} {'-'*4} {'-'*5} {'-'*6} {'-'*8}")
    for cat in sorted(by_cat.keys()):
        s = by_cat[cat]
        avg = s["ms"] // s["total"] if s["total"] else 0
        print(f"  {cat:<18} {s['ok']:>4} {s['fail']:>5} {s['total']:>6} {avg:>8}")

    # List failures
    failures = [r for r in results if not r["success"]]
    if failures:
        print(f"\n  FAILURES ({len(failures)}):")
        for r in failures:
            err_line = (r["error"] or r["output"] or "no output").split("\n")[-1][:80]
            print(f"    - {r['script']:<40} [{r['status']}] {err_line}")

    print("=" * 72 + "\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="IA Agent Swarm Runner — orchestrate ~50 ia_*.py agents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python ia_agent_swarm_runner.py --once
  python ia_agent_swarm_runner.py --list
  python ia_agent_swarm_runner.py --dry-run
  python ia_agent_swarm_runner.py --once --parallel 5 --timeout 90
  python ia_agent_swarm_runner.py --once --category coders
  python ia_agent_swarm_runner.py --once --exclude ia_self_improver.py
  python ia_agent_swarm_runner.py --once --json
""",
    )
    parser.add_argument("--once", action="store_true",
                        help="Activate all agents once (default action)")
    parser.add_argument("--list", action="store_true",
                        help="List available agents with categories")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would run without executing")
    parser.add_argument("--parallel", "-p", type=int, default=3,
                        help="Max agents to run simultaneously (default: 3)")
    parser.add_argument("--timeout", "-t", type=int, default=60,
                        help="Timeout per agent in seconds (default: 60)")
    parser.add_argument("--category", "-c", type=str, default=None,
                        help="Run only agents in this category")
    parser.add_argument("--exclude", "-x", type=str, default=None,
                        help="Comma-separated list of script filenames to exclude")
    parser.add_argument("--include", "-i", type=str, default=None,
                        help="Comma-separated list of script filenames to run (only these)")
    parser.add_argument("--json", action="store_true",
                        help="Output results as JSON")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Show error details during execution")

    args = parser.parse_args()

    # If no action specified, default to --once
    if not args.list and not args.dry_run and not args.once:
        args.once = True

    # Discover agents
    agents = discover_agents()
    registry = build_agent_registry(agents)

    # Filter by category
    if args.category:
        cat_lower = args.category.lower()
        registry = [r for r in registry if r["category"] == cat_lower]
        agents = [Path(r["path"]) for r in registry]
        if not agents:
            valid = sorted(set(r["category"] for r in build_agent_registry(discover_agents())))
            print(f"  No agents in category '{args.category}'. Valid: {', '.join(valid)}")
            sys.exit(1)

    # Filter by --include
    if args.include:
        include_set = set(s.strip() for s in args.include.split(","))
        agents = [a for a in agents if a.name in include_set or a.stem in include_set]
        registry = [r for r in registry if r["file"] in include_set or r["name"] in include_set]

    # Filter by --exclude
    if args.exclude:
        exclude_set = set(s.strip() for s in args.exclude.split(","))
        agents = [a for a in agents if a.name not in exclude_set and a.stem not in exclude_set]
        registry = [r for r in registry if r["file"] not in exclude_set and r["name"] not in exclude_set]

    # List mode
    if args.list:
        print_list(registry)
        return

    # Dry-run or execution
    if args.dry_run:
        print(f"\n  DRY RUN — {len(agents)} agents would be activated:\n")
        results = run_swarm(agents, dry_run=True)
        print(f"\n  {len(results)} agents listed (no execution)\n")
        return

    # Execute swarm
    if args.once:
        if not agents:
            print("  No agents to run.")
            sys.exit(0)
        results = run_swarm(
            agents,
            parallel=args.parallel,
            timeout=args.timeout,
            verbose=args.verbose,
        )
        print_summary(results, as_json=args.json)

        # Exit code reflects failures
        failures = sum(1 for r in results if not r["success"])
        sys.exit(min(failures, 125))  # cap at 125 to stay in valid exit code range


if __name__ == "__main__":
    main()
