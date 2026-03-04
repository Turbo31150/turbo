"""Clipboard Manager — Windows clipboard history and management.

Track clipboard content with history, search, pinning, categories,
and auto-cleanup via TTL. Uses subprocess for Windows clipboard access
(no external dependencies).
"""

from __future__ import annotations

import logging
import subprocess
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger("jarvis.clipboard_manager")


class ClipCategory(Enum):
    TEXT = "text"
    PATH = "path"
    URL = "url"
    CODE = "code"
    OTHER = "other"


@dataclass
class ClipEntry:
    """A clipboard history entry."""
    content: str
    category: ClipCategory = ClipCategory.TEXT
    timestamp: float = field(default_factory=time.time)
    pinned: bool = False
    tags: list[str] = field(default_factory=list)
    source: str = ""

    @property
    def preview(self) -> str:
        return self.content[:80] + ("..." if len(self.content) > 80 else "")


def _detect_category(text: str) -> ClipCategory:
    """Auto-detect category from content."""
    stripped = text.strip()
    if stripped.startswith(("http://", "https://", "ftp://")):
        return ClipCategory.URL
    if stripped.startswith(("/", "\\", "C:", "D:", "E:", "F:")) or "\\" in stripped[:10]:
        return ClipCategory.PATH
    if any(kw in stripped for kw in ("def ", "class ", "function ", "import ", "const ", "var ", "{", "}")):
        return ClipCategory.CODE
    return ClipCategory.TEXT


class ClipboardManager:
    """Manage clipboard history with search, pinning, and categories."""

    def __init__(self, max_history: int = 200, ttl_seconds: float = 3600) -> None:
        self._history: list[ClipEntry] = []
        self._max_history = max_history
        self._ttl = ttl_seconds
        self._lock = threading.Lock()

    # ── Clipboard Operations ────────────────────────────────────────

    def capture(self, content: str, source: str = "", tags: list[str] | None = None) -> ClipEntry:
        """Add content to clipboard history (and optionally set system clipboard)."""
        category = _detect_category(content)
        entry = ClipEntry(
            content=content,
            category=category,
            source=source,
            tags=tags or [],
        )
        with self._lock:
            self._history.append(entry)
            if len(self._history) > self._max_history:
                # Remove oldest unpinned
                unpinned = [i for i, e in enumerate(self._history) if not e.pinned]
                if unpinned:
                    self._history.pop(unpinned[0])
        return entry

    def get_current(self) -> str | None:
        """Get current system clipboard content (Windows)."""
        try:
            result = subprocess.run(
                ["powershell", "-Command", "Get-Clipboard"],
                capture_output=True, text=True, timeout=5,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            return result.stdout.strip() if result.returncode == 0 else None
        except Exception:
            return None

    def set_clipboard(self, content: str) -> bool:
        """Set system clipboard content (Windows)."""
        try:
            proc = subprocess.Popen(
                ["powershell", "-Command", "Set-Clipboard", "-Value", content],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            proc.wait(timeout=5)
            return proc.returncode == 0
        except Exception:
            return False

    # ── History ─────────────────────────────────────────────────────

    def get_history(self, category: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        """Get clipboard history."""
        with self._lock:
            entries = self._history
            if category:
                entries = [e for e in entries if e.category.value == category]
            return [
                {"content": e.preview, "full_content": e.content, "category": e.category.value,
                 "timestamp": e.timestamp, "pinned": e.pinned, "tags": e.tags, "source": e.source}
                for e in entries[-limit:]
            ]

    def search(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        """Search clipboard history."""
        q = query.lower()
        with self._lock:
            matches = [e for e in self._history if q in e.content.lower()]
            return [
                {"content": e.preview, "category": e.category.value,
                 "timestamp": e.timestamp, "pinned": e.pinned}
                for e in matches[-limit:]
            ]

    def pin(self, index: int) -> bool:
        """Pin an entry by index (from end)."""
        with self._lock:
            if 0 <= index < len(self._history):
                self._history[-(index + 1)].pinned = True
                return True
            return False

    def unpin(self, index: int) -> bool:
        """Unpin an entry."""
        with self._lock:
            if 0 <= index < len(self._history):
                self._history[-(index + 1)].pinned = False
                return True
            return False

    def clear(self, keep_pinned: bool = True) -> int:
        """Clear history, optionally keeping pinned entries."""
        with self._lock:
            before = len(self._history)
            if keep_pinned:
                self._history = [e for e in self._history if e.pinned]
            else:
                self._history.clear()
            return before - len(self._history)

    def cleanup_expired(self) -> int:
        """Remove entries older than TTL (except pinned)."""
        now = time.time()
        with self._lock:
            before = len(self._history)
            self._history = [
                e for e in self._history
                if e.pinned or (now - e.timestamp) < self._ttl
            ]
            return before - len(self._history)

    # ── Stats ───────────────────────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        """Get clipboard manager statistics."""
        with self._lock:
            cats: dict[str, int] = {}
            pinned = 0
            for e in self._history:
                cats[e.category.value] = cats.get(e.category.value, 0) + 1
                if e.pinned:
                    pinned += 1
            return {
                "total_entries": len(self._history),
                "pinned": pinned,
                "categories": cats,
                "max_history": self._max_history,
                "ttl_seconds": self._ttl,
            }


# ── Singleton ───────────────────────────────────────────────────────
clipboard_manager = ClipboardManager()
