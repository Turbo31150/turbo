#!/usr/bin/env python3
"""win_file_watcher.py (#196) — File change detector.

Uses os.scandir snapshots, compares mtime+size to detect created/modified/deleted files.
Supports glob pattern filtering.

Usage:
    python dev/win_file_watcher.py --once
    python dev/win_file_watcher.py --watch "C:/Users/franc/.openclaw/workspace/dev"
    python dev/win_file_watcher.py --patterns "*.py,*.json"
    python dev/win_file_watcher.py --history
"""
import argparse
import fnmatch
import json
import os
import sqlite3
import time
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "file_watcher.db"

DEFAULT_WATCH_DIR = str(DEV)
DEFAULT_PATTERNS = ["*.py", "*.json", "*.md", "*.yaml", "*.yml", "*.toml", "*.cfg"]


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL,
        directory TEXT,
        file_count INTEGER,
        total_size INTEGER
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS file_entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        snapshot_id INTEGER,
        path TEXT,
        name TEXT,
        size INTEGER,
        mtime REAL,
        is_dir INTEGER DEFAULT 0,
        FOREIGN KEY (snapshot_id) REFERENCES snapshots(id)
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS changes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL,
        directory TEXT,
        change_type TEXT,
        path TEXT,
        name TEXT,
        old_size INTEGER,
        new_size INTEGER,
        old_mtime REAL,
        new_mtime REAL
    )""")
    db.commit()
    return db


def scan_directory(directory, patterns=None, recursive=False):
    """Scan a directory and return file info dict."""
    files = {}
    try:
        if recursive:
            for root, dirs, filenames in os.walk(directory):
                for name in filenames:
                    full = os.path.join(root, name)
                    if patterns and not any(fnmatch.fnmatch(name, p) for p in patterns):
                        continue
                    try:
                        stat = os.stat(full)
                        files[full] = {
                            "name": name,
                            "size": stat.st_size,
                            "mtime": stat.st_mtime
                        }
                    except OSError:
                        pass
        else:
            with os.scandir(directory) as entries:
                for entry in entries:
                    if entry.is_file():
                        if patterns and not any(fnmatch.fnmatch(entry.name, p) for p in patterns):
                            continue
                        try:
                            stat = entry.stat()
                            files[entry.path] = {
                                "name": entry.name,
                                "size": stat.st_size,
                                "mtime": stat.st_mtime
                            }
                        except OSError:
                            pass
    except PermissionError:
        pass

    return files


def save_snapshot(db, directory, files):
    """Save a directory snapshot to DB."""
    total_size = sum(f["size"] for f in files.values())
    cur = db.execute(
        "INSERT INTO snapshots (ts, directory, file_count, total_size) VALUES (?,?,?,?)",
        (time.time(), directory, len(files), total_size)
    )
    snap_id = cur.lastrowid

    for path, info in files.items():
        db.execute(
            "INSERT INTO file_entries (snapshot_id, path, name, size, mtime) VALUES (?,?,?,?,?)",
            (snap_id, path, info["name"], info["size"], info["mtime"])
        )

    db.commit()
    return snap_id


def get_last_snapshot(db, directory):
    """Get the most recent snapshot for a directory."""
    row = db.execute(
        "SELECT id FROM snapshots WHERE directory=? ORDER BY ts DESC LIMIT 1",
        (directory,)
    ).fetchone()

    if not row:
        return None, {}

    snap_id = row[0]
    rows = db.execute(
        "SELECT path, name, size, mtime FROM file_entries WHERE snapshot_id=?",
        (snap_id,)
    ).fetchall()

    files = {}
    for r in rows:
        files[r[0]] = {"name": r[1], "size": r[2], "mtime": r[3]}

    return snap_id, files


def detect_changes(old_files, new_files):
    """Compare two snapshots and detect changes."""
    changes = []
    old_paths = set(old_files.keys())
    new_paths = set(new_files.keys())

    # Created
    for p in new_paths - old_paths:
        changes.append({
            "type": "created",
            "path": p,
            "name": new_files[p]["name"],
            "new_size": new_files[p]["size"],
            "new_mtime": new_files[p]["mtime"]
        })

    # Deleted
    for p in old_paths - new_paths:
        changes.append({
            "type": "deleted",
            "path": p,
            "name": old_files[p]["name"],
            "old_size": old_files[p]["size"],
            "old_mtime": old_files[p]["mtime"]
        })

    # Modified
    for p in old_paths & new_paths:
        old = old_files[p]
        new = new_files[p]
        if old["size"] != new["size"] or abs(old["mtime"] - new["mtime"]) > 0.01:
            changes.append({
                "type": "modified",
                "path": p,
                "name": new["name"],
                "old_size": old["size"],
                "new_size": new["size"],
                "old_mtime": old["mtime"],
                "new_mtime": new["mtime"],
                "size_delta": new["size"] - old["size"]
            })

    return changes


def watch_directory(db, directory, patterns=None):
    """Watch a directory: scan, compare with last snapshot, report changes."""
    directory = os.path.abspath(directory)
    if not os.path.isdir(directory):
        return {"status": "error", "error": f"Not a directory: {directory}"}

    if patterns is None:
        patterns = DEFAULT_PATTERNS

    # Scan current state
    current_files = scan_directory(directory, patterns)

    # Get last snapshot
    _, old_files = get_last_snapshot(db, directory)

    # Detect changes
    changes = detect_changes(old_files, current_files)

    # Save new snapshot
    snap_id = save_snapshot(db, directory, current_files)

    # Log changes
    now = time.time()
    for ch in changes:
        db.execute(
            """INSERT INTO changes (ts, directory, change_type, path, name,
               old_size, new_size, old_mtime, new_mtime) VALUES (?,?,?,?,?,?,?,?,?)""",
            (now, directory, ch["type"], ch["path"], ch["name"],
             ch.get("old_size"), ch.get("new_size"),
             ch.get("old_mtime"), ch.get("new_mtime"))
        )
    db.commit()

    return {
        "status": "ok",
        "directory": directory,
        "files_scanned": len(current_files),
        "previous_files": len(old_files),
        "snapshot_id": snap_id,
        "changes": {
            "total": len(changes),
            "created": len([c for c in changes if c["type"] == "created"]),
            "modified": len([c for c in changes if c["type"] == "modified"]),
            "deleted": len([c for c in changes if c["type"] == "deleted"]),
            "details": changes[:50]  # Limit output
        },
        "patterns": patterns
    }


def list_patterns():
    """Show default patterns."""
    return {
        "status": "ok",
        "default_patterns": DEFAULT_PATTERNS,
        "common_patterns": {
            "code": ["*.py", "*.js", "*.ts", "*.rs", "*.go"],
            "config": ["*.json", "*.yaml", "*.yml", "*.toml", "*.cfg", "*.ini"],
            "docs": ["*.md", "*.txt", "*.rst"],
            "data": ["*.db", "*.sqlite", "*.csv"]
        }
    }


def get_history(db, limit=50):
    """Get recent file changes."""
    rows = db.execute(
        """SELECT ts, directory, change_type, name, old_size, new_size
           FROM changes ORDER BY ts DESC LIMIT ?""",
        (limit,)
    ).fetchall()

    history = []
    for r in rows:
        entry = {
            "time": datetime.fromtimestamp(r[0]).isoformat(),
            "directory": r[1],
            "type": r[2],
            "name": r[3]
        }
        if r[2] == "modified" and r[4] is not None and r[5] is not None:
            entry["size_delta"] = r[5] - r[4]
        history.append(entry)

    # Stats
    by_type = {}
    for r in rows:
        by_type[r[2]] = by_type.get(r[2], 0) + 1

    return {
        "status": "ok",
        "count": len(history),
        "by_type": by_type,
        "history": history
    }


def once(db):
    """Run once: watch default dir."""
    result = watch_directory(db, DEFAULT_WATCH_DIR)
    total_changes = db.execute("SELECT COUNT(*) FROM changes").fetchone()[0]
    total_snapshots = db.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0]
    result["mode"] = "once"
    result["total_changes_logged"] = total_changes
    result["total_snapshots"] = total_snapshots
    return result


def main():
    parser = argparse.ArgumentParser(description="File Watcher (#196) — File change detection")
    parser.add_argument("--watch", type=str, nargs="?", const=DEFAULT_WATCH_DIR,
                        help="Watch a directory for changes")
    parser.add_argument("--patterns", type=str, help="Comma-separated glob patterns")
    parser.add_argument("--history", action="store_true", help="Show change history")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    args = parser.parse_args()

    db = init_db()

    patterns = None
    if args.patterns:
        patterns = [p.strip() for p in args.patterns.split(",")]

    if args.watch:
        result = watch_directory(db, args.watch, patterns)
    elif args.history:
        result = get_history(db)
    elif args.patterns and not args.watch:
        result = list_patterns()
    elif args.once:
        result = once(db)
    else:
        parser.print_help()
        return

    print(json.dumps(result, indent=2, default=str))
    db.close()


if __name__ == "__main__":
    main()
