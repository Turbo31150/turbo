"""Linux Trash Manager — Trash/Recycle bin management.

Uses gio trash, trash-cli, and ~/.local/share/Trash/ directly.
Designed for JARVIS autonomous cleanup management.
"""

from __future__ import annotations

import logging
import os
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Any


__all__ = [
    "TrashEvent",
    "TrashInfo",
    "LinuxTrashManager",
]

logger = logging.getLogger("jarvis.linux_trash_manager")

_TRASH_DIR = os.path.expanduser("~/.local/share/Trash")
_TRASH_FILES = os.path.join(_TRASH_DIR, "files")
_TRASH_INFO = os.path.join(_TRASH_DIR, "info")


@dataclass
class TrashInfo:
    """Trash bin information."""
    item_count: int = 0
    total_size_mb: float = 0.0


@dataclass
class TrashEvent:
    """Record of a trash action."""
    action: str
    detail: str = ""
    timestamp: float = field(default_factory=time.time)
    success: bool = True


class LinuxTrashManager:
    """Linux Trash management (read-only)."""

    def __init__(self) -> None:
        self._events: list[TrashEvent] = []
        self._lock = threading.Lock()

    def get_info(self) -> dict[str, Any]:
        """Get trash item count and size."""
        # Essayer gio trash first
        info = self._get_info_gio()
        if info:
            return info
        # Essayer trash-cli
        info = self._get_info_trash_cli()
        if info:
            return info
        # Fallback : lire le répertoire directement
        return self._get_info_direct()

    def _get_info_gio(self) -> dict[str, Any] | None:
        """Get trash info via gio."""
        try:
            result = subprocess.run(
                ["gio", "trash", "--list"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                lines = result.stdout.strip().splitlines() if result.stdout.strip() else []
                count = len(lines)
                # Calculer la taille depuis le dossier
                size_mb = self._calc_trash_size()
                self._record("get_info", True)
                return {"item_count": count, "size_mb": size_mb}
        except FileNotFoundError:
            pass
        except Exception:
            pass
        return None

    def _get_info_trash_cli(self) -> dict[str, Any] | None:
        """Get trash info via trash-list."""
        try:
            result = subprocess.run(
                ["trash-list"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                lines = result.stdout.strip().splitlines() if result.stdout.strip() else []
                count = len(lines)
                size_mb = self._calc_trash_size()
                self._record("get_info", True)
                return {"item_count": count, "size_mb": size_mb}
        except FileNotFoundError:
            pass
        except Exception:
            pass
        return None

    def _get_info_direct(self) -> dict[str, Any]:
        """Get trash info directly from filesystem."""
        count = 0
        if os.path.isdir(_TRASH_FILES):
            try:
                count = len(os.listdir(_TRASH_FILES))
            except Exception:
                pass
        size_mb = self._calc_trash_size()
        self._record("get_info", True)
        return {"item_count": count, "size_mb": size_mb}

    def _calc_trash_size(self) -> float:
        """Calculate total trash size in MB."""
        if not os.path.isdir(_TRASH_FILES):
            return 0.0
        total = 0
        try:
            for dirpath, _dirnames, filenames in os.walk(_TRASH_FILES):
                for fname in filenames:
                    fpath = os.path.join(dirpath, fname)
                    try:
                        total += os.path.getsize(fpath)
                    except OSError:
                        pass
        except Exception:
            pass
        return round(total / (1024 * 1024), 2)

    def list_items(self, limit: int = 50) -> list[dict[str, Any]]:
        """List recent items in trash."""
        items: list[dict[str, Any]] = []
        if not os.path.isdir(_TRASH_INFO):
            return items
        try:
            info_files = sorted(os.listdir(_TRASH_INFO), reverse=True)[:limit]
            for info_file in info_files:
                if not info_file.endswith(".trashinfo"):
                    continue
                info_path = os.path.join(_TRASH_INFO, info_file)
                try:
                    with open(info_path, "r", errors="replace") as f:
                        content = f.read()
                    path = ""
                    deletion_date = ""
                    for line in content.splitlines():
                        if line.startswith("Path="):
                            path = line[5:]
                        elif line.startswith("DeletionDate="):
                            deletion_date = line[13:]
                    items.append({
                        "name": os.path.basename(path) if path else info_file,
                        "original_path": path,
                        "deletion_date": deletion_date,
                    })
                except Exception:
                    continue
        except Exception:
            pass
        return items

    def is_empty(self) -> bool:
        """Check if trash is empty."""
        info = self.get_info()
        return info.get("item_count", 0) == 0

    def empty_trash(self) -> bool:
        """Empty the trash."""
        # Essayer gio
        try:
            result = subprocess.run(
                ["gio", "trash", "--empty"],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0:
                self._record("empty_trash", True)
                return True
        except FileNotFoundError:
            pass
        except Exception:
            pass
        # Essayer trash-empty
        try:
            result = subprocess.run(
                ["trash-empty"],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0:
                self._record("empty_trash", True)
                return True
        except FileNotFoundError:
            pass
        except Exception:
            pass
        self._record("empty_trash", False, "No trash tool available")
        return False

    def _record(self, action: str, success: bool, detail: str = "") -> None:
        with self._lock:
            self._events.append(TrashEvent(action=action, success=success, detail=detail))

    def get_events(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {"action": e.action, "timestamp": e.timestamp,
                 "success": e.success, "detail": e.detail}
                for e in self._events[-limit:]
            ]

    def get_stats(self) -> dict[str, Any]:
        with self._lock:
            return {"total_events": len(self._events)}


linux_trash_manager = LinuxTrashManager()
