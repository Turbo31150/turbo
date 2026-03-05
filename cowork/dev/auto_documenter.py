#!/usr/bin/env python3
"""auto_documenter.py

Documenteur automatique de scripts Python.
Analyse les fichiers .py et génère une documentation structurée.

CLI :
    --once [DIR]     : Documenter tous les .py du répertoire
    --file FILE      : Documenter un seul fichier
    --output FORMAT  : Format de sortie (text/json/md)
    --json           : Alias pour --output json
"""

import argparse
import ast
import json
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional

def analyze_file(filepath: Path) -> Dict[str, Any]:
    """Analyse un fichier Python et extrait sa structure."""
    doc = {
        "file": filepath.name,
        "path": str(filepath),
        "docstring": "",
        "imports": [],
        "classes": [],
        "functions": [],
        "constants": [],
        "cli": False,
        "lines": 0
    }

    try:
        source = filepath.read_text(encoding="utf-8")
        doc["lines"] = len(source.splitlines())
        tree = ast.parse(source)
    except Exception as e:
        doc["error"] = str(e)
        return doc

    # Module docstring
    if tree.body and isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, (ast.Str, ast.Constant)):
        val = tree.body[0].value
        doc["docstring"] = val.value if isinstance(val, ast.Constant) else val.s

    for node in ast.walk(tree):
        # Imports
        if isinstance(node, ast.Import):
            for alias in node.names:
                doc["imports"].append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                doc["imports"].append(node.module)

    for node in tree.body:
        # Top-level functions
        if isinstance(node, ast.FunctionDef):
            func_doc = {
                "name": node.name,
                "args": [a.arg for a in node.args.args if a.arg != "self"],
                "returns": None,
                "docstring": ast.get_docstring(node) or "",
                "line": node.lineno
            }
            if node.returns:
                func_doc["returns"] = ast.dump(node.returns)
            doc["functions"].append(func_doc)

        # Classes
        elif isinstance(node, ast.ClassDef):
            cls_doc = {
                "name": node.name,
                "docstring": ast.get_docstring(node) or "",
                "methods": [],
                "line": node.lineno
            }
            for item in node.body:
                if isinstance(item, ast.FunctionDef):
                    cls_doc["methods"].append({
                        "name": item.name,
                        "args": [a.arg for a in item.args.args if a.arg != "self"],
                        "docstring": ast.get_docstring(item) or ""
                    })
            doc["classes"].append(cls_doc)

        # Constants (top-level assignments in UPPER_CASE)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id.isupper():
                    doc["constants"].append(target.id)

    # CLI detection
    doc["cli"] = any(
        isinstance(node, ast.If) and
        any("__main__" in ast.dump(node.test) for _ in [1])
        for node in tree.body
    ) if tree.body else False

    return doc

def format_text(doc: Dict) -> str:
    lines = [f"{'='*60}", f"  {doc['file']} ({doc['lines']} lignes)", f"{'='*60}"]

    if doc.get("error"):
        lines.append(f"  ERREUR: {doc['error']}")
        return "\n".join(lines)

    if doc["docstring"]:
        first_line = doc["docstring"].strip().split("\n")[0]
        lines.append(f"  Description: {first_line}")

    if doc["imports"]:
        lines.append(f"  Imports: {', '.join(doc['imports'][:10])}")

    if doc["constants"]:
        lines.append(f"  Constantes: {', '.join(doc['constants'][:10])}")

    if doc["functions"]:
        lines.append(f"\n  Fonctions ({len(doc['functions'])}):")
        for f in doc["functions"]:
            args_str = ", ".join(f["args"]) if f["args"] else ""
            lines.append(f"    - {f['name']}({args_str}) [L{f['line']}]")
            if f["docstring"]:
                first = f["docstring"].strip().split("\n")[0][:60]
                lines.append(f"      {first}")

    if doc["classes"]:
        lines.append(f"\n  Classes ({len(doc['classes'])}):")
        for c in doc["classes"]:
            lines.append(f"    - {c['name']} [L{c['line']}]")
            for m in c["methods"]:
                lines.append(f"      .{m['name']}({', '.join(m['args'])})")

    if doc["cli"]:
        lines.append(f"\n  CLI: if __name__ == '__main__' détecté")

    return "\n".join(lines)

def format_markdown(doc: Dict) -> str:
    lines = [f"## {doc['file']}", f"**{doc['lines']} lignes**\n"]

    if doc["docstring"]:
        first = doc["docstring"].strip().split("\n")[0]
        lines.append(f"> {first}\n")

    if doc["functions"]:
        lines.append(f"### Fonctions ({len(doc['functions'])})")
        for f in doc["functions"]:
            lines.append(f"- `{f['name']}({', '.join(f['args'])})`")

    if doc["classes"]:
        lines.append(f"\n### Classes ({len(doc['classes'])})")
        for c in doc["classes"]:
            lines.append(f"- **{c['name']}** — {len(c['methods'])} méthodes")

    return "\n".join(lines)

def main():
    parser = argparse.ArgumentParser(description="Documenteur automatique Python.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--once", nargs="?", const=".", metavar="DIR", help="Documenter tous les .py")
    group.add_argument("--file", type=Path, help="Documenter un fichier")
    parser.add_argument("--output", choices=["text", "json", "md"], default="text")
    parser.add_argument("--json", action="store_true", help="Sortie JSON")
    args = parser.parse_args()

    fmt = "json" if args.json else args.output

    if args.file:
        doc = analyze_file(args.file)
        if fmt == "json":
            print(json.dumps(doc, ensure_ascii=False, indent=2))
        elif fmt == "md":
            print(format_markdown(doc))
        else:
            print(format_text(doc))

    elif args.once is not None:
        directory = Path(args.once)
        files = sorted(directory.glob("*.py"))
        if not files:
            print(f"[auto_documenter] Aucun fichier .py dans {directory}")
            return

        all_docs = []
        for f in files:
            doc = analyze_file(f)
            all_docs.append(doc)

        if fmt == "json":
            print(json.dumps(all_docs, ensure_ascii=False, indent=2))
        else:
            total_lines = sum(d["lines"] for d in all_docs)
            total_funcs = sum(len(d["functions"]) for d in all_docs)
            total_classes = sum(len(d["classes"]) for d in all_docs)

            print(f"📚 Documentation — {len(all_docs)} fichiers | {total_lines} lignes | {total_funcs} fonctions | {total_classes} classes\n")
            for doc in all_docs:
                if fmt == "md":
                    print(format_markdown(doc))
                else:
                    print(format_text(doc))
                print()

if __name__ == "__main__":
    main()
