"""JARVIS — Chain Resolver: resolve etoile.db domino_chains into executable cascades.

The 835+ chains in domino_chains define transitions:
  trigger_cmd --[condition]--> next_cmd (delay_ms, auto)

This module resolves a trigger_cmd into a full chain of steps,
following next_cmd links until no more chains match.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field

DB_PATH = "F:/BUREAU/turbo/data/etoile.db"


@dataclass
class ChainStep:
    """A single step in a resolved chain."""
    trigger: str
    condition: str
    next_cmd: str
    delay_ms: int
    auto: bool
    description: str
    chain_id: int


@dataclass
class ResolvedChain:
    """A fully resolved chain from a trigger_cmd."""
    trigger: str
    steps: list[ChainStep]
    total_delay_ms: int
    is_cyclic: bool = False

    @property
    def description(self) -> str:
        if not self.steps:
            return ""
        return self.steps[0].description

    @property
    def step_count(self) -> int:
        return len(self.steps)


def _get_all_chains(db_path: str = DB_PATH) -> list[dict]:
    """Load all domino_chains from DB."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, trigger_cmd, condition, next_cmd, delay_ms, auto, description "
        "FROM domino_chains ORDER BY trigger_cmd, id"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _build_chain_index(chains: list[dict]) -> dict[str, list[dict]]:
    """Index chains by trigger_cmd for fast lookup."""
    index: dict[str, list[dict]] = {}
    for c in chains:
        key = c["trigger_cmd"]
        index.setdefault(key, []).append(c)
    return index


def resolve_chain(trigger: str, db_path: str = DB_PATH, max_depth: int = 20) -> ResolvedChain | None:
    """Resolve a trigger_cmd into a full chain by following next_cmd links."""
    all_chains = _get_all_chains(db_path)
    index = _build_chain_index(all_chains)

    if trigger not in index:
        return None

    steps: list[ChainStep] = []
    visited: set[str] = set()
    current = trigger
    is_cyclic = False

    while current and len(steps) < max_depth:
        if current in visited:
            is_cyclic = True
            break
        visited.add(current)

        chain_entries = index.get(current, [])
        if not chain_entries:
            break

        for entry in chain_entries:
            steps.append(ChainStep(
                trigger=entry["trigger_cmd"],
                condition=entry["condition"] or "always",
                next_cmd=entry["next_cmd"],
                delay_ms=entry["delay_ms"] or 0,
                auto=bool(entry["auto"]),
                description=entry["description"] or "",
                chain_id=entry["id"],
            ))

        # Follow the last entry's next_cmd
        last_next = chain_entries[-1]["next_cmd"]
        current = last_next if last_next and last_next != current else None

    total_delay = sum(s.delay_ms for s in steps)
    return ResolvedChain(trigger=trigger, steps=steps, total_delay_ms=total_delay, is_cyclic=is_cyclic)


def list_all_triggers(db_path: str = DB_PATH) -> list[dict]:
    """List all unique triggers with chain info."""
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT trigger_cmd, COUNT(*) as chain_count, "
        "GROUP_CONCAT(DISTINCT condition) as conditions, "
        "SUM(CASE WHEN auto=1 THEN 1 ELSE 0 END) as auto_count "
        "FROM domino_chains GROUP BY trigger_cmd ORDER BY trigger_cmd"
    ).fetchall()
    conn.close()
    return [
        {"trigger": r[0], "chain_count": r[1], "conditions": r[2], "auto_count": r[3]}
        for r in rows
    ]


def search_chains(query: str, db_path: str = DB_PATH, limit: int = 20) -> list[dict]:
    """Search chains by trigger, next_cmd, or description."""
    conn = sqlite3.connect(db_path)
    q = f"%{query}%"
    rows = conn.execute(
        "SELECT id, trigger_cmd, condition, next_cmd, delay_ms, auto, description "
        "FROM domino_chains "
        "WHERE trigger_cmd LIKE ? OR next_cmd LIKE ? OR description LIKE ? "
        "LIMIT ?",
        (q, q, q, limit)
    ).fetchall()
    conn.close()
    return [
        {"id": r[0], "trigger_cmd": r[1], "condition": r[2], "next_cmd": r[3],
         "delay_ms": r[4], "auto": bool(r[5]), "description": r[6]}
        for r in rows
    ]
