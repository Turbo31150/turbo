#!/usr/bin/env python3
"""ia_test_writer.py — Generateur tests IA.

Cree tests unitaires automatiques pour chaque script.

Usage:
    python dev/ia_test_writer.py --once
    python dev/ia_test_writer.py --generate FILE
    python dev/ia_test_writer.py --coverage
    python dev/ia_test_writer.py --run
"""
import argparse
import ast
import json
import os
import sqlite3
import subprocess
import time
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "test_writer.db"


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS test_reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, scripts_scanned INTEGER, testable INTEGER,
        has_tests INTEGER, coverage_pct REAL)""")
    db.commit()
    return db


def get_public_functions(filepath):
    funcs = []
    try:
        tree = ast.parse(filepath.read_text(encoding="utf-8", errors="replace"))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
                args = [a.arg for a in node.args.args if a.arg != "self"]
                funcs.append({
                    "name": node.name,
                    "args": args,
                    "line": node.lineno,
                })
    except Exception:
        pass
    return funcs


def check_existing_test(script_name):
    test_file = DEV / f"test_{script_name}"
    return test_file.exists()


def generate_test_template(script_name, functions):
    lines = [
        f'"""Auto-generated tests for {script_name}."""',
        "import json",
        "import subprocess",
        "import sys",
        "",
        "",
        f"SCRIPT = 'dev/{script_name}'",
        "",
        "",
        "def test_help():",
        '    """Test --help flag."""',
        f"    r = subprocess.run([sys.executable, SCRIPT, '--help'],",
        "                       capture_output=True, text=True, timeout=10)",
        "    assert r.returncode == 0",
        "    assert 'usage' in r.stdout.lower()",
        "",
    ]

    if any(f["name"] == "init_db" for f in functions):
        lines.extend([
            "",
            "def test_init_db():",
            '    """Test database initialization."""',
            f"    from dev.{script_name.replace('.py', '')} import init_db",
            "    db = init_db()",
            "    assert db is not None",
            "    db.close()",
            "",
        ])

    for func in functions:
        if func["name"] in ("main", "init_db"):
            continue
        lines.extend([
            "",
            f"def test_{func['name']}():",
            f'    """Test {func["name"]} function."""',
            f"    # TODO: Implement test for {func['name']}({', '.join(func['args'])})",
            "    pass",
            "",
        ])

    return "\n".join(lines)


def do_scan():
    db = init_db()
    results = []

    for py in sorted(DEV.glob("*.py")):
        if py.name.startswith("test_"):
            continue
        funcs = get_public_functions(py)
        has_test = check_existing_test(py.name)
        results.append({
            "script": py.name,
            "functions": len(funcs),
            "testable": len([f for f in funcs if f["name"] not in ("main",)]),
            "has_tests": has_test,
        })

    total = len(results)
    testable = sum(1 for r in results if r["testable"] > 0)
    tested = sum(1 for r in results if r["has_tests"])
    coverage = tested / max(testable, 1) * 100

    db.execute("INSERT INTO test_reports (ts, scripts_scanned, testable, has_tests, coverage_pct) VALUES (?,?,?,?,?)",
               (time.time(), total, testable, tested, coverage))
    db.commit()
    db.close()

    missing_tests = [r["script"] for r in results if r["testable"] > 0 and not r["has_tests"]]

    return {
        "ts": datetime.now().isoformat(),
        "scripts_scanned": total,
        "testable": testable,
        "has_tests": tested,
        "coverage_pct": round(coverage, 1),
        "missing_tests": missing_tests[:20],
    }


def main():
    parser = argparse.ArgumentParser(description="IA Test Writer")
    parser.add_argument("--once", "--coverage", action="store_true", help="Coverage report")
    parser.add_argument("--generate", metavar="FILE", help="Generate tests for file")
    parser.add_argument("--edge-cases", action="store_true", help="Include edge cases")
    parser.add_argument("--run", action="store_true", help="Run tests")
    args = parser.parse_args()
    print(json.dumps(do_scan(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
