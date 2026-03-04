"""Command Registry — Named commands with handlers, aliases, categories, and history."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from threading import Lock
from typing import Any, Callable


@dataclass
class Command:
    name: str
    handler: Callable[[dict], Any]
    category: str = "general"
    description: str = ""
    aliases: list[str] = field(default_factory=list)
    enabled: bool = True
    exec_count: int = 0
    last_exec: float = 0.0


class CommandRegistry:
    """Register and execute named commands."""

    def __init__(self):
        self._commands: dict[str, Command] = {}
        self._aliases: dict[str, str] = {}
        self._history: list[dict] = []
        self._max_history = 500
        self._lock = Lock()

    # ── Registration ────────────────────────────────────────────────
    def register(self, name: str, handler: Callable[[dict], Any],
                 category: str = "general", description: str = "",
                 aliases: list[str] | None = None) -> Command:
        cmd = Command(
            name=name, handler=handler, category=category,
            description=description, aliases=aliases or [],
        )
        with self._lock:
            self._commands[name] = cmd
            for alias in cmd.aliases:
                self._aliases[alias] = name
        return cmd

    def unregister(self, name: str) -> bool:
        with self._lock:
            cmd = self._commands.pop(name, None)
            if not cmd:
                return False
            for alias in cmd.aliases:
                self._aliases.pop(alias, None)
            return True

    def get(self, name: str) -> Command | None:
        cmd = self._commands.get(name)
        if cmd:
            return cmd
        resolved = self._aliases.get(name)
        if resolved:
            return self._commands.get(resolved)
        return None

    def enable(self, name: str) -> bool:
        cmd = self.get(name)
        if not cmd:
            return False
        cmd.enabled = True
        return True

    def disable(self, name: str) -> bool:
        cmd = self.get(name)
        if not cmd:
            return False
        cmd.enabled = False
        return True

    # ── Listing ─────────────────────────────────────────────────────
    def list_commands(self, category: str | None = None) -> list[dict]:
        with self._lock:
            cmds = list(self._commands.values())
            if category:
                cmds = [c for c in cmds if c.category == category]
            return [
                {
                    "name": c.name, "category": c.category,
                    "description": c.description, "aliases": c.aliases,
                    "enabled": c.enabled, "exec_count": c.exec_count,
                }
                for c in sorted(cmds, key=lambda c: c.name)
            ]

    def list_categories(self) -> list[str]:
        with self._lock:
            return list(set(c.category for c in self._commands.values()))

    # ── Execution ───────────────────────────────────────────────────
    def execute(self, name: str, args: dict | None = None) -> dict:
        cmd = self.get(name)
        if not cmd:
            return {"success": False, "error": f"Command '{name}' not found"}
        if not cmd.enabled:
            return {"success": False, "error": f"Command '{name}' is disabled"}

        t0 = time.time()
        try:
            result = cmd.handler(args or {})
            elapsed = time.time() - t0
            with self._lock:
                cmd.exec_count += 1
                cmd.last_exec = time.time()
                self._log(name, True, elapsed)
            return {"success": True, "result": result, "time": round(elapsed, 4)}
        except Exception as exc:
            elapsed = time.time() - t0
            with self._lock:
                self._log(name, False, elapsed, str(exc))
            return {"success": False, "error": str(exc), "time": round(elapsed, 4)}

    # ── History ─────────────────────────────────────────────────────
    def _log(self, name: str, success: bool, elapsed: float, error: str = ""):
        self._history.append({
            "command": name, "success": success,
            "time": round(elapsed, 4), "error": error,
            "timestamp": time.time(),
        })
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

    def get_history(self, limit: int = 50) -> list[dict]:
        with self._lock:
            return self._history[-limit:]

    # ── Stats ───────────────────────────────────────────────────────
    def get_stats(self) -> dict:
        with self._lock:
            total = len(self._commands)
            enabled = sum(1 for c in self._commands.values() if c.enabled)
            cats = set(c.category for c in self._commands.values())
            total_execs = sum(c.exec_count for c in self._commands.values())
            return {
                "total_commands": total,
                "enabled": enabled,
                "disabled": total - enabled,
                "categories": len(cats),
                "aliases": len(self._aliases),
                "total_executions": total_execs,
                "history_size": len(self._history),
            }


command_registry = CommandRegistry()
