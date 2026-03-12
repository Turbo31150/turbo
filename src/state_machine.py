"""State Machine — Finite State Machine for workflows.

Define states, transitions with guards, on_enter/on_exit hooks.
Supports multiple named FSMs and transition history.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Callable


__all__ = [
    "FSM",
    "StateConfig",
    "StateMachineManager",
    "Transition",
]

logger = logging.getLogger("jarvis.state_machine")


@dataclass
class Transition:
    from_state: str
    to_state: str
    event: str
    guard: Callable[..., bool] | None = None


@dataclass
class StateConfig:
    name: str
    on_enter: Callable | None = None
    on_exit: Callable | None = None
    metadata: dict = field(default_factory=dict)


class FSM:
    """Single finite state machine instance."""

    def __init__(self, name: str, initial_state: str):
        self.name = name
        self._current = initial_state
        self._states: dict[str, StateConfig] = {}
        self._transitions: list[Transition] = []
        self._history: list[dict] = []
        self._max_history = 100

        self.add_state(initial_state)

    @property
    def current_state(self) -> str:
        return self._current

    def add_state(self, name: str, on_enter: Callable | None = None, on_exit: Callable | None = None) -> None:
        self._states[name] = StateConfig(name=name, on_enter=on_enter, on_exit=on_exit)

    def add_transition(self, from_state: str, to_state: str, event: str, guard: Callable | None = None) -> None:
        self._transitions.append(Transition(from_state=from_state, to_state=to_state, event=event, guard=guard))

    def trigger(self, event: str, context: dict | None = None) -> bool:
        """Trigger an event. Returns True if transition occurred."""
        for t in self._transitions:
            if t.from_state == self._current and t.event == event:
                if t.guard and not t.guard(context or {}):
                    continue
                # Execute on_exit
                old_state = self._states.get(self._current)
                if old_state and old_state.on_exit:
                    old_state.on_exit()
                # Transition
                prev = self._current
                self._current = t.to_state
                # Execute on_enter
                new_state = self._states.get(self._current)
                if new_state and new_state.on_enter:
                    new_state.on_enter()
                # Record
                self._history.append({
                    "ts": time.time(), "event": event,
                    "from": prev, "to": self._current,
                })
                if len(self._history) > self._max_history:
                    self._history = self._history[-self._max_history:]
                return True
        return False

    def can_trigger(self, event: str) -> bool:
        return any(t.from_state == self._current and t.event == event for t in self._transitions)

    def get_available_events(self) -> list[str]:
        return list(set(t.event for t in self._transitions if t.from_state == self._current))

    def get_history(self, limit: int = 20) -> list[dict]:
        return self._history[-limit:]

    def get_info(self) -> dict:
        return {
            "name": self.name,
            "current_state": self._current,
            "states": list(self._states.keys()),
            "transitions": len(self._transitions),
            "history_size": len(self._history),
            "available_events": self.get_available_events(),
        }


class StateMachineManager:
    """Manages multiple named FSMs."""

    def __init__(self):
        self._machines: dict[str, FSM] = {}
        self._lock = threading.Lock()

    def create(self, name: str, initial_state: str = "init") -> FSM:
        with self._lock:
            fsm = FSM(name, initial_state)
            self._machines[name] = fsm
            return fsm

    def get(self, name: str) -> FSM | None:
        return self._machines.get(name)

    def delete(self, name: str) -> bool:
        with self._lock:
            return self._machines.pop(name, None) is not None

    def list_machines(self) -> list[dict]:
        return [m.get_info() for m in self._machines.values()]

    def get_stats(self) -> dict:
        machines = list(self._machines.values())
        return {
            "total_machines": len(machines),
            "states_total": sum(len(m._states) for m in machines),
            "transitions_total": sum(len(m._transitions) for m in machines),
        }


# ── Singleton ────────────────────────────────────────────────────────────────
state_machine_mgr = StateMachineManager()
