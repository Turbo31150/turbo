"""JARVIS Audit Trail — Complete structured action log.

Records every significant action (MCP calls, API requests, cluster queries,
alerts, workflow runs) with metadata for compliance and debugging.

Usage:
    from src.audit_trail import audit_trail
    audit_trail.log("mcp_call", "handle_lm_query", {"node": "M1", "prompt": "..."})
    entries = audit_trail.search(action_type="mcp_call", limit=20)
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

logger = logging.getLogger("jarvis.audit")

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "audit_trail.db"


class AuditTrail:
    """Structured audit log with SQLite persistence."""

    def __init__(self, db_path: Path | None = None) -> None:
        self._db_path = db_path or DB_PATH
        self._init_db()

    def _init_db(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id TEXT PRIMARY KEY,
                    ts REAL NOT NULL,
                    action_type TEXT NOT NULL,
                    action TEXT NOT NULL,
                    source TEXT DEFAULT '',
                    user_id TEXT DEFAULT '',
                    session_id TEXT DEFAULT '',
                    details TEXT DEFAULT '{}',
                    result TEXT DEFAULT '',
                    duration_ms REAL DEFAULT 0,
                    success INTEGER DEFAULT 1
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit_log(ts DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_type ON audit_log(action_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_source ON audit_log(source)")

    def log(self, action_type: str, action: str, details: dict[str, Any] | None = None,
            source: str = "", user_id: str = "", session_id: str = "",
            result: str = "", duration_ms: float = 0, success: bool = True) -> str:
        """Log an action. Returns entry ID."""
        entry_id = str(uuid.uuid4())[:12]
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.execute(
                "INSERT INTO audit_log (id, ts, action_type, action, source, user_id, session_id, "
                "details, result, duration_ms, success) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (entry_id, time.time(), action_type, action, source, user_id, session_id,
                 json.dumps(details or {}, default=str), result, duration_ms, 1 if success else 0),
            )
        return entry_id

    def search(self, action_type: str | None = None, source: str | None = None,
               query: str | None = None, since: float | None = None,
               success_only: bool = False, limit: int = 50) -> list[dict[str, Any]]:
        """Search audit log with filters."""
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.row_factory = sqlite3.Row
            conditions: list[str] = []
            params: list[Any] = []

            if action_type:
                conditions.append("action_type = ?")
                params.append(action_type)
            if source:
                conditions.append("source = ?")
                params.append(source)
            if query:
                conditions.append("(action LIKE ? OR details LIKE ?)")
                params.extend([f"%{query}%", f"%{query}%"])
            if since:
                conditions.append("ts >= ?")
                params.append(since)
            if success_only:
                conditions.append("success = 1")

            sql = "SELECT * FROM audit_log"
            if conditions:
                sql += " WHERE " + " AND ".join(conditions)
            sql += " ORDER BY ts DESC LIMIT ?"
            params.append(limit)

            rows = conn.execute(sql, params).fetchall()
            result = []
            for r in rows:
                d = dict(r)
                d["details"] = json.loads(d["details"])
                d["success"] = bool(d["success"])
                result.append(d)
            return result

    def get_entry(self, entry_id: str) -> dict[str, Any] | None:
        """Get a single audit entry."""
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM audit_log WHERE id=?", (entry_id,)).fetchone()
            if not row:
                return None
            d = dict(row)
            d["details"] = json.loads(d["details"])
            d["success"] = bool(d["success"])
            return d

    def get_stats(self, hours: int = 24) -> dict[str, Any]:
        """Audit stats for the last N hours."""
        cutoff = time.time() - (hours * 3600)
        with sqlite3.connect(str(self._db_path)) as conn:
            total = conn.execute("SELECT COUNT(*) FROM audit_log WHERE ts >= ?", (cutoff,)).fetchone()[0]
            by_type = conn.execute(
                "SELECT action_type, COUNT(*) FROM audit_log WHERE ts >= ? GROUP BY action_type",
                (cutoff,),
            ).fetchall()
            by_source = conn.execute(
                "SELECT source, COUNT(*) FROM audit_log WHERE ts >= ? GROUP BY source",
                (cutoff,),
            ).fetchall()
            failures = conn.execute(
                "SELECT COUNT(*) FROM audit_log WHERE ts >= ? AND success = 0", (cutoff,)
            ).fetchone()[0]
            avg_duration = conn.execute(
                "SELECT COALESCE(AVG(duration_ms), 0) FROM audit_log WHERE ts >= ? AND duration_ms > 0",
                (cutoff,),
            ).fetchone()[0]
            total_all = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]

            return {
                "period_hours": hours,
                "total_recent": total,
                "total_all": total_all,
                "failures_recent": failures,
                "avg_duration_ms": round(avg_duration, 1),
                "by_type": {t: c for t, c in by_type},
                "by_source": {s: c for s, c in by_source},
            }

    def cleanup(self, days: int = 30) -> int:
        """Remove entries older than N days."""
        cutoff = time.time() - (days * 86400)
        with sqlite3.connect(str(self._db_path)) as conn:
            c = conn.execute("DELETE FROM audit_log WHERE ts < ?", (cutoff,))
            return c.rowcount


# Global singleton
audit_trail = AuditTrail()
