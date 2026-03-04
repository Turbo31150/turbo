"""File Watcher — File system change monitoring with callbacks.

Watch directories for file changes (created, modified, deleted) with
glob pattern filtering, debounce, event history, and watch groups.
Designed for JARVIS to react to file system changes on Windows.
"""

from __future__ import annotations

import fnmatch
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

logger = logging.getLogger("jarvis.file_watcher")


class ChangeType(Enum):
    CREATED = "created"
    MODIFIED = "modified"
    DELETED = "deleted"


@dataclass
class FileEvent:
    """A single file change event."""
    path: str
    change_type: ChangeType
    timestamp: float = field(default_factory=time.time)
    size: int | None = None
    watch_name: str = ""


@dataclass
class WatchConfig:
    """Configuration for a file watch."""
    name: str
    directory: str
    patterns: list[str] = field(default_factory=lambda: ["*"])
    recursive: bool = False
    group: str = "default"
    callback: Callable[[FileEvent], None] | None = None
    debounce_ms: int = 100
    enabled: bool = True
    # Runtime
    _snapshot: dict[str, float] = field(default_factory=dict, repr=False)
    created_at: float = field(default_factory=time.time)


class FileWatcher:
    """Monitor file system changes with pattern matching and callbacks."""

    def __init__(self) -> None:
        self._watches: dict[str, WatchConfig] = {}
        self._events: list[FileEvent] = []
        self._lock = threading.Lock()
        self._running = False
        self._thread: threading.Thread | None = None

    # ── Watch Management ────────────────────────────────────────────

    def add_watch(
        self,
        name: str,
        directory: str,
        patterns: list[str] | None = None,
        recursive: bool = False,
        group: str = "default",
        callback: Callable[[FileEvent], None] | None = None,
        debounce_ms: int = 100,
    ) -> WatchConfig:
        """Add a new file watch."""
        watch = WatchConfig(
            name=name,
            directory=directory,
            patterns=patterns or ["*"],
            recursive=recursive,
            group=group,
            callback=callback,
            debounce_ms=debounce_ms,
        )
        # Take initial snapshot
        watch._snapshot = self._scan_directory(directory, watch.patterns, recursive)
        with self._lock:
            self._watches[name] = watch
        return watch

    def remove_watch(self, name: str) -> bool:
        """Remove a file watch."""
        with self._lock:
            if name in self._watches:
                del self._watches[name]
                return True
            return False

    def enable_watch(self, name: str) -> bool:
        """Enable a watch."""
        with self._lock:
            w = self._watches.get(name)
            if w:
                w.enabled = True
                return True
            return False

    def disable_watch(self, name: str) -> bool:
        """Disable a watch."""
        with self._lock:
            w = self._watches.get(name)
            if w:
                w.enabled = False
                return True
            return False

    # ── Scanning ────────────────────────────────────────────────────

    def _scan_directory(self, directory: str, patterns: list[str], recursive: bool) -> dict[str, float]:
        """Scan directory and return {path: mtime} for matching files."""
        result: dict[str, float] = {}
        if not os.path.isdir(directory):
            return result
        try:
            if recursive:
                for root, _, files in os.walk(directory):
                    for fname in files:
                        if self._matches_patterns(fname, patterns):
                            fpath = os.path.join(root, fname)
                            try:
                                result[fpath] = os.path.getmtime(fpath)
                            except OSError:
                                pass
            else:
                for fname in os.listdir(directory):
                    fpath = os.path.join(directory, fname)
                    if os.path.isfile(fpath) and self._matches_patterns(fname, patterns):
                        try:
                            result[fpath] = os.path.getmtime(fpath)
                        except OSError:
                            pass
        except OSError:
            pass
        return result

    @staticmethod
    def _matches_patterns(filename: str, patterns: list[str]) -> bool:
        """Check if filename matches any of the glob patterns."""
        return any(fnmatch.fnmatch(filename, p) for p in patterns)

    def poll(self, name: str | None = None) -> list[FileEvent]:
        """Poll for changes in one or all watches. Returns new events."""
        with self._lock:
            watches = [self._watches[name]] if name and name in self._watches else list(self._watches.values())

        all_events: list[FileEvent] = []
        for watch in watches:
            if not watch.enabled:
                continue
            events = self._check_watch(watch)
            all_events.extend(events)

        with self._lock:
            self._events.extend(all_events)

        # Fire callbacks
        for event in all_events:
            w = self._watches.get(event.watch_name)
            if w and w.callback:
                try:
                    w.callback(event)
                except Exception as e:
                    logger.error("Callback error for %s: %s", event.watch_name, e)

        return all_events

    def _check_watch(self, watch: WatchConfig) -> list[FileEvent]:
        """Check a single watch for changes."""
        events: list[FileEvent] = []
        new_snapshot = self._scan_directory(watch.directory, watch.patterns, watch.recursive)
        old_snapshot = watch._snapshot

        # Detect new/modified files
        for path, mtime in new_snapshot.items():
            if path not in old_snapshot:
                size = None
                try:
                    size = os.path.getsize(path)
                except OSError:
                    pass
                events.append(FileEvent(
                    path=path, change_type=ChangeType.CREATED,
                    size=size, watch_name=watch.name,
                ))
            elif mtime > old_snapshot[path]:
                size = None
                try:
                    size = os.path.getsize(path)
                except OSError:
                    pass
                events.append(FileEvent(
                    path=path, change_type=ChangeType.MODIFIED,
                    size=size, watch_name=watch.name,
                ))

        # Detect deleted files
        for path in old_snapshot:
            if path not in new_snapshot:
                events.append(FileEvent(
                    path=path, change_type=ChangeType.DELETED,
                    watch_name=watch.name,
                ))

        watch._snapshot = new_snapshot
        return events

    # ── Query ───────────────────────────────────────────────────────

    def list_watches(self, group: str | None = None) -> list[dict[str, Any]]:
        """List all watches."""
        with self._lock:
            result = []
            for w in self._watches.values():
                if group and w.group != group:
                    continue
                result.append({
                    "name": w.name,
                    "directory": w.directory,
                    "patterns": w.patterns,
                    "recursive": w.recursive,
                    "group": w.group,
                    "enabled": w.enabled,
                    "files_tracked": len(w._snapshot),
                    "created_at": w.created_at,
                })
            return result

    def list_groups(self) -> list[str]:
        """List all watch groups."""
        with self._lock:
            return list(set(w.group for w in self._watches.values()))

    def get_events(self, watch_name: str | None = None, change_type: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        """Get event history."""
        with self._lock:
            events = self._events
            if watch_name:
                events = [e for e in events if e.watch_name == watch_name]
            if change_type:
                events = [e for e in events if e.change_type.value == change_type]
            return [
                {"path": e.path, "change_type": e.change_type.value,
                 "timestamp": e.timestamp, "size": e.size, "watch_name": e.watch_name}
                for e in events[-limit:]
            ]

    def get_stats(self) -> dict[str, Any]:
        """Get file watcher statistics."""
        with self._lock:
            enabled = sum(1 for w in self._watches.values() if w.enabled)
            total_files = sum(len(w._snapshot) for w in self._watches.values())
            groups = set(w.group for w in self._watches.values())
            created = sum(1 for e in self._events if e.change_type == ChangeType.CREATED)
            modified = sum(1 for e in self._events if e.change_type == ChangeType.MODIFIED)
            deleted = sum(1 for e in self._events if e.change_type == ChangeType.DELETED)
            return {
                "total_watches": len(self._watches),
                "enabled": enabled,
                "disabled": len(self._watches) - enabled,
                "groups": len(groups),
                "total_files_tracked": total_files,
                "total_events": len(self._events),
                "events_created": created,
                "events_modified": modified,
                "events_deleted": deleted,
            }


# ── Singleton ───────────────────────────────────────────────────────
file_watcher = FileWatcher()
