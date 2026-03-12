import ast, os, sys, argparse, textwrap

def add_docstrings_to_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        source = f.read()
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        print(f'Syntax error in {filepath}: {e}', file=sys.stderr)
        return False
    class DocstringTransformer(ast.NodeTransformer):
        def visit_FunctionDef(self, node):
            self.generic_visit(node)
            if not ast.get_docstring(node):
                # simple placeholder docstring using function name and args
                args = [arg.arg for arg in node.args.args]
                args_str = ', '.join(args)
                doc = f"""{node.name}({args_str})\n\n: Add detailed documentation."""
                doc_node = ast.Expr(value=ast.Constant(value=doc, kind=None))
                node.body.insert(0, doc_node)
            return node
        def visit_AsyncFunctionDef(self, node):
            return self.visit_FunctionDef(node)
    transformer = DocstringTransformer()
    new_tree = transformer.visit(tree)
    ast.fix_missing_locations(new_tree)
    new_code = ast.unparse(new_tree)
    if new_code != source:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_code)
        return True
    return False

def process_directory(root_dir):
    changed_files = []
    for dirpath, _, filenames in os.walk(root_dir):
        for fname in filenames:
            if fname.endswith('.py') and not fname.startswith('test_'):
                full = os.path.join(dirpath, fname)
                if add_docstrings_to_file(full):
                    changed_files.append(full)
    return changed_files

def main():
    parser = argparse.ArgumentParser(description='Generate placeholder docstrings for Python functions lacking them.')
    parser.add_argument('--dir', default='.', help='Root directory to scan (default: current)')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be changed without writing files')
    args = parser.parse_args()
    root = os.path.abspath(args.dir)
    changed = []
    for dirpath, _, filenames in os.walk(root):
        for fname in filenames:
            if fname.endswith('.py') and not fname.startswith('test_'):
                full = os.path.join(dirpath, fname)
                # parse and check without writing
                with open(full, 'r', encoding='utf-8') as f:
                    src = f.read()
                tree = ast.parse(src)
                has_missing = any(
                    isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not ast.get_docstring(node)
                    for node in ast.walk(tree)
                )
                if has_missing:
                    changed.append(full)
                    if not args.dry_run:
                        add_docstrings_to_file(full)
    if args.dry_run:
        if changed:
            print('Files that would be modified:')
            for f in changed:
                print(f' - {f}')
        else:
            print('No files need docstrings.')
    else:
        print(f'Processed {len(changed)} file(s).')
        for f in changed:
            print(f'Updated: {f}')

if __name__ == '__main__':
    main()
