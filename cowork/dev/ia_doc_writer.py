#!/usr/bin/env python3
"""ia_doc_writer.py — Redacteur documentation IA.

Genere docs automatiques a partir du code source.

Usage:
    python dev/ia_doc_writer.py --once
    python dev/ia_doc_writer.py --generate FILE
    python dev/ia_doc_writer.py --readme
    python dev/ia_doc_writer.py --api
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
DB_PATH = DEV / "data" / "doc_writer.db"


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS docs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, file_path TEXT, functions INTEGER,
        classes INTEGER, documented INTEGER, score REAL)""")
    db.commit()
    return db


def analyze_python_file(filepath):
    try:
        source = filepath.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source)
    except Exception:
        return None

    functions = []
    classes = []
    documented = 0

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            has_doc = ast.get_docstring(node) is not None
            if has_doc:
                documented += 1
            args = [a.arg for a in node.args.args if a.arg != "self"]
            returns = None
            if node.returns and isinstance(node.returns, ast.Name):
                returns = node.returns.id
            functions.append({
                "name": node.name,
                "args": args,
                "returns": returns,
                "has_docstring": has_doc,
                "line": node.lineno,
            })
        elif isinstance(node, ast.ClassDef):
            has_doc = ast.get_docstring(node) is not None
            if has_doc:
                documented += 1
            methods = [n.name for n in node.body if isinstance(n, ast.FunctionDef)]
            classes.append({
                "name": node.name,
                "methods": methods,
                "has_docstring": has_doc,
                "line": node.lineno,
            })

    total = len(functions) + len(classes)
    score = documented / max(total, 1) * 100

    return {
        "file": filepath.name,
        "functions": functions,
        "classes": classes,
        "total_items": total,
        "documented": documented,
        "doc_coverage_pct": round(score, 1),
    }


def do_scan():
    db = init_db()
    results = []

    for py in sorted(DEV.glob("*.py")):
        info = analyze_python_file(py)
        if info:
            results.append(info)
            db.execute("INSERT INTO docs (ts, file_path, functions, classes, documented, score) VALUES (?,?,?,?,?,?)",
                       (time.time(), py.name, len(info["functions"]), len(info["classes"]),
                        info["documented"], info["doc_coverage_pct"]))

    db.commit()
    db.close()

    total_funcs = sum(len(r["functions"]) for r in results)
    total_classes = sum(len(r["classes"]) for r in results)
    total_documented = sum(r["documented"] for r in results)
    total_items = sum(r["total_items"] for r in results)

    undocumented = [
        {"file": r["file"], "name": f["name"], "type": "function"}
        for r in results for f in r["functions"] if not f["has_docstring"]
    ][:20]

    return {
        "ts": datetime.now().isoformat(),
        "files_scanned": len(results),
        "total_functions": total_funcs,
        "total_classes": total_classes,
        "documented": total_documented,
        "coverage_pct": round(total_documented / max(total_items, 1) * 100, 1),
        "top_undocumented": undocumented,
    }


def main():
    parser = argparse.ArgumentParser(description="IA Doc Writer")
    parser.add_argument("--once", "--readme", action="store_true", help="Scan docs")
    parser.add_argument("--generate", metavar="FILE", help="Generate for file")
    parser.add_argument("--api", action="store_true", help="API reference")
    parser.add_argument("--changelog", action="store_true", help="Changelog")
    args = parser.parse_args()
    print(json.dumps(do_scan(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
