#!/usr/bin/env python3
"""ia_doc_generator.py — Auto documentation from source (#251).

Scans dev/*.py via ast, extracts classes/functions/docstrings,
generates markdown documentation, counts undocumented items.

Usage:
    python dev/ia_doc_generator.py --once
    python dev/ia_doc_generator.py --scan
    python dev/ia_doc_generator.py --generate
    python dev/ia_doc_generator.py --format
    python dev/ia_doc_generator.py --export
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
DB_PATH = DEV / "data" / "doc_generator.db"
DOCS_DIR = DEV / "docs_generated"


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("""CREATE TABLE IF NOT EXISTS documented_files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        filepath TEXT NOT NULL,
        module_doc TEXT,
        functions INTEGER DEFAULT 0,
        classes INTEGER DEFAULT 0,
        documented INTEGER DEFAULT 0,
        undocumented INTEGER DEFAULT 0
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS doc_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        filepath TEXT NOT NULL,
        item_type TEXT NOT NULL,
        name TEXT NOT NULL,
        docstring TEXT,
        args TEXT,
        lineno INTEGER,
        has_doc INTEGER DEFAULT 0
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS generated_docs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        source_file TEXT NOT NULL,
        doc_file TEXT NOT NULL,
        sections INTEGER DEFAULT 0
    )""")
    db.commit()
    return db


def extract_docstring(node):
    """Extract docstring from an AST node."""
    if node.body and isinstance(node.body[0], ast.Expr):
        val = node.body[0].value
        if isinstance(val, ast.Constant) and isinstance(val.value, str):
            return val.value.strip()
        if isinstance(val, ast.Str):
            return val.s.strip()
    return None


def scan_file(filepath):
    """Scan a Python file for documentation items."""
    items = []
    module_doc = None
    try:
        source = filepath.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source)

        # Module docstring
        module_doc = extract_docstring(tree)

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.FunctionDef):
                doc = extract_docstring(node)
                args = [a.arg for a in node.args.args if a.arg != "self"]
                items.append({
                    "type": "function", "name": node.name, "docstring": doc,
                    "args": args, "lineno": node.lineno, "has_doc": doc is not None,
                })
            elif isinstance(node, ast.ClassDef):
                class_doc = extract_docstring(node)
                items.append({
                    "type": "class", "name": node.name, "docstring": class_doc,
                    "args": [], "lineno": node.lineno, "has_doc": class_doc is not None,
                })
                # Class methods
                for item in node.body:
                    if isinstance(item, ast.FunctionDef):
                        mdoc = extract_docstring(item)
                        margs = [a.arg for a in item.args.args if a.arg != "self"]
                        items.append({
                            "type": "method", "name": f"{node.name}.{item.name}",
                            "docstring": mdoc, "args": margs, "lineno": item.lineno,
                            "has_doc": mdoc is not None,
                        })
    except (SyntaxError, Exception):
        pass
    return module_doc, items


def generate_markdown(filepath, module_doc, items):
    """Generate markdown documentation for a file."""
    name = Path(filepath).stem
    lines = [f"# {name}.py", ""]

    if module_doc:
        lines.append(module_doc)
        lines.append("")

    # Group by type
    functions = [i for i in items if i["type"] == "function"]
    classes = [i for i in items if i["type"] == "class"]
    methods = [i for i in items if i["type"] == "method"]

    if classes:
        lines.append("## Classes")
        lines.append("")
        for cls in classes:
            lines.append(f"### `{cls['name']}`")
            if cls["docstring"]:
                lines.append(f"\n{cls['docstring']}")
            lines.append(f"\n- Line: {cls['lineno']}")
            # Add methods for this class
            cls_methods = [m for m in methods if m["name"].startswith(f"{cls['name']}.")]
            if cls_methods:
                lines.append("\n**Methods:**\n")
                for m in cls_methods:
                    mname = m["name"].split(".")[-1]
                    args_str = ", ".join(m["args"]) if m["args"] else ""
                    lines.append(f"- `{mname}({args_str})`" + (f" - {m['docstring'][:80]}" if m["docstring"] else ""))
            lines.append("")

    if functions:
        lines.append("## Functions")
        lines.append("")
        for func in functions:
            args_str = ", ".join(func["args"]) if func["args"] else ""
            lines.append(f"### `{func['name']}({args_str})`")
            if func["docstring"]:
                lines.append(f"\n{func['docstring']}")
            lines.append(f"\n- Line: {func['lineno']}")
            lines.append("")

    # Stats
    documented = sum(1 for i in items if i["has_doc"])
    undocumented = len(items) - documented
    lines.append("## Stats")
    lines.append("")
    lines.append(f"- Total items: {len(items)}")
    lines.append(f"- Documented: {documented}")
    lines.append(f"- Undocumented: {undocumented}")
    lines.append(f"- Coverage: {round(documented / max(len(items), 1) * 100, 1)}%")
    lines.append("")

    return "\n".join(lines)


def do_scan():
    """Scan all Python files for documentation."""
    db = init_db()
    now = datetime.now()
    py_files = sorted(DEV.glob("*.py"))

    scanned = []
    total_documented = 0
    total_undocumented = 0

    for f in py_files:
        module_doc, items = scan_file(f)
        documented = sum(1 for i in items if i["has_doc"])
        undocumented = len(items) - documented
        total_documented += documented
        total_undocumented += undocumented

        funcs = sum(1 for i in items if i["type"] == "function")
        classes = sum(1 for i in items if i["type"] == "class")

        db.execute(
            "INSERT INTO documented_files (ts, filepath, module_doc, functions, classes, documented, undocumented) VALUES (?,?,?,?,?,?,?)",
            (now.isoformat(), str(f), module_doc[:200] if module_doc else None,
             funcs, classes, documented, undocumented),
        )
        for item in items:
            db.execute(
                "INSERT INTO doc_items (ts, filepath, item_type, name, docstring, args, lineno, has_doc) VALUES (?,?,?,?,?,?,?,?)",
                (now.isoformat(), str(f), item["type"], item["name"],
                 item["docstring"][:500] if item["docstring"] else None,
                 json.dumps(item["args"]), item["lineno"], int(item["has_doc"])),
            )

        scanned.append({
            "file": f.name, "functions": funcs, "classes": classes,
            "documented": documented, "undocumented": undocumented,
        })

    db.commit()
    result = {
        "ts": now.isoformat(), "action": "scan", "files_scanned": len(py_files),
        "total_documented": total_documented, "total_undocumented": total_undocumented,
        "doc_coverage": round(total_documented / max(total_documented + total_undocumented, 1) * 100, 1),
        "files": scanned[:30],
    }
    db.close()
    return result


def do_generate():
    """Generate markdown docs for all scanned files."""
    db = init_db()
    now = datetime.now()
    py_files = sorted(DEV.glob("*.py"))
    generated = []

    for f in py_files:
        module_doc, items = scan_file(f)
        if not items:
            continue
        md = generate_markdown(str(f), module_doc, items)
        doc_path = DOCS_DIR / f"{f.stem}.md"
        doc_path.write_text(md, encoding="utf-8")

        db.execute(
            "INSERT INTO generated_docs (ts, source_file, doc_file, sections) VALUES (?,?,?,?)",
            (now.isoformat(), str(f), str(doc_path), len(items)),
        )
        generated.append({"source": f.name, "doc": doc_path.name, "items": len(items)})

    db.commit()
    result = {
        "ts": now.isoformat(), "action": "generate",
        "docs_generated": len(generated), "output_dir": str(DOCS_DIR),
        "files": generated[:30],
    }
    db.close()
    return result


def do_format():
    """Show documentation format summary."""
    db = init_db()
    by_type = db.execute(
        "SELECT item_type, COUNT(*), SUM(has_doc) FROM doc_items GROUP BY item_type"
    ).fetchall()

    undocumented = db.execute(
        "SELECT filepath, name, item_type FROM doc_items WHERE has_doc=0 ORDER BY filepath LIMIT 30"
    ).fetchall()

    result = {
        "ts": datetime.now().isoformat(), "action": "format",
        "by_type": [
            {"type": r[0], "total": r[1], "documented": r[2],
             "coverage": round((r[2] or 0) / max(r[1], 1) * 100, 1)}
            for r in by_type
        ],
        "undocumented_items": [
            {"file": os.path.basename(r[0]), "name": r[1], "type": r[2]}
            for r in undocumented
        ],
    }
    db.close()
    return result


def do_export():
    """Export documentation data."""
    db = init_db()
    result = {
        "ts": datetime.now().isoformat(), "action": "export",
        "total_files": db.execute("SELECT COUNT(*) FROM documented_files").fetchone()[0],
        "total_items": db.execute("SELECT COUNT(*) FROM doc_items").fetchone()[0],
        "total_docs": db.execute("SELECT COUNT(*) FROM generated_docs").fetchone()[0],
        "docs_dir": str(DOCS_DIR),
        "doc_files": [f.name for f in sorted(DOCS_DIR.glob("*.md"))[:30]],
    }
    db.close()
    return result


def do_status():
    db = init_db()
    result = {
        "ts": datetime.now().isoformat(), "script": "ia_doc_generator.py", "script_id": 251,
        "db": str(DB_PATH), "docs_dir": str(DOCS_DIR),
        "documented_files": db.execute("SELECT COUNT(*) FROM documented_files").fetchone()[0],
        "doc_items": db.execute("SELECT COUNT(*) FROM doc_items").fetchone()[0],
        "generated_docs": db.execute("SELECT COUNT(*) FROM generated_docs").fetchone()[0],
        "status": "ok",
    }
    db.close()
    return result


def main():
    parser = argparse.ArgumentParser(description="ia_doc_generator.py — Auto documentation (#251)")
    parser.add_argument("--scan", action="store_true", help="Scan files for documentation")
    parser.add_argument("--generate", action="store_true", help="Generate markdown docs")
    parser.add_argument("--format", action="store_true", help="Show format summary")
    parser.add_argument("--export", action="store_true", help="Export documentation data")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    args = parser.parse_args()

    if args.scan:
        result = do_scan()
    elif args.generate:
        result = do_generate()
    elif args.format:
        result = do_format()
    elif args.export:
        result = do_export()
    else:
        result = do_status()

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
