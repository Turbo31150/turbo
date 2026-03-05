#!/usr/bin/env python3
"""Auto Documentation Updater — Keep COWORK_TASKS.md in sync with scripts.

Scans all *.py files in dev/, extracts docstrings, CLI args, and status,
then updates F:/BUREAU/turbo/cowork/COWORK_TASKS.md automatically.
Tracks changes in SQLite for history and diffing.

Usage:
    python auto_documentation_updater.py --once
    python auto_documentation_updater.py --once --dry-run --verbose
"""

import argparse
import ast
import datetime
import hashlib
import json
import os
import sqlite3
import sys
import time
import glob
import re
import subprocess


# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "cowork_gaps.db")
COWORK_DIR = os.path.dirname(SCRIPT_DIR)
TASKS_MD_PATH = os.path.join(COWORK_DIR, "COWORK_TASKS.md")
DEV_DIR = SCRIPT_DIR


def init_db(conn):
    """Initialize SQLite tables for documentation tracking."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS doc_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            script_name TEXT NOT NULL,
            docstring TEXT,
            cli_args TEXT,
            file_hash TEXT,
            line_count INTEGER,
            status TEXT DEFAULT 'active'
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS doc_updates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            scripts_scanned INTEGER,
            scripts_updated INTEGER,
            md_updated INTEGER DEFAULT 0,
            details TEXT
        )
    """)
    conn.commit()


def compute_file_hash(filepath):
    """Compute MD5 hash of a file."""
    h = hashlib.md5()
    try:
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def extract_docstring(filepath):
    """Extract the module-level docstring from a Python file."""
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            source = f.read()
        tree = ast.parse(source)
        return ast.get_docstring(tree) or ""
    except (SyntaxError, ValueError, OSError):
        return ""


def extract_cli_args(filepath):
    """Extract argparse arguments by parsing the source AST."""
    args_found = []
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            source = f.read()
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                # Look for add_argument calls
                if isinstance(func, ast.Attribute) and func.attr == "add_argument":
                    arg_names = []
                    help_text = ""
                    for arg in node.args:
                        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                            arg_names.append(arg.value)
                    for kw in node.keywords:
                        if kw.arg == "help" and isinstance(kw.value, ast.Constant):
                            help_text = kw.value.value
                    if arg_names:
                        args_found.append({
                            "flags": arg_names,
                            "help": help_text
                        })
    except (SyntaxError, ValueError, OSError):
        pass
    return args_found


def count_lines(filepath):
    """Count lines in a file."""
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            return sum(1 for _ in f)
    except OSError:
        return 0


def detect_status(filepath, docstring):
    """Detect script status from docstring or file content."""
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(2000).lower()
    except OSError:
        content = ""

    doc_lower = docstring.lower()
    if "deprecated" in doc_lower or "deprecated" in content[:500]:
        return "deprecated"
    if "wip" in doc_lower or "work in progress" in doc_lower:
        return "wip"
    if "todo" in doc_lower:
        return "todo"

    # Check if it has a main block
    if "if __name__" in content:
        return "active"
    return "module"


def scan_scripts(verbose=False):
    """Scan all Python scripts in dev/ and extract metadata."""
    scripts = []
    pattern = os.path.join(DEV_DIR, "*.py")
    for filepath in sorted(glob.glob(pattern)):
        name = os.path.basename(filepath)
        if name.startswith("__"):
            continue

        docstring = extract_docstring(filepath)
        cli_args = extract_cli_args(filepath)
        file_hash = compute_file_hash(filepath)
        lines = count_lines(filepath)
        status = detect_status(filepath, docstring)

        info = {
            "name": name,
            "path": filepath,
            "docstring": docstring,
            "cli_args": cli_args,
            "file_hash": file_hash,
            "line_count": lines,
            "status": status,
            "title": docstring.split("\n")[0].strip() if docstring else name.replace(".py", "").replace("_", " ").title()
        }
        scripts.append(info)

        if verbose:
            print(f"  Scanned: {name} ({lines} lines, status={status}, {len(cli_args)} args)")

    return scripts


def generate_markdown(scripts):
    """Generate COWORK_TASKS.md content from script metadata."""
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        f"# COWORK Tasks — Auto-generated {now}",
        "",
        f"> **{len(scripts)} scripts** scanned from `cowork/dev/`",
        "",
        "## Scripts Index",
        "",
        "| # | Script | Status | Lines | CLI Args | Description |",
        "|---|--------|--------|-------|----------|-------------|",
    ]

    for i, s in enumerate(scripts, 1):
        desc = s["title"][:60]
        args_str = ", ".join(
            " ".join(a["flags"]) for a in s["cli_args"]
        )[:40] if s["cli_args"] else "none"
        status_icon = {
            "active": "OK",
            "module": "MOD",
            "wip": "WIP",
            "todo": "TODO",
            "deprecated": "DEP"
        }.get(s["status"], "?")
        lines.append(
            f"| {i} | `{s['name']}` | {status_icon} | {s['line_count']} | {args_str} | {desc} |"
        )

    lines.append("")
    lines.append("## Detailed Descriptions")
    lines.append("")

    for s in scripts:
        lines.append(f"### `{s['name']}`")
        lines.append("")
        if s["docstring"]:
            # First paragraph only
            para = s["docstring"].split("\n\n")[0].strip()
            lines.append(f"{para}")
        else:
            lines.append("_No docstring available._")
        lines.append("")
        if s["cli_args"]:
            lines.append("**CLI Arguments:**")
            for a in s["cli_args"]:
                flags = ", ".join(a["flags"])
                help_text = a["help"] if a["help"] else "no description"
                lines.append(f"- `{flags}` — {help_text}")
            lines.append("")
        lines.append(f"- **Status:** {s['status']} | **Lines:** {s['line_count']}")
        lines.append("")

    lines.append("---")
    lines.append(f"_Auto-generated by `auto_documentation_updater.py` on {now}_")
    lines.append("")

    return "\n".join(lines)


def save_snapshots(conn, scripts):
    """Save current scan results to SQLite."""
    now = datetime.datetime.now().isoformat()
    for s in scripts:
        conn.execute(
            "INSERT INTO doc_snapshots (timestamp, script_name, docstring, cli_args, file_hash, line_count, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (now, s["name"], s["docstring"][:500], json.dumps(s["cli_args"]),
             s["file_hash"], s["line_count"], s["status"])
        )
    conn.commit()


def run(args):
    """Main execution logic."""
    os.makedirs(DATA_DIR, exist_ok=True)

    conn = sqlite3.connect(DB_PATH, timeout=10)
    init_db(conn)

    if args.verbose:
        print(f"[doc-updater] Scanning scripts in {DEV_DIR}")

    scripts = scan_scripts(verbose=args.verbose)

    if args.verbose:
        print(f"[doc-updater] Found {len(scripts)} scripts")

    # Generate markdown
    md_content = generate_markdown(scripts)

    md_updated = 0
    if args.dry_run:
        if args.verbose:
            print("[doc-updater] DRY RUN — would write to:", TASKS_MD_PATH)
            print("--- Preview (first 40 lines) ---")
            for line in md_content.split("\n")[:40]:
                print(f"  {line}")
    else:
        # Check if content changed
        old_content = ""
        if os.path.exists(TASKS_MD_PATH):
            try:
                with open(TASKS_MD_PATH, "r", encoding="utf-8") as f:
                    old_content = f.read()
            except OSError:
                pass

        if old_content != md_content:
            with open(TASKS_MD_PATH, "w", encoding="utf-8") as f:
                f.write(md_content)
            md_updated = 1
            if args.verbose:
                print(f"[doc-updater] Updated {TASKS_MD_PATH}")
        else:
            if args.verbose:
                print("[doc-updater] No changes detected, MD not updated")

    # Save to DB
    save_snapshots(conn, scripts)
    now = datetime.datetime.now().isoformat()
    conn.execute(
        "INSERT INTO doc_updates (timestamp, scripts_scanned, scripts_updated, md_updated, details) "
        "VALUES (?, ?, ?, ?, ?)",
        (now, len(scripts), len(scripts), md_updated, "full scan")
    )
    conn.commit()
    conn.close()

    # JSON output
    result = {
        "timestamp": now,
        "scripts_scanned": len(scripts),
        "md_updated": bool(md_updated),
        "dry_run": args.dry_run,
        "tasks_md_path": TASKS_MD_PATH,
        "scripts": [
            {
                "name": s["name"],
                "status": s["status"],
                "lines": s["line_count"],
                "args_count": len(s["cli_args"])
            }
            for s in scripts
        ]
    }
    print(json.dumps(result, indent=2))
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Auto Documentation Updater — Keep COWORK_TASKS.md in sync with scripts"
    )
    parser.add_argument("--once", action="store_true",
                        help="Run once and exit")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview changes without writing")
    parser.add_argument("--verbose", action="store_true",
                        help="Enable verbose output")
    args = parser.parse_args()

    if args.once:
        run(args)
    else:
        # Continuous mode: run every 60 seconds
        print("[doc-updater] Running in continuous mode (Ctrl+C to stop)")
        while True:
            try:
                run(args)
                time.sleep(60)
            except KeyboardInterrupt:
                print("\n[doc-updater] Stopped")
                break


if __name__ == "__main__":
    main()
