"""
Auto-Documentation Updater for COWORK scripts.

Scans all Python scripts in the COWORK dev directory, analyzes their
documentation completeness using the ast module, and stores results
in cowork_gaps.db. Provides CLI modes for one-shot scanning, finding
undocumented scripts, and showing coverage statistics.

Usage:
    python auto_documentation_updater.py --once
    python auto_documentation_updater.py --missing
    python auto_documentation_updater.py --stats
"""

import argparse
import ast
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DB_PATH = SCRIPT_DIR / "cowork_gaps.db"


def init_db(conn):
    """Create the script_documentation table if it does not exist."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS script_documentation (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            script_name TEXT NOT NULL,
            has_docstring INTEGER NOT NULL DEFAULT 0,
            func_count INTEGER NOT NULL DEFAULT 0,
            documented_funcs INTEGER NOT NULL DEFAULT 0,
            cli_args TEXT NOT NULL DEFAULT '[]',
            doc_score INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_script_doc_name
        ON script_documentation (script_name)
    """)
    conn.commit()


def extract_argparse_args(tree):
    """
    Walk the AST looking for calls to add_argument on argparse parsers.
    Returns a list of argument name strings.
    """
    args_found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        is_add_argument = (
            isinstance(func, ast.Attribute) and func.attr == "add_argument"
        )
        if not is_add_argument:
            continue
        for arg in node.args:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                args_found.append(arg.value)
    return args_found


def compute_doc_score(info):
    """
    Compute a documentation completeness score from 0 to 100.

    Breakdown (weights):
        - Module docstring present:          30 points
        - Function documentation ratio:      40 points (proportional)
        - CLI args documented (if any exist): 15 points
        - Has at least one class or func:     15 points (structural completeness)
    """
    score = 0.0

    if info["has_docstring"]:
        score += 30.0

    if info["func_count"] > 0:
        ratio = info["documented_funcs"] / info["func_count"]
        score += 40.0 * ratio
    else:
        if info["has_docstring"]:
            score += 20.0

    if len(info["cli_args"]) > 0:
        score += 15.0
    else:
        score += 7.5

    if info["func_count"] > 0 or info["class_count"] > 0:
        score += 15.0
    else:
        score += 5.0

    return min(100, max(0, int(round(score))))

def analyze_script(script_path):
    """
    Parse a single Python script and return documentation metrics.

    Returns a dict with:
        script_name, has_docstring, func_count, documented_funcs,
        class_count, cli_args, doc_score
    """
    source = script_path.read_text(encoding="utf-8", errors="replace")
    result = {
        "script_name": script_path.name,
        "has_docstring": False,
        "func_count": 0,
        "documented_funcs": 0,
        "class_count": 0,
        "cli_args": [],
        "doc_score": 0,
    }

    try:
        tree = ast.parse(source, filename=str(script_path))
    except SyntaxError:
        return result

    module_docstring = ast.get_docstring(tree)
    result["has_docstring"] = (
        module_docstring is not None and len(module_docstring.strip()) > 0
    )

    functions = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            doc = ast.get_docstring(node)
            functions.append({
                "name": node.name,
                "has_docstring": doc is not None and len(doc.strip()) > 0,
            })
        elif isinstance(node, ast.ClassDef):
            result["class_count"] += 1

    result["func_count"] = len(functions)
    result["documented_funcs"] = sum(1 for f in functions if f["has_docstring"])

    result["cli_args"] = extract_argparse_args(tree)
    result["doc_score"] = compute_doc_score(result)

    return result


def store_results(conn, results):
    """Insert analysis results into the database, replacing old entries for same scripts."""
    now = datetime.now(timezone.utc).isoformat()

    for r in results:
        conn.execute(
            "DELETE FROM script_documentation WHERE script_name = ?",
            (r["script_name"],),
        )
        conn.execute(
            """INSERT INTO script_documentation
               (timestamp, script_name, has_docstring, func_count,
                documented_funcs, cli_args, doc_score)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                now,
                r["script_name"],
                1 if r["has_docstring"] else 0,
                r["func_count"],
                r["documented_funcs"],
                json.dumps(r["cli_args"]),
                r["doc_score"],
            ),
        )
    conn.commit()


def scan_all_scripts():
    """Scan all *.py files in SCRIPT_DIR and return analysis results."""
    results = []
    for py_file in sorted(SCRIPT_DIR.glob("*.py")):
        if py_file.name == Path(__file__).name:
            continue
        info = analyze_script(py_file)
        results.append(info)
    return results


def _ensure_data(conn):
    """If DB is empty, run a scan first."""
    count = conn.execute("SELECT COUNT(*) FROM script_documentation").fetchone()[0]
    if count == 0:
        print("[INFO] No data in DB. Running scan first...", file=sys.stderr)
        results = scan_all_scripts()
        store_results(conn, results)

def cmd_once(conn):
    """Scan all scripts, store results, and output a JSON summary."""
    results = scan_all_scripts()
    store_results(conn, results)

    total = len(results)
    if total == 0:
        report = {
            "total_scripts": 0,
            "avg_doc_score": 0,
            "fully_documented": 0,
            "partially_documented": 0,
            "undocumented": 0,
            "worst_documented": [],
        }
        print(json.dumps(report, indent=2))
        return

    scores = [r["doc_score"] for r in results]
    avg_score = sum(scores) / total

    fully = sum(1 for s in scores if s >= 80)
    partial = sum(1 for s in scores if 30 <= s < 80)
    undoc = sum(1 for s in scores if s < 30)

    # Bottom 10 by score
    sorted_results = sorted(results, key=lambda r: r["doc_score"])
    worst = []
    for r in sorted_results[:10]:
        worst.append({
            "script": r["script_name"],
            "doc_score": r["doc_score"],
            "has_docstring": r["has_docstring"],
            "functions": r["func_count"],
            "documented_functions": r["documented_funcs"],
        })

    report = {
        "total_scripts": total,
        "avg_doc_score": round(avg_score, 1),
        "fully_documented": fully,
        "partially_documented": partial,
        "undocumented": undoc,
        "worst_documented": worst,
    }
    print(json.dumps(report, indent=2))

def cmd_missing(conn):
    """Show scripts with doc_score < 50 from the database."""
    _ensure_data(conn)

    rows = conn.execute(
        """SELECT script_name, doc_score, has_docstring, func_count, documented_funcs
           FROM script_documentation
           WHERE doc_score < 50
           ORDER BY doc_score ASC"""
    ).fetchall()

    if not rows:
        print("All scripts have doc_score >= 50. No undocumented scripts found.")
        return

    print("{:<45} {:>5}  {:>6}  {:>5}  {:>10}".format(
        "Script", "Score", "Docstr", "Funcs", "Documented"))
    print("-" * 80)
    for name, score, has_doc, func_count, doc_funcs in rows:
        docstr = "Yes" if has_doc else "No"
        print("{:<45} {:>5}  {:>6}  {:>5}  {:>10}".format(
            name, score, docstr, func_count, doc_funcs))

    print("")
    print("Total underdocumented scripts (score < 50): {}".format(len(rows)))

def cmd_stats(conn):
    """Show overall documentation coverage statistics."""
    _ensure_data(conn)

    rows = conn.execute(
        """SELECT script_name, doc_score, has_docstring, func_count, documented_funcs
           FROM script_documentation
           ORDER BY doc_score DESC"""
    ).fetchall()

    if not rows:
        print("No scripts found.")
        return

    total = len(rows)
    scores = [r[1] for r in rows]
    avg = sum(scores) / total
    with_docstring = sum(1 for r in rows if r[2])
    total_funcs = sum(r[3] for r in rows)
    total_doc_funcs = sum(r[4] for r in rows)

    fully = sum(1 for s in scores if s >= 80)
    partial = sum(1 for s in scores if 30 <= s < 80)
    undoc = sum(1 for s in scores if s < 30)

    func_coverage = (total_doc_funcs / total_funcs * 100) if total_funcs > 0 else 0
    docstring_coverage = (with_docstring / total * 100) if total > 0 else 0

    print("=" * 60)
    print("  COWORK Documentation Coverage Report")
    print("=" * 60)
    print("  Total scripts scanned:      {}".format(total))
    print("  Average doc score:           {:.1f}/100".format(avg))
    print()
    print("  Fully documented (>=80):     {0:>4}  ({1:.0f}%)".format(
        fully, fully / total * 100))
    print("  Partially documented (30-79):{0:>4}  ({1:.0f}%)".format(
        partial, partial / total * 100))
    print("  Undocumented (<30):          {0:>4}  ({1:.0f}%)".format(
        undoc, undoc / total * 100))
    print()
    print("  Module docstring coverage:   {0:.1f}%  ({1}/{2})".format(
        docstring_coverage, with_docstring, total))
    print("  Function docstring coverage: {0:.1f}%  ({1}/{2})".format(
        func_coverage, total_doc_funcs, total_funcs))
    print()

    # Score distribution histogram
    buckets = {"0-19": 0, "20-39": 0, "40-59": 0, "60-79": 0, "80-100": 0}
    for s in scores:
        if s < 20:
            buckets["0-19"] += 1
        elif s < 40:
            buckets["20-39"] += 1
        elif s < 60:
            buckets["40-59"] += 1
        elif s < 80:
            buckets["60-79"] += 1
        else:
            buckets["80-100"] += 1

    print("  Score Distribution:")
    max_bar = max(buckets.values()) if buckets.values() else 1
    for label, count in buckets.items():
        bar_len = int(count / max(max_bar, 1) * 30)
        bar = "#" * bar_len
        print("    {0:>6}: {1:<30} {2}".format(label, bar, count))

    print("=" * 60)

    ts = conn.execute(
        "SELECT MAX(timestamp) FROM script_documentation"
    ).fetchone()[0]
    if ts:
        print("  Last scan: {}".format(ts))

def main():
    parser = argparse.ArgumentParser(
        description="Auto-Documentation Updater for COWORK scripts"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--once",
        action="store_true",
        help="Scan all scripts and output JSON documentation report",
    )
    group.add_argument(
        "--missing",
        action="store_true",
        help="Show scripts with documentation score below 50",
    )
    group.add_argument(
        "--stats",
        action="store_true",
        help="Show overall documentation coverage statistics",
    )

    args = parser.parse_args()

    conn = sqlite3.connect(str(DB_PATH))
    try:
        init_db(conn)

        if args.once:
            cmd_once(conn)
        elif args.missing:
            cmd_missing(conn)
        elif args.stats:
            cmd_stats(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
