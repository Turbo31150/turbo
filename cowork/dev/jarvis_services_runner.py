#!/usr/bin/env python3
"""jarvis_services_runner.py — Orchestrate orphan jarvis_* service scripts.

Discovers and runs all jarvis_*.py scripts in cowork/dev/ that are NOT
already managed by another orchestrator (self_evolve, night_ops, mega_runner,
brain).  Scripts are classified into 4 groups: core, analytics, tools,
creative.

Usage:
    python jarvis_services_runner.py --once              # Run all services once
    python jarvis_services_runner.py --list              # List services with categories
    python jarvis_services_runner.py --dry-run           # Show plan without executing
    python jarvis_services_runner.py --category core     # Run only core services
    python jarvis_services_runner.py --parallel 3        # 3 concurrent workers (default)
    python jarvis_services_runner.py --timeout 120       # Per-script timeout (default 120s)
    python jarvis_services_runner.py --json              # Output results as JSON
    python jarvis_services_runner.py --once --category analytics --json
"""

import argparse
import json
import os
import subprocess
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SELF_NAME = Path(__file__).name

# ── Scripts already managed by other orchestrators — always excluded ─────────
ORCHESTRATOR_MANAGED = {
    "jarvis_self_evolve.py",
    "jarvis_night_ops.py",
    "jarvis_mega_runner.py",
    "jarvis_brain.py",
}

# ── Category definitions (explicit mapping) ──────────────────────────────────
CATEGORIES: dict[str, list[str]] = {
    "core": [
        "jarvis_state_machine",
        "jarvis_dialog_manager",
        "jarvis_intent_classifier",
        "jarvis_message_router",
        "jarvis_event_stream",
    ],
    "analytics": [
        "jarvis_response_profiler",
        "jarvis_log_analyzer",
        "jarvis_health_aggregator",
        "jarvis_meta_dashboard",
        "jarvis_ecosystem_map",
    ],
    "tools": [
        "jarvis_code_auditor",
        "jarvis_config_validator",
        "jarvis_cron_optimizer",
        "jarvis_ab_tester",
        "jarvis_self_test_suite",
    ],
    "creative": [
        "jarvis_daily_briefing",
        "jarvis_dictation_mode",
        "jarvis_embedding_engine",
        "jarvis_evolution_engine",
        "jarvis_macro_recorder",
        "jarvis_api_gateway",
    ],
}

# Build reverse lookup: stem -> category
_STEM_TO_CATEGORY: dict[str, str] = {}
for _cat, _stems in CATEGORIES.items():
    for _stem in _stems:
        _STEM_TO_CATEGORY[_stem] = _cat


def classify_service(filename: str) -> str:
    """Return the category for a jarvis_*.py script (or 'uncategorized')."""
    stem = filename.replace(".py", "")
    if stem in _STEM_TO_CATEGORY:
        return _STEM_TO_CATEGORY[stem]
    # Heuristic fallback based on keywords
    name_lower = stem.lower()
    if any(kw in name_lower for kw in ("state", "dialog", "intent", "router", "event", "message")):
        return "core"
    if any(kw in name_lower for kw in ("profiler", "log", "health", "dashboard", "map", "analytics", "monitor", "tracker")):
        return "analytics"
    if any(kw in name_lower for kw in ("audit", "config", "cron", "test", "validator", "scanner", "checker")):
        return "tools"
    return "creative"


# ── Discovery ────────────────────────────────────────────────────────────────

def discover_services() -> list[Path]:
    """Find all jarvis_*.py in SCRIPT_DIR, excluding self and orchestrator-managed."""
    all_scripts = sorted(SCRIPT_DIR.glob("jarvis_*.py"))
    excluded = ORCHESTRATOR_MANAGED | {SELF_NAME}
    return [s for s in all_scripts if s.name not in excluded]


def build_registry(scripts: list[Path]) -> list[dict]:
    """Build a registry entry per script: name, file, path, category."""
    return [
        {
            "name": s.stem,
            "file": s.name,
            "path": str(s),
            "category": classify_service(s.name),
        }
        for s in scripts
    ]


# ── Execution ────────────────────────────────────────────────────────────────

def run_service(script: Path, timeout: int = 120) -> dict:
    """Execute a single jarvis_*.py with --once.  Returns result dict."""
    cmd = [sys.executable, str(script), "--once"]
    start = time.time()
    result = {
        "script": script.name,
        "category": classify_service(script.name),
        "success": False,
        "returncode": -1,
        "duration_ms": 0,
        "output": "",
        "error": "",
        "status": "unknown",
        "timestamp": datetime.now().isoformat(),
    }
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(SCRIPT_DIR),
            env={**dict(os.environ), "PYTHONIOENCODING": "utf-8"},
        )
        elapsed = int((time.time() - start) * 1000)
        result["success"] = proc.returncode == 0
        result["returncode"] = proc.returncode
        result["duration_ms"] = elapsed
        result["output"] = (proc.stdout or "")[-500:].strip()
        result["error"] = (proc.stderr or "")[-500:].strip()
        result["status"] = "ok" if proc.returncode == 0 else f"exit({proc.returncode})"
    except subprocess.TimeoutExpired:
        result["duration_ms"] = timeout * 1000
        result["status"] = "TIMEOUT"
        result["error"] = f"Killed after {timeout}s timeout"
    except FileNotFoundError:
        result["status"] = "NOT_FOUND"
        result["error"] = "Python executable or script not found"
    except PermissionError:
        result["status"] = "PERMISSION_DENIED"
        result["error"] = "Permission denied"
    except Exception as exc:
        result["duration_ms"] = int((time.time() - start) * 1000)
        result["status"] = "ERROR"
        result["error"] = str(exc)[:500]
    return result


def run_all(
    scripts: list[Path],
    parallel: int = 3,
    timeout: int = 120,
    dry_run: bool = False,
    verbose: bool = False,
) -> list[dict]:
    """Run services with controlled parallelism via ThreadPoolExecutor."""
    total = len(scripts)

    if dry_run:
        results = []
        for i, s in enumerate(scripts, 1):
            cat = classify_service(s.name)
            print(f"  [{i:>3}/{total}] [DRY-RUN] {s.name:<50} ({cat})")
            results.append({
                "script": s.name,
                "category": cat,
                "success": True,
                "status": "dry-run",
                "duration_ms": 0,
                "output": "",
                "error": "",
                "timestamp": datetime.now().isoformat(),
            })
        return results

    results: list[dict] = []
    completed = 0
    wall_start = time.time()

    print(f"\n  JARVIS Services Runner: {total} scripts, {parallel} parallel, {timeout}s timeout\n")

    with ThreadPoolExecutor(max_workers=parallel) as pool:
        futures = {
            pool.submit(run_service, s, timeout): s
            for s in scripts
        }
        for future in as_completed(futures):
            completed += 1
            res = future.result()
            results.append(res)

            if res["success"]:
                tag = "  OK "
            elif res["status"] == "TIMEOUT":
                tag = " T/O "
            else:
                tag = "FAIL "

            elapsed_s = res["duration_ms"] / 1000
            print(
                f"  [{completed:>3}/{total}] [{tag}] "
                f"{res['script']:<50} {elapsed_s:>6.1f}s  ({res['category']})"
            )
            if verbose and res["error"]:
                for line in res["error"].split("\n")[-3:]:
                    print(f"           | {line}")

    wall_time = time.time() - wall_start
    print(f"\n  Total wall time: {wall_time:.1f}s")
    return results


# ── Display helpers ──────────────────────────────────────────────────────────

def print_list(registry: list[dict]) -> None:
    """Print registry grouped by category."""
    by_cat: dict[str, list[dict]] = defaultdict(list)
    for entry in registry:
        by_cat[entry["category"]].append(entry)

    print(f"\n  JARVIS Services — {len(registry)} scripts discovered")
    print(f"  Excluded (orchestrator-managed): {', '.join(sorted(ORCHESTRATOR_MANAGED))}\n")
    print(f"  {'Category':<18} {'Count':>5}   Scripts")
    print(f"  {'-' * 18} {'-' * 5}   {'-' * 55}")

    for cat in ("core", "analytics", "tools", "creative", "uncategorized"):
        if cat not in by_cat:
            continue
        items = by_cat[cat]
        names = ", ".join(e["name"].replace("jarvis_", "") for e in items)
        print(f"  {cat:<18} {len(items):>5}   {names}")

    print()


def print_summary(results: list[dict], as_json: bool = False) -> None:
    """Print or dump execution summary."""
    total = len(results)
    ok = sum(1 for r in results if r["success"])
    failed = sum(1 for r in results if not r["success"])
    timeouts = sum(1 for r in results if r["status"] == "TIMEOUT")
    avg_ms = int(sum(r["duration_ms"] for r in results) / total) if total else 0

    if as_json:
        summary = {
            "runner": "jarvis_services_runner",
            "timestamp": datetime.now().isoformat(),
            "total": total,
            "success": ok,
            "failed": failed,
            "timeout": timeouts,
            "avg_duration_ms": avg_ms,
            "categories": {},
            "results": results,
        }
        by_cat: dict[str, dict] = defaultdict(lambda: {"ok": 0, "fail": 0, "total": 0, "ms": 0})
        for r in results:
            c = r.get("category", "uncategorized")
            by_cat[c]["total"] += 1
            by_cat[c]["ms"] += r["duration_ms"]
            by_cat[c]["ok" if r["success"] else "fail"] += 1
        summary["categories"] = dict(by_cat)
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return

    max_ms = max((r["duration_ms"] for r in results), default=0)
    min_ms = min((r["duration_ms"] for r in results if r["duration_ms"] > 0), default=0)

    print("\n" + "=" * 76)
    print("  JARVIS SERVICES — EXECUTION SUMMARY")
    print("=" * 76)
    print(f"  Timestamp : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Total     : {total} scripts")
    print(f"  Success   : {ok} ({ok * 100 // total if total else 0}%)")
    print(f"  Failed    : {failed}")
    print(f"  Timeouts  : {timeouts}")
    print(f"  Avg time  : {avg_ms}ms")
    print(f"  Min/Max   : {min_ms}ms / {max_ms}ms")

    # Per-category breakdown
    by_cat2: dict[str, dict] = defaultdict(lambda: {"ok": 0, "fail": 0, "total": 0, "ms": 0})
    for r in results:
        c = r.get("category", "uncategorized")
        by_cat2[c]["total"] += 1
        by_cat2[c]["ms"] += r["duration_ms"]
        by_cat2[c]["ok" if r["success"] else "fail"] += 1

    print(f"\n  {'Category':<18} {'OK':>4} {'Fail':>5} {'Total':>6} {'Avg ms':>8}")
    print(f"  {'-' * 18} {'-' * 4} {'-' * 5} {'-' * 6} {'-' * 8}")
    for cat in ("core", "analytics", "tools", "creative", "uncategorized"):
        if cat not in by_cat2:
            continue
        s = by_cat2[cat]
        avg = s["ms"] // s["total"] if s["total"] else 0
        print(f"  {cat:<18} {s['ok']:>4} {s['fail']:>5} {s['total']:>6} {avg:>8}")

    # List failures
    failures = [r for r in results if not r["success"]]
    if failures:
        print(f"\n  FAILURES ({len(failures)}):")
        for r in failures:
            err_line = (r["error"] or r["output"] or "no output").split("\n")[-1][:80]
            print(f"    - {r['script']:<45} [{r['status']}] {err_line}")

    print("=" * 76 + "\n")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="JARVIS Services Runner — orchestrate orphan jarvis_*.py scripts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python jarvis_services_runner.py --once
  python jarvis_services_runner.py --list
  python jarvis_services_runner.py --dry-run
  python jarvis_services_runner.py --once --category core --parallel 5
  python jarvis_services_runner.py --once --timeout 180 --json
""",
    )
    parser.add_argument("--once", action="store_true",
                        help="Run all services once (default action)")
    parser.add_argument("--list", action="store_true",
                        help="List discovered services with categories")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show plan without executing anything")
    parser.add_argument("--parallel", "-p", type=int, default=3,
                        help="Max concurrent workers (default: 3)")
    parser.add_argument("--timeout", "-t", type=int, default=120,
                        help="Per-script timeout in seconds (default: 120)")
    parser.add_argument("--category", "-c", type=str, default=None,
                        choices=["core", "analytics", "tools", "creative"],
                        help="Run only scripts in this category")
    parser.add_argument("--json", action="store_true",
                        help="Output results as JSON")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Show error details during execution")

    args = parser.parse_args()

    # Default to --once when no mode specified
    if not args.list and not args.dry_run and not args.once:
        args.once = True

    # Discover
    scripts = discover_services()
    registry = build_registry(scripts)

    # Filter by category
    if args.category:
        registry = [r for r in registry if r["category"] == args.category]
        scripts = [Path(r["path"]) for r in registry]
        if not scripts:
            print(f"  No scripts found in category '{args.category}'.")
            sys.exit(1)

    # List mode
    if args.list:
        print_list(registry)
        return

    # Dry-run
    if args.dry_run:
        print(f"\n  DRY RUN — {len(scripts)} scripts would be executed:\n")
        run_all(scripts, dry_run=True)
        print(f"\n  {len(scripts)} scripts listed (nothing executed)\n")
        return

    # Execute
    if args.once:
        if not scripts:
            print("  No scripts to run.")
            sys.exit(0)
        results = run_all(
            scripts,
            parallel=args.parallel,
            timeout=args.timeout,
            verbose=args.verbose,
        )
        print_summary(results, as_json=args.json)

        failures = sum(1 for r in results if not r["success"])
        sys.exit(min(failures, 125))


if __name__ == "__main__":
    main()
