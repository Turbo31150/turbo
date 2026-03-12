#!/usr/bin/env python3
"""jarvis_release_manager.py — Release manager for JARVIS.
Generates changelogs from git log, version bumping, git tagging.
Usage: python dev/jarvis_release_manager.py --prepare --once
"""
import argparse
import json
import os
import re
import sqlite3
import subprocess
import time
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "release_manager.db"


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS checks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL,
        action TEXT,
        report TEXT
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS releases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL,
        version TEXT,
        tag TEXT,
        changelog TEXT,
        commit_count INTEGER,
        status TEXT DEFAULT 'prepared'
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS changelogs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        release_id INTEGER,
        ts REAL,
        content TEXT,
        commit_hashes TEXT,
        FOREIGN KEY (release_id) REFERENCES releases(id)
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS deployments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        release_id INTEGER,
        ts REAL,
        target TEXT,
        status TEXT,
        log TEXT,
        FOREIGN KEY (release_id) REFERENCES releases(id)
    )""")
    db.commit()
    return db


def _run_git(args_list, cwd=None):
    """Run a git command and return stdout."""
    try:
        r = subprocess.run(
            ["git"] + args_list,
            capture_output=True, text=True, timeout=30,
            cwd=cwd or str(DEV.parent)
        )
        return r.stdout.strip(), r.returncode
    except Exception as e:
        return str(e), 1


def _get_current_version():
    """Get current version from git tags."""
    stdout, rc = _run_git(["describe", "--tags", "--abbrev=0"])
    if rc == 0 and stdout:
        return stdout.strip()
    return "v0.0.0"


def _bump_version(version, bump_type="patch"):
    """Bump version number."""
    match = re.match(r'v?(\d+)\.(\d+)\.(\d+)', version)
    if not match:
        return "v1.0.0"
    major, minor, patch = int(match.group(1)), int(match.group(2)), int(match.group(3))
    if bump_type == "major":
        major += 1
        minor = 0
        patch = 0
    elif bump_type == "minor":
        minor += 1
        patch = 0
    else:
        patch += 1
    return f"v{major}.{minor}.{patch}"


def do_prepare(bump_type="patch"):
    """Prepare a new release: analyze commits, generate changelog, bump version."""
    db = init_db()
    current = _get_current_version()
    new_version = _bump_version(current, bump_type)

    # Get commits since last tag
    stdout, rc = _run_git(["log", f"{current}..HEAD", "--oneline", "--no-decorate"])
    if rc != 0 or not stdout:
        # Fallback: last 20 commits
        stdout, rc = _run_git(["log", "-20", "--oneline", "--no-decorate"])

    commits = []
    if stdout:
        for line in stdout.strip().split("\n"):
            parts = line.split(" ", 1)
            if len(parts) == 2:
                commits.append({"hash": parts[0], "message": parts[1]})

    # Categorize commits
    categories = {"feat": [], "fix": [], "refactor": [], "docs": [], "test": [], "other": []}
    for c in commits:
        msg = c["message"].lower()
        if any(kw in msg for kw in ["feat", "add", "new", "implement"]):
            categories["feat"].append(c)
        elif any(kw in msg for kw in ["fix", "bug", "patch", "repair"]):
            categories["fix"].append(c)
        elif any(kw in msg for kw in ["refactor", "clean", "simplif"]):
            categories["refactor"].append(c)
        elif any(kw in msg for kw in ["doc", "readme", "comment"]):
            categories["docs"].append(c)
        elif any(kw in msg for kw in ["test", "spec"]):
            categories["test"].append(c)
        else:
            categories["other"].append(c)

    # Generate changelog text
    changelog_lines = [f"# Changelog {new_version}\n"]
    changelog_lines.append(f"Released: {datetime.now().strftime('%Y-%m-%d')}\n")
    for cat, items in categories.items():
        if items:
            changelog_lines.append(f"\n## {cat.capitalize()}")
            for item in items:
                changelog_lines.append(f"- {item['message']} ({item['hash']})")
    changelog = "\n".join(changelog_lines)

    # Save release
    cur = db.execute(
        "INSERT INTO releases (ts, version, tag, changelog, commit_count, status) VALUES (?,?,?,?,?,?)",
        (time.time(), new_version, new_version, changelog, len(commits), "prepared")
    )
    release_id = cur.lastrowid

    db.execute(
        "INSERT INTO changelogs (release_id, ts, content, commit_hashes) VALUES (?,?,?,?)",
        (release_id, time.time(), changelog, json.dumps([c["hash"] for c in commits]))
    )
    db.commit()

    result = {
        "ts": datetime.now().isoformat(),
        "action": "prepare",
        "release_id": release_id,
        "current_version": current,
        "new_version": new_version,
        "bump_type": bump_type,
        "total_commits": len(commits),
        "categories": {k: len(v) for k, v in categories.items()},
        "changelog_preview": changelog[:500],
        "status": "prepared"
    }
    db.execute("INSERT INTO checks (ts, action, report) VALUES (?,?,?)",
               (time.time(), "prepare", json.dumps({"version": new_version})))
    db.commit()
    db.close()
    return result


def do_changelog():
    """Show the latest changelog."""
    db = init_db()
    cur = db.execute(
        "SELECT r.version, r.commit_count, c.content FROM releases r JOIN changelogs c ON c.release_id = r.id ORDER BY r.id DESC LIMIT 1"
    )
    row = cur.fetchone()
    if not row:
        return {"ts": datetime.now().isoformat(), "action": "changelog", "error": "no releases prepared"}

    # Also show recent git log
    stdout, _ = _run_git(["log", "-10", "--oneline", "--no-decorate"])

    result = {
        "ts": datetime.now().isoformat(),
        "action": "changelog",
        "version": row[0],
        "commits_in_release": row[1],
        "changelog": row[2],
        "recent_git_log": stdout.split("\n")[:10] if stdout else []
    }
    db.execute("INSERT INTO checks (ts, action, report) VALUES (?,?,?)",
               (time.time(), "changelog", json.dumps({"version": row[0]})))
    db.commit()
    db.close()
    return result


def do_tag(version):
    """Create a git tag for the given version."""
    db = init_db()
    # Check if tag already exists
    stdout, rc = _run_git(["tag", "-l", version])
    if stdout.strip() == version:
        return {"ts": datetime.now().isoformat(), "action": "tag", "error": f"Tag {version} already exists"}

    # Create tag
    stdout, rc = _run_git(["tag", "-a", version, "-m", f"Release {version}"])
    if rc != 0:
        return {"ts": datetime.now().isoformat(), "action": "tag", "error": f"Failed to create tag: {stdout}"}

    # Update release status
    db.execute("UPDATE releases SET status='tagged' WHERE version=?", (version,))
    db.commit()

    result = {
        "ts": datetime.now().isoformat(),
        "action": "tag",
        "version": version,
        "created": True,
        "message": f"Tag {version} created. Use 'git push --tags' to push."
    }
    db.execute("INSERT INTO checks (ts, action, report) VALUES (?,?,?)",
               (time.time(), "tag", json.dumps({"version": version})))
    db.commit()
    db.close()
    return result


def do_deploy():
    """Show deployment readiness and steps."""
    db = init_db()
    cur = db.execute(
        "SELECT id, version, tag, commit_count, status FROM releases ORDER BY id DESC LIMIT 1"
    )
    release = cur.fetchone()
    if not release:
        return {"ts": datetime.now().isoformat(), "action": "deploy", "error": "no releases found"}

    # Check git status
    stdout_status, _ = _run_git(["status", "--short"])
    is_clean = not bool(stdout_status.strip())

    # Check if tag exists
    stdout_tag, _ = _run_git(["tag", "-l", release[2]])
    tag_exists = bool(stdout_tag.strip())

    steps = []
    if not is_clean:
        steps.append("WARN: Working directory has uncommitted changes")
    if not tag_exists:
        steps.append(f"Create tag: git tag -a {release[2]} -m 'Release {release[2]}'")
    steps.append(f"Push tag: git push origin {release[2]}")
    steps.append("Push commits: git push")

    result = {
        "ts": datetime.now().isoformat(),
        "action": "deploy",
        "release_id": release[0],
        "version": release[1],
        "tag": release[2],
        "commits": release[3],
        "status": release[4],
        "working_dir_clean": is_clean,
        "tag_exists": tag_exists,
        "deploy_steps": steps
    }
    db.execute("INSERT INTO checks (ts, action, report) VALUES (?,?,?)",
               (time.time(), "deploy", json.dumps({"version": release[1]})))
    db.commit()
    db.close()
    return result


def main():
    parser = argparse.ArgumentParser(description="Release manager for JARVIS")
    parser.add_argument("--prepare", action="store_true", help="Prepare a new release")
    parser.add_argument("--changelog", action="store_true", help="Show latest changelog")
    parser.add_argument("--tag", type=str, metavar="VERSION", help="Create git tag for version")
    parser.add_argument("--deploy", action="store_true", help="Show deployment steps")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    args = parser.parse_args()

    if args.prepare:
        print(json.dumps(do_prepare(), ensure_ascii=False, indent=2))
    elif args.changelog:
        print(json.dumps(do_changelog(), ensure_ascii=False, indent=2))
    elif args.tag:
        print(json.dumps(do_tag(args.tag), ensure_ascii=False, indent=2))
    elif args.deploy:
        print(json.dumps(do_deploy(), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(do_deploy(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
