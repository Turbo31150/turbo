#!/usr/bin/env python3
"""jarvis_self_test_suite.py — #217 Test ALL dev/*.py scripts: parse + --help validation.
Usage:
    python dev/jarvis_self_test_suite.py --run
    python dev/jarvis_self_test_suite.py --fast
    python dev/jarvis_self_test_suite.py --full
    python dev/jarvis_self_test_suite.py --report
    python dev/jarvis_self_test_suite.py --once
"""
import argparse, json, sqlite3, time, subprocess, os, ast, sys
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "self_test_suite.db"

HELP_TIMEOUT = 10  # seconds
GRADE_THRESHOLDS = {"A": 95, "B": 85, "C": 75, "D": 60, "F": 0}


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("""CREATE TABLE IF NOT EXISTS test_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_type TEXT DEFAULT 'standard',
        total_scripts INTEGER,
        passed INTEGER,
        failed INTEGER,
        errors INTEGER,
        skipped INTEGER,
        pass_rate REAL,
        grade TEXT,
        duration_sec REAL,
        ts TEXT DEFAULT (datetime('now','localtime'))
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS test_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id INTEGER,
        script TEXT NOT NULL,
        test_type TEXT,
        status TEXT DEFAULT 'pending',
        message TEXT,
        duration_ms REAL,
        ts TEXT DEFAULT (datetime('now','localtime')),
        FOREIGN KEY(run_id) REFERENCES test_runs(id)
    )""")
    db.commit()
    return db


def _test_ast_parse(script_path):
    """Test if script can be parsed by ast."""
    try:
        source = script_path.read_text(encoding="utf-8", errors="replace")
        ast.parse(source)
        return {"status": "pass", "message": "AST parse OK"}
    except SyntaxError as e:
        return {"status": "fail", "message": f"SyntaxError line {e.lineno}: {e.msg}"}
    except Exception as e:
        return {"status": "error", "message": str(e)[:200]}


def _test_help(script_path, timeout=HELP_TIMEOUT):
    """Test if --help works."""
    try:
        start = time.perf_counter()
        result = subprocess.run(
            [sys.executable, str(script_path), "--help"],
            capture_output=True, text=True, timeout=timeout,
            cwd=str(DEV.parent),
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        duration = (time.perf_counter() - start) * 1000

        if result.returncode == 0:
            has_usage = "usage" in result.stdout.lower() or "optional arguments" in result.stdout.lower() or "--" in result.stdout
            if has_usage:
                return {"status": "pass", "message": f"--help OK ({duration:.0f}ms)", "duration_ms": duration}
            else:
                return {"status": "pass", "message": f"--help returned (no usage text) ({duration:.0f}ms)", "duration_ms": duration}
        else:
            stderr_preview = (result.stderr or "")[:200]
            return {"status": "fail", "message": f"--help exit {result.returncode}: {stderr_preview}", "duration_ms": duration}

    except subprocess.TimeoutExpired:
        return {"status": "fail", "message": f"--help timeout after {timeout}s"}
    except Exception as e:
        return {"status": "error", "message": str(e)[:200]}


def _test_once(script_path, timeout=15):
    """Test if --once works (for full test only)."""
    try:
        start = time.perf_counter()
        result = subprocess.run(
            [sys.executable, str(script_path), "--once"],
            capture_output=True, text=True, timeout=timeout,
            cwd=str(DEV.parent),
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        duration = (time.perf_counter() - start) * 1000

        if result.returncode == 0:
            # Try to parse as JSON
            stdout = result.stdout.strip()
            try:
                json.loads(stdout)
                return {"status": "pass", "message": f"--once JSON OK ({duration:.0f}ms)", "duration_ms": duration}
            except json.JSONDecodeError:
                if stdout:
                    return {"status": "pass", "message": f"--once OK (non-JSON) ({duration:.0f}ms)", "duration_ms": duration}
                return {"status": "pass", "message": f"--once OK (empty output) ({duration:.0f}ms)", "duration_ms": duration}
        else:
            stderr_preview = (result.stderr or "")[:200]
            return {"status": "fail", "message": f"--once exit {result.returncode}: {stderr_preview}", "duration_ms": duration}

    except subprocess.TimeoutExpired:
        return {"status": "fail", "message": f"--once timeout after {timeout}s"}
    except Exception as e:
        return {"status": "error", "message": str(e)[:200]}


def _grade(pass_rate):
    """Calculate grade from pass rate."""
    for grade, threshold in sorted(GRADE_THRESHOLDS.items(), key=lambda x: x[1], reverse=True):
        if pass_rate >= threshold:
            return grade
    return "F"


def run_tests(db, test_type="standard", full=False):
    """Run tests on all dev/*.py scripts."""
    scripts = sorted(DEV.glob("*.py"))
    start_time = time.perf_counter()

    cur = db.execute(
        "INSERT INTO test_runs (run_type, total_scripts) VALUES (?,?)",
        (test_type, len(scripts))
    )
    run_id = cur.lastrowid
    db.commit()

    passed = 0
    failed = 0
    errors = 0
    skipped = 0
    results = []

    for script in scripts:
        script_results = {"script": script.name, "tests": []}

        # Test 1: AST parse
        ast_result = _test_ast_parse(script)
        db.execute(
            "INSERT INTO test_results (run_id, script, test_type, status, message) VALUES (?,?,?,?,?)",
            (run_id, script.name, "ast_parse", ast_result["status"], ast_result["message"])
        )
        script_results["tests"].append({"type": "ast_parse", **ast_result})

        if ast_result["status"] != "pass":
            errors += 1
            script_results["overall"] = "error"
            results.append(script_results)
            continue

        # Test 2: --help
        if test_type != "ast_only":
            help_result = _test_help(script)
            db.execute(
                "INSERT INTO test_results (run_id, script, test_type, status, message, duration_ms) VALUES (?,?,?,?,?,?)",
                (run_id, script.name, "help", help_result["status"], help_result["message"],
                 help_result.get("duration_ms"))
            )
            script_results["tests"].append({"type": "help", **help_result})

        # Test 3: --once (full test only)
        if full and ast_result["status"] == "pass":
            once_result = _test_once(script)
            db.execute(
                "INSERT INTO test_results (run_id, script, test_type, status, message, duration_ms) VALUES (?,?,?,?,?,?)",
                (run_id, script.name, "once", once_result["status"], once_result["message"],
                 once_result.get("duration_ms"))
            )
            script_results["tests"].append({"type": "once", **once_result})

        # Determine overall status
        statuses = [t["status"] for t in script_results["tests"]]
        if all(s == "pass" for s in statuses):
            passed += 1
            script_results["overall"] = "pass"
        elif "error" in statuses:
            errors += 1
            script_results["overall"] = "error"
        else:
            failed += 1
            script_results["overall"] = "fail"

        results.append(script_results)

    duration = time.perf_counter() - start_time
    total = passed + failed + errors
    pass_rate = round(passed / total * 100, 1) if total else 0
    grade = _grade(pass_rate)

    db.execute(
        "UPDATE test_runs SET passed=?, failed=?, errors=?, skipped=?, pass_rate=?, grade=?, duration_sec=? WHERE id=?",
        (passed, failed, errors, skipped, pass_rate, grade, round(duration, 2), run_id)
    )
    db.commit()

    # Separate pass/fail for clean output
    failures = [r for r in results if r["overall"] != "pass"]

    return {
        "run_id": run_id,
        "type": test_type,
        "total_scripts": len(scripts),
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "pass_rate": pass_rate,
        "grade": grade,
        "duration_sec": round(duration, 2),
        "failures": failures[:20],
        "ts": datetime.now().isoformat()
    }


def get_report(db):
    """Historical test reports."""
    runs = db.execute(
        "SELECT id, run_type, total_scripts, passed, failed, errors, pass_rate, grade, duration_sec, ts FROM test_runs ORDER BY id DESC LIMIT 10"
    ).fetchall()

    history = []
    for r in runs:
        history.append({
            "run_id": r[0], "type": r[1], "total": r[2], "passed": r[3],
            "failed": r[4], "errors": r[5], "pass_rate": r[6],
            "grade": r[7], "duration_sec": r[8], "ts": r[9]
        })

    # Most failing scripts
    failures = db.execute(
        "SELECT script, COUNT(*) as cnt FROM test_results WHERE status='fail' GROUP BY script ORDER BY cnt DESC LIMIT 10"
    ).fetchall()

    return {
        "history": history,
        "most_failing": [{"script": f[0], "failures": f[1]} for f in failures],
        "total_runs": db.execute("SELECT COUNT(*) FROM test_runs").fetchone()[0]
    }


def do_status(db):
    total_runs = db.execute("SELECT COUNT(*) FROM test_runs").fetchone()[0]
    latest = db.execute(
        "SELECT pass_rate, grade, total_scripts, ts FROM test_runs ORDER BY id DESC LIMIT 1"
    ).fetchone()
    scripts = len(list(DEV.glob("*.py")))
    return {
        "script": "jarvis_self_test_suite.py",
        "id": 217,
        "db": str(DB_PATH),
        "total_scripts": scripts,
        "total_runs": total_runs,
        "latest": {
            "pass_rate": latest[0], "grade": latest[1],
            "scripts_tested": latest[2], "ts": latest[3]
        } if latest else None,
        "grade_thresholds": GRADE_THRESHOLDS,
        "ts": datetime.now().isoformat()
    }


def main():
    parser = argparse.ArgumentParser(description="JARVIS Self-Test Suite — validate all dev scripts")
    parser.add_argument("--run", action="store_true", help="Run standard tests (AST + --help)")
    parser.add_argument("--fast", action="store_true", help="Fast run (AST only)")
    parser.add_argument("--full", action="store_true", help="Full run (AST + --help + --once)")
    parser.add_argument("--report", action="store_true", help="Historical report")
    parser.add_argument("--once", action="store_true", help="Quick status")
    args = parser.parse_args()

    db = init_db()

    if args.run:
        result = run_tests(db, "standard")
    elif args.fast:
        result = run_tests(db, "ast_only")
    elif args.full:
        result = run_tests(db, "full", full=True)
    elif args.report:
        result = get_report(db)
    else:
        result = do_status(db)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    db.close()


if __name__ == "__main__":
    main()
