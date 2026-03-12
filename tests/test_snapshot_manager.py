"""Tests for src/snapshot_manager.py — System state snapshots with comparison.

Covers: Snapshot, SnapshotManager (capture, capture_env, get, list_snapshots,
delete, diff, _compute_diff, restore, get_restore_history, add_tag, remove_tag,
get_stats), snapshot_manager singleton.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.snapshot_manager import Snapshot, SnapshotManager, snapshot_manager


# ===========================================================================
# Snapshot dataclass
# ===========================================================================

class TestSnapshot:
    def test_defaults(self):
        s = Snapshot(snapshot_id="s1", name="test", data={"a": 1})
        assert s.tags == []
        assert s.description == ""
        assert s.timestamp > 0

    def test_size_property(self):
        s = Snapshot(snapshot_id="s1", name="test", data={
            "list_val": [1, 2, 3],
            "dict_val": {"a": 1, "b": 2},
            "scalar": 42,
        })
        # list: 3, dict: 2, scalar: 1 → 6
        assert s.size == 6


# ===========================================================================
# SnapshotManager — capture
# ===========================================================================

class TestCapture:
    def test_capture_basic(self):
        sm = SnapshotManager()
        snap = sm.capture("test", {"key": "value"})
        assert snap.snapshot_id == "snap_1"
        assert snap.name == "test"
        assert snap.data == {"key": "value"}

    def test_capture_with_tags_and_desc(self):
        sm = SnapshotManager()
        snap = sm.capture("t", {"k": "v"}, tags=["prod", "v1"], description="initial")
        assert snap.tags == ["prod", "v1"]
        assert snap.description == "initial"

    def test_capture_deep_copies(self):
        sm = SnapshotManager()
        data = {"nested": {"key": "original"}}
        snap = sm.capture("t", data)
        data["nested"]["key"] = "modified"
        assert snap.data["nested"]["key"] == "original"

    def test_capture_env(self):
        sm = SnapshotManager()
        with patch.dict("os.environ", {"TEST_VAR": "hello"}, clear=True):
            snap = sm.capture_env()
        assert "environment" in snap.data
        assert snap.data["environment"]["TEST_VAR"] == "hello"
        assert snap.description == "Environment variables snapshot"

    def test_counter_increments(self):
        sm = SnapshotManager()
        s1 = sm.capture("a", {})
        s2 = sm.capture("b", {})
        assert s1.snapshot_id == "snap_1"
        assert s2.snapshot_id == "snap_2"


# ===========================================================================
# SnapshotManager — query
# ===========================================================================

class TestQuery:
    def test_get_existing(self):
        sm = SnapshotManager()
        snap = sm.capture("test", {"k": "v"})
        retrieved = sm.get(snap.snapshot_id)
        assert retrieved is not None
        assert retrieved.name == "test"

    def test_get_nonexistent(self):
        sm = SnapshotManager()
        assert sm.get("snap_999") is None

    def test_list_snapshots(self):
        sm = SnapshotManager()
        sm.capture("a", {"k": 1})
        sm.capture("b", {"k": 2})
        listing = sm.list_snapshots()
        assert len(listing) == 2
        assert listing[0]["name"] == "a"
        assert listing[1]["name"] == "b"
        assert "size" in listing[0]

    def test_list_snapshots_filter_by_tag(self):
        sm = SnapshotManager()
        sm.capture("a", {}, tags=["prod"])
        sm.capture("b", {}, tags=["dev"])
        sm.capture("c", {}, tags=["prod", "v2"])
        filtered = sm.list_snapshots(tag="prod")
        assert len(filtered) == 2

    def test_delete_existing(self):
        sm = SnapshotManager()
        snap = sm.capture("test", {})
        assert sm.delete(snap.snapshot_id) is True
        assert sm.get(snap.snapshot_id) is None

    def test_delete_nonexistent(self):
        sm = SnapshotManager()
        assert sm.delete("snap_999") is False


# ===========================================================================
# SnapshotManager — diff
# ===========================================================================

class TestDiff:
    def test_identical(self):
        sm = SnapshotManager()
        s1 = sm.capture("a", {"x": 1, "y": 2})
        s2 = sm.capture("b", {"x": 1, "y": 2})
        result = sm.diff(s1.snapshot_id, s2.snapshot_id)
        assert result["identical"] is True
        assert result["added"] == {}
        assert result["removed"] == {}

    def test_added_keys(self):
        sm = SnapshotManager()
        s1 = sm.capture("a", {"x": 1})
        s2 = sm.capture("b", {"x": 1, "y": 2})
        result = sm.diff(s1.snapshot_id, s2.snapshot_id)
        assert "y" in result["added"]
        assert result["identical"] is False

    def test_removed_keys(self):
        sm = SnapshotManager()
        s1 = sm.capture("a", {"x": 1, "y": 2})
        s2 = sm.capture("b", {"x": 1})
        result = sm.diff(s1.snapshot_id, s2.snapshot_id)
        assert "y" in result["removed"]

    def test_changed_keys(self):
        sm = SnapshotManager()
        s1 = sm.capture("a", {"x": 1})
        s2 = sm.capture("b", {"x": 99})
        result = sm.diff(s1.snapshot_id, s2.snapshot_id)
        assert result["changed"]["x"]["old"] == 1
        assert result["changed"]["x"]["new"] == 99

    def test_nested_diff(self):
        sm = SnapshotManager()
        s1 = sm.capture("a", {"cfg": {"a": 1, "b": 2}})
        s2 = sm.capture("b", {"cfg": {"a": 1, "b": 99}})
        result = sm.diff(s1.snapshot_id, s2.snapshot_id)
        assert "cfg" in result["changed"]

    def test_diff_snapshot_not_found(self):
        sm = SnapshotManager()
        sm.capture("a", {})
        result = sm.diff("snap_1", "snap_999")
        assert "error" in result


# ===========================================================================
# SnapshotManager — restore
# ===========================================================================

class TestRestore:
    def test_restore_returns_data(self):
        sm = SnapshotManager()
        snap = sm.capture("test", {"config": "original"})
        restored = sm.restore(snap.snapshot_id)
        assert restored == {"config": "original"}

    def test_restore_deep_copies(self):
        sm = SnapshotManager()
        snap = sm.capture("test", {"nested": {"k": "v"}})
        restored = sm.restore(snap.snapshot_id)
        restored["nested"]["k"] = "changed"
        assert sm.get(snap.snapshot_id).data["nested"]["k"] == "v"

    def test_restore_nonexistent(self):
        sm = SnapshotManager()
        assert sm.restore("snap_999") is None

    def test_restore_history(self):
        sm = SnapshotManager()
        snap = sm.capture("test", {})
        sm.restore(snap.snapshot_id)
        history = sm.get_restore_history()
        assert len(history) == 1
        assert history[0]["snapshot_id"] == snap.snapshot_id


# ===========================================================================
# SnapshotManager — tags
# ===========================================================================

class TestTags:
    def test_add_tag(self):
        sm = SnapshotManager()
        snap = sm.capture("test", {})
        assert sm.add_tag(snap.snapshot_id, "important") is True
        assert "important" in sm.get(snap.snapshot_id).tags

    def test_add_duplicate_tag(self):
        sm = SnapshotManager()
        snap = sm.capture("test", {}, tags=["existing"])
        assert sm.add_tag(snap.snapshot_id, "existing") is False

    def test_add_tag_nonexistent(self):
        sm = SnapshotManager()
        assert sm.add_tag("snap_999", "tag") is False

    def test_remove_tag(self):
        sm = SnapshotManager()
        snap = sm.capture("test", {}, tags=["removeme"])
        assert sm.remove_tag(snap.snapshot_id, "removeme") is True
        assert "removeme" not in sm.get(snap.snapshot_id).tags

    def test_remove_tag_not_present(self):
        sm = SnapshotManager()
        snap = sm.capture("test", {})
        assert sm.remove_tag(snap.snapshot_id, "nope") is False


# ===========================================================================
# SnapshotManager — stats
# ===========================================================================

class TestStats:
    def test_stats(self):
        sm = SnapshotManager()
        sm.capture("a", {}, tags=["t1"])
        sm.capture("b", {}, tags=["t1", "t2"])
        stats = sm.get_stats()
        assert stats["total_snapshots"] == 2
        assert stats["total_tags"] == 2
        assert sorted(stats["tags"]) == ["t1", "t2"]

    def test_stats_empty(self):
        sm = SnapshotManager()
        stats = sm.get_stats()
        assert stats["total_snapshots"] == 0
        assert stats["total_restores"] == 0


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert snapshot_manager is not None
        assert isinstance(snapshot_manager, SnapshotManager)
