"""Log Aggregator — Centralized log management.

Collects logs from all modules, supports filtering by
level/source/time, search, and size-based rotation.
Thread-safe.
"""

from __future__ import annotations

import logging
import re
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("jarvis.log_aggregator")


@dataclass
class LogEntry:
    message: str
    level: str = "info"
    source: str = "system"
    ts: float = field(default_factory=time.time)
    metadata: dict = field(default_factory=dict)


class LogAggregator:
    """Centralized log collection and query engine."""

    def __init__(self, max_entries: int = 5000):
        self._entries: list[LogEntry] = []
        self._max_entries = max_entries
        self._lock = threading.Lock()
        self._source_counts: dict[str, int] = defaultdict(int)
        self._level_counts: dict[str, int] = defaultdict(int)

    def log(self, message: str, level: str = "info", source: str = "system", metadata: dict | None = None) -> None:
        entry = LogEntry(message=message, level=level, source=source, metadata=metadata or {})
        with self._lock:
            self._entries.append(entry)
            self._source_counts[source] += 1
            self._level_counts[level] += 1
            if len(self._entries) > self._max_entries:
                self._entries = self._entries[-self._max_entries:]

    def query(
        self,
        level: str | None = None,
        source: str | None = None,
        search: str | None = None,
        since: float | None = None,
        until: float | None = None,
        limit: int = 100,
    ) -> list[dict]:
        with self._lock:
            entries = self._entries
        if level:
            entries = [e for e in entries if e.level == level]
        if source:
            entries = [e for e in entries if e.source == source]
        if since:
            entries = [e for e in entries if e.ts >= since]
        if until:
            entries = [e for e in entries if e.ts <= until]
        if search:
            pattern = re.compile(search, re.IGNORECASE)
            entries = [e for e in entries if pattern.search(e.message)]
        return [
            {"message": e.message, "level": e.level, "source": e.source, "ts": e.ts}
            for e in entries[-limit:]
        ]

    def get_sources(self) -> list[str]:
        return list(self._source_counts.keys())

    def get_level_counts(self) -> dict[str, int]:
        return dict(self._level_counts)

    def clear(self, source: str | None = None) -> int:
        with self._lock:
            if source:
                before = len(self._entries)
                self._entries = [e for e in self._entries if e.source != source]
                cleared = before - len(self._entries)
            else:
                cleared = len(self._entries)
                self._entries.clear()
                self._source_counts.clear()
                self._level_counts.clear()
            return cleared

    def get_stats(self) -> dict:
        return {
            "total_entries": len(self._entries),
            "max_entries": self._max_entries,
            "sources": len(self._source_counts),
            "level_counts": dict(self._level_counts),
            "source_counts": dict(self._source_counts),
        }


# ── Singleton ────────────────────────────────────────────────────────────────
log_aggregator = LogAggregator()
