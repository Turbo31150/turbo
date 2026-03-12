#!/usr/bin/env python3
"""win_autonomics_runner.py -- Run all Windows automation scripts.

Orchestrates 78 win_*.py scripts in F:/BUREAU/turbo/cowork/dev/.
Groups by category with priority ordering: monitors > guards > analyzers >
managers > optimizers > utilities.

Usage:
    python win_autonomics_runner.py --once                   # Run all once
    python win_autonomics_runner.py --category monitors      # Monitors only
    python win_autonomics_runner.py --category guards,analyzers  # Multiple
    python win_autonomics_runner.py --dry-run                # Show plan
    python win_autonomics_runner.py --dry-run --category managers
    python win_autonomics_runner.py --once --timeout 60      # Custom timeout
    python win_autonomics_runner.py --list                   # List all scripts
    python win_autonomics_runner.py --detect-once            # Probe --once support
"""
import argparse
import subprocess
import sys
import time
import json
import os
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Tuple

SCRIPT_DIR = Path(__file__).resolve().parent
SELF_NAME = Path(__file__).name
DEFAULT_TIMEOUT = 30

# Priority order: lower number = runs first
CATEGORY_PRIORITY = {
    "monitors": 1,
    "guards": 2,
    "analyzers": 3,
    "managers": 4,
    "optimizers": 5,
    "utilities": 6,
}

CATEGORY_DESCRIPTIONS = {
    "monitors": "System monitors and watchers (thermal, service, network, events)",
    "guards": "Security guards and watchdogs (network, privacy, process, registry)",
    "analyzers": "System analyzers, auditors, checkers, and profilers",
    "managers": "Resource and subsystem managers (backup, display, firewall, etc.)",
    "optimizers": "Performance optimizers, tuners, and cleaners",
    "utilities": "Utilities, launchers, controllers, and misc tools",
}


def categorize_script(name: str) -> str:
    """Assign a script stem name to a category based on keywords."""
    if any(kw in name for kw in ("monitor", "watcher", "watchdog")):
        return "monitors"
    if any(kw in name for kw in ("guard", "guardian")):
        return "guards"
    if any(kw in name for kw in ("analyzer", "auditor", "checker", "profiler")):
        return "analyzers"
    if "manager" in name:
        return "managers"
    if any(kw in name for kw in ("optimizer", "tuner", "cleaner", "defrag")):
        return "optimizers"
    return "utilities"


def discover_scripts() -> Dict[str, List[Path]]:
    """Find and categorize all win_*.py scripts, excluding self."""
    categories: Dict[str, List[Path]] = {cat: [] for cat in CATEGORY_PRIORITY}
    for f in sorted(SCRIPT_DIR.glob("win_*.py")):
        if f.name == SELF_NAME:
            continue
        cat = categorize_script(f.stem)
        categories[cat].append(f)
    return categories


def probe_once_support(script: Path, timeout: int = 5) -> bool:
    """Check if a script supports --once by running --help and checking output."""
    try:
        result = subprocess.run(
            [sys.executable, str(script), "--help"],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(SCRIPT_DIR),
        )
        combined = result.stdout + result.stderr
        return "--once" in combined
    except (subprocess.TimeoutExpired, OSError, Exception):
        return False


def run_script(
    script: Path,
    use_once: bool = True,
    timeout: int = DEFAULT_TIMEOUT,
    dry_run: bool = False,
) -> Dict:
    """Run a single script and return a result dict.

    Returns:
        dict with keys: script, category, status, duration, returncode,
                        stdout_tail, stderr_tail, error
    """
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

        # Keep last 500 chars of output to avoid bloat
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


def print_header(text: str, char: str = "=") -> None:
    """Print a formatted section header."""
    line = char * 60
    print(f"\n{line}")
    print(f"  {text}")
    print(f"{line}")


def print_summary(results: List[Dict], total_time: float) -> None:
    """Print a final summary table of all results."""
    print_header("EXECUTION SUMMARY")

    # Stats by status
    status_counts: Dict[str, int] = {}
    for r in results:
        s = r["status"]
        status_counts[s] = status_counts.get(s, 0) + 1

    total = len(results)
    success = status_counts.get("success", 0)
    failed = status_counts.get("failed", 0)
    timeouts = status_counts.get("timeout", 0)
    errors = status_counts.get("error", 0) + status_counts.get("not-found", 0) + status_counts.get("permission-denied", 0)
    dry = status_counts.get("dry-run", 0)
    skipped = status_counts.get("skipped", 0)

    print(f"\n  Total scripts : {total}")
    print(f"  Success       : {success}")
    if dry:
        print(f"  Dry-run       : {dry}")
    if skipped:
        print(f"  Skipped       : {skipped}")
    print(f"  Failed        : {failed}")
    print(f"  Timeouts      : {timeouts}")
    print(f"  Errors        : {errors}")
    print(f"  Total time    : {total_time:.1f}s")

    # Stats by category
    print_header("BY CATEGORY", "-")
    cat_stats: Dict[str, Dict[str, int]] = {}
    for r in results:
        cat = r["category"]
        if cat not in cat_stats:
            cat_stats[cat] = {"total": 0, "success": 0, "fail": 0}
        cat_stats[cat]["total"] += 1
        if r["status"] == "success":
            cat_stats[cat]["success"] += 1
        elif r["status"] not in ("dry-run", "skipped"):
            cat_stats[cat]["fail"] += 1

    for cat in sorted(cat_stats, key=lambda c: CATEGORY_PRIORITY.get(c, 99)):
        s = cat_stats[cat]
        pct = (s["success"] / s["total"] * 100) if s["total"] > 0 else 0
        print(f"  {cat:12s}: {s['success']}/{s['total']} OK ({pct:.0f}%)")

    # List failures
    failures = [r for r in results if r["status"] in ("failed", "timeout", "error", "not-found", "permission-denied")]
    if failures:
        print_header("FAILURES", "-")
        for r in failures:
            print(f"  [{r['status']:>10s}] {r['script']} -- {r['error'] or 'unknown'}")
            if r.get("stderr_tail"):
                # Show first line of stderr
                first_line = r["stderr_tail"].strip().split("\n")[0][:120]
                print(f"             stderr: {first_line}")

    # Slowest scripts
    timed = [r for r in results if r["duration"] > 0 and r["status"] != "dry-run"]
    if timed:
        print_header("SLOWEST (top 10)", "-")
        for r in sorted(timed, key=lambda x: -x["duration"])[:10]:
            marker = " ** TIMEOUT" if r["status"] == "timeout" else ""
            print(f"  {r['duration']:6.1f}s  {r['script']}{marker}")

    print()


def run_category(
    cat_name: str,
    scripts: List[Path],
    use_once: bool,
    timeout: int,
    dry_run: bool,
    verbose: bool,
) -> List[Dict]:
    """Run all scripts in a category sequentially. Returns list of results."""
    results = []
    count = len(scripts)

    if count == 0:
        return results

    print_header(f"{cat_name.upper()} ({count} scripts) -- priority {CATEGORY_PRIORITY.get(cat_name, '?')}")
    if cat_name in CATEGORY_DESCRIPTIONS:
        print(f"  {CATEGORY_DESCRIPTIONS[cat_name]}")
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

        # Status indicator
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


def cmd_list(categories: Dict[str, List[Path]]) -> None:
    """List all discovered scripts by category."""
    total = sum(len(v) for v in categories.values())
    print(f"\nDiscovered {total} win_*.py scripts in {SCRIPT_DIR}\n")
    for cat in sorted(categories, key=lambda c: CATEGORY_PRIORITY.get(c, 99)):
        scripts = categories[cat]
        prio = CATEGORY_PRIORITY.get(cat, "?")
        desc = CATEGORY_DESCRIPTIONS.get(cat, "")
        print(f"[{cat.upper()}] (priority {prio}, {len(scripts)} scripts) -- {desc}")
        for s in scripts:
            print(f"    {s.name}")
        print()


def cmd_detect_once(categories: Dict[str, List[Path]]) -> None:
    """Probe each script for --once support via --help."""
    all_scripts = []
    for cat in sorted(categories, key=lambda c: CATEGORY_PRIORITY.get(c, 99)):
        all_scripts.extend(categories[cat])

    total = len(all_scripts)
    print(f"\nProbing {total} scripts for --once support...\n")
    supported = []
    not_supported = []

    for i, script in enumerate(all_scripts, 1):
        print(f"  [{i}/{total}] {script.name}...", end="", flush=True)
        if probe_once_support(script):
            print(" --once SUPPORTED")
            supported.append(script.name)
        else:
            print(" no --once")
            not_supported.append(script.name)

    print(f"\n  --once supported: {len(supported)}/{total}")
    print(f"  No --once       : {len(not_supported)}/{total}")


def cmd_run(
    categories: Dict[str, List[Path]],
    selected_categories: Optional[List[str]],
    use_once: bool,
    timeout: int,
    dry_run: bool,
    verbose: bool,
    json_output: Optional[str],
) -> int:
    """Main execution: run scripts by category in priority order."""
    # Filter categories if specified
    if selected_categories:
        run_cats = {}
        for cat_name in selected_categories:
            cat_name = cat_name.strip().lower()
            if cat_name not in categories:
                print(f"ERROR: Unknown category '{cat_name}'. Available: {', '.join(CATEGORY_PRIORITY.keys())}")
                return 1
            run_cats[cat_name] = categories[cat_name]
    else:
        run_cats = categories

    # Count total
    total_scripts = sum(len(v) for v in run_cats.values())

    mode = "DRY-RUN" if dry_run else ("--once" if use_once else "continuous")
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print_header(f"WIN AUTONOMICS RUNNER -- {ts}")
    print(f"  Mode       : {mode}")
    print(f"  Timeout    : {timeout}s per script")
    print(f"  Categories : {', '.join(sorted(run_cats, key=lambda c: CATEGORY_PRIORITY.get(c, 99)))}")
    print(f"  Scripts    : {total_scripts} total")
    print(f"  Python     : {sys.executable}")

    all_results: List[Dict] = []
    start_total = time.monotonic()

    # Run in priority order
    for cat in sorted(run_cats, key=lambda c: CATEGORY_PRIORITY.get(c, 99)):
        scripts = run_cats[cat]
        results = run_category(cat, scripts, use_once, timeout, dry_run, verbose)
        all_results.extend(results)

    total_time = time.monotonic() - start_total
    print_summary(all_results, total_time)

    # JSON report
    if json_output:
        report = {
            "timestamp": ts,
            "mode": mode,
            "timeout": timeout,
            "total_scripts": total_scripts,
            "total_time": round(total_time, 2),
            "results": all_results,
            "summary": {
                "success": sum(1 for r in all_results if r["status"] == "success"),
                "failed": sum(1 for r in all_results if r["status"] == "failed"),
                "timeout": sum(1 for r in all_results if r["status"] == "timeout"),
                "errors": sum(1 for r in all_results if r["status"] in ("error", "not-found", "permission-denied")),
            },
        }
        out_path = Path(json_output)
        out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  JSON report saved to: {out_path}\n")

    # Return non-zero if any failures
    failures = sum(1 for r in all_results if r["status"] in ("failed", "timeout", "error"))
    return 1 if failures > 0 and not dry_run else 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Win Autonomics Runner -- Orchestrate 78 win_*.py scripts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Categories (priority order):
  monitors    System monitors and watchers
  guards      Security guards and watchdogs
  analyzers   Analyzers, auditors, checkers, profilers
  managers    Resource and subsystem managers
  optimizers  Performance optimizers, tuners, cleaners
  utilities   Launchers, controllers, misc tools

Examples:
  %(prog)s --once                         Run all scripts once
  %(prog)s --once --category monitors     Only monitors
  %(prog)s --once -c guards,monitors      Guards and monitors
  %(prog)s --dry-run                      Preview execution plan
  %(prog)s --list                         List all scripts
  %(prog)s --detect-once                  Probe --once support
  %(prog)s --once --json report.json      Save JSON report
  %(prog)s --once --timeout 60 -v         Verbose with 60s timeout
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
        help="Comma-separated categories to run (monitors,guards,analyzers,managers,optimizers,utilities)",
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
        "--detect-once",
        action="store_true",
        help="Probe each script to detect --once support",
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
        "--no-once-flag",
        action="store_true",
        help="Run scripts without passing --once (raw execution)",
    )

    args = parser.parse_args()

    # Discover
    categories = discover_scripts()
    total = sum(len(v) for v in categories.values())

    if total == 0:
        print(f"ERROR: No win_*.py scripts found in {SCRIPT_DIR}")
        return 1

    # List mode
    if args.list:
        cmd_list(categories)
        return 0

    # Detect mode
    if args.detect_once:
        cmd_detect_once(categories)
        return 0

    # Require --once or --dry-run to actually do something
    if not args.once and not args.dry_run:
        parser.print_help()
        print(f"\nDiscovered {total} scripts. Use --once to run or --dry-run to preview.")
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
    )


if __name__ == "__main__":
    sys.exit(main())
