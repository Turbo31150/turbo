#!/usr/bin/env python3
"""Generate a changelog from git log, grouped by date and author.

Runs git log --oneline -50 in F:/BUREAU/turbo, parses commits,
groups by date and author. Saves JSON to data/reports/changelog_YYYYMMDD.json.
Logs execution to etoile.db cowork_execution_log.
"""

import argparse
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ETOILE_DB = Path(r"F:\BUREAU\turbo\etoile.db")
REPO_DIR = Path(r"F:\BUREAU\turbo")
REPORTS_DIR = REPO_DIR / "data" / "reports"


def log_run(db_path: Path, script: str, exit_code: int, duration_ms: float,
            success: bool, stdout_preview: str = "", stderr_preview: str = ""):
    try:
        con = sqlite3.connect(str(db_path))
        con.execute(
            "INSERT INTO cowork_execution_log (script,args,exit_code,duration_ms,success,stdout_preview,stderr_preview)"
            " VALUES (?,?,?,?,?,?,?)",
            (script, "--once", exit_code, duration_ms, int(success),
             stdout_preview[:500], stderr_preview[:500]))
        con.commit()
        con.close()
    except Exception:
        pass


def get_git_log() -> list[dict]:
    """Run git log and parse commits with date, author, hash, message."""
    cmd = ["git", "log", "--format=%H|%ai|%an|%s", "-50"]
    proc = subprocess.run(cmd, cwd=str(REPO_DIR), capture_output=True, text=True, timeout=30)
    if proc.returncode != 0:
        raise RuntimeError(f"git log failed: {proc.stderr.strip()}")

    commits = []
    for line in proc.stdout.strip().splitlines():
        parts = line.split("|", 3)
        if len(parts) < 4:
            continue
        hash_, date_str, author, message = parts
        # Extract date portion (YYYY-MM-DD)
        date_only = date_str.strip()[:10]
        commits.append({
            "hash": hash_[:8],
            "date": date_only,
            "author": author.strip(),
            "message": message.strip(),
        })
    return commits


def group_commits(commits: list[dict]) -> dict:
    """Group commits by date then by author."""
    grouped: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    for c in commits:
        grouped[c["date"]][c["author"]].append({
            "hash": c["hash"],
            "message": c["message"],
        })
    # Convert to regular dict for JSON
    return {
        date: {author: entries for author, entries in authors.items()}
        for date, authors in sorted(grouped.items(), reverse=True)
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.parse_args()

    t0 = time.time()
    try:
        commits = get_git_log()
        grouped = group_commits(commits)

        today = datetime.now().strftime("%Y%m%d")
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        out_file = REPORTS_DIR / f"changelog_{today}.json"

        result = {
            "generated_at": datetime.now().isoformat(),
            "total_commits": len(commits),
            "date_range": {"from": commits[-1]["date"] if commits else None,
                           "to": commits[0]["date"] if commits else None},
            "by_date": grouped,
        }
        output = json.dumps(result, indent=2, ensure_ascii=False)
        out_file.write_text(output, encoding="utf-8")
        print(output)

        duration = (time.time() - t0) * 1000
        log_run(ETOILE_DB, "auto_changelog.py", 0, duration, True,
                f"Saved {out_file.name}, {len(commits)} commits")
    except Exception as exc:
        duration = (time.time() - t0) * 1000
        err = str(exc)
        log_run(ETOILE_DB, "auto_changelog.py", 1, duration, False, stderr_preview=err)
        print(json.dumps({"error": err}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
