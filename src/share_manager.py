"""Share Manager — Windows network share management.

List local shares, mapped drives, net connections.
Uses net share / net use commands (no external deps).
Designed for JARVIS autonomous network share management.
"""

from __future__ import annotations

import json
import logging
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("jarvis.share_manager")

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


@dataclass
class ShareInfo:
    """A network share."""
    name: str
    path: str = ""
    remark: str = ""
    share_type: str = ""


@dataclass
class ShareEvent:
    """Record of a share action."""
    action: str
    detail: str = ""
    timestamp: float = field(default_factory=time.time)
    success: bool = True


class ShareManager:
    """Windows network share management."""

    def __init__(self) -> None:
        self._events: list[ShareEvent] = []
        self._lock = threading.Lock()

    # ── Local Shares ───────────────────────────────────────────────────

    def list_shares(self) -> list[dict[str, Any]]:
        """List local shared folders."""
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-SmbShare | Select-Object Name, Path, Description, "
                 "ShareType | ConvertTo-Json -Depth 1"],
                capture_output=True, text=True, timeout=10,
                creationflags=_NO_WINDOW,
                encoding="utf-8", errors="replace",
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                if isinstance(data, dict):
                    data = [data]
                shares = []
                for s in data:
                    shares.append({
                        "name": s.get("Name", ""),
                        "path": s.get("Path", ""),
                        "description": s.get("Description", ""),
                        "type": str(s.get("ShareType", "")),
                    })
                self._record("list_shares", True, f"{len(shares)} shares")
                return shares
        except Exception as e:
            self._record("list_shares", False, str(e))
        return self._list_shares_net()

    def _list_shares_net(self) -> list[dict[str, Any]]:
        """Fallback via net share."""
        try:
            result = subprocess.run(
                ["net", "share"],
                capture_output=True, text=True, timeout=10,
                creationflags=_NO_WINDOW,
                encoding="utf-8", errors="replace",
            )
            shares = []
            for line in result.stdout.split("\n")[4:]:  # Skip headers
                line = line.strip()
                if not line or line.startswith("-") or "command completed" in line.lower():
                    continue
                parts = line.split()
                if len(parts) >= 2:
                    shares.append({
                        "name": parts[0],
                        "path": parts[1] if len(parts) > 1 else "",
                    })
            return shares
        except Exception:
            return []

    # ── Mapped Drives ──────────────────────────────────────────────────

    def list_mapped_drives(self) -> list[dict[str, Any]]:
        """List mapped network drives."""
        try:
            result = subprocess.run(
                ["net", "use"],
                capture_output=True, text=True, timeout=10,
                creationflags=_NO_WINDOW,
                encoding="utf-8", errors="replace",
            )
            drives = []
            for line in result.stdout.split("\n"):
                line = line.strip()
                parts = line.split()
                if len(parts) >= 3 and ":" in line and "\\\\" in line:
                    status = parts[0] if parts[0] in ("OK", "Disconnected", "Unavailable") else ""
                    drive = ""
                    remote = ""
                    for p in parts:
                        if ":" in p and len(p) <= 3:
                            drive = p
                        elif p.startswith("\\\\"):
                            remote = p
                    if drive or remote:
                        drives.append({
                            "status": status,
                            "drive": drive,
                            "remote": remote,
                        })
            self._record("list_mapped_drives", True, f"{len(drives)} drives")
            return drives
        except Exception as e:
            self._record("list_mapped_drives", False, str(e))
            return []

    # ── Search ─────────────────────────────────────────────────────────

    def search_shares(self, query: str) -> list[dict[str, Any]]:
        """Search shares by name."""
        q = query.lower()
        return [s for s in self.list_shares() if q in s.get("name", "").lower()]

    # ── Query ──────────────────────────────────────────────────────────

    def _record(self, action: str, success: bool, detail: str = "") -> None:
        with self._lock:
            self._events.append(ShareEvent(
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
share_manager = ShareManager()
