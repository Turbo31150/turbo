#!/usr/bin/env python3
"""misc_tools_runner.py -- Orchestrate orphan scripts (not win_*/ia_*/jarvis_*).

Dynamically discovers .py scripts in cowork/dev/ that do NOT match:
  - win_*.py      (handled by win_autonomics_runner.py)
  - ia_*.py       (handled by ia_agent_swarm_runner.py)
  - jarvis_*.py   (handled by jarvis_mega_runner.py)
  - _*.py         (private/internal modules)
  - *_runner.py   (other runners)
  - *_orchestrator*.py (orchestrators)

Then categorises them into 4 groups:
  1. cluster    — cluster_*.py scripts
  2. desktop    — desktop_*, window_*, windows_*, workspace_* scripts
  3. data       — conversation_*, data_*, decision_*, domino_*, memory_*,
                  model_*, context_*, knowledge_*, intent_*, ai_* scripts
  4. perf       — generate_*, gpu_*, interaction_*, performance_*, process_*,
                  telegram_*, metrics_*, resource_*, benchmark_*, latency_*,
                  adaptive_*, dynamic_*, load_*, node_*, network_*, smart_*,
                  pipeline_* scripts
  5. ops        — auto_*, deployment_*, scheduled_*, startup_*, night_*,
                  cowork_*, openclaw_*, proactive_*, continuous_* scripts
  6. infra      — api_*, mcp_*, event_*, log_*, config_*, db_*, file_*,
                  task_*, service_*, alert_*, notification_*, report_*,
                  dashboard_*, system_*, security_*, resilient_*, multi_*,
                  dispatch_* scripts
  7. trading    — sniper_*, trading_*, portfolio_*, signal_*, strategy_*,
                  risk_*, crypto_* scripts
  8. misc       — everything else (catch-all)

Excludes scripts already wired in autonomous_orchestrator.py to avoid
double-execution.

Usage:
    python misc_tools_runner.py --once                    # Run all once
    python misc_tools_runner.py --category desktop        # Desktop only
    python misc_tools_runner.py --category data,perf      # Multiple cats
    python misc_tools_runner.py --dry-run                 # Show plan
    python misc_tools_runner.py --list                    # List scripts
    python misc_tools_runner.py --timeout 120             # Custom timeout
    python misc_tools_runner.py --json report.json        # JSON report
    python misc_tools_runner.py --parallel 2              # 2 concurrent
    python misc_tools_runner.py --once -v                 # Verbose output

Stdlib-only (subprocess, json, argparse, time, re, os, pathlib).
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
SELF_NAME = Path(__file__).name
DEFAULT_TIMEOUT = 120

# ---------------------------------------------------------------------------
# Category definitions — priority order (lower = first)
# ---------------------------------------------------------------------------
CATEGORY_PRIORITY = {
    "cluster": 1,
    "desktop": 2,
    "data":    3,
    "perf":    4,
    "ops":     5,
    "infra":   6,
    "trading": 7,
    "misc":    8,
}

CATEGORY_DESCRIPTIONS = {
    "cluster":  "Cluster management, rotation, sync, warmup, failover",
    "desktop":  "Desktop organizer, window/workspace managers, service hardening",
    "data":     "Conversation, data export, decision engine, domino, memory, models",
    "perf":     "GPU, performance profiling, process management, benchmarks, metrics",
    "ops":      "Automation, deployment, scheduling, night ops, proactive agents",
    "infra":    "API, MCP, events, logs, config, DB, tasks, services, dispatch, security",
    "trading":  "Sniper, trading intelligence, portfolio, signals, risk management",
    "misc":     "Uncategorized orphan scripts",
}

# Keywords for each category (checked against the full filename stem)
CATEGORY_KEYWORDS: Dict[str, List[str]] = {
    "cluster": ["cluster_"],
    "desktop": [
        "desktop_", "window_manager", "windows_service", "windows_integration",
        "workspace_", "display_manager", "screenshot_", "bluetooth_",
        "usb_monitor", "wifi_manager", "power_manager", "audio_controller",
        "clipboard_", "browser_automation", "browser_pilot",
        "desktop_workflow",
    ],
    "data": [
        "conversation_", "data_exporter", "decision_engine", "domino_executor",
        "memory_optimizer", "model_manager", "model_rotator", "model_benchmark",
        "model_health", "context_engine", "knowledge_", "intent_classifier",
        "ai_conversation", "prediction_trainer", "quick_answer",
        "response_evaluator", "response_sanitizer", "prompt_optimizer",
        "prompt_router", "self_feeding", "self_improver",
    ],
    "perf": [
        "generate_docstrings", "gpu_", "interaction_predictor",
        "performance_", "process_manager", "telegram_scheduler",
        "metrics_", "resource_", "benchmark_trend", "latency_monitor",
        "adaptive_", "dynamic_timeout", "load_balancer", "node_",
        "network_", "smart_", "pipeline_", "pattern_load",
        "timeout_auto", "grade_optimizer",
    ],
    "ops": [
        "auto_", "deployment_", "scheduled_task", "startup_manager",
        "night_", "cowork_", "openclaw_", "proactive_", "continuous_",
    ],
    "infra": [
        "api_", "mcp_", "event_", "log_", "config_", "db_optimizer",
        "file_organizer", "task_", "service_watch", "service_watcher",
        "alert_manager", "anomaly_detector", "notification_",
        "report_mailer", "dashboard_generator", "system_",
        "security_scanner", "resilient_", "multi_agent", "multi_strategy",
        "dispatch_", "health_checker", "failure_predictor",
        "predictive_failure", "driver_checker", "registry_manager",
        "email_reader", "cross_", "daily_", "test_monitoring",
        "script_dedup", "tts_cache", "usage_analytics",
        "smart_cron", "smart_launcher", "electron_app",
        "perplexity_mcp", "code_generator", "code_reviewer",
        "code_lint", "test_generator", "dependency_vulnerability",
    ],
    "trading": [
        "sniper_", "trading_", "portfolio_", "signal_", "strategy_",
        "risk_manager", "crypto_",
    ],
}

# ---------------------------------------------------------------------------
# Exclusion: scripts already in autonomous_orchestrator.py
# ---------------------------------------------------------------------------
_ORCHESTRATOR_CACHE: Optional[set] = None


def _extract_wired_scripts() -> set:
    """Parse autonomous_orchestrator.py to extract wired script filenames."""
    global _ORCHESTRATOR_CACHE
    if _ORCHESTRATOR_CACHE is not None:
        return _ORCHESTRATOR_CACHE

    wired: set = set()
    orch_path = SCRIPT_DIR / "autonomous_orchestrator.py"
    if orch_path.exists():
        try:
            content = orch_path.read_text(encoding="utf-8", errors="replace")
            # Match "script": "some_file.py" patterns
            wired.update(re.findall(r'"script"\s*:\s*"([^"]+\.py)"', content))
            # Also match 'script': 'some_file.py'
            wired.update(re.findall(r"'script'\s*:\s*'([^']+\.py)'", content))
        except Exception:
            pass

    # Also check autonomous_orchestrator_v3.py
    orch_v3 = SCRIPT_DIR / "autonomous_orchestrator_v3.py"
    if orch_v3.exists():
        try:
            content = orch_v3.read_text(encoding="utf-8", errors="replace")
            wired.update(re.findall(r'"script"\s*:\s*"([^"]+\.py)"', content))
            wired.update(re.findall(r"'script'\s*:\s*'([^']+\.py)'", content))
        except Exception:
            pass

    _ORCHESTRATOR_CACHE = wired
    return wired


# ---------------------------------------------------------------------------
# Filename exclusion
# ---------------------------------------------------------------------------
EXCLUDED_PREFIXES = (
    "win_",       # win_autonomics_runner.py
    "ia_",        # ia_agent_swarm_runner.py
    "jarvis_",    # jarvis_mega_runner.py
)
EXCLUDED_SUFFIXES = ("_runner.py",)
EXCLUDED_PATTERNS = ("_orchestrator",)


def _is_excluded(filename: str, wired_scripts: set) -> bool:
    """Return True if a script should be excluded from this runner."""
    # Private / internal
    if filename.startswith("_"):
        return True

    # Covered by prefix-based runners
    for pfx in EXCLUDED_PREFIXES:
        if filename.startswith(pfx):
            return True

    # Runner files (including self)
    for sfx in EXCLUDED_SUFFIXES:
        if filename.endswith(sfx):
            return True

    # Orchestrator wrappers
    for pat in EXCLUDED_PATTERNS:
        if pat in filename:
            return True

    # Already wired in the autonomous orchestrator
    if filename in wired_scripts:
        return True

    # Not a Python file
    if not filename.endswith(".py"):
        return True

    return False


# ---------------------------------------------------------------------------
# Categorization
# ---------------------------------------------------------------------------

def categorize_script(stem: str) -> str:
    """Assign a script stem to a category based on keyword matching."""
    lower = stem.lower()
    for cat, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if lower.startswith(kw) or kw in lower:
                return cat
    return "misc"


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

def discover_scripts() -> Tuple[Dict[str, List[Path]], set]:
    """Find and categorize all eligible orphan scripts.

    Returns:
        (categories dict, set of excluded-wired script names)
    """
    wired = _extract_wired_scripts()
    categories: Dict[str, List[Path]] = {cat: [] for cat in CATEGORY_PRIORITY}

    for f in sorted(SCRIPT_DIR.glob("*.py")):
        if f.name == SELF_NAME:
            continue
        if _is_excluded(f.name, wired):
            continue
        cat = categorize_script(f.stem)
        categories[cat].append(f)

    return categories, wired


# ---------------------------------------------------------------------------
# Script execution
# ---------------------------------------------------------------------------

def run_script(
    script: Path,
    use_once: bool = True,
    timeout: int = DEFAULT_TIMEOUT,
    dry_run: bool = False,
) -> Dict:
    """Run a single script and return a result dict."""
    name = script.name
    cat = categorize_script(script.stem)
    start = time.monotonic()

    cmd = [sys.executable, str(script)]
    if use_once:
        cmd.append("--once")

    record = {
        "script": name,
        "category": cat,
        "command": " ".join(cmd),
        "status": "pending",
        "duration": 0.0,
        "returncode": None,
        "stdout_tail": "",
        "stderr_tail": "",
        "error": None,
        "timestamp": datetime.now().isoformat(),
    }

    if dry_run:
        record["status"] = "dry-run"
        record["duration"] = 0.0
        return record

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(SCRIPT_DIR),
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
        elapsed = time.monotonic() - start
        record["duration"] = round(elapsed, 2)
        record["returncode"] = result.returncode

        # Keep last 500 chars to avoid bloat
        record["stdout_tail"] = result.stdout[-500:] if result.stdout else ""
        record["stderr_tail"] = result.stderr[-500:] if result.stderr else ""

        if result.returncode == 0:
            record["status"] = "success"
        else:
            record["status"] = "failed"
            record["error"] = f"exit code {result.returncode}"

    except subprocess.TimeoutExpired:
        elapsed = time.monotonic() - start
        record["duration"] = round(elapsed, 2)
        record["status"] = "timeout"
        record["error"] = f"exceeded {timeout}s timeout"

    except FileNotFoundError:
        record["status"] = "not-found"
        record["error"] = "script file not found"

    except PermissionError:
        record["status"] = "permission-denied"
        record["error"] = "permission denied"

    except Exception as exc:
        elapsed = time.monotonic() - start
        record["duration"] = round(elapsed, 2)
        record["status"] = "error"
        record["error"] = str(exc)[:200]

    return record


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def print_header(text: str, char: str = "=") -> None:
    line = char * 64
    print(f"\n{line}")
    print(f"  {text}")
    print(f"{line}")


def print_summary(results: List[Dict], total_time: float) -> None:
    print_header("EXECUTION SUMMARY")

    status_counts: Dict[str, int] = {}
    for r in results:
        s = r["status"]
        status_counts[s] = status_counts.get(s, 0) + 1

    total = len(results)
    success = status_counts.get("success", 0)
    failed = status_counts.get("failed", 0)
    timeouts = status_counts.get("timeout", 0)
    errors = (
        status_counts.get("error", 0)
        + status_counts.get("not-found", 0)
        + status_counts.get("permission-denied", 0)
    )
    dry = status_counts.get("dry-run", 0)

    print(f"\n  Total scripts : {total}")
    print(f"  Success       : {success}")
    if dry:
        print(f"  Dry-run       : {dry}")
    print(f"  Failed        : {failed}")
    print(f"  Timeouts      : {timeouts}")
    print(f"  Errors        : {errors}")
    print(f"  Total time    : {total_time:.1f}s")

    # Per-category stats
    print_header("BY CATEGORY", "-")
    cat_stats: Dict[str, Dict[str, int]] = {}
    for r in results:
        cat = r["category"]
        if cat not in cat_stats:
            cat_stats[cat] = {"total": 0, "success": 0, "fail": 0}
        cat_stats[cat]["total"] += 1
        if r["status"] == "success":
            cat_stats[cat]["success"] += 1
        elif r["status"] not in ("dry-run",):
            cat_stats[cat]["fail"] += 1

    for cat in sorted(cat_stats, key=lambda c: CATEGORY_PRIORITY.get(c, 99)):
        s = cat_stats[cat]
        pct = (s["success"] / s["total"] * 100) if s["total"] > 0 else 0
        desc = CATEGORY_DESCRIPTIONS.get(cat, "")
        print(f"  {cat:10s}: {s['success']:>3}/{s['total']:<3} OK ({pct:5.1f}%)  {desc}")

    # List failures
    failures = [
        r for r in results
        if r["status"] in ("failed", "timeout", "error", "not-found", "permission-denied")
    ]
    if failures:
        print_header("FAILURES", "-")
        for r in failures:
            print(f"  [{r['status']:>17s}] {r['script']} -- {r['error'] or 'unknown'}")
            if r.get("stderr_tail"):
                first_line = r["stderr_tail"].strip().split("\n")[0][:120]
                print(f"                     stderr: {first_line}")

    # Slowest scripts
    timed = [r for r in results if r["duration"] > 0 and r["status"] != "dry-run"]
    if timed:
        print_header("SLOWEST (top 10)", "-")
        for r in sorted(timed, key=lambda x: -x["duration"])[:10]:
            marker = " ** TIMEOUT" if r["status"] == "timeout" else ""
            print(f"  {r['duration']:6.1f}s  {r['script']}{marker}")

    print()


# ---------------------------------------------------------------------------
# Run modes
# ---------------------------------------------------------------------------

def run_category_sequential(
    cat_name: str,
    scripts: List[Path],
    use_once: bool,
    timeout: int,
    dry_run: bool,
    verbose: bool,
) -> List[Dict]:
    """Run all scripts in a category sequentially."""
    results: List[Dict] = []
    count = len(scripts)
    if count == 0:
        return results

    prio = CATEGORY_PRIORITY.get(cat_name, "?")
    desc = CATEGORY_DESCRIPTIONS.get(cat_name, "")
    print_header(f"{cat_name.upper()} ({count} scripts) -- priority {prio}")
    if desc:
        print(f"  {desc}")
    print()

    for i, script in enumerate(scripts, 1):
        tag = f"[{i}/{count}]"
        if dry_run:
            cmd_preview = f"python {script.name}" + (" --once" if use_once else "")
            print(f"  {tag} [DRY-RUN] {cmd_preview}")
            results.append(run_script(script, use_once=use_once, timeout=timeout, dry_run=True))
            continue

        print(f"  {tag} Running {script.name}...", end="", flush=True)
        record = run_script(script, use_once=use_once, timeout=timeout, dry_run=False)
        results.append(record)

        status = record["status"]
        duration = record["duration"]
        if status == "success":
            print(f" OK ({duration:.1f}s)")
        elif status == "timeout":
            print(f" TIMEOUT ({timeout}s)")
        elif status == "failed":
            print(f" FAIL (rc={record['returncode']}, {duration:.1f}s)")
        else:
            print(f" {status.upper()} ({duration:.1f}s)")

        if verbose and record.get("error"):
            print(f"       -> {record['error']}")
        if verbose and record.get("stderr_tail"):
            for line in record["stderr_tail"].strip().split("\n")[-3:]:
                print(f"       | {line[:120]}")

    return results


def run_category_parallel(
    cat_name: str,
    scripts: List[Path],
    use_once: bool,
    timeout: int,
    dry_run: bool,
    verbose: bool,
    max_workers: int = 2,
) -> List[Dict]:
    """Run scripts in a category with limited parallelism."""
    results: List[Dict] = []
    count = len(scripts)
    if count == 0:
        return results

    prio = CATEGORY_PRIORITY.get(cat_name, "?")
    desc = CATEGORY_DESCRIPTIONS.get(cat_name, "")
    print_header(f"{cat_name.upper()} ({count} scripts, parallel={max_workers}) -- priority {prio}")
    if desc:
        print(f"  {desc}")
    print()

    if dry_run:
        for i, script in enumerate(scripts, 1):
            cmd_preview = f"python {script.name}" + (" --once" if use_once else "")
            print(f"  [{i}/{count}] [DRY-RUN] {cmd_preview}")
            results.append(run_script(script, use_once=use_once, timeout=timeout, dry_run=True))
        return results

    futures_map = {}
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        for script in scripts:
            fut = pool.submit(run_script, script, use_once, timeout, False)
            futures_map[fut] = script

        done_count = 0
        for fut in as_completed(futures_map):
            done_count += 1
            script = futures_map[fut]
            try:
                record = fut.result()
            except Exception as exc:
                record = {
                    "script": script.name,
                    "category": cat_name,
                    "command": "",
                    "status": "error",
                    "duration": 0.0,
                    "returncode": None,
                    "stdout_tail": "",
                    "stderr_tail": "",
                    "error": str(exc)[:200],
                    "timestamp": datetime.now().isoformat(),
                }
            results.append(record)

            status = record["status"]
            duration = record["duration"]
            tag = f"[{done_count}/{count}]"
            if status == "success":
                print(f"  {tag} {script.name} OK ({duration:.1f}s)")
            elif status == "timeout":
                print(f"  {tag} {script.name} TIMEOUT ({timeout}s)")
            elif status == "failed":
                print(f"  {tag} {script.name} FAIL (rc={record['returncode']}, {duration:.1f}s)")
            else:
                print(f"  {tag} {script.name} {status.upper()} ({duration:.1f}s)")

            if verbose and record.get("error"):
                print(f"       -> {record['error']}")

    return results


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------

def cmd_list(categories: Dict[str, List[Path]], wired: set) -> None:
    """List all discovered scripts by category."""
    total = sum(len(v) for v in categories.values())
    print(f"\nDiscovered {total} orphan scripts in {SCRIPT_DIR}")
    print(f"Excluded {len(wired)} scripts already wired in autonomous_orchestrator\n")

    for cat in sorted(categories, key=lambda c: CATEGORY_PRIORITY.get(c, 99)):
        scripts = categories[cat]
        if not scripts:
            continue
        prio = CATEGORY_PRIORITY.get(cat, "?")
        desc = CATEGORY_DESCRIPTIONS.get(cat, "")
        print(f"[{cat.upper():>10s}] (priority {prio}, {len(scripts):>3} scripts) -- {desc}")
        for s in scripts:
            print(f"    {s.name}")
        print()


def cmd_run(
    categories: Dict[str, List[Path]],
    selected_categories: Optional[List[str]],
    use_once: bool,
    timeout: int,
    dry_run: bool,
    verbose: bool,
    json_output: Optional[str],
    parallel: int,
) -> int:
    """Main execution: run scripts by category in priority order."""
    # Filter categories if specified
    if selected_categories:
        run_cats: Dict[str, List[Path]] = {}
        for cat_name in selected_categories:
            cat_name = cat_name.strip().lower()
            if cat_name not in CATEGORY_PRIORITY:
                valid = ", ".join(sorted(CATEGORY_PRIORITY.keys()))
                print(f"ERROR: Unknown category '{cat_name}'. Available: {valid}")
                return 1
            run_cats[cat_name] = categories.get(cat_name, [])
    else:
        run_cats = {k: v for k, v in categories.items() if v}

    total_scripts = sum(len(v) for v in run_cats.values())
    mode = "DRY-RUN" if dry_run else ("--once" if use_once else "run")
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print_header(f"MISC TOOLS RUNNER -- {ts}")
    print(f"  Mode       : {mode}")
    print(f"  Timeout    : {timeout}s per script")
    print(f"  Parallel   : {parallel}")
    print(f"  Categories : {', '.join(sorted(run_cats, key=lambda c: CATEGORY_PRIORITY.get(c, 99)))}")
    print(f"  Scripts    : {total_scripts} total")
    print(f"  Python     : {sys.executable}")

    all_results: List[Dict] = []
    start_total = time.monotonic()

    for cat in sorted(run_cats, key=lambda c: CATEGORY_PRIORITY.get(c, 99)):
        scripts = run_cats[cat]
        if not scripts:
            continue
        if parallel > 1:
            results = run_category_parallel(
                cat, scripts, use_once, timeout, dry_run, verbose, parallel
            )
        else:
            results = run_category_sequential(
                cat, scripts, use_once, timeout, dry_run, verbose
            )
        all_results.extend(results)

    total_time = time.monotonic() - start_total
    print_summary(all_results, total_time)

    # JSON report
    if json_output:
        report = {
            "runner": "misc_tools_runner",
            "timestamp": ts,
            "mode": mode,
            "timeout": timeout,
            "parallel": parallel,
            "total_scripts": total_scripts,
            "total_time": round(total_time, 2),
            "results": all_results,
            "summary": {
                "success": sum(1 for r in all_results if r["status"] == "success"),
                "failed": sum(1 for r in all_results if r["status"] == "failed"),
                "timeout": sum(1 for r in all_results if r["status"] == "timeout"),
                "errors": sum(
                    1 for r in all_results
                    if r["status"] in ("error", "not-found", "permission-denied")
                ),
                "dry_run": sum(1 for r in all_results if r["status"] == "dry-run"),
            },
            "categories": {
                cat: [r["script"] for r in all_results if r["category"] == cat]
                for cat in sorted(set(r["category"] for r in all_results))
            },
        }
        out_path = Path(json_output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  JSON report saved to: {out_path}\n")

    # Return non-zero if any failures
    failures = sum(
        1 for r in all_results
        if r["status"] in ("failed", "timeout", "error")
    )
    return 1 if failures > 0 and not dry_run else 0


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Misc Tools Runner -- Orchestrate orphan scripts (not win/ia/jarvis)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Categories (priority order):
  cluster   Cluster management, rotation, sync, warmup
  desktop   Desktop organizer, window/workspace managers
  data      Conversation, data export, decision, memory, models
  perf      GPU, performance, process, benchmarks, metrics
  ops       Automation, deployment, scheduling, night ops
  infra     API, events, logs, config, DB, tasks, services
  trading   Sniper, trading, portfolio, signals, risk
  misc      Everything else (catch-all)

Examples:
  %(prog)s --once                              Run all orphans once
  %(prog)s --once --category desktop           Desktop scripts only
  %(prog)s --once -c data,perf                 Data and perf scripts
  %(prog)s --dry-run                           Preview execution plan
  %(prog)s --list                              List discovered scripts
  %(prog)s --once --parallel 2                 Run 2 scripts at a time
  %(prog)s --once --json report.json           Save JSON report
  %(prog)s --once --timeout 120 -v             Verbose, 120s timeout
""",
    )

    parser.add_argument(
        "--once",
        action="store_true",
        help="Run all scripts with --once flag (single execution)",
    )
    parser.add_argument(
        "--category", "-c",
        type=str,
        default=None,
        help="Comma-separated categories to run (cluster,desktop,data,perf,ops,infra,trading,misc)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would run without executing",
    )
    parser.add_argument(
        "--timeout", "-t",
        type=int,
        default=DEFAULT_TIMEOUT,
        help=f"Timeout per script in seconds (default: {DEFAULT_TIMEOUT})",
    )
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="List all discovered scripts by category",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed error output for failures",
    )
    parser.add_argument(
        "--json",
        type=str,
        default=None,
        metavar="FILE",
        help="Save execution report as JSON to FILE",
    )
    parser.add_argument(
        "--parallel", "-p",
        type=int,
        default=1,
        help="Max concurrent scripts per category (default: 1 = sequential)",
    )
    parser.add_argument(
        "--no-once-flag",
        action="store_true",
        help="Run scripts without passing --once (raw execution)",
    )

    args = parser.parse_args()

    # Discover
    categories, wired = discover_scripts()
    total = sum(len(v) for v in categories.values())

    if total == 0:
        print(f"No orphan scripts found in {SCRIPT_DIR}")
        print("All scripts are either excluded (win_/ia_/jarvis_/private/runner)")
        print(f"or wired in autonomous_orchestrator ({len(wired)} wired).")
        return 0

    # List mode
    if args.list:
        cmd_list(categories, wired)
        return 0

    # Require --once or --dry-run to actually do something
    if not args.once and not args.dry_run:
        parser.print_help()
        print(f"\nDiscovered {total} orphan scripts. Use --once to run or --dry-run to preview.")
        return 0

    # Parse categories
    selected = None
    if args.category:
        selected = [c.strip() for c in args.category.split(",")]

    use_once = args.once and not args.no_once_flag

    return cmd_run(
        categories=categories,
        selected_categories=selected,
        use_once=use_once,
        timeout=args.timeout,
        dry_run=args.dry_run,
        verbose=args.verbose,
        json_output=args.json,
        parallel=args.parallel,
    )


if __name__ == "__main__":
    sys.exit(main())
