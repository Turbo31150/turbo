"""Tests for src/state_machine.py — Finite State Machine.

Covers: Transition, StateConfig, FSM (add_state, add_transition, trigger,
can_trigger, get_available_events, get_history, get_info),
StateMachineManager (create, get, delete, list_machines, get_stats),
state_machine_mgr singleton.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.state_machine import FSM, StateMachineManager, state_machine_mgr


# ===========================================================================
# FSM — states and transitions
# ===========================================================================

class TestFSM:
    def test_initial_state(self):
        fsm = FSM("test", "idle")
        assert fsm.current_state == "idle"

    def test_trigger_transition(self):
        fsm = FSM("test", "idle")
        fsm.add_state("running")
        fsm.add_transition("idle", "running", "start")
        assert fsm.trigger("start") is True
        assert fsm.current_state == "running"

    def test_trigger_no_transition(self):
        fsm = FSM("test", "idle")
        assert fsm.trigger("nonexistent") is False

    def test_guard_blocks(self):
        fsm = FSM("test", "idle")
        fsm.add_state("running")
        fsm.add_transition("idle", "running", "start", guard=lambda ctx: ctx.get("ready", False))
        assert fsm.trigger("start", {"ready": False}) is False
        assert fsm.current_state == "idle"

    def test_guard_allows(self):
        fsm = FSM("test", "idle")
        fsm.add_state("running")
        fsm.add_transition("idle", "running", "start", guard=lambda ctx: ctx.get("ready", False))
        assert fsm.trigger("start", {"ready": True}) is True
        assert fsm.current_state == "running"

    def test_on_enter_on_exit(self):
        log = []
        fsm = FSM("test", "idle")
        fsm.add_state("running", on_enter=lambda: log.append("enter_running"))
        fsm._states["idle"].on_exit = lambda: log.append("exit_idle")
        fsm.add_transition("idle", "running", "start")
        fsm.trigger("start")
        assert "exit_idle" in log
        assert "enter_running" in log

    def test_can_trigger(self):
        fsm = FSM("test", "idle")
        fsm.add_state("running")
        fsm.add_transition("idle", "running", "start")
        assert fsm.can_trigger("start") is True
        assert fsm.can_trigger("stop") is False

    def test_available_events(self):
        fsm = FSM("test", "idle")
        fsm.add_state("running")
        fsm.add_transition("idle", "running", "start")
        fsm.add_transition("running", "idle", "stop")
        assert "start" in fsm.get_available_events()
        assert "stop" not in fsm.get_available_events()

    def test_history(self):
        fsm = FSM("test", "idle")
        fsm.add_state("running")
        fsm.add_transition("idle", "running", "start")
        fsm.trigger("start")
        history = fsm.get_history()
        assert len(history) == 1
        assert history[0]["from"] == "idle"
        assert history[0]["to"] == "running"

    def test_get_info(self):
        fsm = FSM("test", "idle")
        fsm.add_state("running")
        info = fsm.get_info()
        assert info["name"] == "test"
        assert "idle" in info["states"]
        assert "running" in info["states"]


# ===========================================================================
# StateMachineManager
# ===========================================================================

class TestStateMachineManager:
    def test_create_and_get(self):
        smm = StateMachineManager()
        fsm = smm.create("workflow", "start")
        assert smm.get("workflow") is fsm

    def test_delete(self):
        smm = StateMachineManager()
        smm.create("temp")
        assert smm.delete("temp") is True
        assert smm.get("temp") is None

    def test_delete_nonexistent(self):
        smm = StateMachineManager()
        assert smm.delete("nope") is False

    def test_list_machines(self):
        smm = StateMachineManager()
        smm.create("a")
        smm.create("b")
        machines = smm.list_machines()
        assert len(machines) == 2

    def test_stats(self):
        smm = StateMachineManager()
        fsm = smm.create("test")
        fsm.add_state("running")
        fsm.add_transition("init", "running", "go")
        stats = smm.get_stats()
        assert stats["total_machines"] == 1
        assert stats["states_total"] == 2
        assert stats["transitions_total"] == 1


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert state_machine_mgr is not None
        assert isinstance(state_machine_mgr, StateMachineManager)
