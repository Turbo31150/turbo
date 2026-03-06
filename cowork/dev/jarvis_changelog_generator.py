#!/usr/bin/env python3
"""jarvis_changelog_generator.py — Genere changelog JARVIS.

Parse git log + diff pour documentation automatique.

Usage:
    python dev/jarvis_changelog_generator.py --once
    python dev/jarvis_changelog_generator.py --generate
    python dev/jarvis_changelog_generator.py --since 2026-03-01
    python dev/jarvis_changelog_generator.py --format json
"""
import argparse
import json
import os
import re
import sqlite3
import subprocess
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "changelog_generator.db"
from _paths import TURBO_DIR


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS changelogs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, since_date TEXT, commits INTEGER,
        features INTEGER, fixes INTEGER, content TEXT)""")
    db.commit()
    return db


def get_git_log(since="7 days ago", repo_dir=None):
    """Get git log entries."""
    cwd = str(repo_dir) if repo_dir and repo_dir.exists() else None
    commits = []
    try:
        result = subprocess.run(
            ["git", "log", f"--since={since}", "--oneline", "--no-merges", "-100"],
            capture_output=True, text=True, timeout=10, cwd=cwd
        )
        for line in result.stdout.strip().split("\n"):
            if line.strip():
                parts = line.split(" ", 1)
                if len(parts) == 2:
                    commits.append({"hash": parts[0], "message": parts[1]})
    except Exception:
        pass
    return commits


def get_git_stats(since="7 days ago", repo_dir=None):
    """Get git diff stats."""
    cwd = str(repo_dir) if repo_dir and repo_dir.exists() else None
    try:
        result = subprocess.run(
            ["git", "diff", "--stat", f"HEAD~20", "HEAD"],
            capture_output=True, text=True, timeout=10, cwd=cwd
        )
        last_line = result.stdout.strip().split("\n")[-1] if result.stdout.strip() else ""
        # Parse "X files changed, Y insertions(+), Z deletions(-)"
        files = insertions = deletions = 0
        m = re.search(r'(\d+) files? changed', last_line)
        if m:
            files = int(m.group(1))
        m = re.search(r'(\d+) insertions?', last_line)
        if m:
            insertions = int(m.group(1))
        m = re.search(r'(\d+) deletions?', last_line)
        if m:
            deletions = int(m.group(1))
        return {"files_changed": files, "insertions": insertions, "deletions": deletions}
    except Exception:
        return {"files_changed": 0, "insertions": 0, "deletions": 0}


def categorize_commits(commits):
    """Categorize commits by type."""
    categories = defaultdict(list)
    for c in commits:
        msg = c["message"].lower()
        if any(kw in msg for kw in ["feat", "add", "new", "ajout", "nouveau"]):
            categories["features"].append(c)
        elif any(kw in msg for kw in ["fix", "bug", "corrig", "repair"]):
            categories["fixes"].append(c)
        elif any(kw in msg for kw in ["refactor", "clean", "reorgan"]):
            categories["refactor"].append(c)
        elif any(kw in msg for kw in ["test", "spec"]):
            categories["tests"].append(c)
        elif any(kw in msg for kw in ["doc", "readme", "comment"]):
            categories["docs"].append(c)
        else:
            categories["other"].append(c)
    return dict(categories)


def generate_changelog(since="7 days ago", fmt="json"):
    """Generate changelog."""
    db = init_db()

    # Try turbo repo first, then current dir
    commits = get_git_log(since, TURBO_DIR)
    stats = get_git_stats(since, TURBO_DIR)

    if not commits:
        commits = get_git_log(since)
        stats = get_git_stats(since)

    categories = categorize_commits(commits)

    changelog = {
        "ts": datetime.now().isoformat(),
        "since": since,
        "total_commits": len(commits),
        "stats": stats,
        "categories": {
            cat: [{"hash": c["hash"], "msg": c["message"]} for c in items]
            for cat, items in categories.items()
        },
        "summary": {
            "features": len(categories.get("features", [])),
            "fixes": len(categories.get("fixes", [])),
            "refactor": len(categories.get("refactor", [])),
            "tests": len(categories.get("tests", [])),
            "docs": len(categories.get("docs", [])),
            "other": len(categories.get("other", [])),
        },
    }

    db.execute(
        "INSERT INTO changelogs (ts, since_date, commits, features, fixes, content) VALUES (?,?,?,?,?,?)",
        (time.time(), since, len(commits),
         len(categories.get("features", [])), len(categories.get("fixes", [])),
         json.dumps(changelog))
    )
    db.commit()
    db.close()

    if fmt == "md":
        md = f"# CHANGELOG — {since}\n\n"
        for cat, items in categories.items():
            md += f"\n## {cat.title()} ({len(items)})\n"
            for c in items:
                md += f"- `{c['hash']}` {c['message']}\n"
        md += f"\n---\nStats: {stats['files_changed']} files, +{stats['insertions']}/-{stats['deletions']}\n"
        return md

    return changelog


def main():
    parser = argparse.ArgumentParser(description="JARVIS Changelog Generator")
    parser.add_argument("--once", "--generate", action="store_true", help="Generate changelog")
    parser.add_argument("--since", metavar="DATE", default="7 days ago", help="Since date")
    parser.add_argument("--format", metavar="FMT", choices=["json", "md"], default="json", help="Output format")
    args = parser.parse_args()

    result = generate_changelog(args.since, args.format)
    if isinstance(result, str):
        print(result)
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
