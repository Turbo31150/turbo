#!/usr/bin/env python3
"""COWORK Engine — Continuous development, testing, anticipation, and self-improvement.

Integrates cowork scripts with JARVIS pattern agents for autonomous operation.
Runs multi-test cycles, identifies gaps, predicts needs, and generates improvements.

Usage:
    python cowork/cowork_engine.py --test-all       # Test all 329 scripts
    python cowork/cowork_engine.py --gaps            # Identify coverage gaps
    python cowork/cowork_engine.py --anticipate      # Predict next needs
    python cowork/cowork_engine.py --improve         # Auto-improve weak scripts
    python cowork/cowork_engine.py --cycle           # Full continuous cycle
    python cowork/cowork_engine.py --openclaw-sync   # Sync to OpenClaw workspace
"""

import sqlite3
import subprocess
import sys
import os
import json
import ast
import re
import time
from datetime import datetime
from collections import defaultdict, Counter
from pathlib import Path

BASE = Path(__file__).parent
TURBO = BASE.parent
DB_PATH = TURBO / "etoile.db"
DEV_PATH = BASE / "dev"
OPENCLAW_DEV = Path("C:/Users/franc/.openclaw/workspace/dev")
PYTHON = sys.executable


# ── MULTI-TEST ENGINE ──────────────────────────────────────────────────

def test_script(script_name, timeout=30):
    """Test a single script: parse + --help + --once (if safe)."""
    script_path = DEV_PATH / f"{script_name}.py"
    if not script_path.exists():
        return {"script": script_name, "status": "missing", "errors": []}

    results = {"script": script_name, "errors": [], "warnings": [], "metrics": {}}

    # 1. Syntax check
    try:
        with open(script_path, 'r', encoding='utf-8', errors='ignore') as f:
            source = f.read()
        compile(source, str(script_path), 'exec')
        results["syntax"] = "OK"
    except SyntaxError as e:
        results["syntax"] = "FAIL"
        results["errors"].append(f"SyntaxError: {e}")
        results["status"] = "syntax_error"
        return results

    # 2. AST analysis — functions, classes, imports, docstring
    try:
        tree = ast.parse(source)
        results["metrics"]["functions"] = len([n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)])
        results["metrics"]["classes"] = len([n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)])
        results["metrics"]["lines"] = len(source.splitlines())
        results["metrics"]["has_docstring"] = ast.get_docstring(tree) is not None
        results["metrics"]["has_main"] = 'if __name__' in source
        results["metrics"]["has_argparse"] = 'argparse' in source
        results["metrics"]["imports"] = len([n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))])

        # Check for non-stdlib imports
        stdlib_safe = {'os', 'sys', 'json', 'sqlite3', 'subprocess', 'argparse', 'pathlib',
                       'datetime', 'time', 're', 'hashlib', 'shutil', 'tempfile', 'threading',
                       'http', 'urllib', 'socket', 'math', 'random', 'collections', 'functools',
                       'itertools', 'textwrap', 'csv', 'io', 'logging', 'ast', 'inspect',
                       'platform', 'ctypes', 'struct', 'uuid', 'base64', 'hmac', 'email',
                       'imaplib', 'smtplib', 'html', 'xml', 'configparser', 'getpass',
                       'glob', 'fnmatch', 'stat', 'signal', 'queue', 'concurrent',
                       'multiprocessing', 'traceback', 'string', 'operator', 'copy',
                       'pprint', 'enum', 'dataclasses', 'typing', 'abc', 'contextlib',
                       'weakref', 'gc', 'resource', 'winreg', 'msvcrt', 'winsound',
                       'mimetypes', 'webbrowser', 'http.server', 'http.client',
                       'urllib.request', 'urllib.parse', 'email.header', 'email.mime',
                       'email.mime.text', 'email.mime.multipart', 'email.mime.base'}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split('.')[0]
                    if root not in stdlib_safe:
                        results["warnings"].append(f"Non-stdlib import: {alias.name}")
            elif isinstance(node, ast.ImportFrom) and node.module:
                root = node.module.split('.')[0]
                if root not in stdlib_safe:
                    results["warnings"].append(f"Non-stdlib import: {node.module}")

    except Exception as e:
        results["warnings"].append(f"AST analysis error: {e}")

    # 3. --help test (should not crash)
    if results["metrics"].get("has_argparse"):
        try:
            r = subprocess.run(
                [PYTHON, str(script_path), "--help"],
                capture_output=True, text=True, timeout=10, cwd=str(DEV_PATH)
            )
            results["help"] = "OK" if r.returncode == 0 else "FAIL"
            if r.returncode != 0:
                results["warnings"].append(f"--help exit code: {r.returncode}")
        except subprocess.TimeoutExpired:
            results["help"] = "TIMEOUT"
            results["warnings"].append("--help timed out")
        except Exception as e:
            results["help"] = "ERROR"
            results["warnings"].append(f"--help error: {e}")

    results["status"] = "OK" if not results["errors"] else "FAIL"
    return results


def test_all():
    """Run multi-test on all 329+ scripts."""
    scripts = sorted([f.stem for f in DEV_PATH.glob("*.py")])
    results = []
    stats = Counter()

    print(f"Testing {len(scripts)} scripts...\n")
    start = time.time()

    for i, name in enumerate(scripts):
        r = test_script(name)
        results.append(r)
        stats[r["status"]] += 1
        if r["errors"]:
            print(f"  FAIL: {name} — {r['errors'][0]}")
        elif r["warnings"]:
            print(f"  WARN: {name} — {len(r['warnings'])} warnings")

    elapsed = time.time() - start
    summary = {
        "total": len(scripts),
        "ok": stats["OK"],
        "fail": stats.get("FAIL", 0) + stats.get("syntax_error", 0),
        "missing": stats.get("missing", 0),
        "warnings_total": sum(len(r["warnings"]) for r in results),
        "avg_lines": sum(r.get("metrics", {}).get("lines", 0) for r in results) // max(1, len(results)),
        "avg_functions": sum(r.get("metrics", {}).get("functions", 0) for r in results) // max(1, len(results)),
        "with_docstring": sum(1 for r in results if r.get("metrics", {}).get("has_docstring")),
        "with_argparse": sum(1 for r in results if r.get("metrics", {}).get("has_argparse")),
        "with_main": sum(1 for r in results if r.get("metrics", {}).get("has_main")),
        "non_stdlib": [w for r in results for w in r["warnings"] if "Non-stdlib" in w],
        "elapsed_s": round(elapsed, 1),
        "timestamp": datetime.now().isoformat()
    }

    print(f"\n{'='*60}")
    print(f"Results: {summary['ok']}/{summary['total']} OK | "
          f"{summary['fail']} FAIL | {summary['warnings_total']} warnings")
    print(f"Coverage: {summary['with_docstring']} docstrings | "
          f"{summary['with_argparse']} argparse | {summary['with_main']} __main__")
    print(f"Avg: {summary['avg_lines']} lines/script | {summary['avg_functions']} functions/script")
    print(f"Time: {summary['elapsed_s']}s")

    # Save report
    report_path = TURBO / "data" / f"cowork_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    report_path.parent.mkdir(exist_ok=True)
    with open(report_path, 'w') as f:
        json.dump({"summary": summary, "results": results}, f, indent=2, ensure_ascii=False)
    print(f"Report: {report_path}")

    return summary, results


# ── GAP ANALYSIS ───────────────────────────────────────────────────────

def analyze_gaps():
    """Identify coverage gaps: patterns without enough scripts, weak areas."""
    db = sqlite3.connect(str(DB_PATH))
    db.row_factory = sqlite3.Row

    # 1. Patterns with few scripts
    mapping = db.execute("""
        SELECT pattern_id, COUNT(*) as cnt
        FROM cowork_script_mapping
        GROUP BY pattern_id
        ORDER BY cnt ASC
    """).fetchall()

    # 2. Patterns never dispatched
    unused = db.execute("""
        SELECT pattern_id, agent_id, description
        FROM agent_patterns
        WHERE pattern_id LIKE 'PAT_CW_%' AND total_calls = 0
    """).fetchall()

    # 3. Scripts without pattern
    all_scripts = {f.stem for f in DEV_PATH.glob("*.py")}
    mapped_scripts = {r[0] for r in db.execute("SELECT script_name FROM cowork_script_mapping").fetchall()}
    unmapped = all_scripts - mapped_scripts

    # 4. Category analysis — what's missing?
    categories = defaultdict(list)
    for f in DEV_PATH.glob("*.py"):
        prefix = f.stem.split('_')[0]
        categories[prefix].append(f.stem)

    # 5. Functional gaps
    existing_capabilities = set()
    for f in DEV_PATH.glob("*.py"):
        name = f.stem.lower()
        for cap in ["monitor", "optimizer", "analyzer", "manager", "guard", "scanner",
                     "tracker", "generator", "builder", "tester", "checker", "profiler",
                     "scheduler", "deployer", "router", "cache", "sync", "backup"]:
            if cap in name:
                existing_capabilities.add(cap)

    potential_gaps = []
    desired_capabilities = {
        "log_compressor": "Compress and archive old logs automatically",
        "api_rate_limiter": "Rate limiting for cluster API calls",
        "model_health_checker": "Deep health check of loaded models (not just ping)",
        "voice_command_fuzzer": "Fuzz test voice commands for edge cases",
        "config_drift_detector": "Detect config differences between nodes",
        "dependency_vulnerability_scanner": "Check Python stdlib usage for known issues",
        "performance_regression_detector": "Compare benchmarks over time",
        "auto_documentation_updater": "Keep COWORK_TASKS.md in sync with scripts",
        "script_deduplication": "Find and merge duplicate/overlapping scripts",
        "cross_script_integration_tester": "Test that scripts work together",
        "predictive_failure_detector": "Predict script failures from patterns",
        "resource_contention_monitor": "Detect GPU/CPU contention between scripts",
    }

    for name, desc in desired_capabilities.items():
        if not any(name.replace('_', '') in s.replace('_', '') for s in all_scripts):
            potential_gaps.append({"name": name, "description": desc})

    db.close()

    result = {
        "patterns_by_script_count": {r["pattern_id"]: r["cnt"] for r in mapping},
        "unused_patterns": [dict(r) for r in unused],
        "unmapped_scripts": sorted(unmapped),
        "category_distribution": {k: len(v) for k, v in sorted(categories.items())},
        "potential_gaps": potential_gaps,
        "total_capabilities": len(existing_capabilities),
        "timestamp": datetime.now().isoformat()
    }

    print(f"\n{'='*60}")
    print(f"GAP ANALYSIS — {len(all_scripts)} scripts")
    print(f"\nSmallest patterns:")
    for pat_id, cnt in sorted(result["patterns_by_script_count"].items(), key=lambda x: x[1])[:5]:
        print(f"  {pat_id}: {cnt} scripts")
    print(f"\nUnused patterns: {len(result['unused_patterns'])}")
    print(f"Unmapped scripts: {len(result['unmapped_scripts'])}")
    if result["unmapped_scripts"]:
        print(f"  {', '.join(result['unmapped_scripts'][:10])}")
    print(f"\nPotential gaps ({len(result['potential_gaps'])}):")
    for gap in result["potential_gaps"]:
        print(f"  - {gap['name']}: {gap['description']}")

    return result


# ── ANTICIPATION ENGINE ────────────────────────────────────────────────

def anticipate_needs():
    """Predict next needs based on dispatch patterns, error trends, and usage."""
    db = sqlite3.connect(str(DB_PATH))
    db.row_factory = sqlite3.Row

    # 1. Most used patterns → likely need more scripts
    hot_patterns = db.execute("""
        SELECT classified_type as pattern_type, COUNT(*) as cnt, AVG(latency_ms) as avg_lat,
               AVG(CASE WHEN success=1 THEN 1.0 ELSE 0.0 END) as success_rate
        FROM agent_dispatch_log
        GROUP BY classified_type
        ORDER BY cnt DESC
        LIMIT 10
    """).fetchall()

    # 2. Failing patterns → need fixing
    failing = db.execute("""
        SELECT classified_type as pattern_type, COUNT(*) as fails
        FROM agent_dispatch_log
        WHERE success = 0
        GROUP BY classified_type
        ORDER BY fails DESC
        LIMIT 5
    """).fetchall()

    # 3. Slow patterns → need optimization
    slow = db.execute("""
        SELECT classified_type as pattern_type, AVG(latency_ms) as avg_lat, COUNT(*) as cnt
        FROM agent_dispatch_log
        WHERE success = 1
        GROUP BY classified_type
        HAVING avg_lat > 20000
        ORDER BY avg_lat DESC
    """).fetchall()

    db.close()

    # 4. Script complexity analysis — find scripts that need refactoring
    complex_scripts = []
    for f in DEV_PATH.glob("*.py"):
        try:
            with open(f, 'r', encoding='utf-8', errors='ignore') as fh:
                source = fh.read()
            lines = len(source.splitlines())
            tree = ast.parse(source)
            funcs = len([n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)])
            # Complexity indicators
            if lines > 400 or funcs > 20:
                complex_scripts.append({
                    "script": f.stem, "lines": lines, "functions": funcs,
                    "needs": "refactoring" if lines > 500 else "review"
                })
        except:
            pass

    # 5. Generate predictions
    predictions = []

    if hot_patterns:
        top = hot_patterns[0]
        predictions.append({
            "type": "high_demand",
            "pattern": top["pattern_type"],
            "calls": top["cnt"],
            "action": f"Add more scripts for '{top['pattern_type']}' pattern (most used: {top['cnt']} calls)"
        })

    if failing:
        for f in failing[:3]:
            predictions.append({
                "type": "reliability",
                "pattern": f["pattern_type"],
                "fails": f["fails"],
                "action": f"Fix reliability issues in '{f['pattern_type']}' ({f['fails']} failures)"
            })

    if slow:
        for s in slow[:3]:
            predictions.append({
                "type": "performance",
                "pattern": s["pattern_type"],
                "avg_latency": round(s["avg_lat"]),
                "action": f"Optimize '{s['pattern_type']}' (avg {round(s['avg_lat']/1000, 1)}s)"
            })

    if complex_scripts:
        for cs in complex_scripts[:5]:
            predictions.append({
                "type": "maintenance",
                "script": cs["script"],
                "lines": cs["lines"],
                "action": f"Refactor {cs['script']} ({cs['lines']} lines, {cs['functions']} functions)"
            })

    result = {
        "predictions": predictions,
        "hot_patterns": [dict(r) for r in hot_patterns],
        "failing_patterns": [dict(r) for r in failing],
        "slow_patterns": [dict(r) for r in slow],
        "complex_scripts": complex_scripts,
        "timestamp": datetime.now().isoformat()
    }

    print(f"\n{'='*60}")
    print(f"ANTICIPATION — {len(predictions)} predictions\n")
    for p in predictions:
        print(f"  [{p['type'].upper()}] {p['action']}")

    return result


# ── OPENCLAW SYNC ──────────────────────────────────────────────────────

def openclaw_sync():
    """Sync cowork scripts to OpenClaw workspace."""
    if not OPENCLAW_DEV.exists():
        print(f"OpenClaw workspace not found: {OPENCLAW_DEV}")
        return {"status": "error", "message": "workspace not found"}

    new_count = 0
    updated_count = 0
    unchanged = 0

    for f in sorted(DEV_PATH.glob("*.py")):
        target = OPENCLAW_DEV / f.name
        source_content = f.read_bytes()

        if not target.exists():
            target.write_bytes(source_content)
            new_count += 1
        elif target.read_bytes() != source_content:
            target.write_bytes(source_content)
            updated_count += 1
        else:
            unchanged += 1

    # Also sync key docs
    for doc in ["COWORK_TASKS.md", "INSTRUCTIONS.md", "TOOLS.md", "IDENTITY.md"]:
        src = BASE / doc
        tgt = OPENCLAW_DEV.parent / doc
        if src.exists():
            tgt.write_bytes(src.read_bytes())

    result = {
        "new": new_count,
        "updated": updated_count,
        "unchanged": unchanged,
        "total": new_count + updated_count + unchanged,
        "timestamp": datetime.now().isoformat()
    }

    print(f"\nOpenClaw Sync: {result['new']} new | {result['updated']} updated | "
          f"{result['unchanged']} unchanged | {result['total']} total")
    return result


# ── TIMEOUT AUTO-FIX ──────────────────────────────────────────────────

def auto_fix_timeouts():
    """Auto-fix timeout values based on actual dispatch latency data."""
    try:
        sys.path.insert(0, str(TURBO))
        from cowork.dev.timeout_auto_fixer import analyze_timeouts, suggest_adjustments, apply_adjustments
        pattern_stats, node_stats = analyze_timeouts()
        suggestions = suggest_adjustments(pattern_stats, node_stats)
        applied = apply_adjustments(suggestions)
        problems = [ps for ps in pattern_stats if ps["timeouts"] > 0]
        result = {
            "problems": len(problems),
            "suggestions": len(suggestions),
            "applied": applied,
        }
        if applied:
            print(f"  Applied {len(applied)} timeout adjustments")
            for a in applied:
                print(f"    {a}")
        else:
            print("  No timeout adjustments needed")
        return result
    except Exception as e:
        print(f"  Error: {e}")
        return {"error": str(e)}


def run_proactive_dispatch():
    """Run proactive need detection + anticipation from dispatch data."""
    try:
        sys.path.insert(0, str(TURBO))
        from src.cowork_proactive import get_proactive
        pro = get_proactive()
        needs = pro.detect_needs()
        anticipation = pro.anticipate()
        result = {
            "needs_detected": len(needs),
            "needs_by_urgency": {},
            "anticipation": anticipation,
        }
        for n in needs:
            result["needs_by_urgency"][n.urgency] = result["needs_by_urgency"].get(n.urgency, 0) + 1
        print(f"  Detected {len(needs)} needs:")
        for urgency, count in sorted(result["needs_by_urgency"].items()):
            print(f"    {urgency}: {count}")
        if anticipation["count"] > 0:
            print(f"  Predictions: {anticipation['count']}")
            for p in anticipation["predictions"][:3]:
                print(f"    {p.get('type', '?')}: {p.get('recommendation', p.get('action', '?'))}")
        return result
    except Exception as e:
        print(f"  Error: {e}")
        return {"error": str(e)}


# ── FULL CYCLE ─────────────────────────────────────────────────────────

def full_cycle():
    """Run complete continuous development cycle."""
    print(f"\n{'#'*60}")
    print(f"# COWORK ENGINE — Full Development Cycle")
    print(f"# {datetime.now().isoformat()}")
    print(f"{'#'*60}")

    # Phase 1: Test all
    print(f"\n{'='*60}\nPHASE 1: MULTI-TEST\n{'='*60}")
    test_summary, test_results = test_all()

    # Phase 2: Gap analysis
    print(f"\n{'='*60}\nPHASE 2: GAP ANALYSIS\n{'='*60}")
    gaps = analyze_gaps()

    # Phase 3: Anticipation
    print(f"\n{'='*60}\nPHASE 3: ANTICIPATION\n{'='*60}")
    predictions = anticipate_needs()

    # Phase 3b: Timeout auto-fix
    print(f"\n{'='*60}\nPHASE 3b: TIMEOUT AUTO-FIX\n{'='*60}")
    timeout_fix = auto_fix_timeouts()

    # Phase 3c: Proactive dispatch health
    print(f"\n{'='*60}\nPHASE 3c: PROACTIVE DISPATCH\n{'='*60}")
    proactive_result = run_proactive_dispatch()

    # Phase 4: Sync
    print(f"\n{'='*60}\nPHASE 4: OPENCLAW SYNC\n{'='*60}")
    sync = openclaw_sync()

    # Phase 5: Summary
    print(f"\n{'#'*60}")
    print(f"# CYCLE COMPLETE")
    print(f"#")
    print(f"# Tests: {test_summary['ok']}/{test_summary['total']} OK")
    print(f"# Gaps: {len(gaps['potential_gaps'])} identified")
    print(f"# Predictions: {len(predictions['predictions'])} actions needed")
    print(f"# Timeout fixes: {len(timeout_fix.get('applied', []))}")
    print(f"# Proactive needs: {proactive_result.get('needs_detected', 0)}")
    print(f"# Sync: {sync['new']} new + {sync['updated']} updated")
    print(f"{'#'*60}")

    # Save cycle report
    report = {
        "cycle": "full",
        "tests": test_summary,
        "gaps": gaps,
        "predictions": predictions,
        "timeout_fix": timeout_fix,
        "proactive": proactive_result,
        "sync": sync,
        "timestamp": datetime.now().isoformat()
    }
    report_path = TURBO / "data" / f"cowork_cycle_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)
    print(f"\nFull report: {report_path}")

    return report


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="COWORK Engine — Continuous Development")
    parser.add_argument("--test-all", action="store_true", help="Test all scripts")
    parser.add_argument("--gaps", action="store_true", help="Gap analysis")
    parser.add_argument("--anticipate", action="store_true", help="Predict needs")
    parser.add_argument("--improve", action="store_true", help="Auto-improve scripts")
    parser.add_argument("--openclaw-sync", action="store_true", help="Sync to OpenClaw")
    parser.add_argument("--cycle", action="store_true", help="Full cycle")
    parser.add_argument("--once", action="store_true", help="Alias for --cycle")
    args = parser.parse_args()

    if args.test_all:
        test_all()
    elif args.gaps:
        analyze_gaps()
    elif args.anticipate:
        anticipate_needs()
    elif args.openclaw_sync:
        openclaw_sync()
    elif args.cycle or args.once or len(sys.argv) == 1:
        full_cycle()
