#!/usr/bin/env python3
"""code_reviewer.py

Revue de code automatique pour scripts Python.
Analyse qualité, sécurité, conventions et bugs potentiels.

CLI :
    --review FILE    : Reviewer un fichier
    --all [DIR]      : Reviewer tous les .py
    --report         : Rapport global avec scores
"""

import argparse
import ast
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Any

TELEGRAM_TOKEN = "8369376863:AAF-7YGDbun8mXWwqYJFj-eX6P78DeIu9Aw"
TELEGRAM_CHAT_ID = "2010747443"

def telegram_send(msg: str):
    import urllib.parse, urllib.request
    try:
        data = urllib.parse.urlencode({"chat_id": TELEGRAM_CHAT_ID, "text": msg}).encode()
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=10)
    except Exception:
        pass

def review_file(filepath: Path) -> Dict[str, Any]:
    """Analyse un fichier Python et retourne des issues."""
    result = {
        "file": filepath.name,
        "path": str(filepath),
        "score": 100,
        "issues": [],
        "stats": {"lines": 0, "functions": 0, "classes": 0}
    }

    try:
        source = filepath.read_text(encoding="utf-8")
    except Exception as e:
        result["issues"].append({"severity": "error", "msg": f"Cannot read file: {e}"})
        result["score"] = 0
        return result

    lines = source.splitlines()
    result["stats"]["lines"] = len(lines)

    # Parse AST
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        result["issues"].append({"severity": "error", "msg": f"Syntax error line {e.lineno}: {e.msg}", "line": e.lineno})
        result["score"] = 10
        return result

    # Count functions/classes
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            result["stats"]["functions"] += 1
        elif isinstance(node, ast.ClassDef):
            result["stats"]["classes"] += 1

    # Check 1: Module docstring
    has_docstring = (tree.body and isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, (ast.Str, ast.Constant)))
    if not has_docstring:
        result["issues"].append({"severity": "warning", "msg": "Missing module docstring"})
        result["score"] -= 5

    # Check 2: Functions without docstrings
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            if not ast.get_docstring(node) and not node.name.startswith("_"):
                result["issues"].append({"severity": "info", "msg": f"Function '{node.name}' lacks docstring", "line": node.lineno})
                result["score"] -= 2

    # Check 3: Long functions (>50 lines)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            func_lines = node.end_lineno - node.lineno if hasattr(node, "end_lineno") else 0
            if func_lines > 50:
                result["issues"].append({"severity": "warning", "msg": f"Function '{node.name}' is {func_lines} lines long", "line": node.lineno})
                result["score"] -= 5

    # Check 4: Bare except
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler) and node.type is None:
            result["issues"].append({"severity": "warning", "msg": "Bare except clause (catches all exceptions)", "line": node.lineno})
            result["score"] -= 3

    # Check 5: Hardcoded secrets patterns
    secret_patterns = [r'password\s*=\s*["\']', r'token\s*=\s*["\']', r'secret\s*=\s*["\']', r'api_key\s*=\s*["\']']
    for i, line in enumerate(lines, 1):
        for pat in secret_patterns:
            if re.search(pat, line, re.IGNORECASE):
                result["issues"].append({"severity": "security", "msg": f"Possible hardcoded secret", "line": i})
                result["score"] -= 10
                break

    # Check 6: /FIXME/HACK comments
    for i, line in enumerate(lines, 1):
        if re.search(r'#\s*(|FIXME|HACK|XXX)', line, re.IGNORECASE):
            result["issues"].append({"severity": "info", "msg": f"/FIXME found", "line": i})
            result["score"] -= 1

    # Check 7: Unused imports (basic check)
    imports = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.asname or alias.name.split(".")[0]
                imports.append((name, node.lineno))
        elif isinstance(node, ast.ImportFrom):
            if node.names:
                for alias in node.names:
                    name = alias.asname or alias.name
                    imports.append((name, node.lineno))

    for name, lineno in imports:
        # Simple check: name appears only in import line
        count = sum(1 for line in lines if name in line)
        if count <= 1:
            result["issues"].append({"severity": "info", "msg": f"Possibly unused import: {name}", "line": lineno})
            result["score"] -= 2

    # Check 8: if __name__ == "__main__"
    has_main = any("__main__" in ast.dump(node) for node in tree.body if isinstance(node, ast.If))
    if not has_main and result["stats"]["functions"] > 0:
        result["issues"].append({"severity": "info", "msg": "No if __name__ == '__main__' guard"})
        result["score"] -= 3

    result["score"] = max(0, min(100, result["score"]))
    return result

def display_review(review: Dict):
    score = review["score"]
    if score >= 90:
        grade = "A"
    elif score >= 80:
        grade = "B"
    elif score >= 70:
        grade = "C"
    elif score >= 60:
        grade = "D"
    else:
        grade = "F"

    print(f"\n{'='*50}")
    print(f"  {review['file']} — Score: {score}/100 (Grade {grade})")
    print(f"  {review['stats']['lines']} lignes | {review['stats']['functions']} fonctions | {review['stats']['classes']} classes")
    print(f"{'='*50}")

    severity_icons = {"error": "🔴", "security": "🔒", "warning": "🟡", "info": "ℹ️"}
    for issue in review["issues"]:
        icon = severity_icons.get(issue["severity"], "•")
        line_str = f" (L{issue['line']})" if "line" in issue else ""
        print(f"  {icon} [{issue['severity'].upper()}]{line_str} {issue['msg']}")

    if not review["issues"]:
        print("  ✅ Aucun problème détecté !")

def main():
    parser = argparse.ArgumentParser(description="Revue de code automatique Python.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--review", type=Path, help="Reviewer un fichier")
    group.add_argument("--all", nargs="?", const=".", metavar="DIR", help="Reviewer tous les .py")
    group.add_argument("--report", action="store_true", help="Rapport global")
    args = parser.parse_args()

    if args.review:
        r = review_file(args.review)
        display_review(r)

    elif args.all is not None:
        directory = Path(args.all)
        files = sorted(directory.glob("*.py"))
        if not files:
            print(f"[code_reviewer] Aucun .py trouvé dans {directory}")
            return
        reviews = [review_file(f) for f in files]
        for r in reviews:
            display_review(r)

        avg_score = sum(r["score"] for r in reviews) / len(reviews)
        print(f"\n{'='*50}")
        print(f"  RÉSUMÉ : {len(reviews)} fichiers | Score moyen : {avg_score:.1f}/100")
        print(f"{'='*50}")

    elif args.report:
        directory = Path(".")
        files = sorted(directory.glob("*.py"))
        reviews = [review_file(f) for f in files]
        avg = sum(r["score"] for r in reviews) / len(reviews) if reviews else 0
        low = [r for r in reviews if r["score"] < 70]

        msg = f"📋 Code Review — {len(reviews)} fichiers | Score moyen: {avg:.0f}/100"
        if low:
            msg += f"\n⚠️ {len(low)} fichier(s) sous 70/100"
        print(msg)
        telegram_send(msg)

if __name__ == "__main__":
    main()
