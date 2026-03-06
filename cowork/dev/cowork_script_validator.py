#!/usr/bin/env python3
"""cowork_script_validator.py — Validates all cowork scripts can be parsed.

Uses ast.parse to check each .py file in cowork/ subdirectories for syntax
errors. Reports broken scripts, missing docstrings, and missing --once flag.

Usage:
    python dev/cowork_script_validator.py --once
    python dev/cowork_script_validator.py --once --strict
    python dev/cowork_script_validator.py --dry-run
"""
import argparse
import ast
import json
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
TURBO_DIR = SCRIPT_DIR.parent.parent
DATA_DIR = TURBO_DIR / "data"
COWORK_ROOT = SCRIPT_DIR.parent  # cowork/


def validate_script(filepath: Path) -> dict:
    """Validate a single Python script.

    Returns a dict with validation results:
    - parseable: bool (ast.parse succeeded)
    - has_docstring: bool
    - has_main: bool (__name__ == '__main__')
    - has_once_flag: bool (--once in source)
    - error: str or None
    - lines: int
    """
    result = {
        "file": str(filepath.relative_to(COWORK_ROOT)),
        "parseable": False,
        "has_docstring": False,
        "has_main": False,
        "has_once_flag": False,
        "error": None,
        "lines": 0,
    }

    try:
        source = filepath.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        result["error"] = f"Read error: {e}"
        return result

    result["lines"] = source.count("\n") + 1

    # Check ast parse
    try:
        tree = ast.parse(source, filename=str(filepath))
        result["parseable"] = True
    except SyntaxError as e:
        result["error"] = f"SyntaxError line {e.lineno}: {e.msg}"
        return result

    # Check module docstring
    if (
        tree.body
        and isinstance(tree.body[0], ast.Expr)
        and isinstance(tree.body[0].value, (ast.Constant, ast.Str))
    ):
        result["has_docstring"] = True

    # Check __name__ == '__main__'
    result["has_main"] = '__name__' in source and "'__main__'" in source or '"__main__"' in source

    # Check --once flag
    result["has_once_flag"] = "--once" in source

    return result


def scan_and_validate(strict: bool = False) -> dict:
    """Scan all cowork subdirs and validate every .py file."""
    all_results = []
    broken = []
    warnings = []

    for subdir in sorted(COWORK_ROOT.iterdir()):
        if not subdir.is_dir() or subdir.name.startswith((".", "__")):
            continue
        for pyfile in sorted(subdir.glob("*.py")):
            if pyfile.name.startswith("__"):
                continue
            result = validate_script(pyfile)
            all_results.append(result)

            if not result["parseable"]:
                broken.append(result)
            elif strict:
                issues = []
                if not result["has_docstring"]:
                    issues.append("no docstring")
                if not result["has_main"]:
                    issues.append("no __main__ guard")
                if not result["has_once_flag"]:
                    issues.append("no --once flag")
                if issues:
                    result["warnings"] = issues
                    warnings.append(result)

    return {
        "total": len(all_results),
        "parseable": sum(1 for r in all_results if r["parseable"]),
        "broken": broken,
        "warnings": warnings,
        "all_results": all_results,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Validate all cowork scripts (ast.parse + checks)"
    )
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument("--dry-run", action="store_true", help="Validate without side effects")
    parser.add_argument(
        "--strict", action="store_true",
        help="Also warn about missing docstrings, __main__, --once"
    )
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    args = parser.parse_args()

    report = scan_and_validate(strict=args.strict)

    if args.json:
        # Don't dump all_results in json mode for brevity, just summary + broken
        output = {
            "total": report["total"],
            "parseable": report["parseable"],
            "broken_count": len(report["broken"]),
            "broken": report["broken"],
            "warning_count": len(report["warnings"]),
        }
        print(json.dumps(output, indent=2, ensure_ascii=False))
        sys.exit(0 if not report["broken"] else 1)

    # Human-readable
    print("=== Cowork Script Validator ===")
    print(f"Scanned: {report['total']} scripts")
    print(f"Parseable: {report['parseable']}/{report['total']}")
    print()

    if report["broken"]:
        print(f"BROKEN SCRIPTS ({len(report['broken'])}):")
        for b in report["broken"]:
            print(f"  [FAIL] {b['file']}")
            print(f"         {b['error']}")
        print()
    else:
        print("All scripts parse successfully.")
        print()

    if report["warnings"]:
        print(f"WARNINGS ({len(report['warnings'])}):")
        for w in report["warnings"]:
            print(f"  [WARN] {w['file']}: {', '.join(w.get('warnings', []))}")
        print()

    total_lines = sum(r["lines"] for r in report["all_results"])

    result = {
        "status": "ok" if not report["broken"] else "error",
        "timestamp": datetime.now().isoformat(),
        "total_scripts": report["total"],
        "parseable": report["parseable"],
        "broken": len(report["broken"]),
        "warnings": len(report["warnings"]),
        "total_lines": total_lines,
    }
    print(json.dumps(result))
    sys.exit(0 if not report["broken"] else 1)


if __name__ == "__main__":
    main()
