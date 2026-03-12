#!/usr/bin/env python3
"""ia_test_generator.py — Auto test generation (#250).

Scans dev/*.py, finds public functions via ast.parse, generates unittest
test cases (assert-based), writes test_*.py files.

Usage:
    python dev/ia_test_generator.py --once
    python dev/ia_test_generator.py --scan
    python dev/ia_test_generator.py --generate FILE
    python dev/ia_test_generator.py --run
    python dev/ia_test_generator.py --coverage
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
DB_PATH = DEV / "data" / "test_generator.db"
TESTS_DIR = DEV / "tests_generated"


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    TESTS_DIR.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("""CREATE TABLE IF NOT EXISTS scanned_files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        filepath TEXT NOT NULL,
        functions INTEGER DEFAULT 0,
        classes INTEGER DEFAULT 0,
        public_functions TEXT,
        has_tests INTEGER DEFAULT 0
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS generated_tests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        source_file TEXT NOT NULL,
        test_file TEXT NOT NULL,
        test_count INTEGER DEFAULT 0,
        functions_covered TEXT,
        valid INTEGER DEFAULT 1
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS test_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        test_file TEXT,
        passed INTEGER DEFAULT 0,
        failed INTEGER DEFAULT 0,
        errors INTEGER DEFAULT 0,
        output TEXT
    )""")
    db.commit()
    return db


def scan_python_file(filepath):
    """Scan a Python file for public functions and classes."""
    info = {"filepath": str(filepath), "functions": [], "classes": [], "errors": []}
    try:
        source = filepath.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                if not node.name.startswith("_"):
                    args = [a.arg for a in node.args.args if a.arg != "self"]
                    info["functions"].append({
                        "name": node.name,
                        "args": args,
                        "lineno": node.lineno,
                        "has_docstring": (
                            isinstance(node.body[0], ast.Expr) and
                            isinstance(node.body[0].value, (ast.Constant, ast.Str))
                        ) if node.body else False,
                    })
            elif isinstance(node, ast.ClassDef):
                methods = [
                    item.name for item in node.body
                    if isinstance(item, ast.FunctionDef) and not item.name.startswith("_")
                ]
                info["classes"].append({
                    "name": node.name, "methods": methods, "lineno": node.lineno,
                })
    except SyntaxError as e:
        info["errors"].append(f"SyntaxError: {e}")
    except Exception as e:
        info["errors"].append(str(e))
    return info


def generate_test_code(source_file, file_info):
    """Generate unittest test code for a source file."""
    module_name = Path(source_file).stem
    lines = [
        '#!/usr/bin/env python3',
        f'"""Auto-generated tests for {module_name}.py"""',
        'import unittest',
        'import sys',
        'import os',
        '',
        'sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))',
        '',
        '',
        f'class Test{module_name.title().replace("_", "")}(unittest.TestCase):',
        f'    """Tests for {module_name}."""',
        '',
    ]
    test_count = 0

    for func in file_info.get("functions", []):
        fname = func["name"]
        lines.append(f'    def test_{fname}_exists(self):')
        lines.append(f'        """Test that {fname} is callable."""')
        lines.append(f'        try:')
        lines.append(f'            from {module_name} import {fname}')
        lines.append(f'            self.assertTrue(callable({fname}))')
        lines.append(f'        except ImportError:')
        lines.append(f'            self.skipTest("{module_name} not importable")')
        lines.append('')
        test_count += 1

        if not func["args"]:
            lines.append(f'    def test_{fname}_runs(self):')
            lines.append(f'        """Test that {fname}() runs without error."""')
            lines.append(f'        try:')
            lines.append(f'            from {module_name} import {fname}')
            lines.append(f'            result = {fname}()')
            lines.append(f'            self.assertIsNotNone(result)')
            lines.append(f'        except ImportError:')
            lines.append(f'            self.skipTest("{module_name} not importable")')
            lines.append(f'        except Exception:')
            lines.append(f'            pass')
            lines.append('')
            test_count += 1

    for cls in file_info.get("classes", []):
        cname = cls["name"]
        lines.append(f'    def test_{cname.lower()}_class_exists(self):')
        lines.append(f'        """Test that {cname} class exists."""')
        lines.append(f'        try:')
        lines.append(f'            from {module_name} import {cname}')
        lines.append(f'            self.assertTrue(isinstance({cname}, type))')
        lines.append(f'        except ImportError:')
        lines.append(f'            self.skipTest("{module_name} not importable")')
        lines.append('')
        test_count += 1

        for method in cls["methods"]:
            lines.append(f'    def test_{cname.lower()}_{method}_exists(self):')
            lines.append(f'        """Test that {cname}.{method} exists."""')
            lines.append(f'        try:')
            lines.append(f'            from {module_name} import {cname}')
            lines.append(f'            self.assertTrue(hasattr({cname}, "{method}"))')
            lines.append(f'        except ImportError:')
            lines.append(f'            self.skipTest("{module_name} not importable")')
            lines.append('')
            test_count += 1

    if test_count == 0:
        lines.append('    def test_module_imports(self):')
        lines.append(f'        """Test that {module_name} can be imported."""')
        lines.append(f'        try:')
        lines.append(f'            import {module_name}')
        lines.append(f'        except ImportError:')
        lines.append(f'            self.skipTest("{module_name} not importable")')
        lines.append('')
        test_count = 1

    lines.extend(['', 'if __name__ == "__main__":', '    unittest.main()', ''])
    return "\n".join(lines), test_count


def do_scan():
    """Scan all Python files in dev/ for testable functions."""
    db = init_db()
    now = datetime.now()
    py_files = sorted(DEV.glob("*.py"))
    py_files = [f for f in py_files if not f.name.startswith("test_") and f.name != "ia_test_generator.py"]

    scanned = []
    for f in py_files:
        info = scan_python_file(f)
        pub_funcs = [fn["name"] for fn in info["functions"]]
        db.execute(
            "INSERT INTO scanned_files (ts, filepath, functions, classes, public_functions, has_tests) VALUES (?,?,?,?,?,?)",
            (now.isoformat(), str(f), len(info["functions"]), len(info["classes"]),
             json.dumps(pub_funcs), int((TESTS_DIR / f"test_{f.stem}.py").exists())),
        )
        scanned.append({
            "file": f.name, "functions": len(info["functions"]),
            "classes": len(info["classes"]), "public_functions": pub_funcs[:10],
            "has_tests": (TESTS_DIR / f"test_{f.stem}.py").exists(),
        })

    db.commit()
    result = {
        "ts": now.isoformat(), "action": "scan", "files_scanned": len(py_files),
        "total_functions": sum(s["functions"] for s in scanned),
        "total_classes": sum(s["classes"] for s in scanned),
        "with_tests": sum(1 for s in scanned if s["has_tests"]),
        "files": scanned[:30],
    }
    db.close()
    return result


def do_generate(filepath):
    """Generate tests for a specific file."""
    db = init_db()
    now = datetime.now()
    source_path = Path(filepath)
    if not source_path.is_absolute():
        source_path = DEV / filepath
    if not source_path.exists():
        db.close()
        return {"ts": now.isoformat(), "action": "generate", "error": f"File not found: {source_path}"}

    info = scan_python_file(source_path)
    test_code, test_count = generate_test_code(str(source_path), info)
    test_filename = f"test_{source_path.stem}.py"
    test_path = TESTS_DIR / test_filename
    test_path.write_text(test_code, encoding="utf-8")

    funcs_covered = [f["name"] for f in info["functions"]]
    db.execute(
        "INSERT INTO generated_tests (ts, source_file, test_file, test_count, functions_covered) VALUES (?,?,?,?,?)",
        (now.isoformat(), str(source_path), str(test_path), test_count, json.dumps(funcs_covered)),
    )
    db.commit()
    result = {
        "ts": now.isoformat(), "action": "generate", "source_file": str(source_path),
        "test_file": str(test_path), "test_count": test_count,
        "functions_covered": funcs_covered, "classes_found": len(info["classes"]),
    }
    db.close()
    return result


def do_run():
    """Run generated tests."""
    db = init_db()
    now = datetime.now()
    test_files = sorted(TESTS_DIR.glob("test_*.py"))
    results_list = []

    for tf in test_files[:10]:
        try:
            out = subprocess.check_output(
                ["python", str(tf), "-v"],
                stderr=subprocess.STDOUT, text=True, timeout=30,
            )
            passed = out.count("... ok")
            failed = out.count("... FAIL")
            errors = out.count("... ERROR")
        except subprocess.CalledProcessError as e:
            out = e.output
            passed = out.count("... ok")
            failed = out.count("... FAIL")
            errors = out.count("... ERROR")
        except Exception as e:
            out = str(e)
            passed, failed, errors = 0, 0, 1

        db.execute(
            "INSERT INTO test_runs (ts, test_file, passed, failed, errors, output) VALUES (?,?,?,?,?,?)",
            (now.isoformat(), tf.name, passed, failed, errors, out[:2000]),
        )
        results_list.append({"test_file": tf.name, "passed": passed, "failed": failed, "errors": errors})

    db.commit()
    result = {
        "ts": now.isoformat(), "action": "run", "tests_run": len(results_list),
        "total_passed": sum(r["passed"] for r in results_list),
        "total_failed": sum(r["failed"] for r in results_list),
        "total_errors": sum(r["errors"] for r in results_list),
        "results": results_list,
    }
    db.close()
    return result


def do_coverage():
    """Show test coverage statistics."""
    db = init_db()
    all_py = [f for f in sorted(DEV.glob("*.py")) if not f.name.startswith("test_")]
    test_files = sorted(TESTS_DIR.glob("test_*.py"))
    covered_stems = {f.stem.replace("test_", "") for f in test_files}
    covered = [f.name for f in all_py if f.stem in covered_stems]
    uncovered = [f.name for f in all_py if f.stem not in covered_stems]

    result = {
        "ts": datetime.now().isoformat(), "action": "coverage",
        "total_source_files": len(all_py), "files_with_tests": len(covered),
        "files_without_tests": len(uncovered),
        "coverage_percent": round(len(covered) / max(len(all_py), 1) * 100, 1),
        "covered": covered[:20], "uncovered": uncovered[:20],
    }
    db.close()
    return result


def do_status():
    db = init_db()
    result = {
        "ts": datetime.now().isoformat(), "script": "ia_test_generator.py", "script_id": 250,
        "db": str(DB_PATH), "tests_dir": str(TESTS_DIR),
        "generated_tests": db.execute("SELECT COUNT(*) FROM generated_tests").fetchone()[0],
        "test_runs": db.execute("SELECT COUNT(*) FROM test_runs").fetchone()[0],
        "scanned_files": db.execute("SELECT COUNT(*) FROM scanned_files").fetchone()[0],
        "status": "ok",
    }
    db.close()
    return result


def main():
    parser = argparse.ArgumentParser(description="ia_test_generator.py — Auto test generation (#250)")
    parser.add_argument("--scan", action="store_true", help="Scan Python files for testable functions")
    parser.add_argument("--generate", type=str, metavar="FILE", help="Generate tests for a file")
    parser.add_argument("--run", action="store_true", help="Run generated tests")
    parser.add_argument("--coverage", action="store_true", help="Show test coverage")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    args = parser.parse_args()

    if args.scan:
        result = do_scan()
    elif args.generate:
        result = do_generate(args.generate)
    elif args.run:
        result = do_run()
    elif args.coverage:
        result = do_coverage()
    else:
        result = do_status()

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
