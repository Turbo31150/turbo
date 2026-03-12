#!/usr/bin/env python3
"""self_feeding_engine.py — Moteur d'auto-alimentation IA.

JARVIS analyse son propre code, cherche des ameliorations,
interroge le cluster IA, et genere des patches automatiques.
Se nourrit de son historique pour devenir plus intelligent.

Usage:
    python dev/self_feeding_engine.py --analyze              # Analyser tout le code
    python dev/self_feeding_engine.py --improve FILE         # Ameliorer un fichier
    python dev/self_feeding_engine.py --generate "desc"      # Generer un nouveau script
    python dev/self_feeding_engine.py --review               # Review automatique
    python dev/self_feeding_engine.py --metrics              # Metriques d'evolution
    python dev/self_feeding_engine.py --feed                 # Cycle complet d'alimentation
    python dev/self_feeding_engine.py --once                 # Un cycle
"""
import argparse
import ast
import json
import os
import sqlite3
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "self_feed.db"
CLUSTER_URL_M1 = "http://127.0.0.1:1234/api/v1/chat"
CLUSTER_URL_OL1 = "http://127.0.0.1:11434/api/chat"

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS analyses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, file TEXT, lines INTEGER, functions INTEGER,
        classes INTEGER, complexity_score REAL, issues TEXT,
        suggestions TEXT)""")
    db.execute("""CREATE TABLE IF NOT EXISTS improvements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, file TEXT, description TEXT,
        patch TEXT, source TEXT, applied INTEGER DEFAULT 0,
        validated INTEGER DEFAULT 0)""")
    db.execute("""CREATE TABLE IF NOT EXISTS generations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, description TEXT, filename TEXT,
        code TEXT, tested INTEGER DEFAULT 0,
        deployed INTEGER DEFAULT 0, cluster_node TEXT)""")
    db.execute("""CREATE TABLE IF NOT EXISTS feed_cycles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, files_analyzed INTEGER,
        issues_found INTEGER, improvements_generated INTEGER,
        improvements_applied INTEGER, duration_s REAL)""")
    db.commit()
    return db

# ---------------------------------------------------------------------------
# Code Analysis
# ---------------------------------------------------------------------------
def analyze_file(filepath: Path) -> dict:
    """Analyse statique d'un fichier Python."""
    try:
        code = filepath.read_text(encoding="utf-8", errors="ignore")
    except:
        return {"error": f"Cannot read {filepath}"}

    lines = code.split("\n")
    result = {
        "file": filepath.name,
        "path": str(filepath),
        "lines": len(lines),
        "blank_lines": sum(1 for l in lines if not l.strip()),
        "comment_lines": sum(1 for l in lines if l.strip().startswith("#")),
        "functions": 0,
        "classes": 0,
        "imports": 0,
        "complexity_score": 0,
        "issues": [],
        "suggestions": [],
    }

    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                result["functions"] += 1
                # Check function length
                end = getattr(node, "end_lineno", node.lineno + 20)
                func_lines = end - node.lineno
                if func_lines > 50:
                    result["issues"].append(f"Fonction '{node.name}' trop longue ({func_lines} lignes)")
                # Check missing docstring
                if not (node.body and isinstance(node.body[0], ast.Expr)
                        and isinstance(node.body[0].value, (ast.Constant, ast.Str))):
                    result["suggestions"].append(f"Ajouter docstring a '{node.name}'")
            elif isinstance(node, ast.ClassDef):
                result["classes"] += 1
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                result["imports"] += 1
    except SyntaxError as e:
        result["issues"].append(f"Erreur de syntaxe: {e}")

    # Complexity heuristic
    nested_depth = 0
    max_depth = 0
    for line in lines:
        stripped = line.lstrip()
        indent = len(line) - len(stripped)
        depth = indent // 4
        max_depth = max(max_depth, depth)

    result["max_indent_depth"] = max_depth
    result["complexity_score"] = round(
        (result["functions"] * 2 + result["classes"] * 3 + max_depth * 5 + len(result["issues"]) * 10) / max(result["lines"], 1) * 100, 1
    )

    # Check for common issues
    if "import *" in code:
        result["issues"].append("Utilise 'import *' — preferer imports explicites")
    if "except:" in code and "except Exception" not in code:
        result["issues"].append("'except:' nu — attrape tout, utiliser 'except Exception'")
    if "eval(" in code:
        result["issues"].append("Utilise eval() — risque de securite")
    if "os.system(" in code:
        result["issues"].append("Utilise os.system() — preferer subprocess.run()")
    if result["lines"] > 500 and result["functions"] < 5:
        result["suggestions"].append("Fichier long avec peu de fonctions — decomposer")

    return result

def analyze_workspace(dev_path: Path = DEV) -> list:
    """Analyse tous les fichiers Python du workspace."""
    results = []
    for f in sorted(dev_path.glob("*.py")):
        if f.name.startswith("__"):
            continue
        r = analyze_file(f)
        results.append(r)
    return results

# ---------------------------------------------------------------------------
# Cluster AI interaction
# ---------------------------------------------------------------------------
def ask_cluster(prompt: str, node: str = "M1") -> dict:
    """Interroge un noeud du cluster."""
    try:
        if node == "M1":
            data = json.dumps({
                "model": "qwen3-8b",
                "input": f"/nothink\n{prompt}",
                "temperature": 0.2,
                "max_output_tokens": 2048,
                "stream": False,
                "store": False,
            }).encode()
            req = urllib.request.Request(CLUSTER_URL_M1, data=data,
                                         headers={"Content-Type": "application/json"})
        else:  # OL1
            data = json.dumps({
                "model": "qwen3:1.7b",
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
            }).encode()
            req = urllib.request.Request(CLUSTER_URL_OL1, data=data,
                                         headers={"Content-Type": "application/json"})

        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode())
            if node == "M1":
                # Extract last message block from output
                for block in reversed(result.get("output", [])):
                    if block.get("type") == "message":
                        return {"content": block.get("content", [{}])[0].get("text", ""), "node": node}
                return {"content": str(result.get("output", "")), "node": node}
            else:
                return {"content": result.get("message", {}).get("content", ""), "node": node}
    except Exception as e:
        return {"error": str(e), "node": node}

def generate_improvement(filepath: Path, analysis: dict) -> dict:
    """Genere une amelioration via le cluster IA."""
    code = filepath.read_text(encoding="utf-8", errors="ignore")[:3000]
    issues = analysis.get("issues", [])
    suggestions = analysis.get("suggestions", [])

    if not issues and not suggestions:
        return {"skip": True, "reason": "Pas de problemes detectes"}

    prompt = f"""Analyse ce script Python et propose UNE amelioration concrete.

Fichier: {filepath.name}
Issues: {json.dumps(issues)}
Suggestions: {json.dumps(suggestions)}

Code (debut):
```python
{code[:2000]}
```

Reponds en JSON: {{"description": "...", "patch": "code ameliore ou correction"}}"""

    result = ask_cluster(prompt, "M1")
    if "error" in result:
        # Fallback OL1
        result = ask_cluster(prompt, "OL1")

    return result

# ---------------------------------------------------------------------------
# Feed cycle
# ---------------------------------------------------------------------------
def run_feed_cycle(db) -> dict:
    """Execute un cycle complet d'auto-alimentation."""
    start = time.time()
    analyses = analyze_workspace()

    issues_count = sum(len(a.get("issues", [])) for a in analyses)
    improvements = 0
    applied = 0

    # Store analyses
    for a in analyses:
        db.execute(
            "INSERT INTO analyses (ts, file, lines, functions, classes, complexity_score, issues, suggestions) VALUES (?,?,?,?,?,?,?,?)",
            (time.time(), a.get("file", ""), a.get("lines", 0), a.get("functions", 0),
             a.get("classes", 0), a.get("complexity_score", 0),
             json.dumps(a.get("issues", [])), json.dumps(a.get("suggestions", [])))
        )

    # Generate improvements for files with issues (top 3)
    files_with_issues = [a for a in analyses if a.get("issues")]
    files_with_issues.sort(key=lambda x: len(x["issues"]), reverse=True)

    for a in files_with_issues[:3]:
        filepath = Path(a["path"])
        improvement = generate_improvement(filepath, a)
        if not improvement.get("skip") and not improvement.get("error"):
            db.execute(
                "INSERT INTO improvements (ts, file, description, patch, source) VALUES (?,?,?,?,?)",
                (time.time(), a["file"],
                 improvement.get("content", "")[:500],
                 improvement.get("content", "")[:2000],
                 improvement.get("node", "unknown"))
            )
            improvements += 1

    duration = time.time() - start
    db.execute(
        "INSERT INTO feed_cycles (ts, files_analyzed, issues_found, improvements_generated, improvements_applied, duration_s) VALUES (?,?,?,?,?,?)",
        (time.time(), len(analyses), issues_count, improvements, applied, round(duration, 1))
    )
    db.commit()

    return {
        "cycle": "complete",
        "files_analyzed": len(analyses),
        "issues_found": issues_count,
        "improvements_generated": improvements,
        "duration_s": round(duration, 1),
        "timestamp": datetime.now().isoformat(),
        "top_issues": [{"file": a["file"], "issues": len(a.get("issues", [])),
                         "score": a.get("complexity_score", 0)}
                        for a in sorted(analyses, key=lambda x: len(x.get("issues", [])), reverse=True)[:5]],
    }

def get_metrics(db) -> dict:
    """Metriques d'evolution."""
    cycles = db.execute("SELECT COUNT(*), SUM(files_analyzed), SUM(issues_found), SUM(improvements_generated), SUM(improvements_applied) FROM feed_cycles").fetchone()
    last = db.execute("SELECT ts, files_analyzed, issues_found, improvements_generated, duration_s FROM feed_cycles ORDER BY ts DESC LIMIT 1").fetchone()
    trend = db.execute("SELECT ts, issues_found FROM feed_cycles ORDER BY ts DESC LIMIT 10").fetchall()

    return {
        "total_cycles": cycles[0] or 0,
        "total_files_analyzed": cycles[1] or 0,
        "total_issues_found": cycles[2] or 0,
        "total_improvements": cycles[3] or 0,
        "total_applied": cycles[4] or 0,
        "last_cycle": {
            "when": datetime.fromtimestamp(last[0]).isoformat() if last else None,
            "files": last[1] if last else 0,
            "issues": last[2] if last else 0,
            "improvements": last[3] if last else 0,
            "duration_s": last[4] if last else 0,
        } if last else None,
        "trend": [{"ts": datetime.fromtimestamp(t).isoformat(), "issues": i} for t, i in trend],
    }

def review_code(db) -> dict:
    """Review automatique du code."""
    analyses = analyze_workspace()
    # Score global
    total_lines = sum(a.get("lines", 0) for a in analyses)
    total_functions = sum(a.get("functions", 0) for a in analyses)
    total_issues = sum(len(a.get("issues", [])) for a in analyses)
    total_suggestions = sum(len(a.get("suggestions", [])) for a in analyses)

    health = max(0, 100 - total_issues * 2 - total_suggestions)

    return {
        "review": "complete",
        "files": len(analyses),
        "total_lines": total_lines,
        "total_functions": total_functions,
        "total_issues": total_issues,
        "total_suggestions": total_suggestions,
        "health_score": min(health, 100),
        "worst_files": [
            {"file": a["file"], "issues": len(a.get("issues", [])),
             "details": a.get("issues", [])[:3]}
            for a in sorted(analyses, key=lambda x: len(x.get("issues", [])), reverse=True)[:5]
        ],
        "cleanest_files": [
            {"file": a["file"], "lines": a["lines"], "functions": a["functions"]}
            for a in sorted(analyses, key=lambda x: (len(x.get("issues", [])), -x.get("lines", 0)))[:5]
        ],
    }

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="JARVIS Self-Feeding Engine — Auto-alimentation IA")
    parser.add_argument("--analyze", action="store_true", help="Analyser tout le code")
    parser.add_argument("--improve", type=str, help="Ameliorer un fichier specifique")
    parser.add_argument("--generate", type=str, help="Generer un nouveau script")
    parser.add_argument("--review", action="store_true", help="Review automatique")
    parser.add_argument("--metrics", action="store_true", help="Metriques d'evolution")
    parser.add_argument("--feed", action="store_true", help="Cycle complet d'alimentation")
    parser.add_argument("--once", action="store_true", help="Un cycle")
    args = parser.parse_args()

    db = init_db()

    if args.analyze:
        results = analyze_workspace()
        summary = {
            "files": len(results),
            "total_lines": sum(r.get("lines", 0) for r in results),
            "total_functions": sum(r.get("functions", 0) for r in results),
            "total_issues": sum(len(r.get("issues", [])) for r in results),
            "files_with_issues": [
                {"file": r["file"], "issues": r.get("issues", []), "score": r.get("complexity_score", 0)}
                for r in results if r.get("issues")
            ],
        }
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    elif args.improve:
        filepath = Path(args.improve)
        if not filepath.exists():
            filepath = DEV / args.improve
        analysis = analyze_file(filepath)
        improvement = generate_improvement(filepath, analysis)
        print(json.dumps({"analysis": analysis, "improvement": improvement}, indent=2, ensure_ascii=False))
    elif args.generate:
        prompt = f"""Genere un script Python complet pour JARVIS:
Description: {args.generate}
Le script DOIT: utiliser argparse, avoir --once et --help, stdlib uniquement, sortie JSON.
Reponds avec le code Python complet."""
        result = ask_cluster(prompt, "M1")
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.review:
        result = review_code(db)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.feed or args.once:
        result = run_feed_cycle(db)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.metrics:
        result = get_metrics(db)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        # Default: review
        result = review_code(db)
        print(json.dumps(result, indent=2, ensure_ascii=False))

    db.close()

if __name__ == "__main__":
    main()
