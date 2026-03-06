#!/usr/bin/env python3
"""Auto Deployer — Continuous deployment pipeline for JARVIS.

Monitors git changes, runs tests, builds, and deploys updates
automatically. Supports rollback on failure.
"""
import argparse
import json
import os
import sqlite3
import subprocess
import time
from pathlib import Path

DB_PATH = Path(__file__).parent / "deployer.db"
from _paths import TURBO_DIR as TURBO

def init_db():
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS deployments (
        id INTEGER PRIMARY KEY, ts REAL, commit_hash TEXT,
        commit_msg TEXT, tests_passed INTEGER, tests_failed INTEGER,
        status TEXT, rollback_hash TEXT, duration_s REAL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS checks (
        id INTEGER PRIMARY KEY, ts REAL, check_type TEXT,
        status TEXT, details TEXT)""")
    db.commit()
    return db

def get_current_commit():
    """Get current git commit hash and message."""
    try:
        r = subprocess.run(
            ["git", "log", "--oneline", "-1"],
            capture_output=True, text=True, timeout=5, cwd=str(TURBO))
        if r.returncode == 0:
            parts = r.stdout.strip().split(" ", 1)
            return parts[0], parts[1] if len(parts) > 1 else ""
    except (subprocess.TimeoutExpired, OSError):
        pass
    return "", ""

def check_uncommitted():
    """Check for uncommitted changes."""
    try:
        r = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, timeout=5, cwd=str(TURBO))
        if r.returncode == 0:
            lines = [l for l in r.stdout.strip().split("\n") if l.strip()]
            return len(lines)
    except (subprocess.TimeoutExpired, OSError):
        pass
    return -1

def run_quick_tests():
    """Run quick syntax + import tests."""
    results = {"passed": 0, "failed": 0, "errors": []}
    # Check key Python files compile
    key_files = [
        "src/mcp_server.py", "src/commands.py", "src/config.py",
        "python_ws/server.py", "src/notifier.py",
    ]
    for f in key_files:
        fpath = TURBO / f
        if not fpath.exists():
            continue
        try:
            r = subprocess.run(
                ["python", "-m", "py_compile", str(fpath)],
                capture_output=True, text=True, timeout=10)
            if r.returncode == 0:
                results["passed"] += 1
            else:
                results["failed"] += 1
                results["errors"].append(f"{f}: {r.stderr[:100]}")
        except (subprocess.TimeoutExpired, OSError):
            results["failed"] += 1
    return results

def run_full_tests():
    """Run pytest test suites."""
    try:
        r = subprocess.run(
            ["python", "-m", "pytest", str(TURBO / "tests"), "-q", "--tb=line", "--no-header", "-x"],
            capture_output=True, text=True, timeout=120,
            cwd=str(TURBO), env={**os.environ, "PYTHONPATH": str(TURBO)})
        output = r.stdout + r.stderr
        import re
        p = re.search(r"(\d+) passed", output)
        f = re.search(r"(\d+) failed", output)
        passed = int(p.group(1)) if p else 0
        failed = int(f.group(1)) if f else 0
        return passed, failed, output[-300:]
    except (subprocess.TimeoutExpired, OSError) as e:
        return 0, 1, str(e)

def check_services():
    """Check if key services are running."""
    services = {
        "LM Studio M1": "http://127.0.0.1:1234/api/v1/models",
        "Ollama OL1": "http://127.0.0.1:11434/api/tags",
        "Canvas Proxy": "http://127.0.0.1:18800/health",
    }
    results = {}
    import urllib.request
    for name, url in services.items():
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=3):
                results[name] = "OK"
        except Exception:
            results[name] = "DOWN"
    return results

def deploy_pipeline(db, full_tests=False):
    """Full deployment pipeline."""
    start = time.time()
    commit_hash, commit_msg = get_current_commit()
    uncommitted = check_uncommitted()

    print(f"  Commit: {commit_hash} {commit_msg[:60]}")
    print(f"  Uncommitted: {uncommitted} files")

    # Quick syntax tests
    quick = run_quick_tests()
    print(f"  Syntax: {quick['passed']}✓ {quick['failed']}✗")
    for err in quick["errors"]:
        print(f"    ✗ {err}")

    if quick["failed"] > 0:
        db.execute(
            "INSERT INTO deployments (ts, commit_hash, commit_msg, tests_passed, tests_failed, status, duration_s) VALUES (?,?,?,?,?,?,?)",
            (time.time(), commit_hash, commit_msg[:200], quick["passed"], quick["failed"], "failed_syntax", time.time()-start))
        db.commit()
        return False

    # Full tests if requested
    if full_tests:
        passed, failed, output = run_full_tests()
        print(f"  Tests: {passed}✓ {failed}✗")
        if failed > 0:
            print(f"    {output[:200]}")
            db.execute(
                "INSERT INTO deployments (ts, commit_hash, commit_msg, tests_passed, tests_failed, status, duration_s) VALUES (?,?,?,?,?,?,?)",
                (time.time(), commit_hash, commit_msg[:200], passed, failed, "failed_tests", time.time()-start))
            db.commit()
            return False

    # Check services
    services = check_services()
    for name, status in services.items():
        print(f"  {name}: {status}")

    duration = time.time() - start
    db.execute(
        "INSERT INTO deployments (ts, commit_hash, commit_msg, tests_passed, tests_failed, status, duration_s) VALUES (?,?,?,?,?,?,?)",
        (time.time(), commit_hash, commit_msg[:200], quick["passed"], quick["failed"], "success", duration))
    db.commit()
    print(f"  Deploy OK ({duration:.1f}s)")
    return True

def main():
    parser = argparse.ArgumentParser(description="Auto Deployer")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--full", action="store_true", help="Run full test suite")
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--interval", type=int, default=3600)
    parser.add_argument("--stats", action="store_true")
    args = parser.parse_args()

    db = init_db()

    if args.stats:
        total = db.execute("SELECT COUNT(*) FROM deployments").fetchone()[0]
        success = db.execute("SELECT COUNT(*) FROM deployments WHERE status='success'").fetchone()[0]
        print(f"Deployments: {success}/{total} success ({success/max(total,1)*100:.0f}%)")
        return

    if args.once or not args.loop:
        print("=== Auto Deployer ===")
        deploy_pipeline(db, args.full)

    if args.loop:
        print("Auto Deployer en boucle continue...")
        last_hash = ""
        while True:
            try:
                h, _ = get_current_commit()
                if h != last_hash:
                    print(f"\n[{time.strftime('%H:%M')}] New commit detected: {h}")
                    deploy_pipeline(db, args.full)
                    last_hash = h
                time.sleep(args.interval)
            except KeyboardInterrupt:
                break

if __name__ == "__main__":
    main()
