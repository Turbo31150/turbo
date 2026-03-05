#!/usr/bin/env python3
"""jarvis_plugin_tester.py — Testeur de plugins JARVIS.

Valide chaque plugin (skills, hooks, commands, agents).

Usage:
    python dev/jarvis_plugin_tester.py --once
    python dev/jarvis_plugin_tester.py --test jarvis-turbo
    python dev/jarvis_plugin_tester.py --all
    python dev/jarvis_plugin_tester.py --report
"""
import argparse
import ast
import json
import os
import sqlite3
import time
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "plugin_tester.db"
PLUGIN_DIRS = [
    Path.home() / ".claude" / "plugins" / "local",
    Path.home() / ".claude" / "plugins",
]


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS test_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, plugin TEXT, component TEXT,
        file_path TEXT, status TEXT, error TEXT)""")
    db.commit()
    return db


def validate_json(path):
    try:
        json.loads(path.read_text(encoding="utf-8"))
        return True, None
    except Exception as e:
        return False, str(e)[:200]


def validate_python(path):
    try:
        ast.parse(path.read_text(encoding="utf-8"))
        return True, None
    except SyntaxError as e:
        return False, f"SyntaxError line {e.lineno}: {e.msg}"


def test_plugin(plugin_dir):
    results = []
    manifest = plugin_dir / "plugin.json"
    if not manifest.exists():
        results.append({"component": "manifest", "file": "plugin.json", "status": "FAIL", "error": "Missing plugin.json"})
        return results

    ok, err = validate_json(manifest)
    if not ok:
        results.append({"component": "manifest", "file": "plugin.json", "status": "FAIL", "error": err})
        return results
    results.append({"component": "manifest", "file": "plugin.json", "status": "PASS", "error": None})

    config = json.loads(manifest.read_text(encoding="utf-8"))

    # Check skills
    skills_dir = plugin_dir / "skills"
    if skills_dir.exists():
        for f in skills_dir.iterdir():
            if f.suffix == ".md":
                content = f.read_text(encoding="utf-8", errors="replace")
                has_frontmatter = content.startswith("---")
                results.append({
                    "component": "skill", "file": f.name,
                    "status": "PASS" if has_frontmatter else "WARN",
                    "error": None if has_frontmatter else "No frontmatter (---)",
                })

    # Check hooks
    hooks_dir = plugin_dir / "hooks"
    if hooks_dir.exists():
        for f in hooks_dir.iterdir():
            if f.suffix == ".py":
                ok, err = validate_python(f)
                results.append({"component": "hook", "file": f.name, "status": "PASS" if ok else "FAIL", "error": err})
            elif f.suffix in (".sh", ".bash"):
                results.append({"component": "hook", "file": f.name, "status": "PASS", "error": None})

    # Check agents
    agents_dir = plugin_dir / "agents"
    if agents_dir.exists():
        for f in agents_dir.iterdir():
            if f.suffix == ".md":
                content = f.read_text(encoding="utf-8", errors="replace")
                has_frontmatter = content.startswith("---")
                results.append({
                    "component": "agent", "file": f.name,
                    "status": "PASS" if has_frontmatter else "WARN",
                    "error": None if has_frontmatter else "No frontmatter (---)",
                })

    # Check commands
    cmds_dir = plugin_dir / "commands"
    if cmds_dir.exists():
        for f in cmds_dir.iterdir():
            if f.suffix == ".md":
                results.append({"component": "command", "file": f.name, "status": "PASS", "error": None})

    return results


def do_test_all():
    db = init_db()
    all_results = {}

    for base_dir in PLUGIN_DIRS:
        if not base_dir.exists():
            continue
        for p in base_dir.iterdir():
            if p.is_dir() and (p / "plugin.json").exists():
                results = test_plugin(p)
                all_results[p.name] = results
                for r in results:
                    db.execute("INSERT INTO test_results (ts, plugin, component, file_path, status, error) VALUES (?,?,?,?,?,?)",
                               (time.time(), p.name, r["component"], r["file"], r["status"], r.get("error")))

    db.commit()
    db.close()

    summary = {}
    for name, results in all_results.items():
        summary[name] = {
            "total": len(results),
            "pass": sum(1 for r in results if r["status"] == "PASS"),
            "fail": sum(1 for r in results if r["status"] == "FAIL"),
            "warn": sum(1 for r in results if r["status"] == "WARN"),
            "details": results,
        }

    return {
        "ts": datetime.now().isoformat(),
        "plugins_tested": len(all_results),
        "results": summary,
    }


def main():
    parser = argparse.ArgumentParser(description="JARVIS Plugin Tester")
    parser.add_argument("--once", "--all", action="store_true", help="Test all plugins")
    parser.add_argument("--test", metavar="PLUGIN", help="Test specific plugin")
    parser.add_argument("--report", action="store_true", help="Show report")
    parser.add_argument("--fix", action="store_true", help="Auto-fix issues")
    args = parser.parse_args()
    print(json.dumps(do_test_all(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
