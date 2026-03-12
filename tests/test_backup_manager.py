"""Tests for src/backup_manager.py — Automated cluster backup & restore.

Covers: BackupEntry, BackupManager (backup_file, backup_dir, restore,
delete_backup, list_backups, get_stats, _enforce_retention),
backup_manager singleton. Uses tmp_path for file isolation.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.backup_manager import BackupEntry, BackupManager, backup_manager


# ===========================================================================
# BackupEntry
# ===========================================================================

class TestBackupEntry:
    def test_defaults(self):
        e = BackupEntry(backup_id="b1", source="/src", destination="/dst")
        assert e.size_bytes == 0
        assert e.backup_type == "full"
        assert e.status == "completed"
        assert e.metadata == {}
        assert e.ts > 0


# ===========================================================================
# BackupManager — backup_file
# ===========================================================================

class TestBackupFile:
    def test_backup_file_success(self, tmp_path):
        source = tmp_path / "data.db"
        source.write_bytes(b"database content here")
        bm = BackupManager(backup_dir=tmp_path / "backups")
        entry = bm.backup_file(source, tag="test")
        assert entry is not None
        assert entry.status == "completed"
        assert entry.size_bytes > 0
        assert Path(entry.destination).exists()

    def test_backup_file_not_found(self, tmp_path):
        bm = BackupManager(backup_dir=tmp_path / "backups")
        entry = bm.backup_file(tmp_path / "nonexistent.db")
        assert entry is None

    def test_backup_file_with_metadata(self, tmp_path):
        source = tmp_path / "config.json"
        source.write_text("{}")
        bm = BackupManager(backup_dir=tmp_path / "backups")
        entry = bm.backup_file(source, tag="config", metadata={"version": "1.0"})
        assert entry is not None
        assert entry.metadata["version"] == "1.0"
        assert entry.metadata["tag"] == "config"


# ===========================================================================
# BackupManager — backup_dir
# ===========================================================================

class TestBackupDir:
    def test_backup_dir_success(self, tmp_path):
        src_dir = tmp_path / "mydata"
        src_dir.mkdir()
        (src_dir / "file1.txt").write_text("hello")
        (src_dir / "file2.txt").write_text("world")
        bm = BackupManager(backup_dir=tmp_path / "backups")
        entry = bm.backup_dir(src_dir, tag="data")
        assert entry is not None
        assert entry.status == "completed"
        assert entry.size_bytes > 0

    def test_backup_dir_not_found(self, tmp_path):
        bm = BackupManager(backup_dir=tmp_path / "backups")
        assert bm.backup_dir(tmp_path / "nope") is None

    def test_backup_dir_not_a_dir(self, tmp_path):
        f = tmp_path / "file.txt"
        f.write_text("not a dir")
        bm = BackupManager(backup_dir=tmp_path / "backups")
        assert bm.backup_dir(f) is None


# ===========================================================================
# BackupManager — restore
# ===========================================================================

class TestRestore:
    def test_restore_file(self, tmp_path):
        source = tmp_path / "original.txt"
        source.write_text("original content")
        bm = BackupManager(backup_dir=tmp_path / "backups")
        entry = bm.backup_file(source)
        # Modify original
        source.write_text("modified content")
        assert bm.restore(entry.backup_id) is True
        assert source.read_text() == "original content"

    def test_restore_nonexistent(self, tmp_path):
        bm = BackupManager(backup_dir=tmp_path / "backups")
        assert bm.restore("nope") is False

    def test_restore_failed_backup(self, tmp_path):
        bm = BackupManager(backup_dir=tmp_path / "backups")
        bm._manifest.append(BackupEntry(
            backup_id="bad", source="/src", destination="/dst", status="failed"))
        assert bm.restore("bad") is False


# ===========================================================================
# BackupManager — delete_backup
# ===========================================================================

class TestDeleteBackup:
    def test_delete_backup(self, tmp_path):
        source = tmp_path / "data.txt"
        source.write_text("content")
        bm = BackupManager(backup_dir=tmp_path / "backups")
        entry = bm.backup_file(source)
        assert bm.delete_backup(entry.backup_id) is True
        assert bm.list_backups() == []
        assert not Path(entry.destination).exists()

    def test_delete_nonexistent(self, tmp_path):
        bm = BackupManager(backup_dir=tmp_path / "backups")
        assert bm.delete_backup("nope") is False


# ===========================================================================
# BackupManager — list_backups
# ===========================================================================

class TestListBackups:
    def test_list_all(self, tmp_path):
        bm = BackupManager(backup_dir=tmp_path / "backups")
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_text("a")
        f2.write_text("b")
        bm.backup_file(f1)
        bm.backup_file(f2)
        assert len(bm.list_backups()) == 2

    def test_list_with_filter(self, tmp_path):
        bm = BackupManager(backup_dir=tmp_path / "backups")
        f1 = tmp_path / "config.json"
        f2 = tmp_path / "data.db"
        f1.write_text("{}")
        f2.write_bytes(b"db")
        bm.backup_file(f1)
        bm.backup_file(f2)
        result = bm.list_backups(source_filter="config")
        assert len(result) == 1

    def test_list_empty(self, tmp_path):
        bm = BackupManager(backup_dir=tmp_path / "backups")
        assert bm.list_backups() == []


# ===========================================================================
# BackupManager — retention
# ===========================================================================

class TestRetention:
    def test_retention_enforced(self, tmp_path):
        bm = BackupManager(backup_dir=tmp_path / "backups", max_backups=3)
        for i in range(5):
            f = tmp_path / f"file_{i}.txt"
            f.write_text(f"content {i}")
            bm.backup_file(f)
        # Only 3 should remain
        assert len(bm.list_backups()) <= 3


# ===========================================================================
# BackupManager — stats
# ===========================================================================

class TestStats:
    def test_stats(self, tmp_path):
        bm = BackupManager(backup_dir=tmp_path / "backups")
        f = tmp_path / "data.txt"
        f.write_text("hello world")
        bm.backup_file(f)
        stats = bm.get_stats()
        assert stats["total_backups"] == 1
        assert stats["completed"] == 1
        assert stats["failed"] == 0
        assert stats["total_size_bytes"] > 0

    def test_stats_empty(self, tmp_path):
        bm = BackupManager(backup_dir=tmp_path / "backups")
        stats = bm.get_stats()
        assert stats["total_backups"] == 0
        assert stats["total_size_mb"] == 0


# ===========================================================================
# BackupManager — manifest persistence
# ===========================================================================

class TestManifest:
    def test_manifest_survives_reload(self, tmp_path):
        backup_dir = tmp_path / "backups"
        bm = BackupManager(backup_dir=backup_dir)
        f = tmp_path / "data.txt"
        f.write_text("persist")
        bm.backup_file(f)
        # Reload
        bm2 = BackupManager(backup_dir=backup_dir)
        assert len(bm2.list_backups()) == 1


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert backup_manager is not None
        assert isinstance(backup_manager, BackupManager)
