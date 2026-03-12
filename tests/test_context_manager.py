"""Tests for src/context_manager.py — Execution context with scopes and variables.

Covers: Context, ContextEvent, ContextManager (create, delete, set_var, get_var,
delete_var, get_all_vars, create_child, merge, freeze, unfreeze, snapshot, get,
list_contexts, get_events, get_stats), context_manager singleton.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.context_manager import Context, ContextEvent, ContextManager, context_manager


# ===========================================================================
# Dataclasses
# ===========================================================================

class TestContext:
    def test_defaults(self):
        c = Context(context_id="c1", name="test")
        assert c.variables == {}
        assert c.parent_id is None
        assert c.tags == []
        assert c.frozen is False
        assert c.created_at > 0


class TestContextEvent:
    def test_defaults(self):
        e = ContextEvent(context_id="c1", action="created")
        assert e.key == ""
        assert e.timestamp > 0


# ===========================================================================
# ContextManager — create / delete
# ===========================================================================

class TestCreateDelete:
    def test_create(self):
        cm = ContextManager()
        ctx = cm.create("test")
        assert ctx.name == "test"
        assert ctx.context_id.startswith("ctx_")

    def test_create_with_variables(self):
        cm = ContextManager()
        ctx = cm.create("test", variables={"x": 1}, tags=["debug"])
        assert ctx.variables == {"x": 1}
        assert ctx.tags == ["debug"]

    def test_delete(self):
        cm = ContextManager()
        ctx = cm.create("test")
        assert cm.delete(ctx.context_id) is True
        assert cm.get(ctx.context_id) is None

    def test_delete_nonexistent(self):
        cm = ContextManager()
        assert cm.delete("ctx_999") is False

    def test_root_created(self):
        cm = ContextManager()
        # Root is auto-created (ctx_1)
        assert cm.get("ctx_1") is not None
        assert cm.get("ctx_1").name == "root"


# ===========================================================================
# ContextManager — variables
# ===========================================================================

class TestVariables:
    def test_set_and_get(self):
        cm = ContextManager()
        ctx = cm.create("test")
        assert cm.set_var(ctx.context_id, "key", "value") is True
        assert cm.get_var(ctx.context_id, "key") == "value"

    def test_get_missing(self):
        cm = ContextManager()
        ctx = cm.create("test")
        assert cm.get_var(ctx.context_id, "nope", "default") == "default"

    def test_set_on_frozen(self):
        cm = ContextManager()
        ctx = cm.create("test")
        cm.freeze(ctx.context_id)
        assert cm.set_var(ctx.context_id, "key", "value") is False

    def test_set_nonexistent_context(self):
        cm = ContextManager()
        assert cm.set_var("ctx_999", "key", "value") is False

    def test_delete_var(self):
        cm = ContextManager()
        ctx = cm.create("test", variables={"a": 1, "b": 2})
        assert cm.delete_var(ctx.context_id, "a") is True
        assert cm.get_var(ctx.context_id, "a") is None
        assert cm.get_var(ctx.context_id, "b") == 2

    def test_delete_var_missing(self):
        cm = ContextManager()
        ctx = cm.create("test")
        assert cm.delete_var(ctx.context_id, "nope") is False

    def test_delete_var_frozen(self):
        cm = ContextManager()
        ctx = cm.create("test", variables={"a": 1})
        cm.freeze(ctx.context_id)
        assert cm.delete_var(ctx.context_id, "a") is False

    def test_get_var_parent_chain(self):
        cm = ContextManager()
        parent = cm.create("parent", variables={"shared": "from_parent"})
        child = cm.create("child", parent_id=parent.context_id)
        assert cm.get_var(child.context_id, "shared") == "from_parent"

    def test_get_var_child_overrides_parent(self):
        cm = ContextManager()
        parent = cm.create("parent", variables={"x": 1})
        child = cm.create("child", parent_id=parent.context_id, variables={"x": 2})
        assert cm.get_var(child.context_id, "x") == 2

    def test_get_all_vars_no_parents(self):
        cm = ContextManager()
        ctx = cm.create("test", variables={"a": 1, "b": 2})
        assert cm.get_all_vars(ctx.context_id) == {"a": 1, "b": 2}

    def test_get_all_vars_with_parents(self):
        cm = ContextManager()
        parent = cm.create("parent", variables={"x": 1})
        child = cm.create("child", parent_id=parent.context_id, variables={"y": 2})
        result = cm.get_all_vars(child.context_id, include_parents=True)
        assert result["x"] == 1
        assert result["y"] == 2

    def test_get_all_vars_nonexistent(self):
        cm = ContextManager()
        assert cm.get_all_vars("ctx_999") == {}


# ===========================================================================
# ContextManager — create_child
# ===========================================================================

class TestCreateChild:
    def test_inherit(self):
        cm = ContextManager()
        parent = cm.create("parent", variables={"lang": "python"})
        child = cm.create_child(parent.context_id, "child")
        assert child is not None
        assert child.parent_id == parent.context_id
        assert child.variables == {"lang": "python"}

    def test_no_inherit(self):
        cm = ContextManager()
        parent = cm.create("parent", variables={"lang": "python"})
        child = cm.create_child(parent.context_id, "child", inherit=False)
        assert child is not None
        assert child.variables == {}

    def test_missing_parent(self):
        cm = ContextManager()
        assert cm.create_child("ctx_999", "orphan") is None


# ===========================================================================
# ContextManager — merge
# ===========================================================================

class TestMerge:
    def test_merge_overwrite(self):
        cm = ContextManager()
        src = cm.create("src", variables={"a": 1, "b": 2})
        tgt = cm.create("tgt", variables={"b": 0, "c": 3})
        assert cm.merge(src.context_id, tgt.context_id) is True
        tgt_ctx = cm.get(tgt.context_id)
        assert tgt_ctx.variables == {"a": 1, "b": 2, "c": 3}

    def test_merge_no_overwrite(self):
        cm = ContextManager()
        src = cm.create("src", variables={"a": 1, "b": 2})
        tgt = cm.create("tgt", variables={"b": 0})
        cm.merge(src.context_id, tgt.context_id, overwrite=False)
        tgt_ctx = cm.get(tgt.context_id)
        assert tgt_ctx.variables["b"] == 0  # not overwritten

    def test_merge_frozen_target(self):
        cm = ContextManager()
        src = cm.create("src", variables={"a": 1})
        tgt = cm.create("tgt")
        cm.freeze(tgt.context_id)
        assert cm.merge(src.context_id, tgt.context_id) is False

    def test_merge_missing(self):
        cm = ContextManager()
        ctx = cm.create("test")
        assert cm.merge("ctx_999", ctx.context_id) is False
        assert cm.merge(ctx.context_id, "ctx_999") is False


# ===========================================================================
# ContextManager — freeze / unfreeze
# ===========================================================================

class TestFreeze:
    def test_freeze(self):
        cm = ContextManager()
        ctx = cm.create("test")
        assert cm.freeze(ctx.context_id) is True
        assert cm.get(ctx.context_id).frozen is True

    def test_unfreeze(self):
        cm = ContextManager()
        ctx = cm.create("test")
        cm.freeze(ctx.context_id)
        assert cm.unfreeze(ctx.context_id) is True
        assert cm.get(ctx.context_id).frozen is False

    def test_freeze_nonexistent(self):
        cm = ContextManager()
        assert cm.freeze("ctx_999") is False

    def test_unfreeze_nonexistent(self):
        cm = ContextManager()
        assert cm.unfreeze("ctx_999") is False


# ===========================================================================
# ContextManager — snapshot
# ===========================================================================

class TestSnapshot:
    def test_snapshot(self):
        cm = ContextManager()
        ctx = cm.create("test", variables={"x": 1}, tags=["debug"])
        snap = cm.snapshot(ctx.context_id)
        assert snap is not None
        assert snap["name"] == "test"
        assert snap["variables"] == {"x": 1}
        assert snap["tags"] == ["debug"]
        assert "timestamp" in snap

    def test_snapshot_nonexistent(self):
        cm = ContextManager()
        assert cm.snapshot("ctx_999") is None

    def test_snapshot_deep_copy(self):
        cm = ContextManager()
        ctx = cm.create("test", variables={"list": [1, 2]})
        snap = cm.snapshot(ctx.context_id)
        snap["variables"]["list"].append(3)
        assert cm.get_var(ctx.context_id, "list") == [1, 2]  # original unchanged


# ===========================================================================
# ContextManager — list_contexts / get_events / get_stats
# ===========================================================================

class TestQueryMethods:
    def test_list_contexts(self):
        cm = ContextManager()
        cm.create("a", tags=["web"])
        cm.create("b", tags=["db"])
        result = cm.list_contexts()
        assert len(result) >= 3  # root + a + b

    def test_list_contexts_filter_tag(self):
        cm = ContextManager()
        cm.create("a", tags=["web"])
        cm.create("b", tags=["db"])
        result = cm.list_contexts(tag="web")
        assert len(result) == 1
        assert result[0]["name"] == "a"

    def test_get_events(self):
        cm = ContextManager()
        ctx = cm.create("test")
        cm.set_var(ctx.context_id, "x", 1)
        events = cm.get_events()
        assert len(events) >= 2  # root created + test created + updated

    def test_get_events_filter(self):
        cm = ContextManager()
        ctx = cm.create("test")
        cm.set_var(ctx.context_id, "x", 1)
        events = cm.get_events(context_id=ctx.context_id)
        assert all(e["context_id"] == ctx.context_id for e in events)

    def test_get_stats(self):
        cm = ContextManager()
        cm.create("a", variables={"x": 1, "y": 2})
        cm.create("b")
        cm.freeze("ctx_1")  # freeze root
        stats = cm.get_stats()
        assert stats["total_contexts"] == 3  # root + a + b
        assert stats["frozen"] == 1
        assert stats["active"] == 2
        assert stats["total_variables"] >= 2
        assert stats["total_events"] >= 3


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert context_manager is not None
        assert isinstance(context_manager, ContextManager)
