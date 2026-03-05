"""Local Security Policy — Windows security policy reader.

Read local security settings via secedit /export.
Designed for JARVIS autonomous security auditing.
"""

from __future__ import annotations

import logging
import os
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("jarvis.local_security_policy")

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


@dataclass
class SecuritySetting:
    """A security policy setting."""
    section: str
    key: str
    value: str = ""


@dataclass
class SecPolEvent:
    """Record of a security policy action."""
    action: str
    detail: str = ""
    timestamp: float = field(default_factory=time.time)
    success: bool = True


class LocalSecurityPolicy:
    """Windows local security policy reader (read-only)."""

    def __init__(self) -> None:
        self._events: list[SecPolEvent] = []
        self._lock = threading.Lock()

    def export_policy(self) -> dict[str, dict[str, str]]:
        """Export local security policy via secedit."""
        try:
            with tempfile.NamedTemporaryFile(suffix=".inf", delete=False, mode="w") as tmp:
                tmp_path = tmp.name

            result = subprocess.run(
                ["secedit", "/export", "/cfg", tmp_path],
                capture_output=True, text=True, timeout=15,
                creationflags=_NO_WINDOW,
                encoding="utf-8", errors="replace",
            )
            if result.returncode == 0 and os.path.exists(tmp_path):
                policy: dict[str, dict[str, str]] = {}
                current_section = ""
                try:
                    with open(tmp_path, "r", encoding="utf-16-le", errors="replace") as f:
                        for line in f:
                            line = line.strip()
                            if line.startswith("[") and line.endswith("]"):
                                current_section = line[1:-1]
                                policy[current_section] = {}
                            elif "=" in line and current_section:
                                key, _, val = line.partition("=")
                                policy[current_section][key.strip()] = val.strip()
                except Exception:
                    # Fallback encoding
                    with open(tmp_path, "r", encoding="utf-8", errors="replace") as f:
                        for line in f:
                            line = line.strip()
                            if line.startswith("[") and line.endswith("]"):
                                current_section = line[1:-1]
                                policy[current_section] = {}
                            elif "=" in line and current_section:
                                key, _, val = line.partition("=")
                                policy[current_section][key.strip()] = val.strip()
                finally:
                    try:
                        os.unlink(tmp_path)
                    except OSError:
                        pass
                self._record("export_policy", True, f"{sum(len(v) for v in policy.values())} settings")
                return policy
        except Exception as e:
            self._record("export_policy", False, str(e))
        return {}

    def get_password_policy(self) -> dict[str, str]:
        """Get password policy section."""
        policy = self.export_policy()
        return policy.get("System Access", {})

    def get_audit_policy(self) -> dict[str, str]:
        """Get audit policy section."""
        policy = self.export_policy()
        return policy.get("Event Audit", {})

    def get_sections(self) -> list[str]:
        """Get list of policy sections."""
        policy = self.export_policy()
        return list(policy.keys())

    def _record(self, action: str, success: bool, detail: str = "") -> None:
        with self._lock:
            self._events.append(SecPolEvent(action=action, success=success, detail=detail))

    def get_events(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {"action": e.action, "timestamp": e.timestamp,
                 "success": e.success, "detail": e.detail}
                for e in self._events[-limit:]
            ]

    def get_stats(self) -> dict[str, Any]:
        with self._lock:
            return {"total_events": len(self._events)}


local_security_policy = LocalSecurityPolicy()
