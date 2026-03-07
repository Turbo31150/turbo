"""Tests for src/code_improvement_tracker.py — Before/after code tracking.

Covers: FileSnapshot, ImprovementRecord, TrackerEvent, CodeImprovementTracker
(snapshot_before, snapshot_after, snapshot_batch_before, snapshot_batch_after,
get_improvement_summary, get_changed_files, get_diff_for_file,
get_pending_snapshots, clear_pending, save_report, get_events, get_stats),
code_improvement_tracker singleton.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.code_improvement_tracker import (
    FileSnapshot, ImprovementRecord, TrackerEvent,
    CodeImprovementTracker, code_improvement_tracker,
)


class TestFileSnapshot:
    def test_from_file(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("def foo():\n    pass\n\ndef bar():\n    pass\n")
        snap = FileSnapshot.from_file(str(f), label="before")
        assert snap.lines == 6  # 5 lines + trailing newline counts
        assert snap.functions == 2
        assert snap.label == "before"
        assert len(snap.hash) == 32  # md5 hex


class TestImprovementRecord:
    def test_unchanged(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("def foo():\n    pass\n")
        before = FileSnapshot.from_file(str(f), "before")
        after = FileSnapshot.from_file(str(f), "after")
        rec = ImprovementRecord(file=str(f), before=before, after=after)
        assert rec.changed is False
        assert rec.lines_delta == 0

    def test_changed(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("def foo():\n    pass\n")
        before = FileSnapshot.from_file(str(f), "before")
        f.write_text("def foo():\n    return 42\n\ndef bar():\n    pass\n")
        after = FileSnapshot.from_file(str(f), "after")
        rec = ImprovementRecord(file=str(f), before=before, after=after)
        assert rec.changed is True
        assert rec.lines_delta == 3
        assert rec.functions_delta == 1

    def test_get_diff(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("a\nb\nc\n")
        before = FileSnapshot.from_file(str(f), "before")
        f.write_text("a\nB\nc\n")
        after = FileSnapshot.from_file(str(f), "after")
        rec = ImprovementRecord(file=str(f), before=before, after=after)
        diff = rec.get_diff()
        assert "-b" in diff
        assert "+B" in diff

    def test_get_diff_stats(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("line1\nline2\n")
        before = FileSnapshot.from_file(str(f), "before")
        f.write_text("line1\nline2\nline3\nline4\n")
        after = FileSnapshot.from_file(str(f), "after")
        rec = ImprovementRecord(file=str(f), before=before, after=after)
        stats = rec.get_diff_stats()
        assert stats["added"] > 0

    def test_to_dict(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("pass\n")
        before = FileSnapshot.from_file(str(f), "before")
        after = FileSnapshot.from_file(str(f), "after")
        rec = ImprovementRecord(file=str(f), before=before, after=after)
        d = rec.to_dict()
        assert "lines_before" in d
        assert "changed" in d


class TestCodeImprovementTracker:
    def test_snapshot_before_after(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("def foo():\n    pass\n")

        tracker = CodeImprovementTracker()
        tracker.snapshot_before(str(f))

        # Modify file
        f.write_text("def foo():\n    return 42\n\ndef bar():\n    pass\n")

        record = tracker.snapshot_after(str(f))
        assert record is not None
        assert record.changed is True
        assert record.functions_delta == 1

    def test_snapshot_after_without_before(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("pass\n")
        tracker = CodeImprovementTracker()
        assert tracker.snapshot_after(str(f)) is None

    def test_snapshot_batch(self, tmp_path):
        f1 = tmp_path / "a.py"
        f2 = tmp_path / "b.py"
        f1.write_text("pass\n")
        f2.write_text("pass\n")

        tracker = CodeImprovementTracker()
        count = tracker.snapshot_batch_before([str(f1), str(f2)])
        assert count == 2

        # Modify
        f1.write_text("def new():\n    pass\n")

        records = tracker.snapshot_batch_after([str(f1), str(f2)])
        assert len(records) == 2
        changed = [r for r in records if r.changed]
        assert len(changed) == 1

    def test_get_improvement_summary(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("pass\n")

        tracker = CodeImprovementTracker()
        tracker.snapshot_before(str(f))
        f.write_text("def better():\n    return True\n")
        tracker.snapshot_after(str(f))

        summary = tracker.get_improvement_summary()
        assert summary["total_files"] == 1
        assert summary["changed_files"] == 1

    def test_get_improvement_summary_empty(self):
        tracker = CodeImprovementTracker()
        summary = tracker.get_improvement_summary()
        assert summary["total_files"] == 0

    def test_get_changed_files(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("pass\n")

        tracker = CodeImprovementTracker()
        tracker.snapshot_before(str(f))
        f.write_text("changed\n")
        tracker.snapshot_after(str(f))

        changed = tracker.get_changed_files()
        assert len(changed) == 1

    def test_get_diff_for_file(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("old\n")

        tracker = CodeImprovementTracker()
        tracker.snapshot_before(str(f))
        f.write_text("new\n")
        tracker.snapshot_after(str(f))

        diff = tracker.get_diff_for_file(str(f))
        assert diff is not None
        assert "-old" in diff
        assert "+new" in diff

    def test_get_diff_for_unknown_file(self):
        tracker = CodeImprovementTracker()
        assert tracker.get_diff_for_file("nonexistent.py") is None


class TestPending:
    def test_pending_snapshots(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("pass\n")

        tracker = CodeImprovementTracker()
        tracker.snapshot_before(str(f))
        pending = tracker.get_pending_snapshots()
        assert str(f) in pending

    def test_clear_pending(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("pass\n")

        tracker = CodeImprovementTracker()
        tracker.snapshot_before(str(f))
        assert tracker.clear_pending() == 1
        assert tracker.get_pending_snapshots() == []


class TestSaveReport:
    def test_save(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("pass\n")

        tracker = CodeImprovementTracker()
        tracker.snapshot_before(str(f))
        tracker.snapshot_after(str(f))

        report_path = tmp_path / "report.json"
        result = tracker.save_report(report_path)
        assert Path(result).exists()
        data = json.loads(Path(result).read_text())
        assert "total_files" in data


class TestEventsStats:
    def test_events_empty(self):
        assert CodeImprovementTracker().get_events() == []

    def test_stats(self):
        stats = CodeImprovementTracker().get_stats()
        assert stats["total_records"] == 0
        assert stats["pending_snapshots"] == 0


class TestSingleton:
    def test_exists(self):
        assert isinstance(code_improvement_tracker, CodeImprovementTracker)
