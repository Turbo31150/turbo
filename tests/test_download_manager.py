"""Tests for src/download_manager.py — HTTP file downloads with queue and retry.

Covers: DownloadStatus, Download (progress), DownloadManager (add, start, cancel,
remove, retry, start_next, queue_and_start, get, list_downloads, get_stats),
download_manager singleton.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.download_manager import (
    DownloadStatus, Download, DownloadManager, download_manager,
)


# ===========================================================================
# Enums & Dataclasses
# ===========================================================================

class TestDownloadStatus:
    def test_values(self):
        assert DownloadStatus.PENDING.value == "pending"
        assert DownloadStatus.DOWNLOADING.value == "downloading"
        assert DownloadStatus.COMPLETED.value == "completed"
        assert DownloadStatus.FAILED.value == "failed"
        assert DownloadStatus.CANCELLED.value == "cancelled"


class TestDownload:
    def test_defaults(self):
        d = Download(download_id="dl_1", url="http://x.com/f.zip", dest_path="/tmp/f.zip")
        assert d.status == DownloadStatus.PENDING
        assert d.retries == 0
        assert d.max_retries == 3
        assert d.progress == 0.0

    def test_progress(self):
        d = Download(download_id="dl_1", url="http://x.com/f.zip", dest_path="/tmp/f.zip",
                     size_bytes=1000, downloaded_bytes=500)
        assert d.progress == 50.0

    def test_progress_zero_size(self):
        d = Download(download_id="dl_1", url="http://x.com/f.zip", dest_path="/tmp/f.zip")
        assert d.progress == 0.0


# ===========================================================================
# DownloadManager — add
# ===========================================================================

class TestAdd:
    def test_basic_add(self):
        dm = DownloadManager()
        dl = dm.add("http://example.com/file.zip")
        assert dl.download_id == "dl_1"
        assert dl.filename == "file.zip"
        assert dl.status == DownloadStatus.PENDING

    def test_auto_filename(self):
        dm = DownloadManager()
        dl = dm.add("http://example.com/path/data.csv?v=2")
        assert dl.filename == "data.csv"

    def test_custom_filename(self):
        dm = DownloadManager()
        dl = dm.add("http://example.com/file.zip", filename="custom.zip")
        assert dl.filename == "custom.zip"

    def test_counter_increments(self):
        dm = DownloadManager()
        d1 = dm.add("http://x.com/a")
        d2 = dm.add("http://x.com/b")
        assert d1.download_id == "dl_1"
        assert d2.download_id == "dl_2"

    def test_tags(self):
        dm = DownloadManager()
        dl = dm.add("http://x.com/f", tags=["urgent"])
        assert dl.tags == ["urgent"]


# ===========================================================================
# DownloadManager — start (with custom transport)
# ===========================================================================

class TestStart:
    def test_not_found(self):
        dm = DownloadManager()
        result = dm.start("nope")
        assert result["success"] is False
        assert "not found" in result["error"]

    def test_already_completed(self):
        dm = DownloadManager()
        dl = dm.add("http://x.com/f")
        dl.status = DownloadStatus.COMPLETED
        result = dm.start(dl.download_id)
        assert result["success"] is False
        assert "already completed" in result["error"]

    def test_transport_success(self):
        dm = DownloadManager()
        dm.set_transport(lambda url, path: True)
        dl = dm.add("http://x.com/f.zip")
        result = dm.start(dl.download_id)
        assert result["success"] is True
        assert dl.status == DownloadStatus.COMPLETED
        assert dl.completed_at is not None

    def test_transport_failure(self):
        dm = DownloadManager()
        dm.set_transport(lambda url, path: False)
        dl = dm.add("http://x.com/f.zip", max_retries=1)
        result = dm.start(dl.download_id)
        assert result["success"] is False
        assert dl.status == DownloadStatus.FAILED

    def test_transport_exception(self):
        dm = DownloadManager()
        dm.set_transport(lambda url, path: (_ for _ in ()).throw(Exception("network error")))
        dl = dm.add("http://x.com/f.zip", max_retries=1)
        result = dm.start(dl.download_id)
        assert result["success"] is False
        assert "network error" in result["error"]

    def test_retry_pending(self):
        dm = DownloadManager()
        dm.set_transport(lambda url, path: False)
        dl = dm.add("http://x.com/f.zip", max_retries=3)
        dm.start(dl.download_id)
        assert dl.status == DownloadStatus.PENDING  # still has retries left
        assert dl.retries == 1


# ===========================================================================
# DownloadManager — cancel / remove / retry
# ===========================================================================

class TestCancelRemoveRetry:
    def test_cancel(self):
        dm = DownloadManager()
        dl = dm.add("http://x.com/f")
        assert dm.cancel(dl.download_id) is True
        assert dl.status == DownloadStatus.CANCELLED

    def test_cancel_not_found(self):
        dm = DownloadManager()
        assert dm.cancel("nope") is False

    def test_remove(self):
        dm = DownloadManager()
        dl = dm.add("http://x.com/f")
        assert dm.remove(dl.download_id) is True
        assert dm.get(dl.download_id) is None

    def test_remove_not_found(self):
        dm = DownloadManager()
        assert dm.remove("nope") is False

    def test_retry(self):
        dm = DownloadManager()
        dm.set_transport(lambda url, path: True)
        dl = dm.add("http://x.com/f")
        dl.status = DownloadStatus.FAILED
        dl.retries = 3
        result = dm.retry(dl.download_id)
        assert result["success"] is True
        assert dl.status == DownloadStatus.COMPLETED

    def test_retry_not_found(self):
        dm = DownloadManager()
        result = dm.retry("nope")
        assert result["success"] is False


# ===========================================================================
# DownloadManager — queue operations
# ===========================================================================

class TestQueue:
    def test_start_next(self):
        dm = DownloadManager()
        dm.set_transport(lambda url, path: True)
        dm.add("http://x.com/a")
        dm.add("http://x.com/b")
        result = dm.start_next()
        assert result is not None
        assert result["success"] is True

    def test_start_next_empty(self):
        dm = DownloadManager()
        assert dm.start_next() is None

    def test_queue_and_start(self):
        dm = DownloadManager()
        dm.set_transport(lambda url, path: True)
        result = dm.queue_and_start("http://x.com/f.zip")
        assert result["success"] is True


# ===========================================================================
# DownloadManager — query
# ===========================================================================

class TestQuery:
    def test_get(self):
        dm = DownloadManager()
        dl = dm.add("http://x.com/f")
        assert dm.get(dl.download_id) is not None
        assert dm.get("nope") is None

    def test_list_downloads(self):
        dm = DownloadManager()
        dm.add("http://x.com/a")
        dm.add("http://x.com/b")
        result = dm.list_downloads()
        assert len(result) == 2

    def test_list_downloads_filter(self):
        dm = DownloadManager()
        dm.set_transport(lambda url, path: True)
        dm.add("http://x.com/a")
        dl = dm.add("http://x.com/b")
        dm.start(dl.download_id)
        pending = dm.list_downloads(status="pending")
        assert len(pending) == 1
        completed = dm.list_downloads(status="completed")
        assert len(completed) == 1

    def test_stats_empty(self):
        dm = DownloadManager()
        stats = dm.get_stats()
        assert stats["total_downloads"] == 0

    def test_stats_with_data(self):
        dm = DownloadManager()
        dm.set_transport(lambda url, path: True)
        dm.add("http://x.com/a")
        dl = dm.add("http://x.com/b")
        dm.start(dl.download_id)
        stats = dm.get_stats()
        assert stats["total_downloads"] == 2
        assert stats["by_status"]["completed"] == 1


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert download_manager is not None
        assert isinstance(download_manager, DownloadManager)
