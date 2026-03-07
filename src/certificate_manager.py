"""Certificate Manager — Windows certificate store management.

List certificates, check expiration, search, store info.
Uses PowerShell Get-ChildItem Cert:\\ (no external deps).
Designed for JARVIS autonomous security monitoring.
"""

from __future__ import annotations

import json
import logging
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("jarvis.certificate_manager")

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

CERT_STORES = [
    "Cert:\\LocalMachine\\My",
    "Cert:\\LocalMachine\\Root",
    "Cert:\\LocalMachine\\CA",
    "Cert:\\CurrentUser\\My",
    "Cert:\\CurrentUser\\Root",
]


@dataclass
class CertInfo:
    """A certificate."""
    subject: str
    issuer: str = ""
    thumbprint: str = ""
    not_after: str = ""
    not_before: str = ""
    store: str = ""


@dataclass
class CertEvent:
    """Record of a certificate action."""
    action: str
    detail: str = ""
    timestamp: float = field(default_factory=time.time)
    success: bool = True


class CertificateManager:
    """Windows certificate store management."""

    def __init__(self) -> None:
        self._events: list[CertEvent] = []
        self._lock = threading.Lock()

    # ── Certificate Listing ────────────────────────────────────────────

    def list_certs(self, store: str = "Cert:\\LocalMachine\\My") -> list[dict[str, Any]]:
        """List certificates in a store."""
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 f"Get-ChildItem '{store}' | "
                 "Select-Object Subject, Issuer, Thumbprint, NotAfter, NotBefore | "
                 "ConvertTo-Json -Depth 1"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15,
                creationflags=_NO_WINDOW,
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                if isinstance(data, dict):
                    data = [data]
                certs = []
                for c in data:
                    certs.append({
                        "subject": c.get("Subject", ""),
                        "issuer": c.get("Issuer", ""),
                        "thumbprint": c.get("Thumbprint", ""),
                        "not_after": str(c.get("NotAfter", "")),
                        "not_before": str(c.get("NotBefore", "")),
                        "store": store,
                    })
                self._record("list_certs", True, f"{len(certs)} certs in {store}")
                return certs
        except Exception as e:
            self._record("list_certs", False, str(e))
        return []

    def list_stores(self) -> list[str]:
        """List known certificate stores."""
        return list(CERT_STORES)

    def search(self, query: str, store: str = "Cert:\\LocalMachine\\My") -> list[dict[str, Any]]:
        """Search certificates by subject."""
        q = query.lower()
        return [c for c in self.list_certs(store) if q in c.get("subject", "").lower()]

    def get_expiring(self, days: int = 30, store: str = "Cert:\\LocalMachine\\My") -> list[dict[str, Any]]:
        """Get certificates expiring within N days."""
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 f"Get-ChildItem '{store}' | "
                 f"Where-Object {{ $_.NotAfter -lt (Get-Date).AddDays({days}) }} | "
                 "Select-Object Subject, Thumbprint, NotAfter | "
                 "ConvertTo-Json -Depth 1"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15,
                creationflags=_NO_WINDOW,
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                if isinstance(data, dict):
                    data = [data]
                return [
                    {
                        "subject": c.get("Subject", ""),
                        "thumbprint": c.get("Thumbprint", ""),
                        "not_after": str(c.get("NotAfter", "")),
                    }
                    for c in data
                ]
        except Exception:
            pass
        return []

    def count_by_store(self) -> dict[str, int]:
        """Count certificates per store."""
        counts: dict[str, int] = {}
        for store in CERT_STORES:
            certs = self.list_certs(store)
            counts[store] = len(certs)
        return counts

    # ── Query ──────────────────────────────────────────────────────────

    def _record(self, action: str, success: bool, detail: str = "") -> None:
        with self._lock:
            self._events.append(CertEvent(
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
                "known_stores": len(CERT_STORES),
            }


# ── Singleton ───────────────────────────────────────────────────────
certificate_manager = CertificateManager()
