"""Audio Controller — Windows audio volume and device management.

Get/set volume, mute/unmute, list audio devices, audio routing.
Uses ctypes with Windows Core Audio API (MMDevice/EndpointVolume).
Designed for JARVIS voice-commanded audio control.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import logging
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Any


__all__ = [
    "AudioController",
    "AudioDevice",
    "AudioEvent",
]

logger = logging.getLogger("jarvis.audio_controller")

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


@dataclass
class AudioEvent:
    """Record of an audio action."""
    action: str
    timestamp: float = field(default_factory=time.time)
    success: bool = True
    detail: str = ""


@dataclass
class AudioDevice:
    """An audio endpoint device."""
    name: str
    device_id: str = ""
    device_type: str = ""  # playback, recording
    is_default: bool = False


class AudioController:
    """Windows audio control with history."""

    def __init__(self) -> None:
        self._events: list[AudioEvent] = []
        self._lock = threading.Lock()
        self._presets: dict[str, int] = {}  # name -> volume level

    # ── Volume Control (via nircmd/PowerShell) ────────────────────────

    def get_volume(self) -> dict[str, Any]:
        """Get current system volume level."""
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "(Get-AudioDevice -PlaybackVolume).Volume"],
                capture_output=True, text=True, timeout=5,
                creationflags=_NO_WINDOW,
                encoding="utf-8", errors="replace",
            )
            if result.returncode == 0 and result.stdout.strip():
                vol = int(float(result.stdout.strip()))
                return {"volume": vol, "source": "AudioDevice"}
        except Exception as e:
            print(f"Error parsing volume: {e}")
        # Fallback: use PowerShell WMI
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "$vol = [Audio]::Volume; [int]($vol * 100)"],
                capture_output=True, text=True, timeout=5,
                creationflags=_NO_WINDOW,
                encoding="utf-8", errors="replace",
            )
            if result.returncode == 0 and result.stdout.strip():
                return {"volume": int(result.stdout.strip()), "source": "WMI"}
        except Exception as e:
            print(f"Error reading volume: {e}")
            pass
        return {"volume": -1, "error": "Cannot read volume"}

    def set_volume(self, level: int) -> bool:
        """Set system volume (0-100)."""
        level = max(0, min(100, level))
        try:
            # Use nircmd if available, else PowerShell
            subprocess.run(
                ["nircmd", "setsysvolume", str(int(level * 655.35))],
                capture_output=True, timeout=3, creationflags=_NO_WINDOW,
            )
            self._record("set_volume", True, f"level={level}")
            return True
        except FileNotFoundError:
            logging.error("File not found: %s", sys.exc_info()[0])
        # PowerShell fallback
        try:
            ps_cmd = f"$obj = New-Object -ComObject WScript.Shell; " + \
                     "".join(["$obj.SendKeys([char]174); " for _ in range(50)]) + \
                     "".join([f"$obj.SendKeys([char]175); " for _ in range(level // 2)])
            subprocess.run(
                ["powershell", "-Command", ps_cmd],
                capture_output=True, timeout=10, creationflags=_NO_WINDOW,
            )
            self._record("set_volume", True, f"level={level} (ps)")
            return True
        except Exception as e:
            self._record("set_volume", False, str(e))
            return False

    def mute(self) -> bool:
        """Mute system audio."""
        try:
            subprocess.run(
                ["nircmd", "mutesysvolume", "1"],
                capture_output=True, timeout=3, creationflags=_NO_WINDOW,
            )
            self._record("mute", True)
            return True
        except FileNotFoundError:
            # Handle or log the error appropriately instead of silently passing
            pass
        try:
            subprocess.run(
                ["powershell", "-Command",
                 "$obj = New-Object -ComObject WScript.Shell; $obj.SendKeys([char]173)"],
                capture_output=True, timeout=5, creationflags=_NO_WINDOW,
            )
            self._record("mute", True, "ps_toggle")
            return True
        except Exception as e:
            self._record("mute", False, str(e))
            return False

    def unmute(self) -> bool:
        """Unmute system audio."""
        try:
            subprocess.run(
                ["nircmd", "mutesysvolume", "0"],
                capture_output=True, timeout=3, creationflags=_NO_WINDOW,
            )
            self._record("unmute", True)
            return True
        except FileNotFoundError:
            # Handle or log the error instead of silently passing
            pass
        try:
            subprocess.run(
                ["powershell", "-Command",
                 "$obj = New-Object -ComObject WScript.Shell; $obj.SendKeys([char]173)"],
                capture_output=True, timeout=5, creationflags=_NO_WINDOW,
            )
            self._record("unmute", True, "ps_toggle")
            return True
        except Exception as e:
            self._record("unmute", False, str(e))
            return False

    # ── Device Listing ────────────────────────────────────────────────

    def list_devices(self) -> list[dict[str, Any]]:
        """List audio playback and recording devices."""
        devices = []
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-CimInstance Win32_SoundDevice | Select-Object Name, DeviceID, Status | ConvertTo-Json"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10,
                creationflags=_NO_WINDOW,
            )
            if result.returncode == 0 and result.stdout.strip():
                import json
                data = json.loads(result.stdout)
                if isinstance(data, dict):
                    data = [data]
                for d in data:
                    devices.append({
                        "name": d.get("Name", "Unknown"),
                        "device_id": d.get("DeviceID", ""),
                        "status": d.get("Status", ""),
                    })
        except Exception as e:
            logger.debug("list_devices error: %s", e)
        self._record("list_devices", True, f"{len(devices)} devices")
        return devices

    # ── Presets ────────────────────────────────────────────────────────

    def save_preset(self, name: str, volume: int) -> None:
        """Save a named volume preset."""
        with self._lock:
            self._presets[name] = max(0, min(100, volume))

    def load_preset(self, name: str) -> dict[str, Any]:
        """Load and apply a volume preset."""
        with self._lock:
            vol = self._presets.get(name)
        if vol is None:
            return {"success": False, "error": "Preset not found"}
        success = self.set_volume(vol)
        return {"success": success, "preset": name, "volume": vol}

    def list_presets(self) -> list[dict[str, Any]]:
        with self._lock:
            return [{"name": n, "volume": v} for n, v in self._presets.items()]

    def delete_preset(self, name: str) -> bool:
        with self._lock:
            if name in self._presets:
                del self._presets[name]
                return True
            return False

    # ── Query ─────────────────────────────────────────────────────────

    def _record(self, action: str, success: bool, detail: str = "") -> None:
        with self._lock:
            self._events.append(AudioEvent(action=action, success=success, detail=detail))

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
                "total_presets": len(self._presets),
            }


# ── Singleton ───────────────────────────────────────────────────────
audio_controller = AudioController()
