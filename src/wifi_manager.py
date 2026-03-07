"""WiFi Manager — Windows wireless network management.

Scan networks, connect/disconnect, saved profiles, signal monitoring.
Uses netsh wlan commands (no external dependencies).
Designed for JARVIS autonomous network management.
"""

from __future__ import annotations

import logging
import re
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("jarvis.wifi_manager")

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


@dataclass
class WiFiNetwork:
    """A detected WiFi network."""
    ssid: str
    signal: int = 0  # percent
    auth: str = ""
    encryption: str = ""
    channel: int = 0
    bssid: str = ""


@dataclass
class WiFiEvent:
    """Record of a WiFi action."""
    action: str
    ssid: str = ""
    timestamp: float = field(default_factory=time.time)
    success: bool = True
    detail: str = ""


class WiFiManager:
    """Windows WiFi management with scan, connect, and history."""

    def __init__(self) -> None:
        self._events: list[WiFiEvent] = []
        self._lock = threading.Lock()

    # ── Scan ──────────────────────────────────────────────────────────

    def scan(self) -> list[dict[str, Any]]:
        """Scan for available WiFi networks."""
        try:
            result = subprocess.run(
                ["netsh", "wlan", "show", "networks", "mode=bssid"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10,
                creationflags=_NO_WINDOW,
            )
            networks = []
            current: dict[str, Any] = {}
            for line in result.stdout.split("\n"):
                line = line.strip()
                if line.startswith("SSID") and "BSSID" not in line:
                    if current and current.get("ssid"):
                        networks.append(current)
                    ssid = line.split(":", 1)[1].strip() if ":" in line else ""
                    current = {"ssid": ssid, "signal": 0, "auth": "", "encryption": "", "channel": 0}
                elif "Signal" in line and ":" in line:
                    sig = line.split(":", 1)[1].strip().replace("%", "")
                    try:
                        current["signal"] = int(sig)
                    except ValueError:
                        pass
                elif "Authentication" in line and ":" in line:
                    current["auth"] = line.split(":", 1)[1].strip()
                elif "Encryption" in line and ":" in line:
                    current["encryption"] = line.split(":", 1)[1].strip()
                elif "Channel" in line and ":" in line:
                    ch = line.split(":", 1)[1].strip()
                    try:
                        current["channel"] = int(ch)
                    except ValueError:
                        pass
                elif "BSSID" in line and ":" in line:
                    parts = line.split(":", 1)
                    if len(parts) > 1:
                        current["bssid"] = parts[1].strip()
            if current and current.get("ssid"):
                networks.append(current)
            self._record("scan", "", True, f"{len(networks)} networks")
            return networks
        except Exception as e:
            self._record("scan", "", False, str(e))
            return []

    # ── Connection ────────────────────────────────────────────────────

    def get_current(self) -> dict[str, Any]:
        """Get current WiFi connection info."""
        try:
            result = subprocess.run(
                ["netsh", "wlan", "show", "interfaces"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5,
                creationflags=_NO_WINDOW,
            )
            info: dict[str, Any] = {"connected": False}
            for line in result.stdout.split("\n"):
                line = line.strip()
                if "SSID" in line and "BSSID" not in line and ":" in line:
                    info["ssid"] = line.split(":", 1)[1].strip()
                elif "State" in line and ":" in line:
                    state = line.split(":", 1)[1].strip().lower()
                    info["connected"] = "connected" in state
                    info["state"] = state
                elif "Signal" in line and ":" in line:
                    sig = line.split(":", 1)[1].strip().replace("%", "")
                    try:
                        info["signal"] = int(sig)
                    except ValueError:
                        pass
                elif "Channel" in line and ":" in line:
                    ch = line.split(":", 1)[1].strip()
                    try:
                        info["channel"] = int(ch)
                    except ValueError:
                        pass
                elif "Receive rate" in line and ":" in line:
                    info["receive_rate"] = line.split(":", 1)[1].strip()
                elif "Transmit rate" in line and ":" in line:
                    info["transmit_rate"] = line.split(":", 1)[1].strip()
            return info
        except Exception as e:
            return {"connected": False, "error": str(e)}

    def connect(self, ssid: str) -> dict[str, Any]:
        """Connect to a saved WiFi profile."""
        try:
            result = subprocess.run(
                ["netsh", "wlan", "connect", f"name={ssid}"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10,
                creationflags=_NO_WINDOW,
            )
            success = result.returncode == 0
            self._record("connect", ssid, success, result.stdout.strip())
            return {"success": success, "ssid": ssid, "detail": result.stdout.strip()}
        except Exception as e:
            self._record("connect", ssid, False, str(e))
            return {"success": False, "ssid": ssid, "error": str(e)}

    def disconnect(self) -> dict[str, Any]:
        """Disconnect from current WiFi."""
        try:
            result = subprocess.run(
                ["netsh", "wlan", "disconnect"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5,
                creationflags=_NO_WINDOW,
            )
            success = result.returncode == 0
            self._record("disconnect", "", success, result.stdout.strip())
            return {"success": success, "detail": result.stdout.strip()}
        except Exception as e:
            self._record("disconnect", "", False, str(e))
            return {"success": False, "error": str(e)}

    # ── Profiles ──────────────────────────────────────────────────────

    def list_profiles(self) -> list[dict[str, str]]:
        """List saved WiFi profiles."""
        try:
            result = subprocess.run(
                ["netsh", "wlan", "show", "profiles"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5,
                creationflags=_NO_WINDOW,
            )
            profiles = []
            for line in result.stdout.split("\n"):
                if "All User Profile" in line or "Tous les utilisateurs" in line:
                    name = line.split(":", 1)[1].strip() if ":" in line else ""
                    if name:
                        profiles.append({"name": name})
            return profiles
        except Exception as e:
            return []

    def delete_profile(self, name: str) -> bool:
        """Delete a saved WiFi profile."""
        try:
            result = subprocess.run(
                ["netsh", "wlan", "delete", "profile", f"name={name}"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5,
                creationflags=_NO_WINDOW,
            )
            success = result.returncode == 0
            self._record("delete_profile", name, success)
            return success
        except Exception:
            return False

    # ── Query ─────────────────────────────────────────────────────────

    def _record(self, action: str, ssid: str, success: bool, detail: str = "") -> None:
        with self._lock:
            self._events.append(WiFiEvent(
                action=action, ssid=ssid, success=success, detail=detail,
            ))

    def get_events(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {"action": e.action, "ssid": e.ssid, "timestamp": e.timestamp,
                 "success": e.success, "detail": e.detail}
                for e in self._events[-limit:]
            ]

    def get_stats(self) -> dict[str, Any]:
        current = self.get_current()
        with self._lock:
            return {
                "total_events": len(self._events),
                "connected": current.get("connected", False),
                "current_ssid": current.get("ssid", ""),
                "signal": current.get("signal", 0),
            }


# ── Singleton ───────────────────────────────────────────────────────
wifi_manager = WiFiManager()
