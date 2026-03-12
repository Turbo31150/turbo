#!/usr/bin/env python3
"""win_file_watcher_v2.py — File watcher v2. Enhanced os.scandir with recursive, event queue, pattern matching.
Usage: python dev/win_file_watcher_v2.py --watch DIR --once
"""
import argparse, json, os, sqlite3, subprocess, time, hashlib, fnmatch, re
from datetime import datetime
from pathlib import Path
from collections import deque

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "file_watcher_v2.db"


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL,
        directory TEXT,
        total_files INTEGER,
        total_dirs INTEGER,
        total_size_bytes INTEGER
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS file_entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        snapshot_id INTEGER,
        filepath TEXT,
        size INTEGER,
        mtime REAL,
        sha256 TEXT,
        is_dir INTEGER DEFAULT 0
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL,
        event_type TEXT,
        filepath TEXT,
        old_size INTEGER,
        new_size INTEGER,
        details TEXT
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS actions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL,
        event_id INTEGER,
        action_type TEXT,
        filepath TEXT,
        result TEXT
    )""")
    db.commit()
    return db


def scan_directory(directory, recursive=True, patterns=None):
    """Scan directory with os.scandir, optionally recursive."""
    files = []
    dirs = []
    total_size = 0

    def _scan(path, depth=0):
        nonlocal total_size
        if depth > 10:  # Max recursion depth
            return
        try:
            with os.scandir(path) as entries:
                for entry in entries:
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            dirs.append({
                                "path": entry.path,
                                "name": entry.name,
                                "mtime": entry.stat().st_mtime
                            })
                            if recursive:
                                _scan(entry.path, depth + 1)
                        elif entry.is_file(follow_symlinks=False):
                            # Pattern filtering
                            if patterns:
                                matched = any(fnmatch.fnmatch(entry.name, p) for p in patterns)
                                if not matched:
                                    continue

                            stat = entry.stat()
                            total_size += stat.st_size
                            files.append({
                                "path": entry.path,
                                "name": entry.name,
                                "size": stat.st_size,
                                "mtime": stat.st_mtime,
                            })
                    except (PermissionError, OSError):
                        continue
        except (PermissionError, OSError):
            pass

    _scan(str(directory))
    return files, dirs, total_size


def compute_file_hash(filepath, block_size=65536):
    """Compute SHA256 hash of a file."""
    try:
        h = hashlib.sha256()
        with open(filepath, "rb") as f:
            while True:
                block = f.read(block_size)
                if not block:
                    break
                h.update(block)
        return h.hexdigest()
    except (PermissionError, OSError):
        return None


def do_watch(directory, patterns=None):
    """Take a snapshot of a directory and detect changes."""
    db = init_db()
    target = Path(directory)
    if not target.exists():
        db.close()
        return {"ts": datetime.now().isoformat(), "error": f"Directory not found: {directory}"}

    pattern_list = patterns.split(",") if patterns else None
    files, dirs, total_size = scan_directory(target, recursive=True, patterns=pattern_list)

    # Create snapshot
    snapshot_id = db.execute(
        "INSERT INTO snapshots (ts, directory, total_files, total_dirs, total_size_bytes) VALUES (?,?,?,?,?)",
        (time.time(), str(target), len(files), len(dirs), total_size)
    ).lastrowid

    # Store file entries (limit to first 500)
    for f in files[:500]:
        db.execute(
            "INSERT INTO file_entries (snapshot_id, filepath, size, mtime, is_dir) VALUES (?,?,?,?,?)",
            (snapshot_id, f["path"], f["size"], f["mtime"], 0)
        )

    # Compare with previous snapshot
    prev_snapshot = db.execute(
        "SELECT id FROM snapshots WHERE directory=? AND id < ? ORDER BY id DESC LIMIT 1",
        (str(target), snapshot_id)
    ).fetchone()

    events_detected = []
    if prev_snapshot:
        prev_id = prev_snapshot[0]
        prev_files = {
            r[0]: {"size": r[1], "mtime": r[2]}
            for r in db.execute(
                "SELECT filepath, size, mtime FROM file_entries WHERE snapshot_id=?", (prev_id,)
            ).fetchall()
        }
        curr_files = {f["path"]: {"size": f["size"], "mtime": f["mtime"]} for f in files}

        # New files
        for path in curr_files:
            if path not in prev_files:
                events_detected.append({"type": "created", "path": path})
                db.execute(
                    "INSERT INTO events (ts, event_type, filepath, new_size) VALUES (?,?,?,?)",
                    (time.time(), "created", path, curr_files[path]["size"])
                )

        # Deleted files
        for path in prev_files:
            if path not in curr_files:
                events_detected.append({"type": "deleted", "path": path})
                db.execute(
                    "INSERT INTO events (ts, event_type, filepath, old_size) VALUES (?,?,?,?)",
                    (time.time(), "deleted", path, prev_files[path]["size"])
                )

        # Modified files
        for path in curr_files:
            if path in prev_files:
                if curr_files[path]["mtime"] != prev_files[path]["mtime"]:
                    events_detected.append({
                        "type": "modified", "path": path,
                        "old_size": prev_files[path]["size"],
                        "new_size": curr_files[path]["size"]
                    })
                    db.execute(
                        "INSERT INTO events (ts, event_type, filepath, old_size, new_size) VALUES (?,?,?,?,?)",
                        (time.time(), "modified", path, prev_files[path]["size"], curr_files[path]["size"])
                    )

    db.commit()
    db.close()

    return {
        "ts": datetime.now().isoformat(),
        "action": "watch",
        "directory": str(target),
        "snapshot_id": snapshot_id,
        "total_files": len(files),
        "total_dirs": len(dirs),
        "total_size_mb": round(total_size / (1024 * 1024), 2),
        "events_detected": len(events_detected),
        "events": events_detected[:20],
        "largest_files": sorted(files, key=lambda x: x["size"], reverse=True)[:5],
        "patterns": pattern_list
    }


def do_events():
    """Show recent file events."""
    db = init_db()
    rows = db.execute(
        "SELECT ts, event_type, filepath, old_size, new_size FROM events ORDER BY ts DESC LIMIT 30"
    ).fetchall()
    db.close()

    return {
        "ts": datetime.now().isoformat(),
        "total_events": len(rows),
        "events": [
            {
                "ts": datetime.fromtimestamp(r[0]).isoformat(),
                "type": r[1],
                "file": os.path.basename(r[2]),
                "path": r[2],
                "old_size": r[3],
                "new_size": r[4]
            }
            for r in rows
        ]
    }


def do_actions():
    """Show action history."""
    db = init_db()
    rows = db.execute(
        "SELECT ts, action_type, filepath, result FROM actions ORDER BY ts DESC LIMIT 20"
    ).fetchall()
    db.close()

    return {
        "ts": datetime.now().isoformat(),
        "total_actions": len(rows),
        "actions": [
            {
                "ts": datetime.fromtimestamp(r[0]).isoformat(),
                "action": r[1],
                "file": os.path.basename(r[2]) if r[2] else "",
                "result": r[3]
            }
            for r in rows
        ]
    }


def do_history():
    """Show snapshot history."""
    db = init_db()
    rows = db.execute(
        "SELECT id, ts, directory, total_files, total_dirs, total_size_bytes FROM snapshots ORDER BY ts DESC LIMIT 20"
    ).fetchall()
    db.close()

    return {
        "ts": datetime.now().isoformat(),
        "snapshots": [
            {
                "id": r[0],
                "ts": datetime.fromtimestamp(r[1]).isoformat(),
                "directory": r[2],
                "files": r[3],
                "dirs": r[4],
                "size_mb": round(r[5] / (1024 * 1024), 2)
            }
            for r in rows
        ]
    }


def main():
    parser = argparse.ArgumentParser(description="File watcher v2 — Recursive directory monitoring with pattern matching")
    parser.add_argument("--watch", metavar="DIR", help="Watch a directory for changes")
    parser.add_argument("--patterns", metavar="PATS", help="Comma-separated file patterns (e.g., '*.py,*.json')")
    parser.add_argument("--events", action="store_true", help="Show recent file events")
    parser.add_argument("--actions", action="store_true", help="Show action history")
    parser.add_argument("--history", action="store_true", help="Show snapshot history")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    args = parser.parse_args()

    if args.watch:
        result = do_watch(args.watch, args.patterns)
    elif args.events:
        result = do_events()
    elif args.actions:
        result = do_actions()
    elif args.history:
        result = do_history()
    else:
        result = {
            "ts": datetime.now().isoformat(),
            "status": "ok",
            "db": str(DB_PATH),
            "help": "Use --watch DIR / --events / --actions / --history"
        }

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
