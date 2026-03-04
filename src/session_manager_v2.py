"""Session Manager v2 — Advanced multi-session tracking.

Manages user/agent sessions with activity tracking,
timeout policies, metadata, and persistence.
Thread-safe, JSON-backed.
"""

from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

logger = logging.getLogger("jarvis.session_mgr_v2")


@dataclass
class Session:
    session_id: str
    owner: str
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    timeout_s: float = 3600.0  # 1h default
    metadata: dict = field(default_factory=dict)
    status: str = "active"  # active, idle, expired, closed
    activity_count: int = 0
    tags: list[str] = field(default_factory=list)


class SessionManagerV2:
    """Multi-session manager with timeout and activity tracking."""

    def __init__(self, store_path: Path | None = None, default_timeout: float = 3600.0):
        self._sessions: dict[str, Session] = {}
        self._store = store_path or Path("data/sessions_v2.json")
        self._default_timeout = default_timeout
        self._lock = threading.Lock()
        self._load()

    def create(
        self,
        owner: str,
        timeout_s: float | None = None,
        metadata: dict | None = None,
        tags: list[str] | None = None,
    ) -> Session:
        with self._lock:
            sid = str(uuid.uuid4())[:12]
            session = Session(
                session_id=sid, owner=owner,
                timeout_s=timeout_s or self._default_timeout,
                metadata=metadata or {},
                tags=tags or [],
            )
            self._sessions[sid] = session
            self._save()
            return session

    def get(self, session_id: str) -> Session | None:
        with self._lock:
            s = self._sessions.get(session_id)
            if s and s.status == "active":
                self._check_timeout(s)
            return s

    def touch(self, session_id: str) -> bool:
        """Record activity on a session."""
        with self._lock:
            s = self._sessions.get(session_id)
            if not s or s.status != "active":
                return False
            s.last_activity = time.time()
            s.activity_count += 1
            self._save()
            return True

    def close(self, session_id: str) -> bool:
        with self._lock:
            s = self._sessions.get(session_id)
            if not s:
                return False
            s.status = "closed"
            self._save()
            return True

    def cleanup_expired(self) -> int:
        """Mark timed-out sessions as expired."""
        now = time.time()
        count = 0
        with self._lock:
            for s in self._sessions.values():
                if s.status == "active" and (now - s.last_activity) > s.timeout_s:
                    s.status = "expired"
                    count += 1
            if count:
                self._save()
        return count

    def list_sessions(self, owner: str | None = None, status: str | None = None) -> list[dict]:
        with self._lock:
            sessions = list(self._sessions.values())
        if owner:
            sessions = [s for s in sessions if s.owner == owner]
        if status:
            sessions = [s for s in sessions if s.status == status]
        return [asdict(s) for s in sessions]

    def get_stats(self) -> dict:
        with self._lock:
            sessions = list(self._sessions.values())
        active = sum(1 for s in sessions if s.status == "active")
        expired = sum(1 for s in sessions if s.status == "expired")
        closed = sum(1 for s in sessions if s.status == "closed")
        total_activity = sum(s.activity_count for s in sessions)
        return {
            "total_sessions": len(sessions),
            "active": active,
            "expired": expired,
            "closed": closed,
            "total_activity": total_activity,
        }

    def _check_timeout(self, s: Session) -> None:
        if (time.time() - s.last_activity) > s.timeout_s:
            s.status = "expired"

    def _save(self) -> None:
        try:
            self._store.parent.mkdir(parents=True, exist_ok=True)
            data = {sid: asdict(s) for sid, s in self._sessions.items()}
            self._store.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as e:
            logger.debug("session save error: %s", e)

    def _load(self) -> None:
        try:
            if self._store.exists():
                raw = json.loads(self._store.read_text(encoding="utf-8"))
                for sid, d in raw.items():
                    self._sessions[sid] = Session(**d)
        except Exception as e:
            logger.debug("session load error: %s", e)


# ── Singleton ────────────────────────────────────────────────────────────────
session_manager_v2 = SessionManagerV2()
