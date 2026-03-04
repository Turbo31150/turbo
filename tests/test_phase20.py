"""Phase 20 Tests — Clipboard Manager, Shortcut Manager, Snapshot Manager, MCP Handlers."""

import asyncio
import json
import pytest


# ═══════════════════════════════════════════════════════════════════════════
# CLIPBOARD MANAGER
# ═══════════════════════════════════════════════════════════════════════════

class TestClipboardManager:
    @staticmethod
    def _make():
        from src.clipboard_manager import ClipboardManager
        return ClipboardManager()

    def test_singleton_exists(self):
        from src.clipboard_manager import clipboard_manager
        assert clipboard_manager is not None

    def test_capture(self):
        cm = self._make()
        entry = cm.capture("hello world")
        assert entry.content == "hello world"
        assert entry.category.value == "text"

    def test_auto_detect_url(self):
        cm = self._make()
        entry = cm.capture("https://example.com")
        assert entry.category.value == "url"

    def test_auto_detect_path(self):
        cm = self._make()
        entry = cm.capture("C:\\Users\\test\\file.txt")
        assert entry.category.value == "path"

    def test_auto_detect_code(self):
        cm = self._make()
        entry = cm.capture("def hello():\n    pass")
        assert entry.category.value == "code"

    def test_history(self):
        cm = self._make()
        cm.capture("a")
        cm.capture("b")
        h = cm.get_history()
        assert len(h) == 2

    def test_history_filter(self):
        cm = self._make()
        cm.capture("hello")
        cm.capture("https://test.com")
        h = cm.get_history(category="url")
        assert len(h) == 1

    def test_search(self):
        cm = self._make()
        cm.capture("alpha beta")
        cm.capture("gamma delta")
        results = cm.search("alpha")
        assert len(results) == 1

    def test_pin_unpin(self):
        cm = self._make()
        cm.capture("pinme")
        assert cm.pin(0)
        h = cm.get_history()
        assert h[-1]["pinned"]
        assert cm.unpin(0)

    def test_clear_keep_pinned(self):
        cm = self._make()
        cm.capture("a")
        cm.capture("b")
        cm.pin(0)  # pin last
        cleared = cm.clear(keep_pinned=True)
        assert cleared == 1
        assert len(cm.get_history()) == 1

    def test_cleanup_expired(self):
        cm = self._make()
        cm._ttl = 0  # expire immediately
        cm.capture("old")
        import time
        time.sleep(0.01)
        removed = cm.cleanup_expired()
        assert removed == 1

    def test_max_history(self):
        cm = ClipboardManager(max_history=3)
        for i in range(5):
            cm.capture(f"item {i}")
        assert len(cm.get_history()) <= 3

    def test_stats(self):
        cm = self._make()
        cm.capture("hello")
        cm.capture("https://x.com")
        stats = cm.get_stats()
        assert stats["total_entries"] == 2
        assert "categories" in stats


def ClipboardManager(max_history=200, ttl_seconds=3600):
    from src.clipboard_manager import ClipboardManager as CM
    return CM(max_history=max_history, ttl_seconds=ttl_seconds)


# ═══════════════════════════════════════════════════════════════════════════
# SHORTCUT MANAGER
# ═══════════════════════════════════════════════════════════════════════════

class TestShortcutManager:
    @staticmethod
    def _make():
        from src.shortcut_manager import ShortcutManager
        return ShortcutManager()

    def test_singleton_exists(self):
        from src.shortcut_manager import shortcut_manager
        assert shortcut_manager is not None

    def test_register(self):
        sm = self._make()
        sc = sm.register("test", "Ctrl+T")
        assert sc.name == "test"
        assert "Ctrl" in sc.keys

    def test_unregister(self):
        sm = self._make()
        sm.register("temp", "Ctrl+X")
        assert sm.unregister("temp")
        assert not sm.unregister("temp")

    def test_activate(self):
        sm = self._make()
        sm.register("greet", "Ctrl+G", callback=lambda: "hello")
        result = sm.activate("greet")
        assert result["success"]
        assert result["result"] == "hello"

    def test_activate_not_found(self):
        sm = self._make()
        result = sm.activate("nope")
        assert not result["success"]

    def test_activate_disabled(self):
        sm = self._make()
        sm.register("cmd", "Ctrl+D", callback=lambda: "ok")
        sm.disable("cmd")
        result = sm.activate("cmd")
        assert not result["success"]

    def test_activate_by_keys(self):
        sm = self._make()
        sm.register("cmd", "Ctrl+K", callback=lambda: 42)
        result = sm.activate_by_keys("Ctrl+K")
        assert result["success"]
        assert result["result"] == 42

    def test_enable_disable(self):
        sm = self._make()
        sm.register("cmd", "Ctrl+E")
        sm.disable("cmd")
        assert not sm.get("cmd").enabled
        sm.enable("cmd")
        assert sm.get("cmd").enabled

    def test_activation_count(self):
        sm = self._make()
        sm.register("cmd", "Ctrl+C", callback=lambda: None)
        sm.activate("cmd")
        sm.activate("cmd")
        assert sm.get("cmd").activation_count == 2

    def test_list_shortcuts(self):
        sm = self._make()
        sm.register("a", "Ctrl+A", group="g1")
        sm.register("b", "Ctrl+B", group="g2")
        assert len(sm.list_shortcuts()) == 2
        assert len(sm.list_shortcuts(group="g1")) == 1

    def test_list_groups(self):
        sm = self._make()
        sm.register("a", "Ctrl+A", group="alpha")
        sm.register("b", "Ctrl+B", group="beta")
        groups = sm.list_groups()
        assert "alpha" in groups

    def test_check_conflicts(self):
        sm = self._make()
        sm.register("a", "Ctrl+X")
        sm.register("b", "Ctrl+X")
        conflicts = sm.check_conflicts()
        assert len(conflicts) == 1

    def test_activations_history(self):
        sm = self._make()
        sm.register("cmd", "Ctrl+H", callback=lambda: None)
        sm.activate("cmd")
        h = sm.get_activations()
        assert len(h) >= 1

    def test_error_in_callback(self):
        sm = self._make()
        sm.register("bad", "Ctrl+Z", callback=lambda: 1/0)
        result = sm.activate("bad")
        assert not result["success"]

    def test_stats(self):
        sm = self._make()
        sm.register("a", "Ctrl+1", group="g")
        sm.register("b", "Ctrl+2", group="g")
        sm.activate("a")
        stats = sm.get_stats()
        assert stats["total_shortcuts"] == 2
        assert stats["total_activations"] == 1


# ═══════════════════════════════════════════════════════════════════════════
# SNAPSHOT MANAGER
# ═══════════════════════════════════════════════════════════════════════════

class TestSnapshotManager:
    @staticmethod
    def _make():
        from src.snapshot_manager import SnapshotManager
        return SnapshotManager()

    def test_singleton_exists(self):
        from src.snapshot_manager import snapshot_manager
        assert snapshot_manager is not None

    def test_capture(self):
        sm = self._make()
        snap = sm.capture("test", {"key": "val"})
        assert snap.name == "test"
        assert snap.data["key"] == "val"

    def test_get(self):
        sm = self._make()
        snap = sm.capture("test", {"x": 1})
        assert sm.get(snap.snapshot_id) is not None
        assert sm.get("nonexistent") is None

    def test_delete(self):
        sm = self._make()
        snap = sm.capture("del", {})
        assert sm.delete(snap.snapshot_id)
        assert not sm.delete(snap.snapshot_id)

    def test_list_snapshots(self):
        sm = self._make()
        sm.capture("a", {}, tags=["prod"])
        sm.capture("b", {}, tags=["dev"])
        assert len(sm.list_snapshots()) == 2
        assert len(sm.list_snapshots(tag="prod")) == 1

    def test_diff_identical(self):
        sm = self._make()
        s1 = sm.capture("a", {"x": 1, "y": 2})
        s2 = sm.capture("b", {"x": 1, "y": 2})
        d = sm.diff(s1.snapshot_id, s2.snapshot_id)
        assert d["identical"]

    def test_diff_changes(self):
        sm = self._make()
        s1 = sm.capture("a", {"x": 1, "y": 2})
        s2 = sm.capture("b", {"x": 1, "y": 3, "z": 4})
        d = sm.diff(s1.snapshot_id, s2.snapshot_id)
        assert not d["identical"]
        assert "z" in d["added"]
        assert "y" in d["changed"]

    def test_diff_removed(self):
        sm = self._make()
        s1 = sm.capture("a", {"x": 1, "y": 2})
        s2 = sm.capture("b", {"x": 1})
        d = sm.diff(s1.snapshot_id, s2.snapshot_id)
        assert "y" in d["removed"]

    def test_restore(self):
        sm = self._make()
        snap = sm.capture("orig", {"key": "original"})
        data = sm.restore(snap.snapshot_id)
        assert data["key"] == "original"

    def test_restore_history(self):
        sm = self._make()
        snap = sm.capture("r", {"a": 1})
        sm.restore(snap.snapshot_id)
        h = sm.get_restore_history()
        assert len(h) == 1

    def test_add_remove_tag(self):
        sm = self._make()
        snap = sm.capture("t", {})
        assert sm.add_tag(snap.snapshot_id, "important")
        assert "important" in sm.get(snap.snapshot_id).tags
        assert sm.remove_tag(snap.snapshot_id, "important")
        assert "important" not in sm.get(snap.snapshot_id).tags

    def test_capture_env(self):
        sm = self._make()
        snap = sm.capture_env()
        assert "environment" in snap.data
        assert isinstance(snap.data["environment"], dict)

    def test_deep_copy(self):
        sm = self._make()
        data = {"nested": {"val": 1}}
        snap = sm.capture("dc", data)
        data["nested"]["val"] = 999
        assert sm.get(snap.snapshot_id).data["nested"]["val"] == 1

    def test_stats(self):
        sm = self._make()
        sm.capture("a", {}, tags=["t1"])
        sm.capture("b", {}, tags=["t2"])
        stats = sm.get_stats()
        assert stats["total_snapshots"] == 2
        assert stats["total_tags"] == 2


# ═══════════════════════════════════════════════════════════════════════════
# MCP HANDLERS — Phase 20
# ═══════════════════════════════════════════════════════════════════════════

class TestMCPHandlersPhase20:
    def test_clipmgr_history(self):
        from src.mcp_server import handle_clipmgr_history
        result = asyncio.run(handle_clipmgr_history({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_clipmgr_search(self):
        from src.mcp_server import handle_clipmgr_search
        result = asyncio.run(handle_clipmgr_search({"query": "test"}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_clipmgr_stats(self):
        from src.mcp_server import handle_clipmgr_stats
        result = asyncio.run(handle_clipmgr_stats({}))
        data = json.loads(result[0].text)
        assert "total_entries" in data

    def test_hotkey_list(self):
        from src.mcp_server import handle_hotkey_list
        result = asyncio.run(handle_hotkey_list({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_hotkey_activations(self):
        from src.mcp_server import handle_hotkey_activations
        result = asyncio.run(handle_hotkey_activations({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_hotkey_stats(self):
        from src.mcp_server import handle_hotkey_stats
        result = asyncio.run(handle_hotkey_stats({}))
        data = json.loads(result[0].text)
        assert "total_shortcuts" in data

    def test_snapmgr_list(self):
        from src.mcp_server import handle_snapmgr_list
        result = asyncio.run(handle_snapmgr_list({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_snapmgr_restores(self):
        from src.mcp_server import handle_snapmgr_restores
        result = asyncio.run(handle_snapmgr_restores({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_snapmgr_stats(self):
        from src.mcp_server import handle_snapmgr_stats
        result = asyncio.run(handle_snapmgr_stats({}))
        data = json.loads(result[0].text)
        assert "total_snapshots" in data


# ═══════════════════════════════════════════════════════════════════════════
# TOOL COUNT PHASE 20
# ═══════════════════════════════════════════════════════════════════════════

class TestToolCountPhase20:
    def test_tool_count_at_least_265(self):
        """256 + 3 clipmgr + 3 hotkey + 3 snapmgr = 265."""
        from src.mcp_server import TOOL_DEFINITIONS
        assert len(TOOL_DEFINITIONS) >= 265, f"Expected >= 265 tools, got {len(TOOL_DEFINITIONS)}"

    def test_no_duplicate_tool_names(self):
        from src.mcp_server import TOOL_DEFINITIONS
        names = [t[0] for t in TOOL_DEFINITIONS]
        dupes = [n for n in names if names.count(n) > 1]
        assert len(names) == len(set(names)), f"Duplicate tools: {set(dupes)}"
