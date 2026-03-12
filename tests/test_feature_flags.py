"""Tests for src/feature_flags.py — Dynamic feature toggling.

Covers: Flag, FeatureFlagManager (create, is_enabled, toggle, delete,
get_flag, list_flags, get_stats, persistence), feature_flags singleton.
Uses tmp_path for JSON file isolation.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.feature_flags import Flag, FeatureFlagManager, feature_flags


# ===========================================================================
# Flag dataclass
# ===========================================================================

class TestFlag:
    def test_defaults(self):
        f = Flag(name="test")
        assert f.enabled is False
        assert f.percentage == 100.0
        assert f.whitelist == []


# ===========================================================================
# FeatureFlagManager — create & is_enabled
# ===========================================================================

class TestCreateEnabled:
    def test_create(self, tmp_path):
        fm = FeatureFlagManager(store_path=tmp_path / "flags.json")
        flag = fm.create("dark_mode", enabled=True, description="Dark mode")
        assert flag.name == "dark_mode"
        assert flag.enabled is True

    def test_is_enabled_true(self, tmp_path):
        fm = FeatureFlagManager(store_path=tmp_path / "flags.json")
        fm.create("f1", enabled=True)
        assert fm.is_enabled("f1") is True

    def test_is_enabled_false(self, tmp_path):
        fm = FeatureFlagManager(store_path=tmp_path / "flags.json")
        fm.create("f1", enabled=False)
        assert fm.is_enabled("f1") is False

    def test_is_enabled_nonexistent(self, tmp_path):
        fm = FeatureFlagManager(store_path=tmp_path / "flags.json")
        assert fm.is_enabled("nope") is False

    def test_time_window_before(self, tmp_path):
        fm = FeatureFlagManager(store_path=tmp_path / "flags.json")
        future = time.time() + 3600
        fm.create("timed", enabled=True, start_ts=future)
        assert fm.is_enabled("timed") is False

    def test_time_window_after(self, tmp_path):
        fm = FeatureFlagManager(store_path=tmp_path / "flags.json")
        past = time.time() - 3600
        fm.create("timed", enabled=True, end_ts=past)
        assert fm.is_enabled("timed") is False

    def test_blacklist(self, tmp_path):
        fm = FeatureFlagManager(store_path=tmp_path / "flags.json")
        fm.create("f1", enabled=True, blacklist=["node_bad"])
        assert fm.is_enabled("f1", context="node_bad") is False
        assert fm.is_enabled("f1", context="node_ok") is True

    def test_whitelist_bypass(self, tmp_path):
        fm = FeatureFlagManager(store_path=tmp_path / "flags.json")
        fm.create("f1", enabled=True, percentage=0, whitelist=["vip"])
        assert fm.is_enabled("f1", context="vip") is True

    def test_percentage_rollout(self, tmp_path):
        fm = FeatureFlagManager(store_path=tmp_path / "flags.json")
        fm.create("f1", enabled=True, percentage=50.0)
        # With deterministic context, hash-based rollout
        results = {fm.is_enabled("f1", context=f"user_{i}") for i in range(100)}
        assert True in results  # some should be enabled
        assert False in results  # some should be disabled


# ===========================================================================
# FeatureFlagManager — toggle & delete
# ===========================================================================

class TestToggleDelete:
    def test_toggle(self, tmp_path):
        fm = FeatureFlagManager(store_path=tmp_path / "flags.json")
        fm.create("f1", enabled=True)
        fm.toggle("f1")
        assert fm.is_enabled("f1") is False

    def test_toggle_explicit(self, tmp_path):
        fm = FeatureFlagManager(store_path=tmp_path / "flags.json")
        fm.create("f1", enabled=False)
        fm.toggle("f1", enabled=True)
        assert fm.is_enabled("f1") is True

    def test_toggle_nonexistent(self, tmp_path):
        fm = FeatureFlagManager(store_path=tmp_path / "flags.json")
        assert fm.toggle("nope") is False

    def test_delete(self, tmp_path):
        fm = FeatureFlagManager(store_path=tmp_path / "flags.json")
        fm.create("temp")
        assert fm.delete("temp") is True
        assert fm.delete("temp") is False


# ===========================================================================
# FeatureFlagManager — get_flag, list, stats
# ===========================================================================

class TestGetListStats:
    def test_get_flag(self, tmp_path):
        fm = FeatureFlagManager(store_path=tmp_path / "flags.json")
        fm.create("f1", enabled=True)
        flag = fm.get_flag("f1")
        assert flag is not None
        assert flag["enabled"] is True

    def test_get_flag_nonexistent(self, tmp_path):
        fm = FeatureFlagManager(store_path=tmp_path / "flags.json")
        assert fm.get_flag("nope") is None

    def test_list_flags(self, tmp_path):
        fm = FeatureFlagManager(store_path=tmp_path / "flags.json")
        fm.create("a", enabled=True)
        fm.create("b", enabled=False)
        flags = fm.list_flags()
        assert len(flags) == 2

    def test_stats(self, tmp_path):
        fm = FeatureFlagManager(store_path=tmp_path / "flags.json")
        fm.create("a", enabled=True)
        fm.create("b", enabled=False)
        stats = fm.get_stats()
        assert stats["total_flags"] == 2
        assert stats["enabled"] == 1
        assert stats["disabled"] == 1


# ===========================================================================
# FeatureFlagManager — persistence
# ===========================================================================

class TestPersistence:
    def test_save_and_load(self, tmp_path):
        path = tmp_path / "flags.json"
        fm1 = FeatureFlagManager(store_path=path)
        fm1.create("persist", enabled=True, description="test")
        # Create new instance to test load
        fm2 = FeatureFlagManager(store_path=path)
        assert fm2.is_enabled("persist") is True
        flag = fm2.get_flag("persist")
        assert flag["description"] == "test"


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert feature_flags is not None
        assert isinstance(feature_flags, FeatureFlagManager)
