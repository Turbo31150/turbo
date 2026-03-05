#!/usr/bin/env python3
"""JARVIS Self-Evolve — Autonomous self-improvement through code generation.

Analyzes JARVIS codebase, identifies improvement opportunities,
generates code via cluster, validates, and prepares patches.
"""
import argparse
import json
import sqlite3
import time
import ast
import urllib.request
from pathlib import Path

DB_PATH = Path(__file__).parent / "self_evolve.db"
TURBO = Path("F:/BUREAU/turbo")
SRC = TURBO / "src"

def init_db():
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS improvements (
        id INTEGER PRIMARY KEY, ts REAL, file TEXT, line INTEGER DEFAULT 0,
        category TEXT, description TEXT, generated_code TEXT,
        validated INTEGER DEFAULT 0, applied INTEGER DEFAULT 0,
        cluster_node TEXT)""")
    db.execute("""CREATE TABLE IF NOT EXISTS analysis_runs (
        id INTEGER PRIMARY KEY, ts REAL, files_analyzed INTEGER,
        opportunities_found INTEGER, code_generated INTEGER)""")
    db.commit()
    return db

def analyze_file(filepath):
    """Analyze a Python file for improvement opportunities."""
    opportunities = []
    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(content)
    except (SyntaxError, UnicodeDecodeError):
        return opportunities

    rel = str(filepath.relative_to(TURBO))
    lines = content.splitlines()

    for node in ast.walk(tree):
        # Functions without docstrings
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not (node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant)):
                if not node.name.startswith("_"):
                    opportunities.append({
                        "file": rel, "line": node.lineno,
                        "category": "docstring",
                        "description": f"Fonction {node.name}() sans docstring",
                    })

        # Bare except clauses
        if isinstance(node, ast.ExceptHandler):
            if node.type is None:
                opportunities.append({
                    "file": rel, "line": node.lineno,
                    "category": "error_handling",
                    "description": f"Bare except (trop large)",
                })

        # Long functions (>50 lines)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            end_line = getattr(node, "end_lineno", node.lineno + 50)
            length = end_line - node.lineno
            if length > 50:
                opportunities.append({
                    "file": rel, "line": node.lineno,
                    "category": "complexity",
                    "description": f"Fonction {node.name}() trop longue ({length} lignes)",
                })

    # Check for /FIXME in source
    for i, line in enumerate(lines, 1):
        if "# " in line or "# FIXME" in line:
            comment = line.strip()
            opportunities.append({
                "file": rel, "line": i,
                "category": "",
                "description": comment[:100],
            })

    return opportunities

def scan_codebase(db):
    """Scan entire codebase for improvement opportunities."""
    all_opps = []
    files_analyzed = 0
    for py_file in SRC.rglob("*.py"):
        files_analyzed += 1
        opps = analyze_file(py_file)
        all_opps.extend(opps)

    # Store in DB
    for opp in all_opps[:50]:  # Limit to top 50
        existing = db.execute(
            "SELECT id FROM improvements WHERE file=? AND line=? AND category=?",
            (opp.get("file", ""), opp.get("line", 0), opp["category"])).fetchone()
        if not existing:
            db.execute(
                "INSERT INTO improvements (ts, file, category, description) VALUES (?,?,?,?)",
                (time.time(), opp.get("file", ""), opp["category"], opp["description"]))

    db.execute(
        "INSERT INTO analysis_runs (ts, files_analyzed, opportunities_found, code_generated) VALUES (?,?,?,?)",
        (time.time(), files_analyzed, len(all_opps), 0))
    db.commit()
    return files_analyzed, all_opps

def generate_improvement(db, improvement_id):
    """Generate code improvement via cluster."""
    row = db.execute(
        "SELECT file, category, description FROM improvements WHERE id=? AND validated=0",
        (improvement_id,)).fetchone()
    if not row:
        return None

    filepath, category, description = row
    prompt = f"/nothink\nDans {filepath}: {description}. Genere UNIQUEMENT le code Python ameliore (pas d'explication)."

    try:
        body = json.dumps({
            "model": "qwen3-8b", "input": prompt,
            "temperature": 0.2, "max_output_tokens": 1024, "stream": False, "store": False,
        }).encode()
        req = urllib.request.Request(
            "http://127.0.0.1:1234/api/v1/chat",
            data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            text = ""
            for item in reversed(data.get("output", [])):
                if item.get("type") == "message":
                    text = item.get("content", [{}])[0].get("text", "")
                    break

        if text:
            # Validate generated code
            try:
                ast.parse(text)
                valid = True
            except SyntaxError:
                valid = False

            db.execute(
                "UPDATE improvements SET generated_code=?, validated=?, cluster_node='M1' WHERE id=?",
                (text[:5000], 1 if valid else 0, improvement_id))
            db.commit()
            return {"valid": valid, "code": text[:500]}
    except Exception as e:
        return {"valid": False, "error": str(e)}
    return None

def get_summary(db):
    """Get evolution summary."""
    total = db.execute("SELECT COUNT(*) FROM improvements").fetchone()[0]
    by_cat = db.execute(
        "SELECT category, COUNT(*) FROM improvements GROUP BY category ORDER BY COUNT(*) DESC"
    ).fetchall()
    validated = db.execute("SELECT COUNT(*) FROM improvements WHERE validated=1").fetchone()[0]
    return {"total": total, "validated": validated, "by_category": dict(by_cat)}

def main():
    parser = argparse.ArgumentParser(description="JARVIS Self-Evolve")
    parser.add_argument("--scan", action="store_true", help="Scan codebase")
    parser.add_argument("--generate", type=int, help="Generate improvement for ID")
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--interval", type=int, default=3600)
    args = parser.parse_args()

    db = init_db()

    if args.summary:
        s = get_summary(db)
        print(f"=== Self-Evolve Summary ===")
        print(f"  Total opportunities: {s['total']}")
        print(f"  Validated: {s['validated']}")
        for cat, cnt in s["by_category"].items():
            print(f"  {cat}: {cnt}")
        return

    if args.generate:
        result = generate_improvement(db, args.generate)
        if result:
            print(f"Valid: {result.get('valid')}")
            print(result.get("code", result.get("error", ""))[:300])
        return

    if args.scan or args.once:
        files, opps = scan_codebase(db)
        print(f"=== Self-Evolve Scan ===")
        print(f"  Files: {files} | Opportunities: {len(opps)}")
        by_cat = {}
        for o in opps:
            by_cat[o["category"]] = by_cat.get(o["category"], 0) + 1
        for cat, cnt in sorted(by_cat.items(), key=lambda x: -x[1]):
            print(f"  {cat}: {cnt}")

    if args.loop:
        while True:
            try:
                files, opps = scan_codebase(db)
                ts = time.strftime('%H:%M')
                print(f"[{ts}] Scanned {files} files, {len(opps)} opportunities")
                # Auto-generate for top 3 improvements
                pending = db.execute(
                    "SELECT id FROM improvements WHERE validated=0 AND generated_code IS NULL ORDER BY ts DESC LIMIT 3"
                ).fetchall()
                for (imp_id,) in pending:
                    generate_improvement(db, imp_id)
                time.sleep(args.interval)
            except KeyboardInterrupt:
                break

if __name__ == "__main__":
    main()
