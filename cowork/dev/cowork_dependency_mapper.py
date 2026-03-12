#!/usr/bin/env python3
"""cowork_dependency_mapper.py — Maps dependencies between all COWORK scripts.

Scans all *.py in SCRIPT_DIR for:
  1. run_script() / run_analyzer() calls referencing other scripts
  2. subprocess.run() calls invoking other .py files
  3. Shared database tables (CREATE TABLE vs SELECT/INSERT/UPDATE/DELETE)
  4. Shared file paths (DATA_DIR references, .db file paths)

Stores results in cowork_gaps.db table `script_dependencies`.

Usage:
    python dev/cowork_dependency_mapper.py --once     # scan and map
    python dev/cowork_dependency_mapper.py --graph    # ASCII dependency tree
    python dev/cowork_dependency_mapper.py --stats    # dependency stats
"""
import argparse
import ast
import json
import re
import sqlite3
import time
from collections import defaultdict
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data"
DB_PATH = DATA_DIR / "cowork_gaps.db"


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

def init_db():
    """Initialize the database and create the script_dependencies table."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS script_dependencies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_script TEXT NOT NULL,
        target_script TEXT NOT NULL,
        dep_type TEXT NOT NULL,
        details TEXT,
        scanned_at REAL
    )""")
    db.commit()
    return db


def clear_deps(db):
    """Clear all previous dependency records before a fresh scan."""
    db.execute("DELETE FROM script_dependencies")
    db.commit()


def insert_dep(db, source, target, dep_type, details=""):
    """Insert a single dependency record."""
    db.execute(
        "INSERT INTO script_dependencies (source_script, target_script, dep_type, details, scanned_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (source, target, dep_type, details, time.time()),
    )


def load_deps(db):
    """Load all dependencies from the database."""
    rows = db.execute(
        "SELECT source_script, target_script, dep_type, details FROM script_dependencies"
    ).fetchall()
    return [
        {"source": r[0], "target": r[1], "dep_type": r[2], "details": r[3]}
        for r in rows
    ]


# ---------------------------------------------------------------------------
# AST-based scanners
# ---------------------------------------------------------------------------

def _read_source(path):
    """Read file source, return (source_text, ast_tree) or (source_text, None)."""
    try:
        src = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return "", None
    try:
        tree = ast.parse(src, filename=str(path))
    except SyntaxError:
        tree = None
    return src, tree


def _resolve_script_name(name_value):
    """Normalize a script name to a .py filename."""
    if not isinstance(name_value, str):
        return None
    name = name_value.strip().strip("'\"")
    if not name:
        return None
    if not name.endswith(".py"):
        name += ".py"
    return name


def scan_run_script_calls(src, tree, all_script_names):
    """Find run_script('name', ...) and run_analyzer('name', ...) calls."""
    deps = []
    if tree is None:
        return deps
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        fname = None
        if isinstance(func, ast.Name) and func.id in ("run_script", "run_analyzer"):
            fname = func.id
        elif isinstance(func, ast.Attribute) and func.attr in ("run_script", "run_analyzer"):
            fname = func.attr
        if fname and node.args:
            arg0 = node.args[0]
            if isinstance(arg0, ast.Constant) and isinstance(arg0.value, str):
                target = _resolve_script_name(arg0.value)
                if target:
                    deps.append((target, "calls", f"{fname}('{arg0.value}')"))
    return deps


def scan_subprocess_calls(src, tree, all_script_names):
    """Find subprocess.run([..., 'something.py', ...]) calls that reference .py files."""
    deps = []
    if tree is None:
        return deps
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        is_subprocess = False
        if isinstance(func, ast.Attribute) and func.attr == "run":
            if isinstance(func.value, ast.Name) and func.value.id == "subprocess":
                is_subprocess = True
            elif isinstance(func.value, ast.Attribute):
                is_subprocess = True
        if isinstance(func, ast.Attribute) and func.attr in ("Popen", "call", "check_output", "check_call"):
            is_subprocess = True
        if not is_subprocess:
            continue
        # Extract all string constants from the call arguments
        for child in ast.walk(node):
            if isinstance(child, ast.Constant) and isinstance(child.value, str):
                val = child.value
                if val.endswith(".py"):
                    basename = Path(val).name
                    if basename in all_script_names:
                        deps.append((basename, "calls", f"subprocess({val})"))
    return deps


def scan_create_tables(src):
    """Find CREATE TABLE IF NOT EXISTS <name> patterns."""
    tables = set()
    pattern = re.compile(r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)", re.IGNORECASE)
    for m in pattern.finditer(src):
        tables.add(m.group(1).lower())
    return tables


def scan_table_references(src):
    """Find SELECT/INSERT/UPDATE/DELETE ... FROM/INTO <table> patterns."""
    tables = set()
    patterns = [
        re.compile(r"\bFROM\s+(\w+)", re.IGNORECASE),
        re.compile(r"\bINTO\s+(\w+)", re.IGNORECASE),
        re.compile(r"\bUPDATE\s+(\w+)", re.IGNORECASE),
        re.compile(r"\bJOIN\s+(\w+)", re.IGNORECASE),
    ]
    skip = {"select", "set", "table", "values", "where", "and", "or", "not",
            "null", "exists", "if", "replace", "ignore", "distinct"}
    for pat in patterns:
        for m in pat.finditer(src):
            tbl = m.group(1).lower()
            if tbl not in skip and not tbl.startswith("("):
                tables.add(tbl)
    return tables


def scan_db_paths(src):
    """Find explicit .db file references in source."""
    dbs = set()
    pattern = re.compile(r"""['"]([^'"]*\.db)['"]""")
    for m in pattern.finditer(src):
        dbs.add(m.group(1))
    return dbs


def scan_data_dir_refs(src):
    """Find DATA_DIR / 'filename' or os.path.join(DATA_DIR, 'filename') references."""
    files = set()
    # Pathlib style: DATA_DIR / "something"
    pat1 = re.compile(r"""DATA_DIR\s*/\s*['"]([^'"]+)['"]""")
    for m in pat1.finditer(src):
        files.add(m.group(1))
    # os.path.join style
    pat2 = re.compile(r"""os\.path\.join\(\s*DATA_DIR\s*,\s*['"]([^'"]+)['"]""")
    for m in pat2.finditer(src):
        files.add(m.group(1))
    return files


# ---------------------------------------------------------------------------
# Main scan orchestration
# ---------------------------------------------------------------------------

def scan_all():
    """Scan all scripts and return structured dependency data."""
    scripts = sorted(SCRIPT_DIR.glob("*.py"))
    all_script_names = {s.name for s in scripts}

    # Per-script data
    script_creates = {}   # script -> set of tables created
    script_queries = {}   # script -> set of tables queried
    script_db_paths = {}  # script -> set of .db paths
    script_data_files = {}  # script -> set of DATA_DIR files
    all_deps = []         # (source, target, dep_type, details)

    for sp in scripts:
        name = sp.name
        src, tree = _read_source(sp)

        # 1. run_script / run_analyzer calls
        for target, dtype, detail in scan_run_script_calls(src, tree, all_script_names):
            all_deps.append((name, target, dtype, detail))

        # 2. subprocess calls
        for target, dtype, detail in scan_subprocess_calls(src, tree, all_script_names):
            if target != name:  # skip self-references
                all_deps.append((name, target, dtype, detail))

        # 3. Table tracking
        created = scan_create_tables(src)
        queried = scan_table_references(src)
        script_creates[name] = created
        script_queries[name] = queried

        # 4. File path tracking
        script_db_paths[name] = scan_db_paths(src)
        script_data_files[name] = scan_data_dir_refs(src)

    # Build table -> creators/users maps
    table_creators = defaultdict(set)
    table_users = defaultdict(set)
    for sname, tables in script_creates.items():
        for t in tables:
            table_creators[t].add(sname)
    for sname, tables in script_queries.items():
        for t in tables:
            table_users[t].add(sname)

    # Generate table-based dependencies:
    # If script A creates table T and script B queries T, then B depends on A
    all_tables = set(table_creators.keys()) | set(table_users.keys())
    for tbl in all_tables:
        creators = table_creators.get(tbl, set())
        users = table_users.get(tbl, set())
        for creator in creators:
            for user in users:
                if user != creator:
                    all_deps.append((user, creator, "reads_table", f"table:{tbl}"))
            # Also mark the creator as writes_table
            all_deps.append((creator, creator, "writes_table", f"table:{tbl}"))

    # Generate shared-file dependencies:
    # If multiple scripts reference the same DATA_DIR file, they share it
    file_users = defaultdict(set)
    for sname, files in script_data_files.items():
        for f in files:
            file_users[f].add(sname)
    for sname, dbs in script_db_paths.items():
        for db in dbs:
            file_users[db].add(sname)

    for fpath, users in file_users.items():
        users_list = sorted(users)
        if len(users_list) > 1:
            for u in users_list:
                for other in users_list:
                    if u != other:
                        all_deps.append((u, other, "shares_file", f"file:{fpath}"))

    # Deduplicate
    seen = set()
    unique_deps = []
    for d in all_deps:
        key = (d[0], d[1], d[2], d[3])
        if key not in seen:
            seen.add(key)
            unique_deps.append(d)

    # Remove self-referencing writes_table (only keep for stats)
    final_deps = [d for d in unique_deps if not (d[0] == d[1] and d[2] == "writes_table")]
    writes_table_deps = [d for d in unique_deps if d[2] == "writes_table"]

    return {
        "scripts": sorted(all_script_names),
        "deps": final_deps,
        "writes_table": writes_table_deps,
        "table_creators": {k: sorted(v) for k, v in table_creators.items()},
        "table_users": {k: sorted(v) for k, v in table_users.items()},
        "file_users": {k: sorted(v) for k, v in file_users.items()},
    }


# ---------------------------------------------------------------------------
# --once: scan, store, output JSON
# ---------------------------------------------------------------------------

def cmd_once():
    """Scan all scripts, store in DB, output JSON report."""
    db = init_db()
    clear_deps(db)
    data = scan_all()

    # Store deps
    for source, target, dep_type, details in data["deps"]:
        insert_dep(db, source, target, dep_type, details)
    # Store writes_table separately
    for source, target, dep_type, details in data["writes_table"]:
        insert_dep(db, source, target, dep_type, details)
    db.commit()

    # Build graphs
    dep_graph = defaultdict(set)
    rev_graph = defaultdict(set)
    for source, target, dep_type, details in data["deps"]:
        dep_graph[source].add(target)
        rev_graph[target].add(source)

    # Hub scripts: most connections in both directions
    connection_counts = defaultdict(int)
    for s in data["scripts"]:
        connection_counts[s] = len(dep_graph.get(s, set())) + len(rev_graph.get(s, set()))
    hub_scripts = sorted(connection_counts.items(), key=lambda x: -x[1])[:20]
    hub_scripts = [{"script": h[0], "connections": h[1]} for h in hub_scripts if h[1] > 0]

    # Isolated scripts
    connected = set(dep_graph.keys()) | set(rev_graph.keys())
    # Also include self-referencing writes_table scripts
    for source, target, dep_type, details in data["writes_table"]:
        connected.add(source)
    isolated = sorted(set(data["scripts"]) - connected)

    # Shared tables summary
    shared_tables = {}
    all_tables = set(data["table_creators"].keys()) | set(data["table_users"].keys())
    for tbl in sorted(all_tables):
        shared_tables[tbl] = {
            "created_by": data["table_creators"].get(tbl, []),
            "used_by": data["table_users"].get(tbl, []),
        }

    report = {
        "total_scripts": len(data["scripts"]),
        "total_dependencies": len(data["deps"]),
        "dependency_graph": {k: sorted(v) for k, v in dep_graph.items()},
        "reverse_graph": {k: sorted(v) for k, v in rev_graph.items()},
        "hub_scripts": hub_scripts,
        "isolated_scripts": isolated,
        "shared_tables": shared_tables,
        "shared_files": {k: v for k, v in data["file_users"].items() if len(v) > 1},
    }

    print(json.dumps(report, indent=2, ensure_ascii=False))
    db.close()
    return report


# ---------------------------------------------------------------------------
# --graph: ASCII dependency tree of top 20 most-connected scripts
# ---------------------------------------------------------------------------

def cmd_graph():
    """Show ASCII dependency tree of top 20 most-connected scripts."""
    db = init_db()
    deps = load_deps(db)
    db.close()

    if not deps:
        print("No dependencies found. Run --once first.")
        return

    # Build graphs
    dep_graph = defaultdict(set)
    rev_graph = defaultdict(set)
    for d in deps:
        if d["dep_type"] == "writes_table" and d["source"] == d["target"]:
            continue
        dep_graph[d["source"]].add(d["target"])
        rev_graph[d["target"]].add(d["source"])

    # Rank by total connections
    all_scripts = set(dep_graph.keys()) | set(rev_graph.keys())
    ranked = sorted(all_scripts, key=lambda s: len(dep_graph.get(s, set())) + len(rev_graph.get(s, set())), reverse=True)
    top20 = ranked[:20]

    # Print header
    print("=" * 70)
    print("  COWORK DEPENDENCY GRAPH — Top 20 Most-Connected Scripts")
    print("=" * 70)
    print()

    for script in top20:
        outgoing = sorted(dep_graph.get(script, set()))
        incoming = sorted(rev_graph.get(script, set()))
        total = len(outgoing) + len(incoming)
        short = script.replace(".py", "")

        print(f"  [{total:3d}] {short}")

        if outgoing:
            for i, dep in enumerate(outgoing):
                connector = "`-->" if i == len(outgoing) - 1 and not incoming else "|-->"
                print(f"        {connector} {dep.replace('.py', '')}")

        if incoming:
            for i, dep in enumerate(incoming):
                connector = "`<--" if i == len(incoming) - 1 else "|<--"
                print(f"        {connector} {dep.replace('.py', '')}")

        print()

    # Legend
    print("-" * 70)
    print("  --> = depends on (outgoing)    <-- = depended by (incoming)")
    print(f"  Total scripts with dependencies: {len(all_scripts)}")
    print("=" * 70)


# ---------------------------------------------------------------------------
# --stats: counts by dependency type
# ---------------------------------------------------------------------------

def cmd_stats():
    """Output dependency counts by type."""
    db = init_db()
    deps = load_deps(db)
    db.close()

    if not deps:
        print("No dependencies found. Run --once first.")
        return

    # Count by type
    by_type = defaultdict(int)
    for d in deps:
        by_type[d["dep_type"]] += 1

    # Count by source
    by_source = defaultdict(int)
    for d in deps:
        by_source[d["source"]] += 1

    # Count by target
    by_target = defaultdict(int)
    for d in deps:
        by_target[d["target"]] += 1

    # Unique scripts
    all_sources = set(d["source"] for d in deps)
    all_targets = set(d["target"] for d in deps)
    all_scripts = all_sources | all_targets

    print("=" * 60)
    print("  COWORK DEPENDENCY STATS")
    print("=" * 60)
    print()

    print("  Dependencies by type:")
    print("  " + "-" * 40)
    for dtype, count in sorted(by_type.items(), key=lambda x: -x[1]):
        bar = "#" * min(count, 40)
        print(f"    {dtype:<15s} {count:5d}  {bar}")
    print(f"    {'TOTAL':<15s} {sum(by_type.values()):5d}")
    print()

    print("  Top 15 scripts with most outgoing dependencies:")
    print("  " + "-" * 40)
    top_sources = sorted(by_source.items(), key=lambda x: -x[1])[:15]
    for script, count in top_sources:
        bar = "#" * min(count, 30)
        print(f"    {script:<45s} {count:3d}  {bar}")
    print()

    print("  Top 15 scripts most depended upon (incoming):")
    print("  " + "-" * 40)
    top_targets = sorted(by_target.items(), key=lambda x: -x[1])[:15]
    for script, count in top_targets:
        bar = "#" * min(count, 30)
        print(f"    {script:<45s} {count:3d}  {bar}")
    print()

    print(f"  Unique scripts involved: {len(all_scripts)}")
    print(f"  Scripts as dependency source: {len(all_sources)}")
    print(f"  Scripts as dependency target: {len(all_targets)}")
    print("=" * 60)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Map dependencies between COWORK scripts"
    )
    parser.add_argument("--once", action="store_true", help="Scan all scripts and map dependencies (JSON output)")
    parser.add_argument("--graph", action="store_true", help="Show ASCII dependency graph of top 20 scripts")
    parser.add_argument("--stats", action="store_true", help="Show dependency statistics by type")
    args = parser.parse_args()

    if not any([args.once, args.graph, args.stats]):
        parser.print_help()
        return

    if args.once:
        cmd_once()
    if args.graph:
        cmd_graph()
    if args.stats:
        cmd_stats()


if __name__ == "__main__":
    main()
