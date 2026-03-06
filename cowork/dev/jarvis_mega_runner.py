#!/usr/bin/env python3
"""jarvis_mega_runner.py — Unified runner for all jarvis_* scripts not individually wired.

Scans F:\\BUREAU\\turbo\\cowork\\dev\\ for jarvis_*.py scripts, excludes those
already wired in the autonomous_orchestrator (jarvis_brain, jarvis_night_ops,
jarvis_self_evolve) and itself, then executes them in priority order.

Categories (priority ascending = runs first):
  1. health      — aggregators, monitors, health checks
  2. monitoring  — pipeline monitors, performance trackers, profilers
  3. intelligence — brain-adjacent, classifiers, predictors, NLP, context
  4. maintenance — backups, migrations, cache, cleanup, config
  5. evolution   — self-improve, generators, builders, evolvers

Each script gets 60s timeout. Failures are logged but never stop the run.
Results go to cowork_gaps.db table jarvis_runner_log.

CLI:
    python jarvis_mega_runner.py --once       # single pass, all scripts
    python jarvis_mega_runner.py --once -v    # verbose output
    python jarvis_mega_runner.py --list       # list discovered scripts
    python jarvis_mega_runner.py --category health  # run only one category

Stdlib-only: subprocess, sqlite3, pathlib, time, argparse, json, sys.
"""

import argparse
import json
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
DB_PATH = SCRIPT_DIR / "data" / "cowork_gaps.db"

# Scripts already wired individually in autonomous_orchestrator.py — skip them.
EXCLUDE = {
    "jarvis_brain.py",
    "jarvis_night_ops.py",
    "jarvis_self_evolve.py",
    "jarvis_mega_runner.py",  # self
}

# Per-script timeout in seconds.
SCRIPT_TIMEOUT = 60

# Scripts that do NOT accept --once and need special arguments.
SPECIAL_ARGS = {
    "jarvis_super_loop.py": ["--cycles", "1"],
    "jarvis_autonomy_engine.py": ["--scan"],
}

# Category classification by keyword matching on the filename.
# Order matters: first match wins.
CATEGORY_RULES = [
    # Priority 1 — health
    ("health", 1, [
        "health", "backup", "secret_scanner", "permission_auditor",
        "wake_word_tuner",
    ]),
    # Priority 2 — monitoring
    ("monitoring", 2, [
        "monitor", "tracker", "profiler", "pipeline_monitor",
        "usage_analytics", "response_profiler", "performance",
        "autonomy_monitor", "log_analyzer", "meta_dashboard",
        "dashboard", "roi_calculator",
    ]),
    # Priority 3 — intelligence
    ("intelligence", 3, [
        "intent", "classifier", "predictor", "nlp", "sentiment",
        "context", "embedding", "conversation", "dialog", "brain",
        "pattern_learner", "pattern_miner", "command_predictor",
        "personality", "dictation", "voice", "state_machine",
        "rule_engine", "message_router", "notification",
        "multi_language", "telegram",
    ]),
    # Priority 4 — maintenance
    ("maintenance", 4, [
        "backup", "migrator", "cache", "config", "cron",
        "data_exporter", "db_migrator", "tts_cache", "preloader",
        "update_checker", "memory_optimizer", "dependency_mapper",
        "webhook", "api_gateway", "template_engine", "macro",
        "release_manager", "response_cache", "plugin_tester",
    ]),
    # Priority 5 — evolution
    ("evolution", 5, [
        "evolve", "evolution", "improve", "improver", "generator",
        "builder", "feature", "skill", "recommender", "wiki",
        "faq", "changelog", "test_generator", "ab_tester",
        "code_auditor", "ecosystem", "orchestrator", "super_loop",
        "autonomy_engine", "master_autonome", "self_test",
        "daily_briefing", "event_stream",
    ]),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def classify(filename: str) -> tuple:
    """Return (category, priority) for a jarvis_*.py filename."""
    name_lower = filename.lower()
    for cat, prio, keywords in CATEGORY_RULES:
        for kw in keywords:
            if kw in name_lower:
                return cat, prio
    # Default fallback
    return "other", 5


def discover_scripts() -> list:
    """Scan SCRIPT_DIR for jarvis_*.py, exclude wired ones, classify."""
    scripts = []
    for p in sorted(SCRIPT_DIR.glob("jarvis_*.py")):
        if p.name in EXCLUDE:
            continue
        cat, prio = classify(p.name)
        args = SPECIAL_ARGS.get(p.name, ["--once"])
        scripts.append({
            "path": p,
            "name": p.name,
            "stem": p.stem,
            "category": cat,
            "priority": prio,
            "args": args,
        })
    # Sort by priority (1 first) then alphabetically within same priority
    scripts.sort(key=lambda s: (s["priority"], s["name"]))
    return scripts


def get_db() -> sqlite3.Connection:
    """Open (or create) the cowork_gaps.db with jarvis_runner_log table."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.row_factory = sqlite3.Row
    conn.execute("""CREATE TABLE IF NOT EXISTS jarvis_runner_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        script_name TEXT NOT NULL,
        category TEXT,
        priority INTEGER,
        success INTEGER DEFAULT 0,
        duration_ms INTEGER DEFAULT 0,
        return_code INTEGER,
        stdout_tail TEXT,
        stderr_tail TEXT,
        error_msg TEXT
    )""")
    conn.commit()
    return conn


def log_result(conn, run_id, script, result):
    """Insert one row into jarvis_runner_log with retry on DB lock."""
    now = datetime.now().isoformat()
    for attempt in range(5):
        try:
            conn.execute("""
                INSERT INTO jarvis_runner_log
                    (run_id, timestamp, script_name, category, priority,
                     success, duration_ms, return_code, stdout_tail, stderr_tail, error_msg)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                run_id, now, script["name"], script["category"], script["priority"],
                1 if result["success"] else 0,
                result.get("duration_ms", 0),
                result.get("return_code"),
                result.get("stdout_tail", "")[:500],
                result.get("stderr_tail", "")[:500],
                result.get("error", "")[:300],
            ))
            conn.commit()
            return
        except sqlite3.OperationalError as e:
            if "locked" in str(e) and attempt < 4:
                time.sleep(1 * (attempt + 1))
                continue
            raise


def run_script(script: dict, verbose: bool = False) -> dict:
    """Execute a single jarvis_* script with timeout."""
    cmd = [sys.executable, str(script["path"])] + script["args"]
    start = time.time()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=SCRIPT_TIMEOUT,
            cwd=str(SCRIPT_DIR),
        )
        elapsed_ms = int((time.time() - start) * 1000)
        return {
            "success": result.returncode == 0,
            "duration_ms": elapsed_ms,
            "return_code": result.returncode,
            "stdout_tail": (result.stdout or "")[-500:],
            "stderr_tail": (result.stderr or "")[-300:],
        }
    except subprocess.TimeoutExpired:
        elapsed_ms = int(SCRIPT_TIMEOUT * 1000)
        return {
            "success": False,
            "duration_ms": elapsed_ms,
            "return_code": -1,
            "error": f"Timeout after {SCRIPT_TIMEOUT}s",
        }
    except Exception as e:
        elapsed_ms = int((time.time() - start) * 1000)
        return {
            "success": False,
            "duration_ms": elapsed_ms,
            "return_code": -1,
            "error": str(e)[:300],
        }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="JARVIS Mega Runner — batch-execute all jarvis_* scripts"
    )
    parser.add_argument("--once", action="store_true", help="Run all scripts once")
    parser.add_argument("--list", action="store_true", help="List discovered scripts")
    parser.add_argument("--category", type=str, default=None,
                        help="Run only scripts in this category")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    args = parser.parse_args()

    if not any([args.once, args.list]):
        parser.print_help()
        sys.exit(1)

    scripts = discover_scripts()

    # Filter by category if requested
    if args.category:
        scripts = [s for s in scripts if s["category"] == args.category]

    if args.list:
        print(f"Discovered {len(scripts)} jarvis_* scripts to run:\n")
        current_cat = None
        for s in scripts:
            if s["category"] != current_cat:
                current_cat = s["category"]
                print(f"\n  [{current_cat.upper()}] (priority {s['priority']})")
            flag = " ".join(s["args"])
            print(f"    {s['name']:45s} {flag}")
        print(f"\nTotal: {len(scripts)} scripts")
        return

    # --once: run all
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    conn = get_db()

    print(f"[{run_id}] JARVIS Mega Runner — {len(scripts)} scripts to execute")
    print(f"         Timeout per script: {SCRIPT_TIMEOUT}s")
    print()

    ok_count = 0
    fail_count = 0
    skip_count = 0
    total_ms = 0
    results_summary = []

    for i, script in enumerate(scripts, 1):
        ts = datetime.now().strftime("%H:%M:%S")
        if args.verbose:
            print(f"  [{ts}] ({i}/{len(scripts)}) {script['name']} "
                  f"[{script['category']}] ...", end=" ", flush=True)

        result = run_script(script, verbose=args.verbose)
        log_result(conn, run_id, script, result)

        dur = result.get("duration_ms", 0)
        total_ms += dur

        if result["success"]:
            ok_count += 1
            status = "OK"
        else:
            fail_count += 1
            status = "FAIL"

        results_summary.append({
            "script": script["name"],
            "category": script["category"],
            "status": status,
            "duration_ms": dur,
            "error": result.get("error", ""),
        })

        if args.verbose:
            err_info = ""
            if not result["success"] and result.get("error"):
                err_info = f" — {result['error'][:80]}"
            elif not result["success"] and result.get("stderr_tail"):
                err_info = f" — {result['stderr_tail'][:80]}"
            print(f"{status} ({dur}ms){err_info}")

    conn.close()

    # Summary
    print()
    print(f"{'='*60}")
    print(f"  JARVIS Mega Runner — Run {run_id}")
    print(f"  Total:   {len(scripts)} scripts")
    print(f"  OK:      {ok_count}")
    print(f"  FAIL:    {fail_count}")
    print(f"  Duration: {total_ms}ms ({total_ms/1000:.1f}s)")
    print(f"{'='*60}")

    # Print failures if any
    failures = [r for r in results_summary if r["status"] == "FAIL"]
    if failures:
        print(f"\n  Failed scripts ({len(failures)}):")
        for f in failures:
            err = f.get("error", "unknown")[:100]
            print(f"    - {f['script']}: {err}")

    # JSON output for orchestrator consumption
    output = {
        "run_id": run_id,
        "timestamp": datetime.now().isoformat(),
        "total": len(scripts),
        "ok": ok_count,
        "fail": fail_count,
        "duration_ms": total_ms,
        "failures": [f["script"] for f in failures],
    }
    print(f"\n{json.dumps(output)}")

    # Exit code: 0 if at least 50% succeeded, 1 otherwise
    if len(scripts) > 0 and ok_count / len(scripts) < 0.5:
        sys.exit(1)


if __name__ == "__main__":
    main()
