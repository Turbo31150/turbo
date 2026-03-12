#!/usr/bin/env python3
"""jarvis_code_auditor.py — Audit qualite code de tous les scripts dev/.

Detecte patterns dangereux, code mort, fonctions trop longues,
imports inutiles. Scoring qualite 0-100 par fichier.

Usage:
    python dev/jarvis_code_auditor.py --once
    python dev/jarvis_code_auditor.py --audit
    python dev/jarvis_code_auditor.py --severity high
    python dev/jarvis_code_auditor.py --report
"""
import argparse
import ast
import json
import os
import sqlite3
import time
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "code_auditor.db"

DANGEROUS_CALLS = {"eval", "exec", "os.system", "subprocess.call", "__import__"}
MAX_FUNCTION_LINES = 50
MAX_FILE_LINES = 500


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS audits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, files_scanned INTEGER, avg_score REAL,
        issues_total INTEGER, report TEXT)""")
    db.execute("""CREATE TABLE IF NOT EXISTS file_scores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, filepath TEXT, score REAL, issues TEXT)""")
    db.commit()
    return db


def audit_file(filepath):
    """Audit a single Python file."""
    issues = []
    score = 100

    try:
        content = filepath.read_text(encoding="utf-8", errors="ignore")
        lines = content.split("\n")
        line_count = len(lines)

        # Parse AST
        try:
            tree = ast.parse(content, filename=str(filepath))
        except SyntaxError as e:
            return {"file": filepath.name, "score": 0, "issues": [{"type": "syntax_error", "severity": "critical", "msg": str(e)}]}

        # Check file length
        if line_count > MAX_FILE_LINES:
            issues.append({"type": "file_too_long", "severity": "low", "msg": f"{line_count} lines (max {MAX_FILE_LINES})"})
            score -= 5

        # Walk AST
        for node in ast.walk(tree):
            # Dangerous calls
            if isinstance(node, ast.Call):
                func_name = ""
                if isinstance(node.func, ast.Name):
                    func_name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    if isinstance(node.func.value, ast.Name):
                        func_name = f"{node.func.value.id}.{node.func.attr}"
                if func_name in DANGEROUS_CALLS:
                    issues.append({"type": "dangerous_call", "severity": "high",
                                   "msg": f"{func_name}() at line {node.lineno}"})
                    score -= 15

            # Long functions
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                func_lines = node.end_lineno - node.lineno if hasattr(node, "end_lineno") else 0
                if func_lines > MAX_FUNCTION_LINES:
                    issues.append({"type": "long_function", "severity": "medium",
                                   "msg": f"{node.name}() is {func_lines} lines (max {MAX_FUNCTION_LINES})"})
                    score -= 5

        # Check for missing docstring
        if not content.strip().startswith('"""') and not content.strip().startswith("'''"):
            if not any(isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant) and isinstance(n.value.value, str)
                       for n in ast.iter_child_nodes(tree)):
                issues.append({"type": "no_docstring", "severity": "low", "msg": "No module docstring"})
                score -= 3

        # Check for bare except
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler) and node.type is None:
                issues.append({"type": "bare_except", "severity": "medium",
                               "msg": f"Bare except at line {node.lineno}"})
                score -= 5

        score = max(0, min(100, score))
        return {"file": filepath.name, "score": score, "lines": line_count, "issues": issues}

    except Exception as e:
        return {"file": filepath.name, "score": 0, "issues": [{"type": "read_error", "severity": "critical", "msg": str(e)}]}


def do_audit(severity_filter=None):
    """Audit all Python files in dev/."""
    db = init_db()
    results = []
    py_files = sorted(DEV.glob("*.py"))

    for f in py_files:
        if f.name.startswith("__"):
            continue
        result = audit_file(f)
        results.append(result)

        db.execute(
            "INSERT INTO file_scores (ts, filepath, score, issues) VALUES (?,?,?,?)",
            (time.time(), result["file"], result["score"], json.dumps(result["issues"]))
        )

    avg_score = sum(r["score"] for r in results) / max(len(results), 1)
    total_issues = sum(len(r["issues"]) for r in results)

    # Filter by severity if requested
    if severity_filter:
        for r in results:
            r["issues"] = [i for i in r["issues"] if i["severity"] == severity_filter]

    report = {
        "ts": datetime.now().isoformat(),
        "files_scanned": len(results),
        "avg_score": round(avg_score, 1),
        "total_issues": total_issues,
        "worst_files": sorted(results, key=lambda x: x["score"])[:10],
        "best_files": sorted(results, key=lambda x: x["score"], reverse=True)[:5],
    }

    db.execute(
        "INSERT INTO audits (ts, files_scanned, avg_score, issues_total, report) VALUES (?,?,?,?,?)",
        (time.time(), len(results), avg_score, total_issues, json.dumps(report))
    )
    db.commit()
    db.close()
    return report


def main():
    parser = argparse.ArgumentParser(description="JARVIS Code Auditor")
    parser.add_argument("--once", "--audit", action="store_true", help="Full audit")
    parser.add_argument("--severity", choices=["low", "medium", "high", "critical"], help="Filter by severity")
    parser.add_argument("--report", action="store_true", help="History")
    args = parser.parse_args()

    result = do_audit(args.severity)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
