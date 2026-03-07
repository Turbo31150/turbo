"""User Account Manager — Windows user account management.

List local users, groups, account status, SID info.
Uses PowerShell Get-LocalUser / Get-LocalGroup (no external deps).
Designed for JARVIS autonomous user management.
"""

from __future__ import annotations

import json
import logging
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Any


__all__ = [
    "UserAccount",
    "UserAccountManager",
    "UserEvent",
]

logger = logging.getLogger("jarvis.user_account_manager")

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


@dataclass
class UserAccount:
    """A local user account."""
    name: str
    enabled: bool = True
    full_name: str = ""
    description: str = ""


@dataclass
class UserEvent:
    """Record of a user account action."""
    action: str
    detail: str = ""
    timestamp: float = field(default_factory=time.time)
    success: bool = True


class UserAccountManager:
    """Windows local user account management (read-only)."""

    def __init__(self) -> None:
        self._events: list[UserEvent] = []
        self._lock = threading.Lock()

    # ── Users ─────────────────────────────────────────────────────────────

    def list_users(self) -> list[dict[str, Any]]:
        """List local user accounts."""
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-LocalUser | Select-Object Name, Enabled, FullName, "
                 "Description, SID, LastLogon | ConvertTo-Json -Depth 1"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10,
                creationflags=_NO_WINDOW,
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                if isinstance(data, dict):
                    data = [data]
                users = []
                for u in data:
                    users.append({
                        "name": u.get("Name", ""),
                        "enabled": u.get("Enabled", False),
                        "full_name": u.get("FullName", "") or "",
                        "description": u.get("Description", "") or "",
                        "sid": str(u.get("SID", {}).get("Value", "")) if isinstance(u.get("SID"), dict) else str(u.get("SID", "")),
                        "last_logon": str(u.get("LastLogon", "") or ""),
                    })
                self._record("list_users", True, f"{len(users)} users")
                return users
        except Exception as e:
            self._record("list_users", False, str(e))
        return []

    # ── Groups ────────────────────────────────────────────────────────────

    def list_groups(self) -> list[dict[str, Any]]:
        """List local groups."""
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-LocalGroup | Select-Object Name, Description, SID | "
                 "ConvertTo-Json -Depth 1"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10,
                creationflags=_NO_WINDOW,
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                if isinstance(data, dict):
                    data = [data]
                groups = []
                for g in data:
                    groups.append({
                        "name": g.get("Name", ""),
                        "description": g.get("Description", "") or "",
                        "sid": str(g.get("SID", {}).get("Value", "")) if isinstance(g.get("SID"), dict) else str(g.get("SID", "")),
                    })
                return groups
        except Exception:
            pass
        return []

    # ── Search ────────────────────────────────────────────────────────────

    def search_users(self, query: str) -> list[dict[str, Any]]:
        """Search users by name."""
        q = query.lower()
        return [u for u in self.list_users() if q in u.get("name", "").lower()]

    def count_by_status(self) -> dict[str, int]:
        """Count users by enabled/disabled."""
        users = self.list_users()
        enabled = sum(1 for u in users if u.get("enabled"))
        return {"enabled": enabled, "disabled": len(users) - enabled}

    # ── Query ─────────────────────────────────────────────────────────────

    def _record(self, action: str, success: bool, detail: str = "") -> None:
        with self._lock:
            self._events.append(UserEvent(
                action=action, success=success, detail=detail,
            ))

    def get_events(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {"action": e.action, "timestamp": e.timestamp,
                 "success": e.success, "detail": e.detail}
                for e in self._events[-limit:]
            ]

    def get_stats(self) -> dict[str, Any]:
        with self._lock:
            return {
                "total_events": len(self._events),
            }


# ── Singleton ───────────────────────────────────────────────────────
user_account_manager = UserAccountManager()
