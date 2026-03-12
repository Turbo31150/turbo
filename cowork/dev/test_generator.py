#!/usr/bin/env python3
"""test_generator.py

Générateur automatique de tests pour scripts Python.
Analyse les fonctions et génère des tests unittest basiques.

CLI :
    --generate FILE   : Générer des tests pour un fichier
    --all [DIR]       : Générer pour tous les .py
    --run FILE        : Générer et exécuter les tests
"""

import argparse
import ast
import importlib.util
import json
import sys
import unittest
from io import StringIO
from pathlib import Path
from typing import List, Dict

def extract_functions(filepath: Path) -> List[Dict]:
    """Extrait les fonctions publiques d'un fichier Python."""
    try:
        source = filepath.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except Exception:
        return []

    functions = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
            func = {
                "name": node.name,
                "args": [],
                "has_return": False,
                "docstring": ast.get_docstring(node) or "",
                "line": node.lineno
            }
            for arg in node.args.args:
                if arg.arg != "self":
                    ann = ""
                    if arg.annotation:
                        try:
                            ann = ast.dump(arg.annotation)
                        except Exception:
                            pass
                    func["args"].append({"name": arg.arg, "annotation": ann})

            # Check for return statements
            for child in ast.walk(node):
                if isinstance(child, ast.Return) and child.value is not None:
                    func["has_return"] = True
                    break

            functions.append(func)
    return functions

def generate_test_code(filepath: Path, functions: List[Dict]) -> str:
    """Génère le code de test unittest."""
    module_name = filepath.stem
    lines = [
        f'#!/usr/bin/env python3',
        f'"""Tests auto-générés pour {filepath.name}"""',
        f'',
        f'import sys',
        f'import unittest',
        f'from pathlib import Path',
        f'',
        f'# Add parent to path',
        f'sys.path.insert(0, str(Path(__file__).parent))',
        f'',
    ]

    # Try to import the module
    lines.append(f'try:')
    lines.append(f'    import {module_name}')
    lines.append(f'except Exception:')
    lines.append(f'    {module_name} = None')
    lines.append(f'')

    # Test class
    class_name = "".join(w.capitalize() for w in module_name.split("_"))
    lines.append(f'class Test{class_name}(unittest.TestCase):')
    lines.append(f'')
    lines.append(f'    def test_module_imports(self):')
    lines.append(f'        """Le module s\'importe sans erreur."""')
    lines.append(f'        self.assertIsNotNone({module_name}, "{module_name} failed to import")')
    lines.append(f'')

    for func in functions:
        test_name = f"test_{func['name']}_exists"
        lines.append(f'    def {test_name}(self):')
        lines.append(f'        """La fonction {func["name"]} existe."""')
        lines.append(f'        if {module_name} is None:')
        lines.append(f'            self.skipTest("Module not imported")')
        lines.append(f'        self.assertTrue(hasattr({module_name}, "{func["name"]}"), "{func["name"]} not found")')
        lines.append(f'')

        if func["has_return"] and len(func["args"]) == 0:
            test_name2 = f"test_{func['name']}_callable"
            lines.append(f'    def {test_name2}(self):')
            lines.append(f'        """La fonction {func["name"]} est appelable."""')
            lines.append(f'        if {module_name} is None:')
            lines.append(f'            self.skipTest("Module not imported")')
            lines.append(f'        fn = getattr({module_name}, "{func["name"]}", None)')
            lines.append(f'        self.assertTrue(callable(fn))')
            lines.append(f'')

    lines.append(f'if __name__ == "__main__":')
    lines.append(f'    unittest.main()')
    return "\n".join(lines)

def generate_for_file(filepath: Path, output_dir: Path = None):
    functions = extract_functions(filepath)
    if not functions:
        print(f"[test_generator] {filepath.name}: aucune fonction publique trouvée.")
        return None

    test_code = generate_test_code(filepath, functions)
    test_file = (output_dir or filepath.parent) / f"test_{filepath.name}"

    test_file.write_text(test_code, encoding="utf-8")
    print(f"[test_generator] {filepath.name}: {len(functions)} fonctions → {test_file.name}")
    return test_file

def run_tests(test_file: Path):
    """Exécute les tests générés."""
    spec = importlib.util.spec_from_file_location("test_module", str(test_file))
    if spec is None:
        print(f"[test_generator] Impossible de charger {test_file}")
        return

    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as e:
        print(f"[test_generator] Erreur de chargement: {e}")
        return

    # Run
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(module)
    stream = StringIO()
    runner = unittest.TextTestRunner(stream=stream, verbosity=2)
    result = runner.run(suite)

    print(stream.getvalue())
    print(f"\n{'='*40}")
    print(f"Tests: {result.testsRun} | OK: {result.testsRun - len(result.failures) - len(result.errors)} | Failures: {len(result.failures)} | Errors: {len(result.errors)}")

def main():
    parser = argparse.ArgumentParser(description="Générateur de tests Python.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--generate", type=Path, help="Générer tests pour un fichier")
    group.add_argument("--all", nargs="?", const=".", metavar="DIR", help="Générer pour tous les .py")
    group.add_argument("--run", type=Path, help="Générer et exécuter les tests")
    args = parser.parse_args()

    if args.generate:
        generate_for_file(args.generate)

    elif args.all is not None:
        directory = Path(args.all)
        files = sorted(f for f in directory.glob("*.py") if not f.name.startswith("test_"))
        total = 0
        for f in files:
            result = generate_for_file(f)
            if result:
                total += 1
        print(f"\n[test_generator] {total}/{len(files)} fichiers documentés.")

    elif args.run:
        test_file = generate_for_file(args.run)
        if test_file:
            run_tests(test_file)

if __name__ == "__main__":
    main()
