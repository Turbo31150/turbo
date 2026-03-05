#!/usr/bin/env python3
"""test_monitoring_stack.py — Integration tests for monitoring and resilience stack.

Tests:
1. Resilient dispatcher (retry + circuit breaker)
2. Latency monitor (probe + baseline + anomaly)
3. Node reliability scorer (composite scores)
4. Adaptive load balancer (selection + dispatch)
5. Grade optimizer (analyze + optimize)
6. Continuous improver (fast cycle)
7. Cross-system: routing uses reliability scores

Stdlib-only.
"""

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
GAPS_DB = SCRIPT_DIR / "data" / "cowork_gaps.db"
ETOILE_DB = Path("F:/BUREAU/turbo/data/etoile.db")

passed = 0
failed = 0
total = 0


def test(name, condition, detail=""):
    global passed, failed, total
    total += 1
    if condition:
        passed += 1
        print(f"  PASS {name}")
    else:
        failed += 1
        print(f"  FAIL {name} -- {detail}")


def run_script(script, args, timeout=60):
    """Run a cowork script and return (success, stdout, stderr)."""
    cmd = [sys.executable, str(SCRIPT_DIR / script)] + args
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=str(SCRIPT_DIR))
        return r.returncode == 0, r.stdout, r.stderr
    except Exception as e:
        return False, "", str(e)


print("=== Monitoring Stack Tests ===\n")

# 1. Resilient Dispatcher
print("[1] Resilient Dispatcher")
ok, out, err = run_script("resilient_dispatcher.py", ["--status"])
test("CB status runs", ok)
test("CB output has nodes", "M1" in out and "OL1" in out)

ok, out, err = run_script("resilient_dispatcher.py", ["--dispatch", "simple", "/nothink OK", "--json"], timeout=30)
if ok:
    try:
        data = json.loads(out)
        test("Dispatch succeeds", data.get("success"))
        test("Dispatch has node", data.get("node") in ["M1", "OL1", "M2", "M3"])
        test("Dispatch has latency", data.get("latency_ms", 0) > 0)
    except json.JSONDecodeError:
        test("Dispatch JSON parse", False, out[:100])
else:
    test("Dispatch command runs", False, err[:100])

# 2. Latency Monitor
print("\n[2] Latency Monitor")
ok, out, err = run_script("latency_monitor.py", ["--baselines"])
test("Baselines runs", ok)
test("Baselines has data", "avg=" in out or "No baselines" in out)

# 3. Node Reliability Scorer
print("\n[3] Node Reliability Scorer")
ok, out, err = run_script("node_reliability_scorer.py", ["--once", "--update"])
test("Scorer runs", ok)
test("Scorer shows rankings", "#1" in out and "#2" in out)

# Verify DB storage
db = sqlite3.connect(str(GAPS_DB), timeout=30)
db.execute("PRAGMA journal_mode=WAL")
db.row_factory = sqlite3.Row
try:
    rows = db.execute("SELECT * FROM node_reliability ORDER BY rank").fetchall()
    test("Reliability table populated", len(rows) >= 4)
    test("Scores in range", all(0 <= r["composite"] <= 100 for r in rows))
except Exception as e:
    test("Reliability table exists", False, str(e))

# 4. Adaptive Load Balancer
print("\n[4] Adaptive Load Balancer")
ok, out, err = run_script("adaptive_load_balancer.py", ["--once"])
test("Load balancer runs", ok)
test("Load shows nodes", "M1" in out and "OL1" in out)

ok, out, err = run_script("adaptive_load_balancer.py", ["--simulate", "10"])
test("Simulate runs", ok)
test("Distribution shown", "Distribution" in out)

# 5. Grade Optimizer
print("\n[5] Grade Optimizer")
ok, out, err = run_script("grade_optimizer.py", ["--analyze"])
test("Analyzer runs", ok)
if ok:
    try:
        # Find JSON in output
        json_start = out.index("{")
        data = json.loads(out[json_start:])
        test("Grade computed", data.get("overall", 0) > 0)
        test("All components present", all(k in data for k in ["cluster", "dispatch", "orchestrator", "risk"]))
        test("Grade is A or better", data.get("grade", "F") in ["A+", "A", "A-"])
    except (ValueError, json.JSONDecodeError) as e:
        test("Grade JSON parse", False, str(e)[:80])

# 6. Circuit Breaker Table
print("\n[6] Circuit Breaker DB")
try:
    rows = db.execute("SELECT * FROM circuit_breaker_state").fetchall()
    test("CB table exists", True)
    test("CB has nodes", len(rows) >= 1)
    for r in rows:
        test(f"CB {r['node']} state valid", r["state"] in ["CLOSED", "OPEN", "HALF_OPEN"])
except Exception as e:
    test("CB table accessible", False, str(e))

# 7. Latency Baselines DB
print("\n[7] Latency Baselines DB")
try:
    rows = db.execute("SELECT * FROM latency_baselines").fetchall()
    test("Baselines table exists", True)
    test("Baselines populated", len(rows) >= 2)
    for r in rows:
        test(f"Baseline {r['node']} avg valid", r["avg_ms"] > 0)
except Exception as e:
    test("Baselines accessible", False, str(e))

# 8. Cross-system: Dispatch log growth
print("\n[8] Cross-system Integration")
edb = sqlite3.connect(str(ETOILE_DB), timeout=30)
edb.row_factory = sqlite3.Row
try:
    cnt = edb.execute("SELECT COUNT(*) FROM agent_dispatch_log").fetchone()[0]
    test("Dispatch log has records", cnt > 50)
    # Check recent records from our tools
    recent = edb.execute("""
        SELECT COUNT(*) FROM agent_dispatch_log
        WHERE agent_id LIKE 'resilient%' OR agent_id LIKE 'opt%'
    """).fetchone()[0]
    test("Our tools logged dispatches", recent > 0)
except Exception as e:
    test("Dispatch log accessible", False, str(e))
edb.close()

# 9. Load tracking DB
print("\n[9] Load Tracking DB")
try:
    rows = db.execute("SELECT * FROM node_load").fetchall()
    test("Load table exists", True)
    test("Load tracking active", len(rows) >= 1)
except Exception as e:
    test("Load table accessible", False, str(e))

db.close()

# Summary
print(f"\n{'='*40}")
print(f"  Results: {passed}/{total} passed ({failed} failed)")
print(f"  Rate: {passed/total*100:.0f}%")
if failed == 0:
    print("  ALL TESTS PASSED")
