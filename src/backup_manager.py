"""Backup Manager — Automated cluster backup & restore.

Manages backups of databases, configs, and data dirs.
Supports retention policies and manifest tracking.
"""

from __future__ import annotations

import json
import logging
import shutil
import threading
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

logger = logging.getLogger("jarvis.backup_manager")


@dataclass
class BackupEntry:
    backup_id: str
    source: str
    destination: str
    size_bytes: int = 0
    ts: float = field(default_factory=time.time)
    backup_type: str = "full"  # full, incremental
    status: str = "completed"  # completed, failed
    metadata: dict = field(default_factory=dict)


class BackupManager:
    """Automated backup management with retention."""

    def __init__(self, backup_dir: Path | None = None, max_backups: int = 20):
        self._backup_dir = backup_dir or Path("data/backups")
        self._max_backups = max_backups
        self._manifest: list[BackupEntry] = []
        self._lock = threading.Lock()
        self._manifest_path = self._backup_dir / "manifest.json"
        self._load_manifest()

    def backup_file(self, source: Path, tag: str = "", metadata: dict | None = None) -> BackupEntry | None:
        """Backup a single file."""
        if not source.exists():
            logger.warning("Backup source not found: %s", source)
            return None

        with self._lock:
            ts = time.time()
            bid = f"{source.stem}_{int(ts)}"
            dest_dir = self._backup_dir / bid
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / source.name

            try:
                shutil.copy2(str(source), str(dest))
                size = dest.stat().st_size
            except Exception as e:
                logger.error("Backup failed %s: %s", source, e)
                entry = BackupEntry(
                    backup_id=bid, source=str(source), destination=str(dest),
                    status="failed", metadata=metadata or {},
                )
                self._manifest.append(entry)
                self._save_manifest()
                return entry

            entry = BackupEntry(
                backup_id=bid, source=str(source), destination=str(dest),
                size_bytes=size, backup_type="full", status="completed",
                metadata={**(metadata or {}), "tag": tag},
            )
            self._manifest.append(entry)
            self._enforce_retention()
            self._save_manifest()
            return entry

    def backup_dir(self, source: Path, tag: str = "") -> BackupEntry | None:
        """Backup an entire directory."""
        if not source.exists() or not source.is_dir():
            return None

        with self._lock:
            ts = time.time()
            bid = f"{source.name}_{int(ts)}"
            dest = self._backup_dir / bid

            try:
                shutil.copytree(str(source), str(dest))
                size = sum(f.stat().st_size for f in dest.rglob("*") if f.is_file())
            except Exception as e:
                logger.error("Dir backup failed %s: %s", source, e)
                return None

            entry = BackupEntry(
                backup_id=bid, source=str(source), destination=str(dest),
                size_bytes=size, backup_type="full", status="completed",
                metadata={"tag": tag, "type": "directory"},
            )
            self._manifest.append(entry)
            self._enforce_retention()
            self._save_manifest()
            return entry

    def restore(self, backup_id: str) -> bool:
        """Restore a backup to its original location."""
        with self._lock:
            entry = self._find(backup_id)
            if not entry or entry.status != "completed":
                return False
            dest = Path(entry.destination)
            source = Path(entry.source)
            if not dest.exists():
                return False
            try:
                if dest.is_dir():
                    if source.exists():
                        shutil.rmtree(str(source))
                    shutil.copytree(str(dest), str(source))
                else:
                    shutil.copy2(str(dest), str(source))
                return True
            except Exception as e:
                logger.error("Restore failed %s: %s", backup_id, e)
                return False

    def delete_backup(self, backup_id: str) -> bool:
        with self._lock:
            entry = self._find(backup_id)
            if not entry:
                return False
            dest = Path(entry.destination)
            try:
                if dest.is_dir():
                    shutil.rmtree(str(dest))
                elif dest.exists():
                    dest.unlink()
            except Exception:
                pass
            self._manifest = [e for e in self._manifest if e.backup_id != backup_id]
            self._save_manifest()
            return True

    def list_backups(self, source_filter: str | None = None) -> list[dict]:
        entries = self._manifest
        if source_filter:
            entries = [e for e in entries if source_filter in e.source]
        return [asdict(e) for e in entries]

    def get_stats(self) -> dict:
        completed = [e for e in self._manifest if e.status == "completed"]
        failed = [e for e in self._manifest if e.status == "failed"]
        total_size = sum(e.size_bytes for e in completed)
        return {
            "total_backups": len(self._manifest),
            "completed": len(completed),
            "failed": len(failed),
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "max_backups": self._max_backups,
            "backup_dir": str(self._backup_dir),
        }

    # ── Internal ──────────────────────────────────────────────────

    def _find(self, backup_id: str) -> BackupEntry | None:
        for e in self._manifest:
            if e.backup_id == backup_id:
                return e
        return None

    def _enforce_retention(self) -> None:
        completed = [e for e in self._manifest if e.status == "completed"]
        while len(completed) > self._max_backups:
            oldest = completed.pop(0)
            dest = Path(oldest.destination)
            try:
                if dest.is_dir():
                    shutil.rmtree(str(dest))
                elif dest.exists():
                    dest.unlink()
            except Exception:
                pass
            self._manifest = [e for e in self._manifest if e.backup_id != oldest.backup_id]

    def _save_manifest(self) -> None:
        try:
            self._backup_dir.mkdir(parents=True, exist_ok=True)
            data = [asdict(e) for e in self._manifest]
            self._manifest_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as e:
            logger.debug("Manifest save error: %s", e)

    def _load_manifest(self) -> None:
        try:
            if self._manifest_path.exists():
                raw = json.loads(self._manifest_path.read_text(encoding="utf-8"))
                self._manifest = [BackupEntry(**d) for d in raw]
        except Exception as e:
            logger.debug("Manifest load error: %s", e)


# ── Singleton ────────────────────────────────────────────────────────────────
backup_manager = BackupManager()
