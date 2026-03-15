"""JARVIS Session Manager — User session context with persistence.

Manages user sessions with preferences, active conversations, last commands,
preferred nodes, and auto-cleanup of inactive sessions.

Usage:
    from src.session_manager import session_manager
    sid = session_manager.create("electron")
    session_manager.set_preference(sid, "theme", "dark")
    session_manager.record_command(sid, "/cluster-check")
    ctx = session_manager.get_context(sid)
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

logger = logging.getLogger("jarvis.session")

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "sessions.db"


class SessionManager:
    """Persistent user session manager."""

    def __init__(self, db_path: Path | None = None) -> None:
        self._db_path = db_path or DB_PATH
        self._init_db()

    def _init_db(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    source TEXT DEFAULT 'unknown',
                    preferences TEXT NOT NULL DEFAULT '{}',
                    last_commands TEXT NOT NULL DEFAULT '[]',
                    active_conversation TEXT DEFAULT '',
                    preferred_node TEXT DEFAULT '',
                    created_at REAL,
                    last_active REAL,
                    metadata TEXT NOT NULL DEFAULT '{}'
                )
            """)

    def create(self, source: str = "unknown") -> str:
        """Create a new session. Returns session ID."""
        sid = str(uuid.uuid4())[:8]
        now = time.time()
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.execute(
                "INSERT INTO sessions (id, source, created_at, last_active) VALUES (?, ?, ?, ?)",
                (sid, source, now, now),
            )
        return sid

    def get_context(self, sid: str) -> dict[str, Any] | None:
        """Get full session context."""
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM sessions WHERE id=?", (sid,)).fetchone()
            if not row:
                return None
            d = dict(row)
            d["preferences"] = json.loads(d["preferences"])
            d["last_commands"] = json.loads(d["last_commands"])
            d["metadata"] = json.loads(d["metadata"])
            return d

    def touch(self, sid: str) -> None:
        """Update last_active timestamp."""
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.execute("UPDATE sessions SET last_active=? WHERE id=?", (time.time(), sid))

    def set_preference(self, sid: str, key: str, value: Any) -> None:
        """Set a session preference."""
        with sqlite3.connect(str(self._db_path)) as conn:
            row = conn.execute("SELECT preferences FROM sessions WHERE id=?", (sid,)).fetchone()
            if not row:
                return
            prefs = json.loads(row[0])
            prefs[key] = value
            conn.execute(
                "UPDATE sessions SET preferences=?, last_active=? WHERE id=?",
                (json.dumps(prefs), time.time(), sid),
            )

    def get_preference(self, sid: str, key: str, default: Any = None) -> Any:
        """Get a session preference."""
        ctx = self.get_context(sid)
        if not ctx:
            return default
        return ctx["preferences"].get(key, default)

    def record_command(self, sid: str, command: str, max_history: int = 20) -> None:
        """Record a command in session history."""
        with sqlite3.connect(str(self._db_path)) as conn:
            row = conn.execute("SELECT last_commands FROM sessions WHERE id=?", (sid,)).fetchone()
            if not row:
                return
            cmds = json.loads(row[0])
            cmds.append({"cmd": command, "ts": time.time()})
            cmds = cmds[-max_history:]
            conn.execute(
                "UPDATE sessions SET last_commands=?, last_active=? WHERE id=?",
                (json.dumps(cmds), time.time(), sid),
            )

    def set_active_conversation(self, sid: str, conv_id: str) -> None:
        """Set the active conversation for this session."""
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.execute(
                "UPDATE sessions SET active_conversation=?, last_active=? WHERE id=?",
                (conv_id, time.time(), sid),
            )

    def set_preferred_node(self, sid: str, node: str) -> None:
        """Set the preferred cluster node for this session."""
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.execute(
                "UPDATE sessions SET preferred_node=?, last_active=? WHERE id=?",
                (node, time.time(), sid),
            )

    def list_sessions(self, limit: int = 20, active_only: bool = False) -> list[dict[str, Any]]:
        """List sessions."""
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.row_factory = sqlite3.Row
            sql = "SELECT id, source, created_at, last_active, preferred_node, active_conversation FROM sessions"
            params: list[Any] = []
            if active_only:
                cutoff = time.time() - 3600  # active = last hour
                sql += " WHERE last_active > ?"
                params.append(cutoff)
            sql += " ORDER BY last_active DESC LIMIT ?"
            params.append(limit)
            return [dict(r) for r in conn.execute(sql, params).fetchall()]

    def cleanup(self, inactive_hours: int = 24) -> int:
        """Remove sessions inactive for more than N hours."""
        cutoff = time.time() - (inactive_hours * 3600)
        with sqlite3.connect(str(self._db_path)) as conn:
            c = conn.execute("DELETE FROM sessions WHERE last_active < ?", (cutoff,))
            return c.rowcount

    def delete(self, sid: str) -> bool:
        """Delete a session."""
        with sqlite3.connect(str(self._db_path)) as conn:
            c = conn.execute("DELETE FROM sessions WHERE id=?", (sid,))
            return c.rowcount > 0

    def get_stats(self) -> dict[str, Any]:
        """Session stats."""
        with sqlite3.connect(str(self._db_path)) as conn:
            total = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
            active = conn.execute(
                "SELECT COUNT(*) FROM sessions WHERE last_active > ?",
                (time.time() - 3600,),
            ).fetchone()[0]
            by_source = conn.execute(
                "SELECT source, COUNT(*) FROM sessions GROUP BY source"
            ).fetchall()
            return {
                "total_sessions": total,
                "active_sessions": active,
                "by_source": {s: c for s, c in by_source},
            }


# Global singleton
session_manager = SessionManager()
