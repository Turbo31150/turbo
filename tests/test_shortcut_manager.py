"""Tests for src/shortcut_manager.py — Global hotkey registration and management.

Covers: Shortcut, ActivationEvent, ShortcutManager (register, unregister,
_normalize_keys, activate, activate_by_keys, enable/disable, list_shortcuts,
list_groups, check_conflicts, get_activations, get_stats),
shortcut_manager singleton.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.shortcut_manager import (
    Shortcut, ActivationEvent, ShortcutManager, shortcut_manager,
)


# ===========================================================================
# Dataclasses
# ===========================================================================

class TestShortcut:
    def test_defaults(self):
        s = Shortcut(name="test", keys="Ctrl+A")
        assert s.callback is None
        assert s.description == ""
        assert s.group == "default"
        assert s.enabled is True
        assert s.activation_count == 0
        assert s.last_activated is None
        assert s.created_at > 0


class TestActivationEvent:
    def test_defaults(self):
        e = ActivationEvent(name="test", keys="Ctrl+A")
        assert e.result == ""
        assert e.success is True
        assert e.timestamp > 0


# ===========================================================================
# ShortcutManager — registration
# ===========================================================================

class TestRegistration:
    def test_register(self):
        sm = ShortcutManager()
        sc = sm.register("test", "Ctrl+A", description="Test shortcut")
        assert sc.name == "test"
        assert sc.keys == "A+Ctrl"  # normalized + sorted
        assert sc.description == "Test shortcut"

    def test_register_with_callback(self):
        sm = ShortcutManager()
        cb = lambda: "hello"
        sc = sm.register("test", "Ctrl+Shift+J", callback=cb)
        assert sc.callback is cb

    def test_register_with_group(self):
        sm = ShortcutManager()
        sc = sm.register("test", "Alt+F4", group="system")
        assert sc.group == "system"

    def test_unregister(self):
        sm = ShortcutManager()
        sm.register("test", "Ctrl+A")
        assert sm.unregister("test") is True
        assert sm.unregister("test") is False

    def test_unregister_nonexistent(self):
        sm = ShortcutManager()
        assert sm.unregister("nope") is False


# ===========================================================================
# ShortcutManager — _normalize_keys
# ===========================================================================

class TestNormalizeKeys:
    def test_basic(self):
        assert ShortcutManager._normalize_keys("ctrl+a") == "A+Ctrl"

    def test_case_insensitive(self):
        assert ShortcutManager._normalize_keys("CTRL+SHIFT+J") == "Ctrl+J+Shift"

    def test_sorted(self):
        assert ShortcutManager._normalize_keys("shift+ctrl+alt") == "Alt+Ctrl+Shift"

    def test_spaces(self):
        assert ShortcutManager._normalize_keys("ctrl + a") == "A+Ctrl"

    def test_single_key(self):
        assert ShortcutManager._normalize_keys("f1") == "F1"


# ===========================================================================
# ShortcutManager — activate
# ===========================================================================

class TestActivate:
    def test_activate_with_callback(self):
        sm = ShortcutManager()
        sm.register("test", "Ctrl+A", callback=lambda: 42)
        result = sm.activate("test")
        assert result["success"] is True
        assert result["result"] == 42
        assert result["name"] == "test"

    def test_activate_no_callback(self):
        sm = ShortcutManager()
        sm.register("test", "Ctrl+A")
        result = sm.activate("test")
        assert result["success"] is True
        assert result["result"] is None

    def test_activate_not_found(self):
        sm = ShortcutManager()
        result = sm.activate("nope")
        assert result["success"] is False
        assert "not found" in result["error"]

    def test_activate_disabled(self):
        sm = ShortcutManager()
        sm.register("test", "Ctrl+A")
        sm.disable("test")
        result = sm.activate("test")
        assert result["success"] is False
        assert "disabled" in result["error"]

    def test_activate_callback_exception(self):
        sm = ShortcutManager()
        sm.register("test", "Ctrl+A", callback=lambda: 1 / 0)
        result = sm.activate("test")
        assert result["success"] is False
        assert "division" in str(result["result"]).lower()

    def test_activate_increments_count(self):
        sm = ShortcutManager()
        sm.register("test", "Ctrl+A", callback=lambda: None)
        sm.activate("test")
        sm.activate("test")
        sc = sm.get("test")
        assert sc.activation_count == 2
        assert sc.last_activated is not None

    def test_activate_by_keys(self):
        sm = ShortcutManager()
        sm.register("test", "Ctrl+A", callback=lambda: "ok")
        result = sm.activate_by_keys("ctrl+a")
        assert result["success"] is True
        assert result["result"] == "ok"

    def test_activate_by_keys_not_found(self):
        sm = ShortcutManager()
        result = sm.activate_by_keys("Ctrl+Z")
        assert result["success"] is False
        assert "No shortcut" in result["error"]


# ===========================================================================
# ShortcutManager — enable / disable
# ===========================================================================

class TestEnableDisable:
    def test_enable(self):
        sm = ShortcutManager()
        sm.register("test", "Ctrl+A")
        sm.disable("test")
        assert sm.enable("test") is True
        sc = sm.get("test")
        assert sc.enabled is True

    def test_disable(self):
        sm = ShortcutManager()
        sm.register("test", "Ctrl+A")
        assert sm.disable("test") is True
        sc = sm.get("test")
        assert sc.enabled is False

    def test_enable_nonexistent(self):
        sm = ShortcutManager()
        assert sm.enable("nope") is False

    def test_disable_nonexistent(self):
        sm = ShortcutManager()
        assert sm.disable("nope") is False


# ===========================================================================
# ShortcutManager — query
# ===========================================================================

class TestQuery:
    def test_list_shortcuts(self):
        sm = ShortcutManager()
        sm.register("a", "Ctrl+A", group="nav")
        sm.register("b", "Ctrl+B", group="edit")
        result = sm.list_shortcuts()
        assert len(result) == 2

    def test_list_shortcuts_filter_group(self):
        sm = ShortcutManager()
        sm.register("a", "Ctrl+A", group="nav")
        sm.register("b", "Ctrl+B", group="edit")
        result = sm.list_shortcuts(group="nav")
        assert len(result) == 1
        assert result[0]["name"] == "a"

    def test_list_groups(self):
        sm = ShortcutManager()
        sm.register("a", "Ctrl+A", group="nav")
        sm.register("b", "Ctrl+B", group="edit")
        sm.register("c", "Ctrl+C", group="nav")
        groups = sm.list_groups()
        assert set(groups) == {"nav", "edit"}

    def test_check_conflicts_none(self):
        sm = ShortcutManager()
        sm.register("a", "Ctrl+A")
        sm.register("b", "Ctrl+B")
        assert sm.check_conflicts() == []

    def test_check_conflicts_found(self):
        sm = ShortcutManager()
        sm.register("a", "Ctrl+A")
        # Force same keys on a different shortcut
        sm._shortcuts["a"].keys = "A+Ctrl"
        sm.register("b", "Ctrl+A")  # same keys -> conflict
        conflicts = sm.check_conflicts()
        assert len(conflicts) == 1
        assert set(conflicts[0]["shortcuts"]) == {"a", "b"}

    def test_get_activations_empty(self):
        sm = ShortcutManager()
        assert sm.get_activations() == []

    def test_get_activations_filtered(self):
        sm = ShortcutManager()
        sm.register("a", "Ctrl+A", callback=lambda: None)
        sm.register("b", "Ctrl+B", callback=lambda: None)
        sm.activate("a")
        sm.activate("b")
        sm.activate("a")
        result = sm.get_activations(name="a")
        assert len(result) == 2
        assert all(r["name"] == "a" for r in result)

    def test_get_activations_limit(self):
        sm = ShortcutManager()
        sm.register("a", "Ctrl+A", callback=lambda: None)
        for _ in range(20):
            sm.activate("a")
        result = sm.get_activations(limit=5)
        assert len(result) == 5


# ===========================================================================
# ShortcutManager — get_stats
# ===========================================================================

class TestStats:
    def test_stats(self):
        sm = ShortcutManager()
        sm.register("a", "Ctrl+A", callback=lambda: None, group="g1")
        sm.register("b", "Ctrl+B", group="g2")
        sm.disable("b")
        sm.activate("a")
        stats = sm.get_stats()
        assert stats["total_shortcuts"] == 2
        assert stats["enabled"] == 1
        assert stats["disabled"] == 1
        assert stats["groups"] == 2
        assert stats["total_activations"] == 1
        assert stats["history_size"] == 1


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert shortcut_manager is not None
        assert isinstance(shortcut_manager, ShortcutManager)
