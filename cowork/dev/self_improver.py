#!/usr/bin/env python3
"""self_improver.py — Analyse et améliore automatiquement les scripts Python du répertoire dev/.

CLI:
  --analyze      Analyse les fichiers et produit un rapport JSON des problèmes détectés.
  --suggest      Affiche les suggestions d'amélioration sans les appliquer.
  --apply        Applique les modifications suggérées de façon sûre (backup .bak).
  --report       Génère un rapport détaillé (JSON) après analyse/apply.
  --help         Affiche l'aide.
"""

import argparse
import ast
import json
import os
import sys
import shutil
from pathlib import Path
from typing import List, Dict, Any

# Types for issues
Issue = Dict[str, Any]

def find_python_files(root: Path) -> List[Path]:
    return [p for p in root.rglob('*.py') if p.is_file()]

def analyze_file(path: Path) -> List[Issue]:
    issues: List[Issue] = []
    try:
        source = path.read_text(encoding='utf-8')
        tree = ast.parse(source, filename=str(path))
    except Exception as e:
        issues.append({
            'file': str(path),
            'type': 'parse_error',
            'severity': 'high',
            'message': f'Impossible d\'analyser le fichier: {e}',
            'suggestion': None,
        })
        return issues

    # 1. Détection de code mort : fonctions non appelées au niveau du module
    defined_funcs = {node.name: node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
    called_funcs = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            called_funcs.add(node.func.id)
    dead_funcs = set(defined_funcs) - called_funcs
    for func in dead_funcs:
        issues.append({
            'file': str(path),
            'type': 'dead_code',
            'severity': 'medium',
            'message': f'Fonction "{func}" définie mais jamais appelée.',
            'suggestion': f'Supprimer ou utiliser la fonction "{func}".',
        })

    # 2. Imports inutilisés / non-optimisés
    imported_names = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_names[alias.asname or alias.name] = node
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ''
            for alias in node.names:
                name = alias.asname or alias.name
                imported_names[name] = node
    # find used names
    used_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            used_names.add(node.id)
    for name, node in imported_names.items():
        if name not in used_names:
            issues.append({
                'file': str(path),
                'type': 'unused_import',
                'severity': 'low',
                'message': f'Import "{name}" jamais utilisé.',
                'suggestion': 'Supprimer cet import.',
            })

    # 3. Absence de gestion d'exceptions autour de blocs I/O simples
    class IOErrorVisitor(ast.NodeVisitor):
        def visit_Call(self, node: ast.Call):
            if isinstance(node.func, ast.Attribute):
                if node.func.attr in {'open', 'read', 'write', 'close'}:
                    # check parent try/except
                    parent = getattr(node, 'parent', None)
                    # We cannot easily get parent; approximate by scanning surrounding nodes later
                    # For simplicity, propose adding try/except if not already inside a Try node
                    if not any(isinstance(anc, ast.Try) for anc in ast.iter_child_nodes(node)):
                        issues.append({
                            'file': str(path),
                            'type': 'missing_error_handling',
                            'severity': 'medium',
                            'message': f'Appel à "{node.func.attr}" sans bloc try/except.',
                            'suggestion': 'Envelopper cet appel dans un try/except.'
                        })
            self.generic_visit(node)
    # Attach parent references (optional, not critical)
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            setattr(child, 'parent', node)
    IOErrorVisitor().visit(tree)

    return issues

def generate_report(issues: List[Issue]) -> Dict[str, Any]:
    report: Dict[str, Any] = {'summary': {}, 'issues': issues}
    sev_counts = {'high':0,'medium':0,'low':0}
    for iss in issues:
        sev = iss.get('severity')
        if sev in sev_counts:
            sev_counts[sev] += 1
    report['summary'] = sev_counts
    return report

def apply_fixes(issues: List[Issue]):
    # Simple safe fixes: remove dead functions and unused imports.
    files_modified = set()
    for issue in issues:
        path = Path(issue['file'])
        if not path.is_file():
            continue
        source = path.read_text(encoding='utf-8')
        lines = source.splitlines()
        modified = False
        if issue['type'] == 'dead_code':
            func_name = issue['message'].split('"')[1]
            # Find function definition line range
            try:
                tree = ast.parse(source, filename=str(path))
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef) and node.name == func_name:
                        start = node.lineno - 1
                        # naive: remove until next top-level def or end
                        end = start + 1
                        while end < len(lines) and not (lines[end].startswith('def ') or lines[end].startswith('class ')):
                            end += 1
                        del lines[start:end]
                        modified = True
                        break
            except Exception:
                continue
        elif issue['type'] == 'unused_import':
            import_line = None
            # Find line containing the import name
            for i, line in enumerate(lines):
                if issue['message'].split('"')[1] in line:
                    import_line = i
                    break
            if import_line is not None:
                del lines[import_line]
                modified = True
        if modified:
            backup = path.with_suffix('.bak')
            shutil.copy2(path, backup)
            path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
            files_modified.add(str(path))
    return list(files_modified)

def main():
    parser = argparse.ArgumentParser(description='Analyse et améliore les scripts Python du répertoire dev/')
    parser.add_argument('--analyze', action='store_true', help='Analyse les fichiers et produit un rapport JSON')
    parser.add_argument('--suggest', action='store_true', help='Affiche les suggestions sans les appliquer')
    parser.add_argument('--apply', action='store_true', help='Applique les corrections suggérées (création d\'un backup .bak)')
    parser.add_argument('--report', action='store_true', help='Génère un rapport détaillé après analyse/appliquer')
    args = parser.parse_args()

    root = Path(__file__).parent
    all_issues: List[Issue] = []
    for py_file in find_python_files(root):
        all_issues.extend(analyze_file(py_file))

    if args.analyze:
        report = generate_report(all_issues)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    if args.suggest:
        # Print suggestions only
        suggestions = [i for i in all_issues if i.get('suggestion')]
        print(json.dumps(suggestions, ensure_ascii=False, indent=2))
        return
    if args.apply:
        modified_files = apply_fixes(all_issues)
        print(json.dumps({'modified_files': modified_files}, ensure_ascii=False, indent=2))
        return
    if args.report:
        report = generate_report(all_issues)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    # If no arg, show help
    parser.print_help()

if __name__ == '__main__':
    main()
