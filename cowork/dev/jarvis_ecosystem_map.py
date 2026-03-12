#!/usr/bin/env python3
"""jarvis_ecosystem_map.py — Carte ecosysteme JARVIS.

Visualise toutes les connexions entre composants.

Usage:
    python dev/jarvis_ecosystem_map.py --once
    python dev/jarvis_ecosystem_map.py --map
    python dev/jarvis_ecosystem_map.py --stats
    python dev/jarvis_ecosystem_map.py --dependencies
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
DB_PATH = DEV / "data" / "ecosystem_map.db"


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS maps (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, components INTEGER, connections INTEGER,
        orphans INTEGER, graph TEXT)""")
    db.commit()
    return db


def parse_imports(filepath):
    imports = set()
    try:
        tree = ast.parse(filepath.read_text(encoding="utf-8", errors="replace"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module.split(".")[0])
    except Exception:
        pass
    return imports


def scan_scripts():
    components = {}
    for py in sorted(DEV.glob("*.py")):
        name = py.stem
        imports = parse_imports(py)
        # Count functions
        funcs = []
        try:
            tree = ast.parse(py.read_text(encoding="utf-8", errors="replace"))
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    funcs.append(node.name)
        except Exception:
            pass
        components[name] = {
            "file": py.name,
            "imports": sorted(imports),
            "functions": len(funcs),
            "size_kb": round(py.stat().st_size / 1024, 1),
        }
    return components


def build_graph(components):
    script_names = set(components.keys())
    edges = []
    for name, info in components.items():
        for imp in info["imports"]:
            if imp in script_names and imp != name:
                edges.append({"from": name, "to": imp})
    return edges


def do_map():
    db = init_db()
    components = scan_scripts()
    edges = build_graph(components)

    connected = set()
    for e in edges:
        connected.add(e["from"])
        connected.add(e["to"])
    orphans = [n for n in components if n not in connected]

    # Category detection
    categories = defaultdict(list)
    for name in components:
        if name.startswith("win_"):
            categories["windows"].append(name)
        elif name.startswith("jarvis_"):
            categories["jarvis"].append(name)
        elif name.startswith("ia_"):
            categories["ia"].append(name)
        else:
            categories["other"].append(name)

    graph = {
        "components": {k: v for k, v in sorted(components.items())},
        "edges": edges,
        "orphans": orphans,
        "categories": dict(categories),
    }

    db.execute("INSERT INTO maps (ts, components, connections, orphans, graph) VALUES (?,?,?,?,?)",
               (time.time(), len(components), len(edges), len(orphans), json.dumps(graph)))
    db.commit()
    db.close()

    return {
        "ts": datetime.now().isoformat(),
        "total_components": len(components),
        "total_connections": len(edges),
        "orphans": len(orphans),
        "categories": {k: len(v) for k, v in categories.items()},
        "top_connected": sorted(
            [(n, sum(1 for e in edges if e["from"] == n or e["to"] == n)) for n in components],
            key=lambda x: x[1], reverse=True
        )[:10],
        "orphan_list": orphans[:20],
    }


def main():
    parser = argparse.ArgumentParser(description="JARVIS Ecosystem Map")
    parser.add_argument("--once", "--map", action="store_true", help="Generate map")
    parser.add_argument("--visualize", action="store_true", help="ASCII viz")
    parser.add_argument("--stats", action="store_true", help="Stats")
    parser.add_argument("--dependencies", action="store_true", help="Dependencies")
    args = parser.parse_args()
    print(json.dumps(do_map(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
