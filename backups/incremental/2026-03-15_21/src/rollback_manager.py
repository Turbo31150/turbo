"""JARVIS Rollback Manager — snapshot/restore for safe auto-fixes.

Before any auto-fix, take a snapshot. After fix, verify. If broken, rollback.
Used by auto_heal, auto_improve, and self_diagnostic.

Usage:
    from src.rollback_manager import rollback_manager

    with rollback_manager.safe_fix("db_vacuum", target="etoile.db"):
        conn.execute("VACUUM")
    # Auto-rollback if exception raised inside the block
"""

from __future__ import annotations

import json
import logging
import shutil
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Generator

logger = logging.getLogger("jarvis.rollback")

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
SNAPSHOT_DIR = DATA_DIR / "snapshots"
DB_PATH = DATA_DIR / "rollback.db"


@dataclass
class Snapshot:
    """Represents a point-in-time snapshot before a fix."""
    fix_id: str
    target: str
    timestamp: float
    snapshot_path: str
    metadata: dict = field(default_factory=dict)


class RollbackManager:
    """Manages snapshots and rollbacks for safe auto-fixes."""

    def __init__(self, max_snapshots: int = 50):
        self._max_snapshots = max_snapshots
        SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute("""CREATE TABLE IF NOT EXISTS rollback_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fix_id TEXT, target TEXT, ts TEXT,
            snapshot_path TEXT, status TEXT,
            duration_ms REAL, error TEXT
        )""")
        conn.commit()
        conn.close()

    def snapshot_file(self, file_path: str | Path) -> str | None:
        """Create a backup copy of a file. Returns snapshot path."""
        src = Path(file_path)
        if not src.exists():
            return None
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = SNAPSHOT_DIR / f"{src.stem}_{ts}{src.suffix}"
        shutil.copy2(src, dest)
        logger.info("Snapshot: %s -> %s", src.name, dest.name)
        return str(dest)

    def restore_file(self, snapshot_path: str, original_path: str | Path) -> bool:
        """Restore a file from snapshot."""
        snap = Path(snapshot_path)
        orig = Path(original_path)
        if not snap.exists():
            logger.error("Snapshot not found: %s", snapshot_path)
            return False
        shutil.copy2(snap, orig)
        logger.info("Restored: %s from %s", orig.name, snap.name)
        return True

    @contextmanager
    def safe_fix(
        self, fix_id: str, target: str = "", files: list[str] | None = None
    ) -> Generator[dict, None, None]:
        """Context manager for safe auto-fixes with automatic rollback.

        Usage:
            with rollback_manager.safe_fix("vacuum", target="etoile.db", files=["data/etoile.db"]):
                # do the fix
                pass
            # If exception: auto-rollback + log failure
            # If success: log success + cleanup old snapshots
        """
        t0 = time.time()
        snapshots: dict[str, str] = {}
        context: dict[str, Any] = {"fix_id": fix_id, "target": target, "snapshots": snapshots}

        # Take snapshots
        for f in (files or []):
            snap = self.snapshot_file(f)
            if snap:
                snapshots[f] = snap

        try:
            yield context
            # Success
            duration = (time.time() - t0) * 1000
            self._log(fix_id, target, list(snapshots.values()), "success", duration)
            logger.info("Fix OK: %s (%s) in %.0fms", fix_id, target, duration)
        except Exception as e:
            # Rollback
            duration = (time.time() - t0) * 1000
            logger.warning("Fix FAILED: %s (%s) — rolling back: %s", fix_id, target, e)
            for orig, snap in snapshots.items():
                self.restore_file(snap, orig)
            self._log(fix_id, target, list(snapshots.values()), "rolled_back", duration, str(e))
            # Re-raise so caller knows it failed
            raise

        # Cleanup old snapshots
        self._cleanup_old_snapshots()

    def _log(self, fix_id: str, target: str, paths: list, status: str,
             duration_ms: float, error: str = ""):
        try:
            conn = sqlite3.connect(str(DB_PATH))
            conn.execute(
                "INSERT INTO rollback_log (fix_id, target, ts, snapshot_path, status, duration_ms, error) "
                "VALUES (?,?,?,?,?,?,?)",
                (fix_id, target, datetime.now().isoformat(),
                 json.dumps(paths), status, duration_ms, error)
            )
            conn.commit()
            conn.close()
        except Exception:
            pass

    def _cleanup_old_snapshots(self):
        """Remove oldest snapshots if over limit."""
        snaps = sorted(SNAPSHOT_DIR.glob("*"), key=lambda p: p.stat().st_mtime)
        while len(snaps) > self._max_snapshots:
            oldest = snaps.pop(0)
            oldest.unlink(missing_ok=True)
            logger.info("Cleaned snapshot: %s", oldest.name)

    def get_history(self, limit: int = 20) -> list[dict]:
        """Get recent rollback history."""
        try:
            conn = sqlite3.connect(str(DB_PATH))
            rows = conn.execute(
                "SELECT fix_id, target, ts, status, duration_ms, error "
                "FROM rollback_log ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
            conn.close()
            return [
                {"fix_id": r[0], "target": r[1], "ts": r[2],
                 "status": r[3], "duration_ms": r[4], "error": r[5]}
                for r in rows
            ]
        except Exception:
            return []

    def get_stats(self) -> dict:
        """Get rollback statistics."""
        try:
            conn = sqlite3.connect(str(DB_PATH))
            total = conn.execute("SELECT COUNT(*) FROM rollback_log").fetchone()[0]
            success = conn.execute("SELECT COUNT(*) FROM rollback_log WHERE status='success'").fetchone()[0]
            rolled = conn.execute("SELECT COUNT(*) FROM rollback_log WHERE status='rolled_back'").fetchone()[0]
            conn.close()
            snap_count = len(list(SNAPSHOT_DIR.glob("*")))
            return {
                "total_fixes": total, "successful": success,
                "rolled_back": rolled, "active_snapshots": snap_count,
                "max_snapshots": self._max_snapshots,
            }
        except Exception:
            return {"total_fixes": 0}


# Singleton
rollback_manager = RollbackManager()
