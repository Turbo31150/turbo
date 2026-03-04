"""Download Manager — HTTP file downloads with queue and retry.

Download files with progress tracking, retry on failure, queue
management, resume support, and history. Designed for JARVIS
voice-commanded file downloading.
"""

from __future__ import annotations

import logging
import os
import threading
import time
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

logger = logging.getLogger("jarvis.download_manager")


class DownloadStatus(Enum):
    PENDING = "pending"
    DOWNLOADING = "downloading"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


@dataclass
class Download:
    """A download task."""
    download_id: str
    url: str
    dest_path: str
    filename: str = ""
    status: DownloadStatus = DownloadStatus.PENDING
    size_bytes: int = 0
    downloaded_bytes: int = 0
    speed_bps: float = 0.0
    retries: int = 0
    max_retries: int = 3
    error: str = ""
    tags: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    completed_at: float | None = None

    @property
    def progress(self) -> float:
        if self.size_bytes <= 0:
            return 0.0
        return round(self.downloaded_bytes / self.size_bytes * 100, 1)


class DownloadManager:
    """Manage file downloads with queue, retry, and history."""

    def __init__(self, download_dir: str = "") -> None:
        self._downloads: dict[str, Download] = {}
        self._counter = 0
        self._lock = threading.Lock()
        self._download_dir = download_dir or os.path.join(os.path.expanduser("~"), "Downloads")
        self._transport: Callable[[str, str], bool] | None = None

    def set_transport(self, fn: Callable[[str, str], bool]) -> None:
        """Inject custom transport for testing."""
        self._transport = fn

    # ── Download Management ─────────────────────────────────────────

    def add(self, url: str, dest_path: str = "", filename: str = "",
            tags: list[str] | None = None, max_retries: int = 3) -> Download:
        """Add a download to the queue."""
        if not filename:
            filename = url.split("/")[-1].split("?")[0] or "download"
        if not dest_path:
            dest_path = os.path.join(self._download_dir, filename)

        with self._lock:
            self._counter += 1
            did = f"dl_{self._counter}"
            dl = Download(
                download_id=did, url=url, dest_path=dest_path,
                filename=filename, tags=tags or [], max_retries=max_retries,
            )
            self._downloads[did] = dl
            return dl

    def start(self, download_id: str) -> dict[str, Any]:
        """Start a download."""
        with self._lock:
            dl = self._downloads.get(download_id)
            if not dl:
                return {"success": False, "error": "not found"}
            if dl.status == DownloadStatus.COMPLETED:
                return {"success": False, "error": "already completed"}
            dl.status = DownloadStatus.DOWNLOADING
            dl.started_at = time.time()

        success = False
        error = ""

        if self._transport:
            try:
                success = self._transport(dl.url, dl.dest_path)
                if success:
                    dl.downloaded_bytes = 1
                    dl.size_bytes = 1
            except Exception as e:
                error = str(e)
        else:
            try:
                success = self._http_download(dl)
            except Exception as e:
                error = str(e)

        with self._lock:
            if success:
                dl.status = DownloadStatus.COMPLETED
                dl.completed_at = time.time()
            else:
                dl.retries += 1
                if dl.retries >= dl.max_retries:
                    dl.status = DownloadStatus.FAILED
                    dl.error = error
                else:
                    dl.status = DownloadStatus.PENDING
                    dl.error = error

        return {"success": success, "download_id": download_id, "error": error}

    def _http_download(self, dl: Download) -> bool:
        """Download file via HTTP."""
        os.makedirs(os.path.dirname(dl.dest_path) or ".", exist_ok=True)
        req = urllib.request.Request(dl.url, headers={"User-Agent": "JARVIS/1.0"})
        with urllib.request.urlopen(req, timeout=60) as response:
            total = int(response.headers.get("Content-Length", 0))
            dl.size_bytes = total
            chunk_size = 8192
            downloaded = 0
            start = time.time()
            with open(dl.dest_path, "wb") as f:
                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    dl.downloaded_bytes = downloaded
                    elapsed = time.time() - start
                    if elapsed > 0:
                        dl.speed_bps = downloaded / elapsed
        return True

    def cancel(self, download_id: str) -> bool:
        """Cancel a download."""
        with self._lock:
            dl = self._downloads.get(download_id)
            if not dl:
                return False
            dl.status = DownloadStatus.CANCELLED
            return True

    def remove(self, download_id: str) -> bool:
        """Remove a download from history."""
        with self._lock:
            if download_id in self._downloads:
                del self._downloads[download_id]
                return True
            return False

    def retry(self, download_id: str) -> dict[str, Any]:
        """Retry a failed download."""
        with self._lock:
            dl = self._downloads.get(download_id)
            if not dl:
                return {"success": False, "error": "not found"}
            dl.status = DownloadStatus.PENDING
            dl.retries = 0
            dl.error = ""
        return self.start(download_id)

    # ── Queue ───────────────────────────────────────────────────────

    def start_next(self) -> dict[str, Any] | None:
        """Start the next pending download."""
        with self._lock:
            for dl in self._downloads.values():
                if dl.status == DownloadStatus.PENDING:
                    did = dl.download_id
                    break
            else:
                return None
        return self.start(did)

    def queue_and_start(self, url: str, **kwargs: Any) -> dict[str, Any]:
        """Add and immediately start a download."""
        dl = self.add(url, **kwargs)
        return self.start(dl.download_id)

    # ── Query ───────────────────────────────────────────────────────

    def get(self, download_id: str) -> Download | None:
        with self._lock:
            return self._downloads.get(download_id)

    def list_downloads(self, status: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            dls = list(self._downloads.values())
            if status:
                dls = [d for d in dls if d.status.value == status]
            return [
                {"id": d.download_id, "url": d.url, "filename": d.filename,
                 "status": d.status.value, "progress": d.progress,
                 "size_bytes": d.size_bytes, "speed_bps": d.speed_bps,
                 "tags": d.tags, "error": d.error}
                for d in dls[-limit:]
            ]

    def get_stats(self) -> dict[str, Any]:
        with self._lock:
            by_status: dict[str, int] = {}
            total_bytes = 0
            for d in self._downloads.values():
                by_status[d.status.value] = by_status.get(d.status.value, 0) + 1
                total_bytes += d.downloaded_bytes
            return {
                "total_downloads": len(self._downloads),
                "by_status": by_status,
                "total_bytes_downloaded": total_bytes,
                "download_dir": self._download_dir,
            }


# ── Singleton ───────────────────────────────────────────────────────
download_manager = DownloadManager()
