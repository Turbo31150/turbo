#!/usr/bin/env python3
"""jarvis_backup_manager.py — Gestionnaire backup JARVIS.

Sauvegarde incrementale de toutes les DB + configs critiques.

Usage:
    python dev/jarvis_backup_manager.py --once
    python dev/jarvis_backup_manager.py --backup
    python dev/jarvis_backup_manager.py --restore DATE
    python dev/jarvis_backup_manager.py --list
"""
import argparse
from _paths import TURBO_DIR, ETOILE_DB, JARVIS_DB, SNIPER_DB
import hashlib
import json
import os
import shutil
import sqlite3
import time
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "backup_manager.db"
BACKUP_DIR = DEV / "data" / "backups"
RETENTION_DAYS = 30

CRITICAL_FILES = {
    "etoile.db": Path(str(ETOILE_DB)),
    "jarvis.db": Path(str(JARVIS_DB)),
    "sniper.db": Path(str(SNIPER_DB)),
    "finetuning.db": TURBO_DIR / "finetuning" / "data" / "finetuning.db",
    "CLAUDE.md": Path.home() / ".claude" / "CLAUDE.md",
    "MEMORY.md": Path.home() / ".claude" / "projects" / "C--Users-franc" / "memory" / "MEMORY.md",
}


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS backups (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, file_name TEXT, original_path TEXT,
        backup_path TEXT, size_bytes INTEGER, sha256 TEXT)""")
    db.commit()
    return db


def file_sha256(path, chunk_size=8192):
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return ""


def do_backup():
    db = init_db()
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    results = []

    for name, src in CRITICAL_FILES.items():
        if not src.exists():
            results.append({"file": name, "status": "NOT_FOUND", "path": str(src)})
            continue

        dst = BACKUP_DIR / f"{ts}_{name}"
        try:
            shutil.copy2(str(src), str(dst))
            size = dst.stat().st_size
            sha = file_sha256(dst)

            db.execute("INSERT INTO backups (ts, file_name, original_path, backup_path, size_bytes, sha256) VALUES (?,?,?,?,?,?)",
                       (time.time(), name, str(src), str(dst), size, sha))

            results.append({
                "file": name,
                "status": "OK",
                "size_kb": round(size / 1024, 1),
                "sha256": sha[:16] + "...",
            })
        except Exception as e:
            results.append({"file": name, "status": "ERROR", "error": str(e)[:100]})

    # Prune old backups
    pruned = 0
    cutoff = time.time() - RETENTION_DAYS * 86400
    for f in BACKUP_DIR.iterdir():
        if f.is_file() and f.stat().st_mtime < cutoff:
            try:
                f.unlink()
                pruned += 1
            except Exception:
                pass

    db.commit()
    db.close()

    return {
        "ts": datetime.now().isoformat(),
        "files_backed_up": sum(1 for r in results if r["status"] == "OK"),
        "files_missing": sum(1 for r in results if r["status"] == "NOT_FOUND"),
        "errors": sum(1 for r in results if r["status"] == "ERROR"),
        "pruned_old": pruned,
        "retention_days": RETENTION_DAYS,
        "details": results,
    }


def do_list():
    db = init_db()
    rows = db.execute(
        "SELECT ts, file_name, size_bytes, sha256 FROM backups ORDER BY ts DESC LIMIT 30"
    ).fetchall()
    db.close()

    return {
        "ts": datetime.now().isoformat(),
        "total_backups": len(rows),
        "backups": [
            {"ts": datetime.fromtimestamp(r[0]).isoformat(), "file": r[1],
             "size_kb": round(r[2] / 1024, 1), "sha256": (r[3] or "")[:16]}
            for r in rows
        ],
    }


def main():
    parser = argparse.ArgumentParser(description="JARVIS Backup Manager")
    parser.add_argument("--once", "--backup", action="store_true", help="Run backup")
    parser.add_argument("--restore", metavar="DATE", help="Restore from date")
    parser.add_argument("--list", action="store_true", help="List backups")
    parser.add_argument("--verify", action="store_true", help="Verify integrity")
    args = parser.parse_args()

    if args.list:
        print(json.dumps(do_list(), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(do_backup(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()