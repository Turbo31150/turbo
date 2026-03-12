"""JARVIS Conversation Store — Persistent IA conversation history.

Records every prompt/response exchange with metadata (node, latency, tokens).
SQLite backend for persistence, search, and audit.

Usage:
    from src.conversation_store import conversation_store
    conv_id = conversation_store.create("Code review task")
    conversation_store.add_turn(conv_id, "M1", "Fix this bug", "Here's the fix...", latency_ms=120, tokens=50)
    history = conversation_store.get_conversation(conv_id)
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

logger = logging.getLogger("jarvis.conversations")

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "conversations.db"


class ConversationStore:
    """Persistent conversation history with search."""

    def __init__(self, db_path: Path | None = None) -> None:
        self._db_path = db_path or DB_PATH
        self._init_db()

    def _init_db(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    title TEXT DEFAULT '',
                    source TEXT DEFAULT 'chat',
                    created_at REAL,
                    updated_at REAL,
                    turn_count INTEGER DEFAULT 0,
                    total_tokens INTEGER DEFAULT 0,
                    total_latency_ms REAL DEFAULT 0
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS turns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conv_id TEXT NOT NULL,
                    node TEXT DEFAULT '',
                    prompt TEXT NOT NULL,
                    response TEXT DEFAULT '',
                    latency_ms REAL DEFAULT 0,
                    tokens INTEGER DEFAULT 0,
                    success INTEGER DEFAULT 1,
                    created_at REAL,
                    metadata TEXT DEFAULT '{}',
                    FOREIGN KEY (conv_id) REFERENCES conversations(id)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_turns_conv ON turns(conv_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_conv_updated ON conversations(updated_at DESC)")

    def create(self, title: str = "", source: str = "chat") -> str:
        """Create a new conversation. Returns conversation ID."""
        conv_id = str(uuid.uuid4())[:8]
        now = time.time()
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.execute(
                "INSERT INTO conversations (id, title, source, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (conv_id, title, source, now, now),
            )
        return conv_id

    def add_turn(self, conv_id: str, node: str, prompt: str, response: str = "",
                 latency_ms: float = 0, tokens: int = 0, success: bool = True,
                 metadata: dict | None = None) -> int:
        """Add a turn to a conversation. Returns turn ID."""
        now = time.time()
        meta_str = json.dumps(metadata or {})
        with sqlite3.connect(str(self._db_path)) as conn:
            c = conn.execute(
                "INSERT INTO turns (conv_id, node, prompt, response, latency_ms, tokens, success, created_at, metadata) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (conv_id, node, prompt, response, latency_ms, tokens, 1 if success else 0, now, meta_str),
            )
            turn_id = c.lastrowid
            conn.execute(
                "UPDATE conversations SET updated_at=?, turn_count=turn_count+1, "
                "total_tokens=total_tokens+?, total_latency_ms=total_latency_ms+? WHERE id=?",
                (now, tokens, latency_ms, conv_id),
            )
        return turn_id

    def get_conversation(self, conv_id: str) -> dict[str, Any] | None:
        """Get full conversation with turns."""
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.row_factory = sqlite3.Row
            conv = conn.execute("SELECT * FROM conversations WHERE id=?", (conv_id,)).fetchone()
            if not conv:
                return None
            turns = conn.execute(
                "SELECT * FROM turns WHERE conv_id=? ORDER BY created_at ASC", (conv_id,)
            ).fetchall()
            return {
                **dict(conv),
                "turns": [dict(t) for t in turns],
            }

    def list_conversations(self, limit: int = 20, source: str | None = None) -> list[dict[str, Any]]:
        """List recent conversations."""
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.row_factory = sqlite3.Row
            sql = "SELECT * FROM conversations"
            params: list[Any] = []
            if source:
                sql += " WHERE source = ?"
                params.append(source)
            sql += " ORDER BY updated_at DESC LIMIT ?"
            params.append(limit)
            return [dict(r) for r in conn.execute(sql, params).fetchall()]

    def search_turns(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        """Search through turn prompts and responses."""
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT t.*, c.title as conv_title FROM turns t "
                "JOIN conversations c ON t.conv_id = c.id "
                "WHERE t.prompt LIKE ? OR t.response LIKE ? "
                "ORDER BY t.created_at DESC LIMIT ?",
                (f"%{query}%", f"%{query}%", limit),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_node_history(self, node: str, limit: int = 20) -> list[dict[str, Any]]:
        """Get recent turns for a specific node."""
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM turns WHERE node=? ORDER BY created_at DESC LIMIT ?",
                (node, limit),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_stats(self) -> dict[str, Any]:
        """Conversation stats."""
        with sqlite3.connect(str(self._db_path)) as conn:
            total_convs = conn.execute("SELECT COUNT(*) FROM conversations").fetchone()[0]
            total_turns = conn.execute("SELECT COUNT(*) FROM turns").fetchone()[0]
            total_tokens = conn.execute("SELECT COALESCE(SUM(tokens), 0) FROM turns").fetchone()[0]
            avg_latency = conn.execute("SELECT COALESCE(AVG(latency_ms), 0) FROM turns WHERE latency_ms > 0").fetchone()[0]
            by_node = conn.execute(
                "SELECT node, COUNT(*), COALESCE(AVG(latency_ms), 0) FROM turns GROUP BY node"
            ).fetchall()
            return {
                "total_conversations": total_convs,
                "total_turns": total_turns,
                "total_tokens": total_tokens,
                "avg_latency_ms": round(avg_latency, 1),
                "by_node": {n: {"count": c, "avg_ms": round(a, 1)} for n, c, a in by_node},
            }

    def cleanup(self, days: int = 30) -> int:
        """Remove old conversations."""
        cutoff = time.time() - (days * 86400)
        with sqlite3.connect(str(self._db_path)) as conn:
            old_ids = conn.execute(
                "SELECT id FROM conversations WHERE updated_at < ?", (cutoff,)
            ).fetchall()
            if not old_ids:
                return 0
            ids = [r[0] for r in old_ids]
            placeholders = ",".join("?" * len(ids))
            conn.execute(f"DELETE FROM turns WHERE conv_id IN ({placeholders})", ids)
            conn.execute(f"DELETE FROM conversations WHERE id IN ({placeholders})", ids)
            return len(ids)


# Global singleton
conversation_store = ConversationStore()
