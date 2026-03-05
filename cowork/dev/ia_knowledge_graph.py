#!/usr/bin/env python3
"""ia_knowledge_graph.py — Graphe de connaissances JARVIS.

Relie concepts, scripts, commandes, skills. Parse docstrings.

Usage:
    python dev/ia_knowledge_graph.py --once
    python dev/ia_knowledge_graph.py --build
    python dev/ia_knowledge_graph.py --query "cluster"
    python dev/ia_knowledge_graph.py --update
"""
import argparse
import ast
import json
import os
import sqlite3
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
TURBO_SRC = Path("F:/BUREAU/turbo/src")
DB_PATH = DEV / "data" / "knowledge_graph.db"


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS nodes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE, node_type TEXT,
        description TEXT, filepath TEXT)""")
    db.execute("""CREATE TABLE IF NOT EXISTS edges (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source TEXT, target TEXT, edge_type TEXT)""")
    db.execute("""CREATE TABLE IF NOT EXISTS builds (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, nodes_count INTEGER, edges_count INTEGER)""")
    db.commit()
    return db


def extract_module_info(filepath):
    """Extract module info from a Python file."""
    info = {"name": filepath.stem, "type": "script" if "dev" in str(filepath) else "module",
            "filepath": str(filepath), "description": "", "imports": [], "functions": []}
    try:
        content = filepath.read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(content)

        # Module docstring
        if (isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, ast.Constant)):
            info["description"] = str(tree.body[0].value.value)[:200]

        # Imports
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    info["imports"].append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    info["imports"].append(node.module)

        # Functions
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                info["functions"].append(node.name)

    except Exception:
        pass
    return info


def build_graph():
    """Build the knowledge graph."""
    db = init_db()

    # Clear old data
    db.execute("DELETE FROM nodes")
    db.execute("DELETE FROM edges")

    modules = []

    # Scan dev/
    for f in sorted(DEV.glob("*.py")):
        if not f.name.startswith("__"):
            modules.append(extract_module_info(f))

    # Scan src/
    if TURBO_SRC.exists():
        for f in sorted(TURBO_SRC.glob("*.py")):
            if not f.name.startswith("__"):
                modules.append(extract_module_info(f))

    # Create nodes
    for mod in modules:
        db.execute(
            "INSERT OR REPLACE INTO nodes (name, node_type, description, filepath) VALUES (?,?,?,?)",
            (mod["name"], mod["type"], mod["description"], mod["filepath"])
        )

        # Create function nodes
        for func in mod["functions"][:10]:
            db.execute(
                "INSERT OR REPLACE INTO nodes (name, node_type, description, filepath) VALUES (?,?,?,?)",
                (f"{mod['name']}.{func}", "function", "", mod["filepath"])
            )
            db.execute(
                "INSERT INTO edges (source, target, edge_type) VALUES (?,?,?)",
                (mod["name"], f"{mod['name']}.{func}", "contains")
            )

    # Create import edges
    all_names = {m["name"] for m in modules}
    for mod in modules:
        for imp in mod["imports"]:
            imp_base = imp.split(".")[0]
            if imp_base in all_names:
                db.execute(
                    "INSERT INTO edges (source, target, edge_type) VALUES (?,?,?)",
                    (mod["name"], imp_base, "imports")
                )

    nodes_count = db.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
    edges_count = db.execute("SELECT COUNT(*) FROM edges").fetchone()[0]

    db.execute("INSERT INTO builds (ts, nodes_count, edges_count) VALUES (?,?,?)",
               (time.time(), nodes_count, edges_count))
    db.commit()
    db.close()

    return {
        "ts": datetime.now().isoformat(),
        "nodes": nodes_count,
        "edges": edges_count,
        "modules": len(modules),
    }


def query_graph(topic):
    """Query the knowledge graph."""
    db = init_db()
    nodes = db.execute(
        "SELECT name, node_type, description FROM nodes WHERE name LIKE ? OR description LIKE ?",
        (f"%{topic}%", f"%{topic}%")
    ).fetchall()

    results = []
    for n in nodes:
        edges = db.execute(
            "SELECT target, edge_type FROM edges WHERE source=?", (n[0],)
        ).fetchall()
        results.append({
            "name": n[0], "type": n[1], "description": n[2][:100],
            "connections": [{"target": e[0], "type": e[1]} for e in edges[:10]],
        })

    db.close()
    return results


def main():
    parser = argparse.ArgumentParser(description="IA Knowledge Graph")
    parser.add_argument("--once", "--build", action="store_true", help="Build graph")
    parser.add_argument("--query", metavar="TOPIC", help="Query graph")
    parser.add_argument("--update", action="store_true", help="Update graph")
    args = parser.parse_args()

    if args.query:
        result = query_graph(args.query)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        result = build_graph()
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
