"""Tests for src/command_registry.py — Named commands with handlers.

Covers: Command, CommandRegistry (register, unregister, get, enable, disable,
list_commands, list_categories, execute, get_history, get_stats),
command_registry singleton.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.command_registry import Command, CommandRegistry, command_registry


def _echo_handler(args: dict):
    return args.get("msg", "ok")


def _fail_handler(args: dict):
    raise RuntimeError("boom")


# ===========================================================================
# Command dataclass
# ===========================================================================

class TestCommand:
    def test_defaults(self):
        c = Command(name="test", handler=_echo_handler)
        assert c.category == "general"
        assert c.aliases == []
        assert c.enabled is True
        assert c.exec_count == 0


# ===========================================================================
# CommandRegistry — register & unregister
# ===========================================================================

class TestRegisterUnregister:
    def test_register(self):
        cr = CommandRegistry()
        cmd = cr.register("greet", _echo_handler, description="Say hi")
        assert cmd.name == "greet"
        assert cr.get("greet") is not None

    def test_register_with_aliases(self):
        cr = CommandRegistry()
        cr.register("greet", _echo_handler, aliases=["hi", "hello"])
        assert cr.get("hi") is not None
        assert cr.get("hello") is not None

    def test_unregister(self):
        cr = CommandRegistry()
        cr.register("temp", _echo_handler, aliases=["t"])
        assert cr.unregister("temp") is True
        assert cr.get("temp") is None
        assert cr.get("t") is None

    def test_unregister_nonexistent(self):
        cr = CommandRegistry()
        assert cr.unregister("nope") is False


# ===========================================================================
# CommandRegistry — get
# ===========================================================================

class TestGet:
    def test_by_name(self):
        cr = CommandRegistry()
        cr.register("cmd1", _echo_handler)
        assert cr.get("cmd1").name == "cmd1"

    def test_by_alias(self):
        cr = CommandRegistry()
        cr.register("cmd1", _echo_handler, aliases=["c1"])
        assert cr.get("c1").name == "cmd1"

    def test_nonexistent(self):
        cr = CommandRegistry()
        assert cr.get("nope") is None


# ===========================================================================
# CommandRegistry — enable/disable
# ===========================================================================

class TestEnableDisable:
    def test_disable_enable(self):
        cr = CommandRegistry()
        cr.register("toggle", _echo_handler)
        assert cr.disable("toggle") is True
        assert cr.get("toggle").enabled is False
        assert cr.enable("toggle") is True
        assert cr.get("toggle").enabled is True

    def test_enable_nonexistent(self):
        cr = CommandRegistry()
        assert cr.enable("nope") is False
        assert cr.disable("nope") is False


# ===========================================================================
# CommandRegistry — list_commands & list_categories
# ===========================================================================

class TestListing:
    def test_list_commands(self):
        cr = CommandRegistry()
        cr.register("b_cmd", _echo_handler, category="tools")
        cr.register("a_cmd", _echo_handler, category="general")
        cmds = cr.list_commands()
        assert len(cmds) == 2
        # Sorted by name
        assert cmds[0]["name"] == "a_cmd"
        assert cmds[1]["name"] == "b_cmd"

    def test_list_commands_filter_category(self):
        cr = CommandRegistry()
        cr.register("cmd1", _echo_handler, category="tools")
        cr.register("cmd2", _echo_handler, category="general")
        cmds = cr.list_commands(category="tools")
        assert len(cmds) == 1
        assert cmds[0]["name"] == "cmd1"

    def test_list_categories(self):
        cr = CommandRegistry()
        cr.register("a", _echo_handler, category="tools")
        cr.register("b", _echo_handler, category="general")
        cats = cr.list_categories()
        assert set(cats) == {"tools", "general"}


# ===========================================================================
# CommandRegistry — execute
# ===========================================================================

class TestExecute:
    def test_success(self):
        cr = CommandRegistry()
        cr.register("echo", _echo_handler)
        result = cr.execute("echo", {"msg": "hello"})
        assert result["success"] is True
        assert result["result"] == "hello"
        assert "time" in result

    def test_increments_exec_count(self):
        cr = CommandRegistry()
        cr.register("echo", _echo_handler)
        cr.execute("echo")
        cr.execute("echo")
        assert cr.get("echo").exec_count == 2

    def test_nonexistent(self):
        cr = CommandRegistry()
        result = cr.execute("nope")
        assert result["success"] is False
        assert "not found" in result["error"]

    def test_disabled(self):
        cr = CommandRegistry()
        cr.register("cmd", _echo_handler)
        cr.disable("cmd")
        result = cr.execute("cmd")
        assert result["success"] is False
        assert "disabled" in result["error"]

    def test_handler_exception(self):
        cr = CommandRegistry()
        cr.register("fail", _fail_handler)
        result = cr.execute("fail")
        assert result["success"] is False
        assert "boom" in result["error"]

    def test_execute_via_alias(self):
        cr = CommandRegistry()
        cr.register("echo", _echo_handler, aliases=["e"])
        result = cr.execute("e", {"msg": "alias"})
        assert result["success"] is True
        assert result["result"] == "alias"


# ===========================================================================
# CommandRegistry — history
# ===========================================================================

class TestHistory:
    def test_empty(self):
        cr = CommandRegistry()
        assert cr.get_history() == []

    def test_after_execute(self):
        cr = CommandRegistry()
        cr.register("cmd", _echo_handler)
        cr.execute("cmd")
        history = cr.get_history()
        assert len(history) == 1
        assert history[0]["command"] == "cmd"
        assert history[0]["success"] is True


# ===========================================================================
# CommandRegistry — stats
# ===========================================================================

class TestStats:
    def test_stats(self):
        cr = CommandRegistry()
        cr.register("a", _echo_handler, category="tools", aliases=["aa"])
        cr.register("b", _echo_handler, category="general")
        cr.disable("b")
        cr.execute("a")
        stats = cr.get_stats()
        assert stats["total_commands"] == 2
        assert stats["enabled"] == 1
        assert stats["disabled"] == 1
        assert stats["categories"] == 2
        assert stats["aliases"] == 1
        assert stats["total_executions"] == 1


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert command_registry is not None
        assert isinstance(command_registry, CommandRegistry)
