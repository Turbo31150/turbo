"""Context Manager — Execution context with scopes and variables.

Manage hierarchical execution contexts with variable scoping,
isolation, merge, inheritance, and history tracking.
Designed for JARVIS to maintain state across conversations and tasks.
"""

from __future__ import annotations

import copy
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("jarvis.context_manager")


@dataclass
class Context:
    """An execution context with variables."""
    context_id: str
    name: str
    variables: dict[str, Any] = field(default_factory=dict)
    parent_id: str | None = None
    tags: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    frozen: bool = False


@dataclass
class ContextEvent:
    """Record of a context change."""
    context_id: str
    action: str  # created, updated, merged, frozen, deleted
    key: str = ""
    timestamp: float = field(default_factory=time.time)


class ContextManager:
    """Manage hierarchical execution contexts."""

    def __init__(self) -> None:
        self._contexts: dict[str, Context] = {}
        self._events: list[ContextEvent] = []
        self._counter = 0
        self._lock = threading.Lock()
        # Create root context
        self._root = self.create("root")

    # ── Creation ────────────────────────────────────────────────────

    def create(self, name: str, parent_id: str | None = None,
               variables: dict[str, Any] | None = None,
               tags: list[str] | None = None) -> Context:
        """Create a new context."""
        with self._lock:
            self._counter += 1
            cid = f"ctx_{self._counter}"
            ctx = Context(
                context_id=cid, name=name,
                variables=variables or {},
                parent_id=parent_id,
                tags=tags or [],
            )
            self._contexts[cid] = ctx
            self._events.append(ContextEvent(context_id=cid, action="created"))
            return ctx

    def delete(self, context_id: str) -> bool:
        """Delete a context."""
        with self._lock:
            if context_id in self._contexts:
                del self._contexts[context_id]
                self._events.append(ContextEvent(context_id=context_id, action="deleted"))
                return True
            return False

    # ── Variables ───────────────────────────────────────────────────

    def set_var(self, context_id: str, key: str, value: Any) -> bool:
        """Set a variable in a context."""
        with self._lock:
            ctx = self._contexts.get(context_id)
            if not ctx or ctx.frozen:
                return False
            ctx.variables[key] = value
            ctx.updated_at = time.time()
            self._events.append(ContextEvent(context_id=context_id, action="updated", key=key))
            return True

    def get_var(self, context_id: str, key: str, default: Any = None) -> Any:
        """Get a variable, walking up parent chain if not found."""
        with self._lock:
            return self._resolve_var(context_id, key, default)

    def _resolve_var(self, context_id: str, key: str, default: Any = None) -> Any:
        """Resolve variable with parent chain (caller must hold lock)."""
        ctx = self._contexts.get(context_id)
        if not ctx:
            return default
        if key in ctx.variables:
            return ctx.variables[key]
        if ctx.parent_id:
            return self._resolve_var(ctx.parent_id, key, default)
        return default

    def delete_var(self, context_id: str, key: str) -> bool:
        """Delete a variable from a context."""
        with self._lock:
            ctx = self._contexts.get(context_id)
            if not ctx or ctx.frozen or key not in ctx.variables:
                return False
            del ctx.variables[key]
            ctx.updated_at = time.time()
            return True

    def get_all_vars(self, context_id: str, include_parents: bool = False) -> dict[str, Any]:
        """Get all variables in a context."""
        with self._lock:
            ctx = self._contexts.get(context_id)
            if not ctx:
                return {}
            if not include_parents:
                return dict(ctx.variables)
            # Merge from root down
            result = {}
            chain = self._get_chain(context_id)
            for cid in reversed(chain):
                c = self._contexts.get(cid)
                if c:
                    result.update(c.variables)
            return result

    def _get_chain(self, context_id: str) -> list[str]:
        """Get context chain from current to root (caller must hold lock)."""
        chain = []
        cid = context_id
        visited = set()
        while cid and cid not in visited:
            visited.add(cid)
            chain.append(cid)
            ctx = self._contexts.get(cid)
            cid = ctx.parent_id if ctx else None
        return chain

    # ── Scope Operations ────────────────────────────────────────────

    def create_child(self, parent_id: str, name: str, inherit: bool = True) -> Context | None:
        """Create a child context that inherits from parent."""
        with self._lock:
            parent = self._contexts.get(parent_id)
            if not parent:
                return None
        variables = dict(parent.variables) if inherit else {}
        return self.create(name, parent_id=parent_id, variables=variables)

    def merge(self, source_id: str, target_id: str, overwrite: bool = True) -> bool:
        """Merge variables from source into target."""
        with self._lock:
            source = self._contexts.get(source_id)
            target = self._contexts.get(target_id)
            if not source or not target or target.frozen:
                return False
            for key, val in source.variables.items():
                if overwrite or key not in target.variables:
                    target.variables[key] = copy.deepcopy(val)
            target.updated_at = time.time()
            self._events.append(ContextEvent(context_id=target_id, action="merged", key=source_id))
            return True

    def freeze(self, context_id: str) -> bool:
        """Freeze a context (no more modifications)."""
        with self._lock:
            ctx = self._contexts.get(context_id)
            if ctx:
                ctx.frozen = True
                self._events.append(ContextEvent(context_id=context_id, action="frozen"))
                return True
            return False

    def unfreeze(self, context_id: str) -> bool:
        """Unfreeze a context."""
        with self._lock:
            ctx = self._contexts.get(context_id)
            if ctx:
                ctx.frozen = False
                return True
            return False

    def snapshot(self, context_id: str) -> dict[str, Any] | None:
        """Take a snapshot of a context's current state."""
        with self._lock:
            ctx = self._contexts.get(context_id)
            if not ctx:
                return None
            return {
                "id": ctx.context_id,
                "name": ctx.name,
                "variables": copy.deepcopy(ctx.variables),
                "parent_id": ctx.parent_id,
                "frozen": ctx.frozen,
                "tags": list(ctx.tags),
                "timestamp": time.time(),
            }

    # ── Query ───────────────────────────────────────────────────────

    def get(self, context_id: str) -> Context | None:
        with self._lock:
            return self._contexts.get(context_id)

    def list_contexts(self, tag: str | None = None) -> list[dict[str, Any]]:
        with self._lock:
            result = []
            for ctx in self._contexts.values():
                if tag and tag not in ctx.tags:
                    continue
                result.append({
                    "id": ctx.context_id, "name": ctx.name,
                    "parent_id": ctx.parent_id, "frozen": ctx.frozen,
                    "variables_count": len(ctx.variables),
                    "tags": ctx.tags, "created_at": ctx.created_at,
                })
            return result

    def get_events(self, context_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            events = self._events
            if context_id:
                events = [e for e in events if e.context_id == context_id]
            return [
                {"context_id": e.context_id, "action": e.action,
                 "key": e.key, "timestamp": e.timestamp}
                for e in events[-limit:]
            ]

    def get_stats(self) -> dict[str, Any]:
        with self._lock:
            frozen = sum(1 for c in self._contexts.values() if c.frozen)
            total_vars = sum(len(c.variables) for c in self._contexts.values())
            return {
                "total_contexts": len(self._contexts),
                "frozen": frozen,
                "active": len(self._contexts) - frozen,
                "total_variables": total_vars,
                "total_events": len(self._events),
            }


# ── Singleton ───────────────────────────────────────────────────────
context_manager = ContextManager()
