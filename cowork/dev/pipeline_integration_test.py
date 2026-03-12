#!/usr/bin/env python3
"""pipeline_integration_test.py — End-to-end test of JARVIS autonomous pipeline.

Tests the full chain:
1. Heartbeat -> node status
2. Quality benchmark -> dispatch log
3. Learner -> routing recommendations
4. Routing engine -> optimal routes
5. Health summary -> overall score
6. Orchestrator -> all tasks execute

CLI:
    --once         : Run full integration test
    --quick        : Quick smoke test (skip benchmark)

Stdlib-only (json, argparse, subprocess, sqlite3, time).
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
from _paths import ETOILE_DB
GAPS_DB = SCRIPT_DIR / "data" / "cowork_gaps.db"

TESTS = []
PASS = 0
FAIL = 0


def test(name, func):
    """Run a test and track result."""
    global PASS, FAIL
    try:
        result = func()
        if result:
            PASS += 1
            print(f"  PASS  {name}")
            return True
        else:
            FAIL += 1
            print(f"  FAIL  {name}")
            return False
    except Exception as e:
        FAIL += 1
        print(f"  FAIL  {name}: {e}")
        return False


def run_script(script, args, timeout=120):
    """Run a cowork script and return (success, output)."""
    cmd = [sys.executable, str(SCRIPT_DIR / script)] + args
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=str(SCRIPT_DIR))
        return r.returncode == 0, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return False, "", "timeout"
    except Exception as e:
        return False, "", str(e)


def main():
    global PASS, FAIL
    parser = argparse.ArgumentParser(description="Pipeline Integration Test")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--quick", action="store_true", help="Quick smoke test")
    args = parser.parse_args()

    if not any([args.once, args.quick]):
        parser.print_help()
        sys.exit(1)

    start = time.time()
    print("=== JARVIS Pipeline Integration Test ===\n")

    # 1. Test heartbeat
    print("1. Cluster Heartbeat")
    ok, out, err = run_script("cluster_heartbeat.py", ["--once"])
    test("heartbeat executes", lambda: ok)
    test("heartbeat shows online nodes", lambda: "online" in out.lower())
    if ok:
        try:
            # Find JSON in output (may have text before it)
            json_start = out.index("{")
            data = json.loads(out[json_start:])
            test("heartbeat has node data", lambda: data.get("online", 0) >= 1)
        except (ValueError, json.JSONDecodeError):
            test("heartbeat has node data", lambda: "online" in out.lower())

    # 2. Test crypto alerts
    print("\n2. Crypto Price Alerts")
    ok, out, err = run_script("crypto_price_alert.py", ["--once", "--pairs", "IPUSDT"])
    test("crypto alert executes", lambda: ok)
    test("crypto shows price", lambda: "price" in out.lower())

    # 3. Test dispatch quality tracker
    print("\n3. Dispatch Quality Tracker")
    ok, out, err = run_script("dispatch_quality_tracker.py", ["--init"])
    test("tracker init", lambda: ok)
    ok, out, err = run_script("dispatch_quality_tracker.py", ["--once"])
    test("tracker analysis", lambda: ok)

    # 4. Quality benchmark (skip if --quick)
    if not args.quick:
        print("\n4. Quality Benchmark (this takes ~3 min)")
        ok, out, err = run_script("dispatch_quality_tracker.py", ["--benchmark"], timeout=300)
        test("benchmark executes", lambda: ok)
        if ok:
            test("benchmark has results", lambda: "benchmark" in out.lower() or "M1" in out)
    else:
        print("\n4. Quality Benchmark [SKIPPED --quick]")

    # 5. Test dispatch learner
    print("\n5. Dispatch Learner")
    ok, out, err = run_script("dispatch_learner.py", ["--routing"])
    test("learner routing", lambda: ok)
    ok, out, err = run_script("dispatch_learner.py", ["--learn"])
    test("learner learning cycle", lambda: ok)
    test("learner outputs routes", lambda: "Route" in out or "route" in out or "Routing" in out)

    # 6. Test smart routing engine
    print("\n6. Smart Routing Engine")
    ok, out, err = run_script("smart_routing_engine.py", ["--once"])
    test("routing table", lambda: ok)
    test("routing shows nodes", lambda: "M1" in out or "OL1" in out)
    ok, out, err = run_script("smart_routing_engine.py", ["--route", "code"])
    test("route for code type", lambda: ok and ("M1" in out or "OL1" in out))

    # 7. Test health summary
    print("\n7. Health Summary")
    ok, out, err = run_script("cowork_health_summary.py", ["--once"], timeout=60)
    test("health summary executes", lambda: ok)
    if ok:
        try:
            data = json.loads(out)
            test("health has overall_score", lambda: "overall_score" in data)
            test("health score > 50", lambda: data.get("overall_score", 0) > 50)
            test("health has grade", lambda: "grade" in data)
        except:
            test("health JSON parse", lambda: False)

    # 8. Test orchestrator
    print("\n8. Autonomous Orchestrator")
    ok, out, err = run_script("autonomous_orchestrator.py", ["--dry-run"])
    test("orchestrator dry-run", lambda: ok)
    test("orchestrator lists tasks", lambda: "heartbeat" in out.lower() or "Running" in out)

    # 9. Database integrity
    print("\n9. Database Integrity")
    try:
        edb = sqlite3.connect(str(ETOILE_DB), timeout=10)
        has_dispatch = edb.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE name='agent_dispatch_log'"
        ).fetchone()[0]
        test("agent_dispatch_log exists", lambda: has_dispatch == 1)
        if has_dispatch:
            cnt = edb.execute("SELECT COUNT(*) FROM agent_dispatch_log").fetchone()[0]
            test("dispatch log has data", lambda: cnt > 0)
        has_mapping = edb.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE name='cowork_script_mapping'"
        ).fetchone()[0]
        test("cowork_script_mapping exists", lambda: has_mapping == 1)
        if has_mapping:
            cnt = edb.execute("SELECT COUNT(*) FROM cowork_script_mapping WHERE status='active'").fetchone()[0]
            test("script mappings > 350", lambda: cnt > 350)
        edb.close()
    except Exception as e:
        test("etoile.db accessible", lambda: False)

    try:
        gdb = sqlite3.connect(str(GAPS_DB), timeout=10)
        tables = ["heartbeat_log", "heartbeat_state", "orchestrator_runs",
                   "routing_recommendations", "timeout_configs"]
        for t in tables:
            has = gdb.execute(
                f"SELECT COUNT(*) FROM sqlite_master WHERE name='{t}'"
            ).fetchone()[0]
            test(f"table {t} exists", lambda: has == 1)
        gdb.close()
    except Exception as e:
        test("cowork_gaps.db accessible", lambda: False)

    # Summary
    elapsed = time.time() - start
    total = PASS + FAIL
    print(f"\n{'='*50}")
    print(f"Results: {PASS}/{total} passed ({PASS/max(total,1)*100:.0f}%) in {elapsed:.1f}s")
    if FAIL == 0:
        print("ALL TESTS PASSED")
    else:
        print(f"{FAIL} FAILURES")

    result = {
        "timestamp": datetime.now().isoformat(),
        "total": total, "passed": PASS, "failed": FAIL,
        "elapsed_s": round(elapsed, 1),
        "pass_rate": round(PASS / max(total, 1) * 100, 1),
    }
    print(json.dumps(result, indent=2))
    sys.exit(0 if FAIL == 0 else 1)


if __name__ == "__main__":
    main()
