#!/usr/bin/env python3
"""cross_script_integration_tester.py — Tests that COWORK scripts work together correctly.

Runs integration tests that verify cross-script pipelines, data flow,
and inter-module compatibility within the COWORK ecosystem.

Integration test cases:
  1. pipeline_health    — health watchdog -> alert monitor pipeline
  2. pipeline_quality   — quality scorer -> auto-improver --dry-run pipeline
  3. pipeline_cycle     — cowork_full_cycle --quick (all subscripts execute)
  4. pipeline_scheduler — cowork_scheduler --status (task list correct)
  5. dashboard_sections — telegram_cowork_dashboard section functions return (text, kb)
  6. data_consistency   — etoile.db tables have expected data
  7. self_test_levels   — cowork_self_test_runner --level 1, 2, 3 all pass

CLI:
    --once       : run all integration tests
    --quick      : run fast subset (pipeline_health, pipeline_cycle, data_consistency)
    --stats      : show test history

Stdlib-only (sqlite3, json, argparse, subprocess, time).
"""

import argparse
import json
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data"
DB_PATH = DATA_DIR / "cowork_gaps.db"
from _paths import ETOILE_DB
PYTHON = sys.executable


# ── Database ─────────────────────────────────────────────────────────────────

def init_db(conn):
    """Create integration_tests table if it does not exist, migrate if needed."""
    conn.execute("""CREATE TABLE IF NOT EXISTS integration_tests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        test_name TEXT NOT NULL,
        status TEXT NOT NULL,
        duration_ms INTEGER,
        error TEXT
    )""")
    # Migrate: old schema had 'details' and 'pattern' instead of 'error'
    cols = [r[1] for r in conn.execute("PRAGMA table_info(integration_tests)").fetchall()]
    if "error" not in cols:
        try:
            conn.execute("ALTER TABLE integration_tests ADD COLUMN error TEXT")
        except Exception:
            pass
    conn.commit()


def get_db():
    """Open (and initialize) the database."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


# ── Helpers ──────────────────────────────────────────────────────────────────

def run_script(name, args, timeout=120):
    """Run a COWORK script via subprocess and return (returncode, stdout, stderr)."""
    script_path = SCRIPT_DIR / f"{name}.py"
    if not script_path.exists():
        return -1, "", f"Script not found: {name}.py"

    cmd = [PYTHON, str(script_path)]
    if isinstance(args, list):
        cmd.extend(args)
    else:
        cmd.append(args)

    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=timeout, cwd=str(SCRIPT_DIR)
        )
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return -2, "", f"Timeout after {timeout}s"
    except Exception as e:
        return -3, "", str(e)[:200]


def parse_json_output(stdout):
    """Try to parse stdout as JSON. Returns (data, error)."""
    text = stdout.strip()
    if not text:
        return None, "Empty output"
    try:
        return json.loads(text), None
    except json.JSONDecodeError as e:
        return None, f"Invalid JSON: {str(e)[:100]}"


def assert_keys(data, required_keys):
    """Check that data dict contains all required keys. Returns error or None."""
    if not isinstance(data, dict):
        return f"Expected dict, got {type(data).__name__}"
    missing = [k for k in required_keys if k not in data]
    if missing:
        return f"Missing keys: {', '.join(missing)}"
    return None


# ── Integration Test Cases ───────────────────────────────────────────────────

def test_pipeline_health():
    """Test 1: cluster_health_watchdog -> proactive_alert_monitor pipeline.

    Verify that alert_monitor can consume health data produced by the watchdog.
    """
    errors = []

    # Step 1: Run health watchdog
    rc1, out1, err1 = run_script("cluster_health_watchdog", "--once", timeout=30)
    if rc1 != 0:
        return f"cluster_health_watchdog failed (rc={rc1}): {err1[:150]}"

    data1, jerr1 = parse_json_output(out1)
    if jerr1:
        return f"cluster_health_watchdog output: {jerr1}"

    key_err = assert_keys(data1, ["cluster_status", "nodes", "alerts"])
    if key_err:
        errors.append(f"health_watchdog: {key_err}")

    # Verify nodes list is non-empty and has expected structure
    nodes = data1.get("nodes", [])
    if not nodes:
        errors.append("health_watchdog returned 0 nodes")
    else:
        for node in nodes:
            nk_err = assert_keys(node, ["node", "status", "response_ms"])
            if nk_err:
                errors.append(f"node {node.get('node', '?')}: {nk_err}")
                break

    # Step 2: Run alert monitor (internally calls health watchdog and reads its data)
    rc2, out2, err2 = run_script("proactive_alert_monitor", "--once", timeout=60)
    if rc2 != 0:
        return f"proactive_alert_monitor failed (rc={rc2}): {err2[:150]}"

    data2, jerr2 = parse_json_output(out2)
    if jerr2:
        return f"proactive_alert_monitor output: {jerr2}"

    key_err2 = assert_keys(data2, ["checks_run", "alerts_generated", "status"])
    if key_err2:
        errors.append(f"alert_monitor: {key_err2}")

    # Verify alert_monitor ran health checks (checks_run >= 1)
    if data2.get("checks_run", 0) < 1:
        errors.append("alert_monitor ran 0 checks")

    return "; ".join(errors) if errors else None


def test_pipeline_quality():
    """Test 2: dispatch_quality_scorer -> cowork_auto_improver --dry-run pipeline.

    Verify that the improver can read quality analysis output.
    """
    errors = []

    # Step 1: Run quality scorer
    rc1, out1, err1 = run_script("dispatch_quality_scorer", "--once", timeout=60)
    if rc1 != 0:
        return f"dispatch_quality_scorer failed (rc={rc1}): {err1[:150]}"

    data1, jerr1 = parse_json_output(out1)
    if jerr1:
        return f"dispatch_quality_scorer output: {jerr1}"

    key_err = assert_keys(data1, ["overall_quality", "quality_map"])
    if key_err:
        errors.append(f"quality_scorer: {key_err}")

    # Step 2: Run auto-improver in dry-run mode (reads quality data from DB)
    rc2, out2, err2 = run_script("cowork_auto_improver", "--dry-run", timeout=120)
    if rc2 != 0:
        return f"cowork_auto_improver --dry-run failed (rc={rc2}): {err2[:150]}"

    data2, jerr2 = parse_json_output(out2)
    if jerr2:
        return f"cowork_auto_improver output: {jerr2}"

    key_err2 = assert_keys(data2, ["total_improvements", "by_type", "total"])
    if key_err2:
        errors.append(f"auto_improver: {key_err2}")

    # Verify dry-run did not apply anything
    applied = data2.get("applied", 0)
    if applied != 0:
        errors.append(f"auto_improver --dry-run applied {applied} changes (expected 0)")

    return "; ".join(errors) if errors else None


def test_pipeline_cycle():
    """Test 3: cowork_full_cycle --quick verifies all subscripts execute."""
    rc, out, err = run_script("cowork_full_cycle", "--quick", timeout=120)
    if rc != 0:
        return f"cowork_full_cycle --quick failed (rc={rc}): {err[:150]}"

    data, jerr = parse_json_output(out)
    if jerr:
        return f"cowork_full_cycle output: {jerr}"

    errors = []
    key_err = assert_keys(data, ["total_scripts", "ok", "errors", "duration_ms", "results"])
    if key_err:
        return f"full_cycle: {key_err}"

    total = data.get("total_scripts", 0)
    ok = data.get("ok", 0)
    if total == 0:
        errors.append("full_cycle ran 0 scripts")

    # Check each result entry has required fields
    for r in data.get("results", []):
        rk_err = assert_keys(r, ["script", "status"])
        if rk_err:
            errors.append(f"result entry: {rk_err}")
            break

    # Allow some failures (network-dependent) but at least half should pass
    if total > 0 and ok < total // 2:
        errors.append(f"Too many failures: {ok}/{total} OK")

    return "; ".join(errors) if errors else None


def test_pipeline_scheduler():
    """Test 4: cowork_scheduler --status verifies task list is correct."""
    rc, out, err = run_script("cowork_scheduler", "--status", timeout=30)
    if rc != 0:
        return f"cowork_scheduler --status failed (rc={rc}): {err[:150]}"

    data, jerr = parse_json_output(out)
    if jerr:
        return f"cowork_scheduler output: {jerr}"

    errors = []
    key_err = assert_keys(data, ["total_tasks", "tasks"])
    if key_err:
        return f"scheduler: {key_err}"

    tasks = data.get("tasks", [])
    if not tasks:
        errors.append("scheduler has 0 tasks")

    # Verify each task has required structure
    required_task_keys = ["task_name", "script_name", "interval_minutes", "enabled"]
    for task in tasks:
        tk_err = assert_keys(task, required_task_keys)
        if tk_err:
            errors.append(f"task '{task.get('task_name', '?')}': {tk_err}")
            break

    # Verify some expected tasks exist
    task_names = {t.get("task_name") for t in tasks}
    expected_names = {"health_check", "quality_check", "self_tests"}
    found = expected_names & task_names
    if not found:
        errors.append(f"None of expected tasks found: {expected_names}")

    return "; ".join(errors) if errors else None


def test_dashboard_sections():
    """Test 5: Import telegram_cowork_dashboard, call section functions.

    Verify each returns a (text, keyboard) tuple.
    """
    # Build inline test code that imports the dashboard and calls each section
    escaped_dir = str(SCRIPT_DIR).replace("/", "//")
    test_code = (
        "import sys, json\n"
        f"sys.path.insert(0, r\"{escaped_dir}\")\n"
        "import telegram_cowork_dashboard as tcd\n"
        "\n"
        "sections = ['section_main', 'section_cluster', 'section_gpu',\n"
        "            'section_dispatch', 'section_quality', 'section_errors',\n"
        "            'section_trends', 'section_tests', 'section_cycle',\n"
        "            'section_improve', 'section_nodes', 'section_history',\n"
        "            'section_search', 'section_scheduler']\n"
        "\n"
        "results = []\n"
        "for name in sections:\n"
        "    fn = getattr(tcd, name, None)\n"
        "    if fn is None:\n"
        "        results.append({'name': name, 'ok': False, 'error': 'function not found'})\n"
        "        continue\n"
        "    try:\n"
        "        ret = fn()\n"
        "        if not isinstance(ret, tuple) or len(ret) != 2:\n"
        "            results.append({'name': name, 'ok': False,\n"
        "                            'error': f'expected (text, kb) tuple, got {type(ret).__name__}'})\n"
        "            continue\n"
        "        text, kb = ret\n"
        "        if not isinstance(text, str):\n"
        "            results.append({'name': name, 'ok': False,\n"
        "                            'error': f'text is {type(text).__name__}, expected str'})\n"
        "            continue\n"
        "        if not isinstance(kb, list):\n"
        "            results.append({'name': name, 'ok': False,\n"
        "                            'error': f'kb is {type(kb).__name__}, expected list'})\n"
        "            continue\n"
        "        results.append({'name': name, 'ok': True, 'text_len': len(text), 'kb_rows': len(kb)})\n"
        "    except Exception as e:\n"
        "        results.append({'name': name, 'ok': False, 'error': str(e)[:120]})\n"
        "\n"
        "print(json.dumps({'sections': results,\n"
        "                   'total': len(sections),\n"
        "                   'passed': sum(1 for r in results if r['ok']),\n"
        "                   'failed': sum(1 for r in results if not r['ok'])}))\n"
    )

    try:
        r = subprocess.run(
            [PYTHON, "-c", test_code],
            capture_output=True, text=True, timeout=120,
            cwd=str(SCRIPT_DIR)
        )
    except subprocess.TimeoutExpired:
        return "Dashboard section test timed out (120s)"
    except Exception as e:
        return f"Failed to run dashboard test: {str(e)[:150]}"

    if r.returncode != 0:
        return f"Dashboard test process failed (rc={r.returncode}): {r.stderr[:200]}"

    data, jerr = parse_json_output(r.stdout)
    if jerr:
        return f"Dashboard test output: {jerr}"

    errors = []
    failed_sections = [s for s in data.get("sections", []) if not s.get("ok")]
    if failed_sections:
        msgs = [f"{s['name']}: {s.get('error', '?')}" for s in failed_sections[:5]]
        errors.extend(msgs)

    return "; ".join(errors) if errors else None


def test_data_consistency():
    """Test 6: Open etoile.db, verify agent_dispatch_log and cowork_script_mapping have data."""
    errors = []

    if not ETOILE_DB.exists():
        return f"etoile.db not found at {ETOILE_DB}"

    try:
        conn = sqlite3.connect(str(ETOILE_DB))
        conn.row_factory = sqlite3.Row

        # List tables
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()]

        # Check agent_dispatch_log has data
        if "agent_dispatch_log" not in tables:
            errors.append("agent_dispatch_log table missing")
        else:
            count = conn.execute("SELECT COUNT(*) FROM agent_dispatch_log").fetchone()[0]
            if count == 0:
                errors.append("agent_dispatch_log is empty")

            # Verify expected columns exist
            cols = [r[1] for r in conn.execute(
                "PRAGMA table_info(agent_dispatch_log)"
            ).fetchall()]
            expected_cols = ["node", "success", "latency_ms"]
            for ec in expected_cols:
                if ec not in cols:
                    errors.append(f"agent_dispatch_log missing column: {ec}")

        # Check cowork_script_mapping has entries
        if "cowork_script_mapping" not in tables:
            errors.append("cowork_script_mapping table missing")
        else:
            count = conn.execute("SELECT COUNT(*) FROM cowork_script_mapping").fetchone()[0]
            if count == 0:
                errors.append("cowork_script_mapping is empty")

            # Verify at least some entries are active
            active = conn.execute(
                "SELECT COUNT(*) FROM cowork_script_mapping WHERE status='active'"
            ).fetchone()[0]
            if active == 0:
                errors.append("cowork_script_mapping has 0 active entries")

        conn.close()
    except Exception as e:
        return f"DB error: {str(e)[:200]}"

    return "; ".join(errors) if errors else None


def test_self_test_levels():
    """Test 7: Run cowork_self_test_runner --level 1, 2, 3 and verify all pass."""
    errors = []

    for level in [1, 2, 3]:
        rc, out, err = run_script(
            "cowork_self_test_runner", ["--level", str(level)], timeout=120
        )
        if rc != 0:
            errors.append(f"Level {level} failed (rc={rc}): {err[:100]}")
            continue

        data, jerr = parse_json_output(out)
        if jerr:
            errors.append(f"Level {level} output: {jerr}")
            continue

        key_err = assert_keys(data, ["passed", "failed", "success_rate_pct", "total_tests"])
        if key_err:
            errors.append(f"Level {level}: {key_err}")
            continue

        total = data.get("total_tests", 0)
        passed = data.get("passed", 0)
        failed = data.get("failed", 0)
        rate = data.get("success_rate_pct", 0)

        if total == 0:
            errors.append(f"Level {level}: 0 tests ran")
        elif rate < 80:
            errors.append(
                f"Level {level}: {rate}% pass rate ({passed}/{total}), {failed} failed"
            )

    return "; ".join(errors) if errors else None


# ── Test Registry ────────────────────────────────────────────────────────────

ALL_TESTS = [
    ("pipeline_health", test_pipeline_health),
    ("pipeline_quality", test_pipeline_quality),
    ("pipeline_cycle", test_pipeline_cycle),
    ("pipeline_scheduler", test_pipeline_scheduler),
    ("dashboard_sections", test_dashboard_sections),
    ("data_consistency", test_data_consistency),
    ("self_test_levels", test_self_test_levels),
]

QUICK_TESTS = {"pipeline_health", "pipeline_cycle", "data_consistency"}


# ── Runner ───────────────────────────────────────────────────────────────────

def run_integration_tests(quick=False):
    """Run integration tests and store results in cowork_gaps.db."""
    conn = get_db()
    ts = datetime.now().isoformat()
    t0_global = time.time()

    tests_to_run = [(n, f) for n, f in ALL_TESTS if not quick or n in QUICK_TESTS]

    results = []
    passed = 0
    failed = 0

    for test_name, test_fn in tests_to_run:
        t0 = time.time()
        try:
            error = test_fn()
        except Exception as e:
            error = f"Exception: {str(e)[:200]}"
        duration_ms = int((time.time() - t0) * 1000)

        status = "passed" if error is None else "failed"
        if status == "passed":
            passed += 1
        else:
            failed += 1

        result = {
            "test_name": test_name,
            "status": status,
            "duration_ms": duration_ms,
            "error": error,
        }
        results.append(result)

        # Store in DB
        conn.execute("""
            INSERT INTO integration_tests
            (timestamp, test_name, status, duration_ms, error)
            VALUES (?, ?, ?, ?, ?)
        """, (ts, test_name, status, duration_ms, error))

    conn.commit()
    conn.close()

    total = len(tests_to_run)
    total_duration_ms = int((time.time() - t0_global) * 1000)

    return {
        "total_tests": total,
        "passed": passed,
        "failed": failed,
        "success_rate_pct": round(passed / max(total, 1) * 100, 1),
        "duration_ms": total_duration_ms,
        "results": results,
    }


def show_stats():
    """Show test history from the database."""
    conn = get_db()

    # Recent runs (aggregate by timestamp)
    runs = conn.execute("""
        SELECT timestamp,
               COUNT(*) as total,
               SUM(CASE WHEN status = 'passed' THEN 1 ELSE 0 END) as passed,
               SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
               SUM(duration_ms) as total_duration_ms
        FROM integration_tests
        GROUP BY timestamp
        ORDER BY timestamp DESC
        LIMIT 20
    """).fetchall()

    # Per-test pass rates
    per_test = conn.execute("""
        SELECT test_name,
               COUNT(*) as runs,
               SUM(CASE WHEN status = 'passed' THEN 1 ELSE 0 END) as passed,
               ROUND(AVG(CASE WHEN status = 'passed' THEN 100.0 ELSE 0.0 END), 1) as pass_rate_pct,
               ROUND(AVG(duration_ms)) as avg_duration_ms
        FROM integration_tests
        GROUP BY test_name
        ORDER BY pass_rate_pct ASC
    """).fetchall()

    # Recent failures
    recent_failures = conn.execute("""
        SELECT timestamp, test_name, error
        FROM integration_tests
        WHERE status = 'failed'
        ORDER BY id DESC
        LIMIT 10
    """).fetchall()

    conn.close()

    return {
        "recent_runs": [dict(r) for r in runs],
        "per_test_stats": [dict(r) for r in per_test],
        "recent_failures": [dict(r) for r in recent_failures],
    }


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Cross-Script Integration Tester — verifies COWORK pipeline interoperability"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--once", action="store_true", help="Run all integration tests")
    group.add_argument("--quick", action="store_true", help="Run fast subset (health, cycle, data)")
    group.add_argument("--stats", action="store_true", help="Show test history")
    args = parser.parse_args()

    if args.stats:
        result = show_stats()
    elif args.quick:
        result = run_integration_tests(quick=True)
    else:
        result = run_integration_tests(quick=False)

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
