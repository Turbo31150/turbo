"""Group Policy Reader — Windows GPO result reading.

Read applied group policies via gpresult.
Uses gpresult /R command (no external deps).
Designed for JARVIS autonomous policy auditing.
"""

from __future__ import annotations

import logging
import re
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("jarvis.group_policy_reader")

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


@dataclass
class GPOInfo:
    """Group policy object info."""
    name: str
    link_location: str = ""
    status: str = ""


@dataclass
class GPOEvent:
    """Record of a GPO action."""
    action: str
    detail: str = ""
    timestamp: float = field(default_factory=time.time)
    success: bool = True


class GroupPolicyReader:
    """Windows Group Policy result reading (read-only)."""

    def __init__(self) -> None:
        self._events: list[GPOEvent] = []
        self._lock = threading.Lock()
        self._last_result: str = ""

    # ── GPO Results ───────────────────────────────────────────────────────

    def get_rsop(self) -> dict[str, Any]:
        """Get Resultant Set of Policy summary."""
        try:
            result = subprocess.run(
                ["gpresult", "/R"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
                creationflags=_NO_WINDOW,
            )
            if result.returncode == 0 and result.stdout.strip():
                self._last_result = result.stdout
                parsed = self._parse_gpresult(result.stdout)
                self._record("get_rsop", True)
                return parsed
        except Exception as e:
            self._record("get_rsop", False, str(e))
        return {"error": "Unable to read group policy"}

    def get_raw(self) -> str:
        """Get raw gpresult output."""
        if not self._last_result:
            self.get_rsop()
        return self._last_result

    def get_applied_gpos(self) -> list[dict[str, Any]]:
        """Extract applied GPOs from result."""
        rsop = self.get_rsop()
        return rsop.get("applied_gpos", [])

    # ── Parser ────────────────────────────────────────────────────────────

    def _parse_gpresult(self, output: str) -> dict[str, Any]:
        """Parse gpresult /R output into structured data."""
        info: dict[str, Any] = {
            "computer_name": "",
            "domain": "",
            "site_name": "",
            "applied_gpos": [],
            "sections": {},
        }

        current_section = ""
        gpo_section = False

        for line in output.split("\n"):
            stripped = line.strip()
            if not stripped:
                gpo_section = False
                continue

            # Key: Value pairs at top level
            if ":" in stripped and not stripped.startswith("-"):
                key, _, value = stripped.partition(":")
                key_lower = key.strip().lower()
                value = value.strip()

                if "computer name" in key_lower or "nom de l'ordinateur" in key_lower:
                    info["computer_name"] = value
                elif key_lower in ("domain name", "nom du domaine", "domain"):
                    info["domain"] = value
                elif "site name" in key_lower or "nom du site" in key_lower:
                    info["site_name"] = value

            # Section headers (indented lines with uppercase)
            if stripped.isupper() or stripped.endswith(":"):
                current_section = stripped.rstrip(":")
                if current_section not in info["sections"]:
                    info["sections"][current_section] = []

            # Applied Group Policy Objects section
            if "applied group policy" in stripped.lower() or "objets de strategie de groupe appliques" in stripped.lower():
                gpo_section = True
                continue

            if gpo_section and stripped and not stripped.startswith("-"):
                info["applied_gpos"].append({"name": stripped})

            # Store section content
            if current_section and current_section in info["sections"]:
                info["sections"][current_section].append(stripped)

        return info

    # ── Query ─────────────────────────────────────────────────────────────

    def _record(self, action: str, success: bool, detail: str = "") -> None:
        with self._lock:
            self._events.append(GPOEvent(
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
group_policy_reader = GroupPolicyReader()
