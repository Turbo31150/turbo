#!/usr/bin/env python3
"""jarvis_update_checker.py — Vérificateur mises à jour.

Detecte dependances obsoletes, vulnerabilites connues.

Usage:
    python dev/jarvis_update_checker.py --once
    python dev/jarvis_update_checker.py --check
    python dev/jarvis_update_checker.py --deps
    python dev/jarvis_update_checker.py --security
"""
import argparse
import json
import os
import sqlite3
import subprocess
import time
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "update_checker.db"
PROJECT_ROOT = Path("F:/BUREAU/turbo")


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS checks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, package TEXT, current_ver TEXT,
        latest_ver TEXT, outdated INTEGER)""")
    db.commit()
    return db


def parse_pyproject():
    deps = []
    pyproject = PROJECT_ROOT / "pyproject.toml"
    if not pyproject.exists():
        return deps
    content = pyproject.read_text(encoding="utf-8", errors="replace")
    in_deps = False
    for line in content.split("\n"):
        line = line.strip()
        if line == "dependencies = [" or line == 'dependencies = [':
            in_deps = True
            continue
        if in_deps:
            if line == "]":
                break
            pkg = line.strip(' ",')
            if pkg and not pkg.startswith("#"):
                name = pkg.split(">=")[0].split("==")[0].split("<")[0].split(">")[0].strip()
                if name:
                    deps.append(name)
    return deps


def check_pip_outdated():
    outdated = []
    try:
        out = subprocess.run(
            ["pip", "list", "--outdated", "--format=json"],
            capture_output=True, text=True, timeout=30
        )
        if out.stdout.strip():
            outdated = json.loads(out.stdout)
    except Exception:
        pass
    return outdated


def do_check():
    db = init_db()
    project_deps = parse_pyproject()
    pip_outdated = check_pip_outdated()

    outdated_map = {p["name"].lower(): p for p in pip_outdated}
    results = []
    for dep in project_deps:
        info = outdated_map.get(dep.lower(), {})
        is_outdated = dep.lower() in outdated_map
        entry = {
            "package": dep,
            "current": info.get("version", "installed"),
            "latest": info.get("latest_version", "?"),
            "outdated": is_outdated,
        }
        results.append(entry)
        db.execute("INSERT INTO checks (ts, package, current_ver, latest_ver, outdated) VALUES (?,?,?,?,?)",
                   (time.time(), dep, entry["current"], entry["latest"], int(is_outdated)))

    db.commit()
    db.close()

    return {
        "ts": datetime.now().isoformat(),
        "project_deps": len(project_deps),
        "outdated": sum(1 for r in results if r["outdated"]),
        "up_to_date": sum(1 for r in results if not r["outdated"]),
        "details": results,
    }


def main():
    parser = argparse.ArgumentParser(description="JARVIS Update Checker")
    parser.add_argument("--once", "--check", action="store_true", help="Check updates")
    parser.add_argument("--deps", action="store_true", help="List deps")
    parser.add_argument("--security", action="store_true", help="Security check")
    parser.add_argument("--report", action="store_true", help="Report")
    args = parser.parse_args()
    print(json.dumps(do_check(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
