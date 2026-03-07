"""Credential Vault — Windows Credential Manager access.

List, search stored credentials. Read-only access via cmdkey.
Uses cmdkey.exe subprocess (no external deps).
Designed for JARVIS autonomous credential inventory.
"""

from __future__ import annotations

import logging
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Any


__all__ = [
    "CredentialEntry",
    "CredentialVault",
    "VaultEvent",
]

logger = logging.getLogger("jarvis.credential_vault")

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


@dataclass
class CredentialEntry:
    """A stored credential."""
    target: str
    cred_type: str = ""
    user: str = ""
    persistence: str = ""


@dataclass
class VaultEvent:
    """Record of a vault action."""
    action: str
    detail: str = ""
    timestamp: float = field(default_factory=time.time)
    success: bool = True


class CredentialVault:
    """Windows Credential Manager read-only access."""

    def __init__(self) -> None:
        self._events: list[VaultEvent] = []
        self._lock = threading.Lock()

    # ── Credential Listing ─────────────────────────────────────────────

    def list_credentials(self) -> list[dict[str, Any]]:
        """List all stored credentials (targets only, no secrets)."""
        try:
            result = subprocess.run(
                ["cmdkey", "/list"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10,
                creationflags=_NO_WINDOW,
            )
            if result.returncode == 0:
                creds = self._parse_cmdkey(result.stdout)
                self._record("list_credentials", True, f"{len(creds)} credentials")
                return creds
        except Exception as e:
            self._record("list_credentials", False, str(e))
        return []

    def _parse_cmdkey(self, output: str) -> list[dict[str, Any]]:
        """Parse cmdkey /list output."""
        creds = []
        current: dict[str, str] = {}
        for line in output.split("\n"):
            line = line.strip()
            if line.startswith("Target:") or line.startswith("Cible"):
                if current.get("target"):
                    creds.append(current)
                target = line.split(":", 1)[1].strip() if ":" in line else ""
                # Clean TERMSRV/ prefix
                current = {"target": target}
            elif ("Type:" in line or "Type :" in line) and current:
                current["type"] = line.split(":", 1)[1].strip()
            elif ("User:" in line or "Utilisateur:" in line) and current:
                current["user"] = line.split(":", 1)[1].strip()
            elif ("Persistence:" in line or "Persistance:" in line) and current:
                current["persistence"] = line.split(":", 1)[1].strip()
        if current.get("target"):
            creds.append(current)
        return creds

    def search(self, query: str) -> list[dict[str, Any]]:
        """Search credentials by target name."""
        q = query.lower()
        return [c for c in self.list_credentials()
                if q in c.get("target", "").lower()]

    def count_by_type(self) -> dict[str, int]:
        """Count credentials by type."""
        creds = self.list_credentials()
        counts: dict[str, int] = {}
        for c in creds:
            t = c.get("type", "unknown")
            counts[t] = counts.get(t, 0) + 1
        return counts

    def has_credential(self, target: str) -> bool:
        """Check if a credential exists for a target."""
        t = target.lower()
        return any(t in c.get("target", "").lower() for c in self.list_credentials())

    # ── Query ──────────────────────────────────────────────────────────

    def _record(self, action: str, success: bool, detail: str = "") -> None:
        with self._lock:
            self._events.append(VaultEvent(
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
credential_vault = CredentialVault()
