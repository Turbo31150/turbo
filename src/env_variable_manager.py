"""Environment Variable Manager — Windows environment variables.

List, search, read system and user environment variables.
Uses PowerShell Registry access (no external deps).
Designed for JARVIS autonomous environment management.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("jarvis.env_variable_manager")

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


@dataclass
class EnvVariable:
    """An environment variable."""
    name: str
    value: str = ""
    scope: str = ""  # "System", "User", "Process"


@dataclass
class EnvEvent:
    """Record of an env variable action."""
    action: str
    detail: str = ""
    timestamp: float = field(default_factory=time.time)
    success: bool = True


class EnvVariableManager:
    """Windows environment variable management (read-only)."""

    def __init__(self) -> None:
        self._events: list[EnvEvent] = []
        self._lock = threading.Lock()

    # ── List Variables ────────────────────────────────────────────────────

    def list_system_vars(self) -> list[dict[str, Any]]:
        """List system-level environment variables."""
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "[System.Environment]::GetEnvironmentVariables('Machine') | "
                 "ForEach-Object { $_.GetEnumerator() | "
                 "Select-Object Key, Value } | ConvertTo-Json -Depth 1 -Compress"],
                capture_output=True, text=True, timeout=10,
                creationflags=_NO_WINDOW,
                encoding="utf-8", errors="replace",
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                if isinstance(data, dict):
                    data = [data]
                variables = []
                for item in data:
                    variables.append({
                        "name": item.get("Key", ""),
                        "value": str(item.get("Value", "")),
                        "scope": "System",
                    })
                self._record("list_system_vars", True, f"{len(variables)} vars")
                return sorted(variables, key=lambda v: v["name"].lower())
        except Exception as e:
            self._record("list_system_vars", False, str(e))
        return []

    def list_user_vars(self) -> list[dict[str, Any]]:
        """List user-level environment variables."""
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "[System.Environment]::GetEnvironmentVariables('User') | "
                 "ForEach-Object { $_.GetEnumerator() | "
                 "Select-Object Key, Value } | ConvertTo-Json -Depth 1 -Compress"],
                capture_output=True, text=True, timeout=10,
                creationflags=_NO_WINDOW,
                encoding="utf-8", errors="replace",
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                if isinstance(data, dict):
                    data = [data]
                variables = []
                for item in data:
                    variables.append({
                        "name": item.get("Key", ""),
                        "value": str(item.get("Value", "")),
                        "scope": "User",
                    })
                self._record("list_user_vars", True, f"{len(variables)} vars")
                return sorted(variables, key=lambda v: v["name"].lower())
        except Exception as e:
            self._record("list_user_vars", False, str(e))
        return []

    def list_all(self) -> list[dict[str, Any]]:
        """List all environment variables (system + user)."""
        return self.list_system_vars() + self.list_user_vars()

    # ── Get / Search ──────────────────────────────────────────────────────

    def get_var(self, name: str) -> dict[str, Any] | None:
        """Get a specific variable value from current process env."""
        value = os.environ.get(name)
        if value is not None:
            return {"name": name, "value": value, "scope": "Process"}
        return None

    def search(self, query: str) -> list[dict[str, Any]]:
        """Search variables by name."""
        q = query.lower()
        return [v for v in self.list_all() if q in v.get("name", "").lower()]

    def get_path_entries(self) -> list[str]:
        """Get PATH entries as a list."""
        path = os.environ.get("PATH", "")
        return [p for p in path.split(os.pathsep) if p.strip()]

    # ── Query ─────────────────────────────────────────────────────────────

    def _record(self, action: str, success: bool, detail: str = "") -> None:
        with self._lock:
            self._events.append(EnvEvent(
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
                "process_var_count": len(os.environ),
            }


# ── Singleton ───────────────────────────────────────────────────────
env_variable_manager = EnvVariableManager()
