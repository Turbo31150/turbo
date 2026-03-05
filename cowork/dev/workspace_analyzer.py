#!/usr/bin/env python3
"""workspace_analyzer.py — Analyse le workspace JARVIS et propose des ameliorations.

Scan complet des scripts, detection code mort, duplications, sante globale.

Usage:
    python dev/workspace_analyzer.py --analyze
    python dev/workspace_analyzer.py --health
    python dev/workspace_analyzer.py --suggest
    python dev/workspace_analyzer.py --cleanup
    python dev/workspace_analyzer.py --deps
"""
import argparse
import ast
import json
import os
import sqlite3
import time
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "workspace.db"
DEV = Path(__file__).parent
WORKSPACE = DEV.parent

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS analyses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, total_files INTEGER, total_lines INTEGER,
        total_functions INTEGER, health_score REAL,
        issues INTEGER, details TEXT)""")
    db.commit()
    return db

# ---------------------------------------------------------------------------
# Scan scripts
# ---------------------------------------------------------------------------
def scan_scripts() -> list:
    scripts = []
    for py_file in sorted(DEV.glob("*.py")):
        try:
            content = py_file.read_text(encoding="utf-8", errors="replace")
            lines = content.count("\n") + 1
            size_kb = py_file.stat().st_size / 1024
            mtime = datetime.fromtimestamp(py_file.stat().st_mtime).isoformat()

            # AST analysis
            functions = 0
            classes = 0
            imports = 0
            has_main = False
            has_argparse = False
            has_help = False
            issues = []

            try:
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        functions += 1
                        if node.name == "main":
                            has_main = True
                    elif isinstance(node, ast.ClassDef):
                        classes += 1
                    elif isinstance(node, (ast.Import, ast.ImportFrom)):
                        imports += 1
                        if isinstance(node, ast.ImportFrom) and node.module == "argparse":
                            has_argparse = True

                if "argparse" in content:
                    has_argparse = True
                if "--help" in content or "add_argument" in content:
                    has_help = True

            except SyntaxError as e:
                issues.append(f"SyntaxError: {e.msg} ligne {e.lineno}")

            # Detection problemes
            if lines > 500:
                issues.append(f"Fichier long ({lines} lignes)")
            if not has_main and lines > 20:
                issues.append("Pas de fonction main()")
            if not has_argparse and lines > 30:
                issues.append("Pas d'argparse CLI")
            if "import *" in content:
                issues.append("Import wildcard (import *)")
            if "eval(" in content and "evaluate" not in py_file.name:
                issues.append("Utilisation de eval()")
            if "os.system(" in content:
                issues.append("os.system() au lieu de subprocess")

            # Docstring
            has_docstring = '"""' in content[:500] or "'''" in content[:500]
            if not has_docstring and lines > 20:
                issues.append("Pas de docstring module")

            scripts.append({
                "name": py_file.name,
                "lines": lines,
                "size_kb": round(size_kb, 1),
                "functions": functions,
                "classes": classes,
                "imports": imports,
                "has_main": has_main,
                "has_argparse": has_argparse,
                "has_docstring": has_docstring,
                "issues": issues,
                "modified": mtime,
            })
        except Exception as e:
            scripts.append({"name": py_file.name, "error": str(e)})

    return scripts

# ---------------------------------------------------------------------------
# Health score
# ---------------------------------------------------------------------------
def compute_health(scripts: list) -> dict:
    total_files = len(scripts)
    total_lines = sum(s.get("lines", 0) for s in scripts)
    total_functions = sum(s.get("functions", 0) for s in scripts)
    total_issues = sum(len(s.get("issues", [])) for s in scripts)

    # Score components
    score = 100.0

    # Penalite issues (-0.5 par issue, max -20)
    score -= min(total_issues * 0.5, 20)

    # Bonus main/argparse
    with_main = sum(1 for s in scripts if s.get("has_main"))
    with_argparse = sum(1 for s in scripts if s.get("has_argparse"))
    with_docstring = sum(1 for s in scripts if s.get("has_docstring"))

    main_pct = with_main / max(total_files, 1) * 100
    argparse_pct = with_argparse / max(total_files, 1) * 100
    doc_pct = with_docstring / max(total_files, 1) * 100

    if main_pct < 80:
        score -= (80 - main_pct) * 0.2
    if argparse_pct < 70:
        score -= (70 - argparse_pct) * 0.2
    if doc_pct < 60:
        score -= (60 - doc_pct) * 0.1

    score = max(0, min(100, score))

    return {
        "health_score": round(score, 1),
        "total_files": total_files,
        "total_lines": total_lines,
        "total_functions": total_functions,
        "total_issues": total_issues,
        "with_main": with_main,
        "with_argparse": with_argparse,
        "with_docstring": with_docstring,
        "main_pct": round(main_pct, 1),
        "argparse_pct": round(argparse_pct, 1),
        "docstring_pct": round(doc_pct, 1),
    }

# ---------------------------------------------------------------------------
# Suggestions
# ---------------------------------------------------------------------------
def generate_suggestions(scripts: list) -> list:
    suggestions = []

    for s in scripts:
        name = s.get("name", "?")
        for issue in s.get("issues", []):
            severity = "warning"
            if "SyntaxError" in issue:
                severity = "error"
            elif "eval(" in issue or "os.system" in issue:
                severity = "security"
            suggestions.append({
                "file": name,
                "issue": issue,
                "severity": severity,
            })

    # Detection duplications (noms similaires)
    names = [s["name"] for s in scripts if "name" in s]
    for i, n1 in enumerate(names):
        base1 = n1.replace(".py", "").replace("_", "")
        for n2 in names[i+1:]:
            base2 = n2.replace(".py", "").replace("_", "")
            if base1 in base2 or base2 in base1:
                if abs(len(base1) - len(base2)) < 5 and base1 != base2:
                    suggestions.append({
                        "file": f"{n1} / {n2}",
                        "issue": "Noms similaires — possible duplication",
                        "severity": "info",
                    })

    return sorted(suggestions, key=lambda x: {"error": 0, "security": 1, "warning": 2, "info": 3}.get(x["severity"], 4))

# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------
def analyze_deps(scripts: list) -> dict:
    deps = {}
    all_names = {s["name"].replace(".py", "") for s in scripts if "name" in s}

    for s in scripts:
        name = s.get("name", "?")
        try:
            content = (DEV / name).read_text(encoding="utf-8", errors="replace")
            imports = []
            for line in content.split("\n"):
                line = line.strip()
                if line.startswith("from ") and " import " in line:
                    mod = line.split("from ")[1].split(" import")[0].strip()
                    if mod.replace(".", "_") in all_names or mod in all_names:
                        imports.append(mod)
                elif line.startswith("import "):
                    mod = line.split("import ")[1].split(",")[0].split(" as ")[0].strip()
                    if mod in all_names:
                        imports.append(mod)
            if imports:
                deps[name] = imports
        except Exception:
            pass

    return deps

# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------
def cleanup_workspace() -> dict:
    removed = []
    freed_bytes = 0

    # __pycache__
    for cache_dir in WORKSPACE.rglob("__pycache__"):
        try:
            size = sum(f.stat().st_size for f in cache_dir.rglob("*") if f.is_file())
            import shutil
            shutil.rmtree(cache_dir)
            removed.append({"path": str(cache_dir.relative_to(WORKSPACE)), "type": "__pycache__", "size_kb": round(size / 1024, 1)})
            freed_bytes += size
        except Exception:
            pass

    # .pyc files
    for pyc in WORKSPACE.rglob("*.pyc"):
        try:
            size = pyc.stat().st_size
            pyc.unlink()
            removed.append({"path": str(pyc.relative_to(WORKSPACE)), "type": ".pyc", "size_kb": round(size / 1024, 1)})
            freed_bytes += size
        except Exception:
            pass

    # Temp files
    for pattern in ["*.tmp", "*.temp", "*.bak"]:
        for tmp in DEV.glob(pattern):
            try:
                size = tmp.stat().st_size
                tmp.unlink()
                removed.append({"path": str(tmp.relative_to(WORKSPACE)), "type": "temp", "size_kb": round(size / 1024, 1)})
                freed_bytes += size
            except Exception:
                pass

    # Old logs (>7 jours)
    seven_days_ago = time.time() - 7 * 86400
    for log in DEV.glob("*.log"):
        try:
            if log.stat().st_mtime < seven_days_ago:
                size = log.stat().st_size
                log.unlink()
                removed.append({"path": str(log.relative_to(WORKSPACE)), "type": "old_log", "size_kb": round(size / 1024, 1)})
                freed_bytes += size
        except Exception:
            pass

    return {
        "cleaned": len(removed),
        "freed_kb": round(freed_bytes / 1024, 1),
        "removed": removed,
    }

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="JARVIS Workspace Analyzer — Sante et ameliorations")
    parser.add_argument("--analyze", action="store_true", help="Analyse complete du workspace")
    parser.add_argument("--health", action="store_true", help="Score de sante global")
    parser.add_argument("--suggest", action="store_true", help="Suggestions d'amelioration")
    parser.add_argument("--cleanup", action="store_true", help="Nettoyer cache/temp/logs")
    parser.add_argument("--deps", action="store_true", help="Graphe de dependances internes")
    parser.add_argument("--top", type=int, default=10, help="Nombre de scripts a afficher (defaut: 10)")
    args = parser.parse_args()

    db = init_db()
    scripts = scan_scripts()

    if args.analyze:
        health = compute_health(scripts)
        # Top scripts par taille
        sorted_scripts = sorted(scripts, key=lambda x: x.get("lines", 0), reverse=True)
        # Store
        db.execute(
            "INSERT INTO analyses (ts, total_files, total_lines, total_functions, health_score, issues, details) VALUES (?,?,?,?,?,?,?)",
            (time.time(), health["total_files"], health["total_lines"], health["total_functions"],
             health["health_score"], health["total_issues"], json.dumps(health))
        )
        db.commit()

        result = {
            "health": health,
            "top_scripts": sorted_scripts[:args.top],
            "issues_summary": {},
        }
        # Count issues by type
        for s in scripts:
            for issue in s.get("issues", []):
                key = issue.split(":")[0] if ":" in issue else issue.split("(")[0].strip()
                result["issues_summary"][key] = result["issues_summary"].get(key, 0) + 1

        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif args.health:
        health = compute_health(scripts)
        print(json.dumps(health, indent=2, ensure_ascii=False))

    elif args.suggest:
        suggestions = generate_suggestions(scripts)
        print(json.dumps({
            "total": len(suggestions),
            "by_severity": {
                "error": sum(1 for s in suggestions if s["severity"] == "error"),
                "security": sum(1 for s in suggestions if s["severity"] == "security"),
                "warning": sum(1 for s in suggestions if s["severity"] == "warning"),
                "info": sum(1 for s in suggestions if s["severity"] == "info"),
            },
            "suggestions": suggestions,
        }, indent=2, ensure_ascii=False))

    elif args.cleanup:
        result = cleanup_workspace()
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif args.deps:
        deps = analyze_deps(scripts)
        print(json.dumps({
            "total_with_internal_deps": len(deps),
            "dependencies": deps,
        }, indent=2, ensure_ascii=False))

    else:
        parser.print_help()

    db.close()

if __name__ == "__main__":
    main()
