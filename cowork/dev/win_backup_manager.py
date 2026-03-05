#!/usr/bin/env python3
"""win_backup_manager.py — Backup manager. Backs up DBs + configs to dev/data/backups/. SHA256 verification.
Usage: python dev/win_backup_manager.py --backup --once
"""
import argparse, json, os, sqlite3, subprocess, time, hashlib, shutil
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "backup_manager_v2.db"
BACKUP_DIR = DEV / "data" / "backups"

# Files to back up
BACKUP_TARGETS = {
    "databases": ["data/*.db"],
    "configs": ["*.json", "*.yaml", "*.yml", "*.toml", "*.ini"],
    "scripts": ["*.py"],
}


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS backups (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL,
        backup_dir TEXT,
        files_count INTEGER,
        total_size_bytes INTEGER,
        status TEXT DEFAULT 'completed'
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS backup_files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        backup_id INTEGER,
        source_path TEXT,
        backup_path TEXT,
        size_bytes INTEGER,
        sha256 TEXT,
        verified INTEGER DEFAULT 0
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS schedules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL,
        interval_hours REAL,
        last_run REAL,
        active INTEGER DEFAULT 1
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS verifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL,
        backup_id INTEGER,
        total_files INTEGER,
        verified_ok INTEGER,
        verified_fail INTEGER
    )""")
    db.commit()
    return db


def compute_sha256(filepath):
    """Compute SHA256 hash of a file."""
    h = hashlib.sha256()
    try:
        with open(filepath, "rb") as f:
            while True:
                chunk = f.read(65536)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()
    except (PermissionError, OSError):
        return None


def do_backup():
    """Create a full backup of databases and configs."""
    db = init_db()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_subdir = BACKUP_DIR / timestamp
    backup_subdir.mkdir(parents=True, exist_ok=True)

    files_backed_up = []
    total_size = 0

    # Create backup record
    backup_id = db.execute(
        "INSERT INTO backups (ts, backup_dir, files_count, total_size_bytes, status) VALUES (?,?,?,?,?)",
        (time.time(), str(backup_subdir), 0, 0, "in_progress")
    ).lastrowid

    # Backup databases
    data_dir = DEV / "data"
    if data_dir.exists():
        for db_file in data_dir.glob("*.db"):
            if db_file.name == "backup_manager_v2.db":
                continue  # Skip own DB
            try:
                dest = backup_subdir / "data" / db_file.name
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(db_file), str(dest))
                size = db_file.stat().st_size
                sha = compute_sha256(str(dest))
                total_size += size
                files_backed_up.append({
                    "source": str(db_file),
                    "backup": str(dest),
                    "size": size,
                    "sha256": sha
                })
                db.execute(
                    "INSERT INTO backup_files (backup_id, source_path, backup_path, size_bytes, sha256) VALUES (?,?,?,?,?)",
                    (backup_id, str(db_file), str(dest), size, sha)
                )
            except Exception as e:
                files_backed_up.append({"source": str(db_file), "error": str(e)})

    # Backup config files
    for pattern in BACKUP_TARGETS["configs"]:
        for cfg_file in DEV.glob(pattern):
            try:
                dest = backup_subdir / "configs" / cfg_file.name
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(cfg_file), str(dest))
                size = cfg_file.stat().st_size
                sha = compute_sha256(str(dest))
                total_size += size
                files_backed_up.append({
                    "source": str(cfg_file),
                    "backup": str(dest),
                    "size": size,
                    "sha256": sha
                })
                db.execute(
                    "INSERT INTO backup_files (backup_id, source_path, backup_path, size_bytes, sha256) VALUES (?,?,?,?,?)",
                    (backup_id, str(cfg_file), str(dest), size, sha)
                )
            except Exception as e:
                files_backed_up.append({"source": str(cfg_file), "error": str(e)})

    # Update backup record
    db.execute(
        "UPDATE backups SET files_count=?, total_size_bytes=?, status=? WHERE id=?",
        (len([f for f in files_backed_up if "error" not in f]), total_size, "completed", backup_id)
    )
    db.commit()
    db.close()

    return {
        "ts": datetime.now().isoformat(),
        "action": "backup",
        "backup_id": backup_id,
        "backup_dir": str(backup_subdir),
        "files_backed_up": len([f for f in files_backed_up if "error" not in f]),
        "errors": len([f for f in files_backed_up if "error" in f]),
        "total_size_mb": round(total_size / (1024 * 1024), 2),
        "files": [
            {"file": os.path.basename(f.get("source", "")), "size": f.get("size", 0),
             "sha256": f.get("sha256", "")[:16] + "..." if f.get("sha256") else None,
             "error": f.get("error")}
            for f in files_backed_up[:20]
        ]
    }


def do_restore():
    """List available backups for restore."""
    db = init_db()
    rows = db.execute(
        "SELECT id, ts, backup_dir, files_count, total_size_bytes, status FROM backups ORDER BY ts DESC LIMIT 10"
    ).fetchall()
    db.close()

    backups = []
    for r in rows:
        backup_dir = Path(r[2])
        exists = backup_dir.exists()
        backups.append({
            "id": r[0],
            "ts": datetime.fromtimestamp(r[1]).isoformat(),
            "dir": r[2],
            "files": r[3],
            "size_mb": round(r[4] / (1024 * 1024), 2),
            "status": r[5],
            "exists": exists
        })

    return {
        "ts": datetime.now().isoformat(),
        "action": "restore",
        "available_backups": len(backups),
        "backups": backups,
        "note": "Use backup_dir path to manually restore files"
    }


def do_schedule():
    """Show/set backup schedule."""
    db = init_db()
    rows = db.execute(
        "SELECT id, interval_hours, last_run, active FROM schedules ORDER BY id DESC LIMIT 5"
    ).fetchall()

    if not rows:
        # Create default schedule
        db.execute(
            "INSERT INTO schedules (ts, interval_hours, last_run, active) VALUES (?,?,?,?)",
            (time.time(), 24.0, 0, 1)
        )
        db.commit()
        rows = db.execute(
            "SELECT id, interval_hours, last_run, active FROM schedules ORDER BY id DESC LIMIT 5"
        ).fetchall()

    db.close()
    return {
        "ts": datetime.now().isoformat(),
        "action": "schedule",
        "schedules": [
            {
                "id": r[0],
                "interval_hours": r[1],
                "last_run": datetime.fromtimestamp(r[2]).isoformat() if r[2] > 0 else "never",
                "active": bool(r[3])
            }
            for r in rows
        ]
    }


def do_verify():
    """Verify the latest backup with SHA256 checksums."""
    db = init_db()
    backup = db.execute(
        "SELECT id, backup_dir FROM backups WHERE status='completed' ORDER BY ts DESC LIMIT 1"
    ).fetchone()

    if not backup:
        db.close()
        return {"ts": datetime.now().isoformat(), "action": "verify", "status": "no_backups"}

    backup_id = backup[0]
    files = db.execute(
        "SELECT id, source_path, backup_path, sha256 FROM backup_files WHERE backup_id=?",
        (backup_id,)
    ).fetchall()

    verified_ok = 0
    verified_fail = 0
    results = []

    for fid, source, backup_path, expected_sha in files:
        if not Path(backup_path).exists():
            verified_fail += 1
            results.append({"file": os.path.basename(source), "status": "missing"})
            continue

        actual_sha = compute_sha256(backup_path)
        if actual_sha == expected_sha:
            verified_ok += 1
            db.execute("UPDATE backup_files SET verified=1 WHERE id=?", (fid,))
            results.append({"file": os.path.basename(source), "status": "ok"})
        else:
            verified_fail += 1
            results.append({
                "file": os.path.basename(source), "status": "mismatch",
                "expected": expected_sha[:16] + "..." if expected_sha else None,
                "actual": actual_sha[:16] + "..." if actual_sha else None
            })

    db.execute(
        "INSERT INTO verifications (ts, backup_id, total_files, verified_ok, verified_fail) VALUES (?,?,?,?,?)",
        (time.time(), backup_id, len(files), verified_ok, verified_fail)
    )
    db.commit()
    db.close()

    return {
        "ts": datetime.now().isoformat(),
        "action": "verify",
        "backup_id": backup_id,
        "total_files": len(files),
        "verified_ok": verified_ok,
        "verified_fail": verified_fail,
        "integrity": "ok" if verified_fail == 0 else "corrupted",
        "results": results[:20]
    }


def main():
    parser = argparse.ArgumentParser(description="Backup manager — DB/config backup with SHA256 verification")
    parser.add_argument("--backup", action="store_true", help="Create a full backup")
    parser.add_argument("--restore", action="store_true", help="List available backups for restore")
    parser.add_argument("--schedule", action="store_true", help="Show/set backup schedule")
    parser.add_argument("--verify", action="store_true", help="Verify latest backup integrity")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    args = parser.parse_args()

    if args.backup:
        result = do_backup()
    elif args.restore:
        result = do_restore()
    elif args.schedule:
        result = do_schedule()
    elif args.verify:
        result = do_verify()
    else:
        result = {
            "ts": datetime.now().isoformat(),
            "status": "ok",
            "db": str(DB_PATH),
            "backup_dir": str(BACKUP_DIR),
            "help": "Use --backup / --restore / --schedule / --verify"
        }

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
