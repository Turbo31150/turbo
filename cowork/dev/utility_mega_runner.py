#!/usr/bin/env python3
"""utility_mega_runner.py -- Universal safety-net runner for uncovered scripts.

Scans all .py scripts in cowork/dev/, excludes those already wired in
autonomous_orchestrator.py or covered by prefix-based runners, categorizes
the remainder, and executes them by priority.

This is the FILET DE SECURITE: any script not covered elsewhere runs here.

CLI:
    --once          Run all discovered scripts once
    --dry-run       Show what would run without executing
    --list          List all discovered scripts with categories
    --category X    Run only scripts in category X (comma-separated)
    --timeout N     Override default 60s timeout per script
    --json          Output results as JSON
    --verbose       Show detailed output

Stdlib-only (json, argparse, subprocess, sqlite3, time, re, os).
"""

import argparse
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data"
DB_PATH = DATA_DIR / "cowork_gaps.db"

# ---------------------------------------------------------------------------
# 1) Build the set of ALREADY-WIRED scripts from autonomous_orchestrator.py
# ---------------------------------------------------------------------------

def _extract_wired_scripts():
    """Parse autonomous_orchestrator.py to find all script filenames in TASKS."""
    orch_path = SCRIPT_DIR / "autonomous_orchestrator.py"
    wired = set()
    if orch_path.exists():
        content = orch_path.read_text(encoding="utf-8", errors="replace")
        wired.update(re.findall(r'"script"\s*:\s*"([^"]+)"', content))
    return wired


# ---------------------------------------------------------------------------
# 2) Exclusion rules
# ---------------------------------------------------------------------------

# Prefixes covered by dedicated runners or other agents
EXCLUDED_PREFIXES = (
    "jarvis_",    # ~80 scripts, managed by jarvis agents
    "ia_",        # ~50 scripts, covered by ia_agent_swarm_runner.py
    "win_",       # ~78 scripts, covered by win_autonomics_runner.py
    "cluster_",   # cluster management scripts
    "dispatch_",  # dispatch pipeline scripts
    "telegram_",  # telegram bot scripts
    "voice_",     # voice pipeline scripts
    "auto_",      # auto-* automation scripts
)

# Filename patterns to always exclude
EXCLUDED_PATTERNS = (
    "_runner.py",
    "_orchestrator",
    "_paths.py",
)


def _is_excluded(filename, wired_scripts):
    """Return True if a script should be excluded from the mega runner."""
    # Internal/private
    if filename.startswith("_") or filename.startswith("__"):
        return True

    # Already individually wired in the orchestrator
    if filename in wired_scripts:
        return True

    # Covered by prefix-based runners
    for pfx in EXCLUDED_PREFIXES:
        if filename.startswith(pfx):
            return True

    # Runner/orchestrator wrappers (including self)
    for pat in EXCLUDED_PATTERNS:
        if pat in filename:
            return True

    # Not a .py file
    if not filename.endswith(".py"):
        return True

    return False


# ---------------------------------------------------------------------------
# 3) Categorization by prefix/keyword
# ---------------------------------------------------------------------------

CATEGORY_RULES = [
    # (category, priority, prefixes/keywords)
    ("health_monitoring",  1, ["health_", "monitor_", "alert_", "anomaly_", "watchdog",
                               "predictive_failure", "service_watcher"]),
    ("intelligence",       2, ["knowledge_", "memory_", "pattern_", "decision_", "context_",
                               "intent_", "interaction_", "prediction_", "ai_", "proactive_",
                               "prompt_", "response_", "quick_answer", "conversation_",
                               "multi_agent"]),
    ("maintenance",        3, ["file_", "log_", "config_", "db_", "backup_", "cleanup_",
                               "script_dedup", "timeout_", "startup_", "scheduled_task",
                               "deployment_", "system_restore", "tts_cache"]),
    ("development",        4, ["code_", "test_", "generate_", "lint_", "continuous_coder",
                               "continuous_learner", "pipeline_integration",
                               "dependency_vulnerability"]),
    ("trading",            5, ["sniper_", "trading_", "portfolio_", "signal_", "strategy_",
                               "risk_"]),
    ("system",             6, ["desktop_", "display_", "bluetooth_", "driver_", "electron_",
                               "power_", "process_", "window_", "windows_", "usb_", "wifi_",
                               "screenshot_", "registry_", "audio_", "clipboard_",
                               "browser_automation"]),
    ("communication",      7, ["email_", "mcp_", "notification_", "report_mailer",
                               "cross_channel", "cross_script"]),
    ("performance",        8, ["performance_", "resource_", "gpu_", "pipeline_", "load_",
                               "node_", "adaptive_", "dynamic_", "smart_", "network_optim"]),
    ("evolution",          9, ["self_improv", "continuous_improv", "self_feeding",
                               "cowork_", "workspace_", "night_", "openclaw_"]),
    ("infrastructure",    10, ["api_rate_", "autonomous_cluster", "dashboard_generator",
                               "data_exporter", "domino_executor", "event_bus", "event_logger",
                               "metrics_collector", "model_benchmark", "model_manager",
                               "model_rotator", "system_benchmark", "task_automator",
                               "task_learner", "task_queue", "usage_analytics",
                               "daily_audit"]),
    ("misc",              99, []),  # Catch-all
]


def _categorize(filename):
    """Return (category, priority) for a script filename."""
    lower = filename.lower()
    for category, priority, keywords in CATEGORY_RULES:
        for kw in keywords:
            if kw in lower:
                return category, priority
    return "misc", 10


# ---------------------------------------------------------------------------
# 4) Discovery
# ---------------------------------------------------------------------------

def discover_scripts():
    """Find all uncovered .py scripts and categorize them.

    Returns dict: {category: [(filename, priority), ...]}
    """
    wired = _extract_wired_scripts()
    all_py = sorted(f for f in os.listdir(str(SCRIPT_DIR)) if f.endswith(".py"))

    categorized = {}
    for filename in all_py:
        if _is_excluded(filename, wired):
            continue
        # Verify file actually exists (not a broken symlink etc.)
        if not (SCRIPT_DIR / filename).is_file():
            continue

        cat, prio = _categorize(filename)
        categorized.setdefault(cat, []).append((filename, prio))

    return categorized


# ---------------------------------------------------------------------------
# 5) Database logging
# ---------------------------------------------------------------------------

def get_db():
    """Open/create the utility_runner_log table in cowork_gaps.db."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.row_factory = sqlite3.Row
    conn.execute("""CREATE TABLE IF NOT EXISTS utility_runner_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        script_name TEXT NOT NULL,
        category TEXT NOT NULL,
        success INTEGER DEFAULT 0,
        duration_ms INTEGER DEFAULT 0,
        return_code INTEGER DEFAULT -1,
        output_summary TEXT,
        error_summary TEXT
    )""")
    conn.execute("""CREATE INDEX IF NOT EXISTS idx_utility_runner_ts
        ON utility_runner_log(timestamp)""")
    conn.execute("""CREATE INDEX IF NOT EXISTS idx_utility_runner_script
        ON utility_runner_log(script_name)""")
    conn.commit()
    return conn


def record_run(conn, script_name, category, result):
    """Write one execution record with retry on DB lock."""
    now = datetime.now().isoformat()
    for attempt in range(5):
        try:
            conn.execute("""
                INSERT INTO utility_runner_log
                    (timestamp, script_name, category, success, duration_ms,
                     return_code, output_summary, error_summary)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                now, script_name, category,
                1 if result["success"] else 0,
                result.get("duration_ms", 0),
                result.get("returncode", -1),
                (result.get("output", "") or "")[:500],
                (result.get("error", "") or "")[:500],
            ))
            conn.commit()
            return
        except sqlite3.OperationalError as e:
            if "locked" in str(e) and attempt < 4:
                time.sleep(1.5 * (attempt + 1))
                continue
            raise


# ---------------------------------------------------------------------------
# 6) Execution
# ---------------------------------------------------------------------------

def run_script(script_name, timeout_s=60):
    """Run a single script with --once flag, return result dict."""
    script_path = SCRIPT_DIR / script_name

    if not script_path.exists():
        return {"success": False, "error": f"Not found: {script_path}",
                "duration_ms": 0, "returncode": -1}

    # Check if script accepts --once by peeking at its content
    args = ["--once"]
    try:
        head = script_path.read_text(encoding="utf-8", errors="replace")[:2000]
        if "--once" not in head:
            args = []
    except Exception:
        args = []

    cmd = [sys.executable, str(script_path)] + args
    start = time.time()

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            cwd=str(SCRIPT_DIR),
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        elapsed_ms = int((time.time() - start) * 1000)
        return {
            "success": result.returncode == 0,
            "duration_ms": elapsed_ms,
            "returncode": result.returncode,
            "output": (result.stdout or "")[-500:],
            "error": (result.stderr or "")[-300:],
        }
    except subprocess.TimeoutExpired:
        elapsed_ms = int(timeout_s * 1000)
        return {
            "success": False,
            "duration_ms": elapsed_ms,
            "returncode": -9,
            "error": f"TIMEOUT after {timeout_s}s",
        }
    except Exception as e:
        elapsed_ms = int((time.time() - start) * 1000)
        return {
            "success": False,
            "duration_ms": elapsed_ms,
            "returncode": -1,
            "error": str(e)[:300],
        }


# ---------------------------------------------------------------------------
# 7) Main run logic
# ---------------------------------------------------------------------------

def run_all(categories_filter=None, timeout_s=60, dry_run=False, verbose=False):
    """Discover and run all uncovered scripts by priority (parallel within groups).

    Returns: (total, succeeded, failed, results_list)
    """
    MAX_WORKERS = 3
    discovered = discover_scripts()

    if categories_filter:
        allowed = set(c.strip().lower() for c in categories_filter.split(","))
        discovered = {k: v for k, v in discovered.items() if k in allowed}

    # Flatten and sort by priority then name
    flat = []
    for cat, scripts in discovered.items():
        for script_name, prio in scripts:
            flat.append((prio, cat, script_name))
    flat.sort(key=lambda x: (x[0], x[2]))

    if not flat:
        if verbose:
            print("No uncovered scripts found.")
        return 0, 0, 0, []

    conn = None if dry_run else get_db()
    results = []
    succeeded = 0
    failed = 0

    if dry_run:
        for prio, cat, script_name in flat:
            if verbose:
                print(f"  [DRY] [{cat:20}] P{prio} {script_name}")
            results.append({
                "script": script_name, "category": cat, "priority": prio,
                "dry_run": True,
            })
        return len(flat), 0, 0, results

    # Group by priority for parallel execution within each group
    from itertools import groupby
    priority_groups = []
    for prio, group in groupby(flat, key=lambda x: x[0]):
        priority_groups.append((prio, list(group)))

    for prio, group_items in priority_groups:
        if verbose:
            cats = set(cat for _, cat, _ in group_items)
            print(f"  --- Priority {prio} ({len(group_items)} scripts: {', '.join(cats)}) ---")

        with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(group_items))) as pool:
            future_map = {}
            for _, cat, script_name in group_items:
                future = pool.submit(run_script, script_name, timeout_s)
                future_map[future] = (script_name, cat)

            for future in as_completed(future_map):
                script_name, cat = future_map[future]
                try:
                    result = future.result()
                except Exception as e:
                    result = {"success": False, "duration_ms": 0, "returncode": -1,
                              "error": str(e)[:300]}

                record_run(conn, script_name, cat, result)

                if result["success"]:
                    succeeded += 1
                    status = "OK"
                else:
                    failed += 1
                    status = "FAIL"

                dur = result.get("duration_ms", 0)
                if verbose:
                    ts = datetime.now().strftime("%H:%M:%S")
                    print(f"  [{ts}] [{cat:20}] {script_name} {status} ({dur}ms)")
                    if not result["success"] and result.get("error"):
                        err_line = result["error"].strip().split("\n")[-1][:120]
                        print(f"           -> {err_line}")

                results.append({
                    "script": script_name,
                    "category": cat,
                    "priority": prio,
                    "success": result["success"],
                    "duration_ms": dur,
                    "returncode": result.get("returncode", -1),
                })

    total = len(flat)
    if conn:
        conn.close()

    return total, succeeded, failed, results


def list_scripts(categories_filter=None):
    """List all discovered scripts with categories."""
    discovered = discover_scripts()

    if categories_filter:
        allowed = set(c.strip().lower() for c in categories_filter.split(","))
        discovered = {k: v for k, v in discovered.items() if k in allowed}

    total = 0
    for cat in sorted(discovered.keys()):
        scripts = sorted(discovered[cat], key=lambda x: x[0])
        print(f"\n  [{cat}] ({len(scripts)} scripts)")
        for script_name, prio in scripts:
            print(f"    P{prio}  {script_name}")
            total += 1

    print(f"\n  Total uncovered scripts: {total}")
    return total


def get_stats():
    """Get execution statistics from the database."""
    conn = get_db()
    rows = conn.execute("""
        SELECT script_name, category,
               COUNT(*) as runs,
               SUM(success) as ok,
               AVG(duration_ms) as avg_ms,
               MAX(timestamp) as last_run
        FROM utility_runner_log
        GROUP BY script_name
        ORDER BY category, script_name
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# 8) CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Utility Mega Runner -- safety net for uncovered scripts"
    )
    parser.add_argument("--once", action="store_true",
                        help="Run all discovered scripts once")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would run without executing")
    parser.add_argument("--list", action="store_true",
                        help="List all discovered scripts with categories")
    parser.add_argument("--stats", action="store_true",
                        help="Show execution statistics from DB")
    parser.add_argument("--category", type=str, default=None,
                        help="Filter by category (comma-separated)")
    parser.add_argument("--timeout", type=int, default=60,
                        help="Timeout per script in seconds (default: 60)")
    parser.add_argument("--json", action="store_true",
                        help="Output results as JSON")
    parser.add_argument("--verbose", action="store_true",
                        help="Verbose output")

    args = parser.parse_args()

    if not any([args.once, args.dry_run, args.list, args.stats]):
        parser.print_help()
        sys.exit(1)

    if args.list:
        total = list_scripts(args.category)
        if args.json:
            discovered = discover_scripts()
            print(json.dumps({
                cat: [s[0] for s in scripts]
                for cat, scripts in discovered.items()
            }, indent=2))
        sys.exit(0)

    if args.stats:
        stats = get_stats()
        if args.json:
            print(json.dumps(stats, indent=2))
        else:
            for s in stats:
                ok_rate = (s["ok"] / s["runs"] * 100) if s["runs"] else 0
                print(f"  {s['script_name']:45} [{s['category']:20}] "
                      f"runs={s['runs']} ok={ok_rate:.0f}% "
                      f"avg={s['avg_ms']:.0f}ms last={s['last_run']}")
        sys.exit(0)

    if args.dry_run:
        print("=== Utility Mega Runner -- Dry Run ===")
        total, _, _, results = run_all(
            categories_filter=args.category,
            timeout_s=args.timeout,
            dry_run=True,
            verbose=True,
        )
        print(f"\n  Would run {total} scripts")
        if args.json:
            print(json.dumps(results, indent=2))
        sys.exit(0)

    if args.once:
        # Check VRAM guard pause flag
        _pause_flag = SCRIPT_DIR.parent.parent / "data" / ".cowork-paused"
        if _pause_flag.exists():
            print("[PAUSED] VRAM guard has paused cowork execution. Skipping.")
            sys.exit(0)

        ts_start = datetime.now().strftime("%H:%M:%S")
        print(f"[{ts_start}] Utility Mega Runner -- executing uncovered scripts...")

        total, succeeded, failed, results = run_all(
            categories_filter=args.category,
            timeout_s=args.timeout,
            dry_run=False,
            verbose=not args.json,
        )

        ts_end = datetime.now().strftime("%H:%M:%S")
        total_ms = sum(r.get("duration_ms", 0) for r in results)

        summary = {
            "timestamp": datetime.now().isoformat(),
            "total": total,
            "succeeded": succeeded,
            "failed": failed,
            "total_duration_ms": total_ms,
            "categories": {},
        }
        for r in results:
            cat = r.get("category", "misc")
            summary["categories"].setdefault(cat, {"ok": 0, "fail": 0})
            if r.get("success"):
                summary["categories"][cat]["ok"] += 1
            else:
                summary["categories"][cat]["fail"] += 1

        if args.json:
            summary["results"] = results
            print(json.dumps(summary, indent=2))
        else:
            print(f"\n[{ts_end}] Done: {succeeded}/{total} succeeded, "
                  f"{failed} failed ({total_ms}ms total)")
            for cat, counts in sorted(summary["categories"].items()):
                print(f"  {cat:25} OK={counts['ok']} FAIL={counts['fail']}")

        sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
