#!/usr/bin/env python3
"""Script Deduplication — Find and merge duplicate/overlapping scripts.

Compares all Python scripts in dev/ by function names, imports, docstrings,
and AST structural similarity. Detects pairs with configurable overlap
threshold and reports duplicates with merge suggestions.

Usage:
    python script_deduplication.py --once
    python script_deduplication.py --once --threshold 70 --verbose
"""

import argparse
import ast
import datetime
import json
import os
import sqlite3
import sys
import time
import glob
import re
import hashlib
from collections import defaultdict


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "cowork_gaps.db")
DEV_DIR = SCRIPT_DIR


def init_db(conn):
    """Initialize SQLite tables for deduplication tracking."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS dedup_scans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            scripts_scanned INTEGER,
            pairs_found INTEGER,
            max_similarity REAL,
            details TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS dedup_pairs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            script_a TEXT NOT NULL,
            script_b TEXT NOT NULL,
            similarity REAL NOT NULL,
            overlap_type TEXT,
            merge_suggestion TEXT
        )
    """)
    conn.commit()


def parse_script(filepath):
    """Parse a Python script and extract structural information."""
    info = {
        "name": os.path.basename(filepath),
        "path": filepath,
        "functions": [],
        "classes": [],
        "imports": [],
        "docstring": "",
        "constants": [],
        "ast_nodes": 0,
        "lines": 0,
        "parse_error": False
    }

    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            source = f.read()
        info["lines"] = source.count("\n") + 1
    except OSError:
        info["parse_error"] = True
        return info

    try:
        tree = ast.parse(source)
    except SyntaxError:
        info["parse_error"] = True
        return info

    info["docstring"] = ast.get_docstring(tree) or ""
    info["ast_nodes"] = sum(1 for _ in ast.walk(tree))

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
            info["functions"].append(node.name)
        elif isinstance(node, ast.ClassDef):
            info["classes"].append(node.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                info["imports"].append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                info["imports"].append(f"{module}.{alias.name}")
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id.isupper():
                    info["constants"].append(target.id)

    return info


def jaccard_similarity(set_a, set_b):
    """Compute Jaccard similarity between two sets."""
    if not set_a and not set_b:
        return 0.0
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union) if union else 0.0


def compute_similarity(info_a, info_b):
    """Compute overall similarity between two scripts."""
    scores = {}

    # Function name similarity
    funcs_a = set(info_a["functions"])
    funcs_b = set(info_b["functions"])
    # Exclude common names like main, run, init_db
    common_generic = {"main", "run", "init_db", "__init__", "parse_args"}
    funcs_a_filtered = funcs_a - common_generic
    funcs_b_filtered = funcs_b - common_generic
    scores["functions"] = jaccard_similarity(funcs_a_filtered, funcs_b_filtered)

    # Import similarity
    imports_a = set(info_a["imports"])
    imports_b = set(info_b["imports"])
    scores["imports"] = jaccard_similarity(imports_a, imports_b)

    # Docstring similarity (simple word overlap)
    words_a = set(re.findall(r'\w+', info_a["docstring"].lower()))
    words_b = set(re.findall(r'\w+', info_b["docstring"].lower()))
    scores["docstring"] = jaccard_similarity(words_a, words_b)

    # AST size similarity (structural)
    nodes_a = info_a["ast_nodes"]
    nodes_b = info_b["ast_nodes"]
    if max(nodes_a, nodes_b) > 0:
        scores["structure"] = min(nodes_a, nodes_b) / max(nodes_a, nodes_b)
    else:
        scores["structure"] = 0.0

    # Class name similarity
    classes_a = set(info_a["classes"])
    classes_b = set(info_b["classes"])
    scores["classes"] = jaccard_similarity(classes_a, classes_b)

    # Constants similarity
    consts_a = set(info_a["constants"])
    consts_b = set(info_b["constants"])
    scores["constants"] = jaccard_similarity(consts_a, consts_b)

    # Weighted average
    weights = {
        "functions": 3.0,
        "imports": 1.5,
        "docstring": 1.0,
        "structure": 1.0,
        "classes": 2.0,
        "constants": 1.0
    }
    total_weight = sum(weights.values())
    overall = sum(scores[k] * weights[k] for k in scores) / total_weight

    # Determine overlap type
    overlap_types = []
    if scores["functions"] > 0.5:
        overlap_types.append("functions")
    if scores["imports"] > 0.7:
        overlap_types.append("imports")
    if scores["docstring"] > 0.5:
        overlap_types.append("docstring")
    if scores["classes"] > 0.5:
        overlap_types.append("classes")

    return {
        "overall": round(overall * 100, 1),
        "scores": {k: round(v * 100, 1) for k, v in scores.items()},
        "overlap_types": overlap_types
    }


def suggest_merge(info_a, info_b, similarity):
    """Generate merge suggestion for a duplicate pair."""
    suggestions = []

    # Determine which is likely the "primary" (more functions, more lines)
    if len(info_a["functions"]) >= len(info_b["functions"]):
        primary, secondary = info_a, info_b
    else:
        primary, secondary = info_b, info_a

    if similarity["overall"] > 90:
        suggestions.append(
            f"STRONG DUPLICATE: Consider removing `{secondary['name']}` "
            f"and keeping `{primary['name']}` as the canonical version."
        )
    elif similarity["overall"] > 70:
        shared_funcs = set(info_a["functions"]) & set(info_b["functions"])
        if shared_funcs:
            suggestions.append(
                f"Extract shared functions ({', '.join(list(shared_funcs)[:5])}) "
                f"into a common module."
            )
        suggestions.append(
            f"Consider merging `{secondary['name']}` into `{primary['name']}` "
            f"or creating a shared base class."
        )
    else:
        suggestions.append(
            f"Partial overlap detected. Review shared imports/patterns "
            f"for potential refactoring."
        )

    return " | ".join(suggestions)


def run(args):
    """Main execution logic."""
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    init_db(conn)

    threshold = args.threshold

    if args.verbose:
        print(f"[dedup] Scanning scripts in {DEV_DIR} (threshold={threshold}%)")

    # Parse all scripts
    pattern = os.path.join(DEV_DIR, "*.py")
    scripts = []
    for filepath in sorted(glob.glob(pattern)):
        name = os.path.basename(filepath)
        if name.startswith("__"):
            continue
        info = parse_script(filepath)
        if not info["parse_error"]:
            scripts.append(info)
            if args.verbose:
                print(f"  Parsed: {name} ({len(info['functions'])} funcs, "
                      f"{len(info['imports'])} imports, {info['ast_nodes']} AST nodes)")
        else:
            if args.verbose:
                print(f"  SKIP (parse error): {name}")

    if args.verbose:
        print(f"[dedup] Parsed {len(scripts)} scripts, comparing pairs...")

    # Compare all pairs
    pairs = []
    now = datetime.datetime.now().isoformat()

    for i in range(len(scripts)):
        for j in range(i + 1, len(scripts)):
            sim = compute_similarity(scripts[i], scripts[j])
            if sim["overall"] >= threshold:
                merge_suggestion = suggest_merge(scripts[i], scripts[j], sim)
                pair = {
                    "script_a": scripts[i]["name"],
                    "script_b": scripts[j]["name"],
                    "similarity": sim["overall"],
                    "scores": sim["scores"],
                    "overlap_types": sim["overlap_types"],
                    "merge_suggestion": merge_suggestion
                }
                pairs.append(pair)

                # Save to DB
                conn.execute(
                    "INSERT INTO dedup_pairs (timestamp, script_a, script_b, similarity, overlap_type, merge_suggestion) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (now, pair["script_a"], pair["script_b"], pair["similarity"],
                     ",".join(sim["overlap_types"]), merge_suggestion)
                )

                if args.verbose:
                    print(f"  MATCH: {pair['script_a']} <-> {pair['script_b']} "
                          f"= {pair['similarity']}% [{','.join(sim['overlap_types']) or 'general'}]")

    # Sort by similarity descending
    pairs.sort(key=lambda p: p["similarity"], reverse=True)

    # Save scan record
    max_sim = pairs[0]["similarity"] if pairs else 0.0
    conn.execute(
        "INSERT INTO dedup_scans (timestamp, scripts_scanned, pairs_found, max_similarity, details) "
        "VALUES (?, ?, ?, ?, ?)",
        (now, len(scripts), len(pairs), max_sim,
         json.dumps({"threshold": threshold}))
    )
    conn.commit()
    conn.close()

    # JSON output
    result = {
        "timestamp": now,
        "scripts_scanned": len(scripts),
        "threshold_percent": threshold,
        "duplicate_pairs_found": len(pairs),
        "max_similarity": max_sim,
        "pairs": pairs
    }
    print(json.dumps(result, indent=2))
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Script Deduplication — Find and merge duplicate/overlapping scripts"
    )
    parser.add_argument("--once", action="store_true",
                        help="Run once and exit")
    parser.add_argument("--threshold", type=int, default=70,
                        help="Minimum similarity threshold in percent (default: 70)")
    parser.add_argument("--verbose", action="store_true",
                        help="Enable verbose output")
    args = parser.parse_args()

    if args.once:
        run(args)
    else:
        print("[dedup] Running in continuous mode (Ctrl+C to stop)")
        while True:
            try:
                run(args)
                time.sleep(300)
            except KeyboardInterrupt:
                print("\n[dedup] Stopped")
                break


if __name__ == "__main__":
    main()
