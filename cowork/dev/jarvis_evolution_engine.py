#!/usr/bin/env python3
"""jarvis_evolution_engine.py -- #218 Analyzes test results, identifies failures, suggests fixes.
Usage:
    python dev/jarvis_evolution_engine.py --evolve
    python dev/jarvis_evolution_engine.py --status
    python dev/jarvis_evolution_engine.py --rollback 3
    python dev/jarvis_evolution_engine.py --report
    python dev/jarvis_evolution_engine.py --once
"""
import argparse, json, sqlite3, time, os, ast, re
from datetime import datetime
from pathlib import Path
from collections import Counter

DEV = Path(__file__).parent
DATA_DIR = DEV / "data"
DB_PATH = DATA_DIR / "evolution_engine.db"
SELF_TEST_DB = DATA_DIR / "self_test_suite.db"

ERROR_PATTERNS = {
    "syntax": {
        "patterns": [r"SyntaxError", r"IndentationError", r"TabError"],
        "severity": "critical",
        "fix_hint": "Fix syntax: check indentation, colons, brackets, quotes"
    },
    "import": {
        "patterns": [r"ModuleNotFoundError", r"ImportError", r"No module named"],
        "severity": "high",
        "fix_hint": "Use stdlib-only imports. Remove pip dependencies or add fallback"
    },
    "runtime": {
        "patterns": [r"RuntimeError", r"RecursionError", r"MemoryError"],
        "severity": "high",
        "fix_hint": "Add error handling, resource limits, or simplify logic"
    },
    "type_err": {
        "patterns": [r"TypeError", r"AttributeError", r"ValueError"],
        "severity": "medium",
        "fix_hint": "Check variable types, add type validation, handle None cases"
    },
    "io_err": {
        "patterns": [r"FileNotFoundError", r"PermissionError", r"IOError", r"OSError"],
        "severity": "medium",
        "fix_hint": "Add path existence checks, handle permissions, use try/except"
    },
    "timeout": {
        "patterns": [r"timeout", r"TimeoutExpired", r"timed out"],
        "severity": "low",
        "fix_hint": "Reduce timeout-prone operations, add --once fast path"
    },
    "json_err": {
        "patterns": [r"JSONDecodeError", r"json\.decoder"],
        "severity": "medium",
        "fix_hint": "Add JSON parse error handling, validate input data"
    },
    "network": {
        "patterns": [r"ConnectionRefused", r"URLError", r"socket\.timeout", r"ConnectionError"],
        "severity": "low",
        "fix_hint": "Add connection timeout, retry logic, or offline fallback"
    },
    "exit_code": {
        "patterns": [r"exit \d+", r"returncode"],
        "severity": "low",
        "fix_hint": "Check subprocess exit codes, add proper error handling"
    },
}

_STDLIB_MODULES = {
    "abc", "argparse", "ast", "asyncio", "base64", "binascii", "bisect",
    "calendar", "cgi", "cmd", "code", "codecs", "collections", "colorsys",
    "compileall", "concurrent", "configparser", "contextlib", "copy", "copyreg",
    "csv", "ctypes", "dataclasses", "datetime", "decimal", "difflib", "dis",
    "distutils", "email", "encodings", "enum", "errno", "faulthandler",
    "filecmp", "fileinput", "fnmatch", "fractions", "ftplib", "functools",
    "gc", "getopt", "getpass", "gettext", "glob", "gzip", "hashlib", "heapq",
    "hmac", "html", "http", "imaplib", "importlib", "inspect", "io",
    "ipaddress", "itertools", "json", "keyword", "linecache", "locale",
    "logging", "lzma", "math", "mimetypes", "mmap", "multiprocessing",
    "numbers", "operator", "os", "pathlib", "pdb", "pickle", "pkgutil",
    "platform", "plistlib", "poplib", "posixpath", "pprint", "profile",
    "pstats", "py_compile", "queue", "quopri", "random", "re", "readline",
    "reprlib", "rlcompleter", "runpy", "sched", "secrets", "select",
    "selectors", "shelve", "shlex", "shutil", "signal", "site", "smtplib",
    "sndhdr", "socket", "socketserver", "sqlite3", "ssl", "stat",
    "statistics", "string", "stringprep", "struct", "subprocess", "sunau",
    "symtable", "sys", "sysconfig", "tabnanny", "tarfile", "tempfile",
    "test", "textwrap", "threading", "time", "timeit", "tkinter", "token",
    "tokenize", "tomllib", "trace", "traceback", "tracemalloc", "tty",
    "turtle", "types", "typing", "unicodedata", "unittest", "urllib",
    "uu", "uuid", "venv", "warnings", "wave", "weakref", "webbrowser",
    "winreg", "winsound", "wsgiref", "xml", "xmlrpc", "zipapp", "zipfile",
    "zipimport", "zlib", "_thread", "__future__"
}


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("""CREATE TABLE IF NOT EXISTS evolution_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        total_scripts INTEGER,
        failing_scripts INTEGER,
        error_types TEXT,
        evolution_score REAL,
        previous_score REAL,
        delta REAL,
        ts TEXT DEFAULT (datetime('now','localtime'))
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS script_issues (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id INTEGER,
        script TEXT NOT NULL,
        error_type TEXT,
        severity TEXT,
        message TEXT,
        fix_hint TEXT,
        fixed INTEGER DEFAULT 0,
        ts TEXT DEFAULT (datetime('now','localtime')),
        FOREIGN KEY(run_id) REFERENCES evolution_runs(id)
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS evolution_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        score REAL,
        scripts_total INTEGER,
        scripts_passing INTEGER,
        grade TEXT,
        ts TEXT DEFAULT (datetime('now','localtime'))
    )""")
    db.commit()
    return db


def _classify_error(message):
    """Classify an error message into error types."""
    if not message:
        return "unknown", "low", "Review error manually"
    for error_type, config in ERROR_PATTERNS.items():
        for pattern in config["patterns"]:
            if re.search(pattern, message, re.IGNORECASE):
                return error_type, config["severity"], config["fix_hint"]
    return "unknown", "low", "Review error details and fix accordingly"


def _get_test_results():
    """Pull latest test results from self_test_suite.db."""
    if not SELF_TEST_DB.exists():
        return None
    try:
        conn = sqlite3.connect(str(SELF_TEST_DB))
        run = conn.execute(
            "SELECT id, total_scripts, passed, failed, errors, pass_rate, grade FROM test_runs ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if not run:
            conn.close()
            return None
        run_id = run[0]
        failures = conn.execute(
            "SELECT script, test_type, status, message FROM test_results WHERE run_id=? AND status IN ('fail','error')",
            (run_id,)
        ).fetchall()
        conn.close()
        return {
            "run_id": run_id, "total": run[1], "passed": run[2],
            "failed": run[3], "errors": run[4], "pass_rate": run[5], "grade": run[6],
            "failures": [{"script": f[0], "test": f[1], "status": f[2], "message": f[3]} for f in failures]
        }
    except Exception:
        return None


def _analyze_script_directly(script_path):
    """Directly analyze a script for common issues."""
    issues = []
    try:
        source = script_path.read_text(encoding="utf-8", errors="replace")
        try:
            tree = ast.parse(source)
        except SyntaxError as e:
            issues.append({
                "type": "syntax", "severity": "critical",
                "message": "SyntaxError line {}: {}".format(e.lineno, e.msg),
                "fix_hint": "Fix syntax error at the indicated line"
            })
            return issues

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    mod = alias.name.split(".")[0]
                    if mod not in _STDLIB_MODULES:
                        issues.append({
                            "type": "import", "severity": "high",
                            "message": "Non-stdlib import: {}".format(alias.name),
                            "fix_hint": "Replace with stdlib alternative or add try/except"
                        })
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    mod = node.module.split(".")[0]
                    if mod not in _STDLIB_MODULES:
                        issues.append({
                            "type": "import", "severity": "high",
                            "message": "Non-stdlib import: from {}".format(node.module),
                            "fix_hint": "Replace with stdlib alternative"
                        })

        if "if __name__" not in source:
            issues.append({
                "type": "structure", "severity": "low",
                "message": "Missing if __name__ guard",
                "fix_hint": "Add main guard for proper script behavior"
            })
        if "argparse" not in source:
            issues.append({
                "type": "structure", "severity": "low",
                "message": "No argparse CLI",
                "fix_hint": "Add argparse with --help and --once for COWORK convention"
            })
    except Exception as e:
        issues.append({
            "type": "io_err", "severity": "medium",
            "message": "Cannot read file: {}".format(str(e)),
            "fix_hint": "Check file encoding and permissions"
        })
    return issues


def evolve(db):
    """Analyze self_test results + direct analysis, identify issues, suggest fixes."""
    test_data = _get_test_results()
    scripts = sorted(DEV.glob("*.py"))
    all_issues = []
    error_type_counts = Counter()

    if test_data and test_data.get("failures"):
        for f in test_data["failures"]:
            error_type, severity, fix_hint = _classify_error(f.get("message", ""))
            all_issues.append({
                "script": f["script"], "error_type": error_type,
                "severity": severity, "message": (f.get("message", "") or "")[:300],
                "fix_hint": fix_hint, "source": "self_test"
            })
            error_type_counts[error_type] += 1

    for script in scripts:
        direct_issues = _analyze_script_directly(script)
        for issue in direct_issues:
            all_issues.append({
                "script": script.name, "error_type": issue["type"],
                "severity": issue["severity"], "message": issue["message"],
                "fix_hint": issue["fix_hint"], "source": "direct_analysis"
            })
            error_type_counts[issue["type"]] += 1

    total_scripts = len(scripts)
    failing_set = set(i["script"] for i in all_issues if i["severity"] in ("critical", "high"))
    failing_count = len(failing_set)
    evolution_score = round((1 - failing_count / total_scripts) * 100, 1) if total_scripts else 0

    prev = db.execute("SELECT evolution_score FROM evolution_runs ORDER BY id DESC LIMIT 1").fetchone()
    previous_score = prev[0] if prev else 0
    delta = round(evolution_score - previous_score, 1)

    cur = db.execute(
        "INSERT INTO evolution_runs (total_scripts, failing_scripts, error_types, evolution_score, previous_score, delta) VALUES (?,?,?,?,?,?)",
        (total_scripts, failing_count, json.dumps(dict(error_type_counts)), evolution_score, previous_score, delta)
    )
    run_id = cur.lastrowid

    for issue in all_issues:
        db.execute(
            "INSERT INTO script_issues (run_id, script, error_type, severity, message, fix_hint) VALUES (?,?,?,?,?,?)",
            (run_id, issue["script"], issue["error_type"], issue["severity"], issue["message"][:500], issue["fix_hint"])
        )

    grade = "A" if evolution_score >= 95 else "B" if evolution_score >= 85 else "C" if evolution_score >= 75 else "D" if evolution_score >= 60 else "F"
    db.execute(
        "INSERT INTO evolution_history (score, scripts_total, scripts_passing, grade) VALUES (?,?,?,?)",
        (evolution_score, total_scripts, total_scripts - failing_count, grade)
    )
    db.commit()

    priority_issues = sorted(all_issues, key=lambda x: {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(x["severity"], 4))
    return {
        "run_id": run_id, "evolution_score": evolution_score, "previous_score": previous_score,
        "delta": delta, "grade": grade, "total_scripts": total_scripts,
        "failing_scripts": failing_count, "error_types": dict(error_type_counts),
        "priority_issues": priority_issues[:15], "total_issues": len(all_issues)
    }


def get_evolution_status(db):
    """Current evolution status."""
    history = db.execute(
        "SELECT score, grade, scripts_total, scripts_passing, ts FROM evolution_history ORDER BY id DESC LIMIT 10"
    ).fetchall()
    trend = "stable"
    if len(history) >= 2:
        if history[0][0] > history[1][0]:
            trend = "improving"
        elif history[0][0] < history[1][0]:
            trend = "declining"
    return {
        "history": [{"score": h[0], "grade": h[1], "total": h[2], "passing": h[3], "ts": h[4]} for h in history],
        "trend": trend
    }


def rollback_info(db, run_id):
    """Show issues from a specific run for potential rollback analysis."""
    issues = db.execute(
        "SELECT script, error_type, severity, message, fix_hint FROM script_issues WHERE run_id=? ORDER BY severity",
        (run_id,)
    ).fetchall()
    run = db.execute(
        "SELECT evolution_score, total_scripts, failing_scripts FROM evolution_runs WHERE id=?",
        (run_id,)
    ).fetchone()
    return {
        "run_id": run_id,
        "evolution_score": run[0] if run else None,
        "total": run[1] if run else None,
        "failing": run[2] if run else None,
        "issues": [{"script": i[0], "type": i[1], "severity": i[2], "message": i[3][:200], "fix": i[4]} for i in issues]
    }


def full_report(db):
    """Complete evolution report."""
    status = get_evolution_status(db)
    latest_run = db.execute(
        "SELECT id, evolution_score, error_types FROM evolution_runs ORDER BY id DESC LIMIT 1"
    ).fetchone()
    recurring = db.execute(
        "SELECT script, error_type, COUNT(*) as cnt FROM script_issues GROUP BY script, error_type ORDER BY cnt DESC LIMIT 10"
    ).fetchall()
    return {
        **status,
        "latest_run_id": latest_run[0] if latest_run else None,
        "latest_score": latest_run[1] if latest_run else None,
        "latest_error_types": json.loads(latest_run[2]) if latest_run and latest_run[2] else {},
        "recurring_issues": [{"script": r[0], "type": r[1], "occurrences": r[2]} for r in recurring],
        "total_runs": db.execute("SELECT COUNT(*) FROM evolution_runs").fetchone()[0]
    }


def do_status(db):
    total_runs = db.execute("SELECT COUNT(*) FROM evolution_runs").fetchone()[0]
    latest = db.execute("SELECT evolution_score, delta FROM evolution_runs ORDER BY id DESC LIMIT 1").fetchone()
    return {
        "script": "jarvis_evolution_engine.py",
        "id": 218,
        "db": str(DB_PATH),
        "total_runs": total_runs,
        "latest_score": latest[0] if latest else None,
        "latest_delta": latest[1] if latest else None,
        "self_test_db": str(SELF_TEST_DB),
        "self_test_exists": SELF_TEST_DB.exists(),
        "ts": datetime.now().isoformat()
    }


def main():
    parser = argparse.ArgumentParser(description="JARVIS Evolution Engine -- analyze failures, suggest fixes, track evolution")
    parser.add_argument("--evolve", action="store_true", help="Run evolution analysis")
    parser.add_argument("--status", action="store_true", help="Evolution status history")
    parser.add_argument("--rollback", type=int, metavar="RUN_ID", help="Rollback analysis for a run")
    parser.add_argument("--report", action="store_true", help="Full evolution report")
    parser.add_argument("--once", action="store_true", help="Quick status")
    args = parser.parse_args()

    db = init_db()

    if args.evolve:
        result = evolve(db)
    elif args.status:
        result = get_evolution_status(db)
    elif args.rollback:
        result = rollback_info(db, args.rollback)
    elif args.report:
        result = full_report(db)
    else:
        result = do_status(db)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    db.close()


if __name__ == "__main__":
    main()
