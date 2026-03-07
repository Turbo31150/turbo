"""Code Improvement Tracker — Before/after code change analysis.

Tracks file snapshots before modifications, computes diffs,
quality deltas, and generates improvement reports.
Integrates with auto_auditor for scoring.
Designed for JARVIS total automation.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import logging
import re
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger("jarvis.code_improvement_tracker")


@dataclass
class FileSnapshot:
    """Snapshot of a file at a point in time."""
    path: str
    content: str
    hash: str
    lines: int
    functions: int
    classes: int
    timestamp: float = field(default_factory=time.time)
    label: str = ""  # "before" or "after"

    @staticmethod
    def from_file(filepath: str, label: str = "") -> FileSnapshot:
        content = Path(filepath).read_text(encoding="utf-8", errors="replace")
        return FileSnapshot(
            path=filepath,
            content=content,
            hash=hashlib.md5(content.encode()).hexdigest(),
            lines=content.count("\n") + 1,
            functions=len(re.findall(r'^(?:    )?def \w+', content, re.MULTILINE)),
            classes=len(re.findall(r'^class \w+', content, re.MULTILINE)),
            label=label,
        )


@dataclass
class ImprovementRecord:
    """Record of a before/after improvement."""
    file: str
    before: FileSnapshot
    after: FileSnapshot
    timestamp: float = field(default_factory=time.time)

    @property
    def changed(self) -> bool:
        return self.before.hash != self.after.hash

    @property
    def lines_delta(self) -> int:
        return self.after.lines - self.before.lines

    @property
    def functions_delta(self) -> int:
        return self.after.functions - self.before.functions

    def get_diff(self, context: int = 3) -> str:
        """Generate unified diff between before and after."""
        before_lines = self.before.content.splitlines(keepends=True)
        after_lines = self.after.content.splitlines(keepends=True)
        diff = difflib.unified_diff(
            before_lines, after_lines,
            fromfile=f"{self.file} (before)",
            tofile=f"{self.file} (after)",
            n=context,
        )
        return "".join(diff)

    def get_diff_stats(self) -> dict[str, int]:
        """Count added/removed/modified lines."""
        diff = self.get_diff(0)
        added = sum(1 for line in diff.splitlines() if line.startswith("+") and not line.startswith("+++"))
        removed = sum(1 for line in diff.splitlines() if line.startswith("-") and not line.startswith("---"))
        return {"added": added, "removed": removed, "net": added - removed}

    def to_dict(self) -> dict[str, Any]:
        stats = self.get_diff_stats()
        return {
            "file": self.file,
            "changed": self.changed,
            "lines_before": self.before.lines,
            "lines_after": self.after.lines,
            "lines_delta": self.lines_delta,
            "functions_before": self.before.functions,
            "functions_after": self.after.functions,
            "functions_delta": self.functions_delta,
            "lines_added": stats["added"],
            "lines_removed": stats["removed"],
            "timestamp": self.timestamp,
        }


@dataclass
class TrackerEvent:
    action: str
    detail: str = ""
    timestamp: float = field(default_factory=time.time)
    success: bool = True


class CodeImprovementTracker:
    """Tracks code changes with before/after snapshots."""

    def __init__(self, store_path: Path | None = None):
        self._snapshots: dict[str, FileSnapshot] = {}  # path -> before snapshot
        self._records: list[ImprovementRecord] = []
        self._events: list[TrackerEvent] = []
        self._lock = threading.Lock()
        self._store = store_path

    # ── Snapshot Management ───────────────────────────────────────────────

    def snapshot_before(self, filepath: str) -> FileSnapshot:
        """Take a 'before' snapshot of a file."""
        snap = FileSnapshot.from_file(filepath, label="before")
        with self._lock:
            self._snapshots[filepath] = snap
            self._events.append(TrackerEvent(
                action="snapshot_before", detail=filepath,
            ))
        return snap

    def snapshot_after(self, filepath: str) -> ImprovementRecord | None:
        """Take an 'after' snapshot and create improvement record."""
        with self._lock:
            before = self._snapshots.pop(filepath, None)
        if before is None:
            logger.warning("No before snapshot for %s", filepath)
            return None

        after = FileSnapshot.from_file(filepath, label="after")
        record = ImprovementRecord(file=filepath, before=before, after=after)

        with self._lock:
            self._records.append(record)
            self._events.append(TrackerEvent(
                action="snapshot_after", detail=f"{filepath} changed={record.changed}",
            ))

        return record

    def snapshot_batch_before(self, filepaths: list[str]) -> int:
        """Snapshot multiple files before changes."""
        count = 0
        for fp in filepaths:
            try:
                self.snapshot_before(fp)
                count += 1
            except Exception as e:
                logger.debug("snapshot_before %s: %s", fp, e)
        return count

    def snapshot_batch_after(self, filepaths: list[str]) -> list[ImprovementRecord]:
        """Complete snapshots for multiple files."""
        records = []
        for fp in filepaths:
            try:
                rec = self.snapshot_after(fp)
                if rec:
                    records.append(rec)
            except Exception as e:
                logger.debug("snapshot_after %s: %s", fp, e)
        return records

    # ── Analysis ──────────────────────────────────────────────────────────

    def get_improvement_summary(self) -> dict[str, Any]:
        """Summarize all tracked improvements."""
        with self._lock:
            records = list(self._records)

        if not records:
            return {"total_files": 0, "changed_files": 0}

        changed = [r for r in records if r.changed]
        total_added = sum(r.get_diff_stats()["added"] for r in changed)
        total_removed = sum(r.get_diff_stats()["removed"] for r in changed)

        return {
            "total_files": len(records),
            "changed_files": len(changed),
            "unchanged_files": len(records) - len(changed),
            "total_lines_added": total_added,
            "total_lines_removed": total_removed,
            "net_lines": total_added - total_removed,
            "records": [r.to_dict() for r in records],
        }

    def get_changed_files(self) -> list[dict]:
        """Get only files that were actually modified."""
        with self._lock:
            return [r.to_dict() for r in self._records if r.changed]

    def get_diff_for_file(self, filepath: str) -> str | None:
        """Get diff for a specific tracked file."""
        with self._lock:
            for r in reversed(self._records):
                if r.file == filepath and r.changed:
                    return r.get_diff()
        return None

    # ── Pending ───────────────────────────────────────────────────────────

    def get_pending_snapshots(self) -> list[str]:
        """List files with 'before' snapshot but no 'after' yet."""
        with self._lock:
            return list(self._snapshots.keys())

    def clear_pending(self) -> int:
        """Clear all pending before snapshots."""
        with self._lock:
            count = len(self._snapshots)
            self._snapshots.clear()
            return count

    # ── Persistence ───────────────────────────────────────────────────────

    def save_report(self, filepath: Path | None = None) -> str:
        """Save improvement summary to JSON file."""
        path = filepath or (self._store or Path("data/improvement_report.json"))
        path.parent.mkdir(parents=True, exist_ok=True)
        summary = self.get_improvement_summary()
        summary["generated_at"] = time.time()
        path.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
        return str(path)

    # ── Events / Stats ────────────────────────────────────────────────────

    def get_events(self, limit: int = 50) -> list[dict]:
        with self._lock:
            return [
                {"action": e.action, "timestamp": e.timestamp,
                 "success": e.success, "detail": e.detail}
                for e in self._events[-limit:]
            ]

    def get_stats(self) -> dict:
        with self._lock:
            return {
                "total_records": len(self._records),
                "pending_snapshots": len(self._snapshots),
                "total_events": len(self._events),
                "changed_files": sum(1 for r in self._records if r.changed),
            }


# ── Singleton ─────────────────────────────────────────────────────────────────
code_improvement_tracker = CodeImprovementTracker()
