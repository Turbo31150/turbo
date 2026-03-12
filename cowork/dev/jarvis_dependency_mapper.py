#!/usr/bin/env python3
"""jarvis_dependency_mapper.py — Cartographie les dependances entre scripts.

Parse les imports AST, detecte circulaires, orphelins,
genere graphe JSON, score couplage.

Usage:
    python dev/jarvis_dependency_mapper.py --once
    python dev/jarvis_dependency_mapper.py --map
    python dev/jarvis_dependency_mapper.py --circular
    python dev/jarvis_dependency_mapper.py --orphans
"""
import argparse
from _paths import TURBO_DIR
import ast
import json
import os
import sqlite3
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
TURBO_SRC = TURBO_DIR / "src"
DB_PATH = DEV / "data" / "dependency_mapper.db"


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS maps (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, total_files INTEGER, total_deps INTEGER,
        circular INTEGER, orphans INTEGER, score REAL, graph TEXT)""")
    db.commit()
    return db


def extract_imports(filepath):
    """Extract import names from a Python file."""
    imports = set()
    try:
        content = filepath.read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(content, filename=str(filepath))
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


def build_graph():
    """Build dependency graph for all Python files."""
    graph = {}  # file -> set of dependencies
    all_files = set()

    # Scan dev/
    for f in sorted(DEV.glob("*.py")):
        if f.name.startswith("__"):
            continue
        name = f.stem
        all_files.add(name)
        imports = extract_imports(f)
        # Filter to only internal deps (other dev scripts or src modules)
        internal = set()
        for imp in imports:
            if (DEV / f"{imp}.py").exists():
                internal.add(imp)
            elif TURBO_SRC.exists() and (TURBO_SRC / f"{imp}.py").exists():
                internal.add(f"src.{imp}")
        graph[name] = internal

    # Scan src/
    if TURBO_SRC.exists():
        for f in sorted(TURBO_SRC.glob("*.py")):
            if f.name.startswith("__"):
                continue
            name = f"src.{f.stem}"
            all_files.add(name)
            imports = extract_imports(f)
            internal = set()
            for imp in imports:
                if imp.startswith("src."):
                    internal.add(imp)
                elif (TURBO_SRC / f"{imp}.py").exists():
                    internal.add(f"src.{imp}")
            graph[name] = internal

    return graph, all_files


def find_circular(graph):
    """Find circular dependencies using DFS."""
    circular = []
    visited = set()
    path = []

    def dfs(node):
        if node in path:
            cycle_start = path.index(node)
            circular.append(path[cycle_start:] + [node])
            return
        if node in visited:
            return
        visited.add(node)
        path.append(node)
        for dep in graph.get(node, set()):
            dfs(dep)
        path.pop()

    for node in graph:
        visited.clear()
        path.clear()
        dfs(node)

    return circular


def find_orphans(graph, all_files):
    """Find files that are never imported by others."""
    imported = set()
    for deps in graph.values():
        imported.update(deps)
    orphans = all_files - imported - {"__init__"}
    return sorted(orphans)


def do_map():
    """Full dependency mapping."""
    db = init_db()
    graph, all_files = build_graph()
    circular = find_circular(graph)
    orphans = find_orphans(graph, all_files)

    total_deps = sum(len(deps) for deps in graph.values())
    avg_deps = total_deps / max(len(graph), 1)

    # Coupling score: lower is better (fewer deps per file)
    coupling_score = max(0, 100 - int(avg_deps * 10))

    # Convert sets to lists for JSON
    json_graph = {k: sorted(v) for k, v in graph.items()}

    report = {
        "ts": datetime.now().isoformat(),
        "total_files": len(all_files),
        "total_dependencies": total_deps,
        "avg_deps_per_file": round(avg_deps, 2),
        "circular_dependencies": len(circular),
        "circular_details": circular[:10],
        "orphans": orphans[:20],
        "coupling_score": coupling_score,
        "most_depended": sorted(
            [(f, sum(1 for deps in graph.values() if f in deps)) for f in all_files],
            key=lambda x: x[1], reverse=True
        )[:10],
    }

    db.execute(
        "INSERT INTO maps (ts, total_files, total_deps, circular, orphans, score, graph) VALUES (?,?,?,?,?,?,?)",
        (time.time(), len(all_files), total_deps, len(circular),
         len(orphans), coupling_score, json.dumps(json_graph))
    )
    db.commit()
    db.close()
    return report


def main():
    parser = argparse.ArgumentParser(description="JARVIS Dependency Mapper")
    parser.add_argument("--once", "--map", action="store_true", help="Full mapping")
    parser.add_argument("--circular", action="store_true", help="Show circular deps only")
    parser.add_argument("--orphans", action="store_true", help="Show orphan files")
    args = parser.parse_args()

    result = do_map()
    if args.circular:
        print(json.dumps({"circular": result["circular_details"]}, ensure_ascii=False, indent=2))
    elif args.orphans:
        print(json.dumps({"orphans": result["orphans"]}, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()