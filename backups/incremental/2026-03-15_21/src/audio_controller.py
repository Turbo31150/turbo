"""Audio Controller — Linux audio volume and device management.

Get/set volume, mute/unmute, list audio devices via PulseAudio/PipeWire.
Falls back to amixer if pactl is not available.
Designed for JARVIS voice-commanded audio control.
"""

from __future__ import annotations

import logging
import re
import shutil
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


def _has_pactl() -> bool:
    return shutil.which("pactl") is not None


def _has_amixer() -> bool:
    return shutil.which("amixer") is not None


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
    device_type: str = ""
    is_default: bool = False


class AudioController:
    """Linux audio control with history."""

    def __init__(self) -> None:
        self._events: list[AudioEvent] = []
        self._lock = threading.Lock()
        self._presets: dict[str, int] = {}
        self._use_pactl = _has_pactl()
        self._use_amixer = _has_amixer()

    def _run(self, cmd: list[str], timeout: int = 5) -> subprocess.CompletedProcess:
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )

    def get_volume(self) -> dict[str, Any]:
        """Get current system volume level."""
        if self._use_pactl:
            try:
                result = self._run(["pactl", "get-sink-volume", "@DEFAULT_SINK@"])
                if result.returncode == 0 and result.stdout.strip():
                    match = re.search(r"(\d+)%", result.stdout)
                    if match:
                        vol = int(match.group(1))
                        self._record("get_volume", True, f"volume={vol}")
                        return {"volume": vol, "source": "pactl"}
            except Exception as e:
                logger.debug("pactl get_volume error: %s", e)

        if self._use_amixer:
            try:
                result = self._run(["amixer", "sget", "Master"])
                if result.returncode == 0 and result.stdout.strip():
                    match = re.search(r"\[(\d+)%\]", result.stdout)
                    if match:
                        vol = int(match.group(1))
                        self._record("get_volume", True, f"volume={vol}")
                        return {"volume": vol, "source": "amixer"}
            except Exception as e:
                logger.debug("amixer get_volume error: %s", e)

        self._record("get_volume", False, "no backend available")
        return {"volume": -1, "error": "Cannot read volume"}

    def set_volume(self, level: int) -> bool:
        """Set system volume (0-100)."""
        level = max(0, min(100, level))

        if self._use_pactl:
            try:
                result = self._run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{level}%"])
                if result.returncode == 0:
                    self._record("set_volume", True, f"level={level}")
                    return True
            except Exception as e:
                logger.debug("pactl set_volume error: %s", e)

        if self._use_amixer:
            try:
                result = self._run(["amixer", "sset", "Master", f"{level}%"])
                if result.returncode == 0:
                    self._record("set_volume", True, f"level={level} (amixer)")
                    return True
            except Exception as e:
                logger.debug("amixer set_volume error: %s", e)

        self._record("set_volume", False, "no backend available")
        return False

    def mute(self) -> bool:
        """Mute system audio."""
        if self._use_pactl:
            try:
                result = self._run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "1"])
                if result.returncode == 0:
                    self._record("mute", True)
                    return True
            except Exception as e:
                logger.debug("pactl mute error: %s", e)

        if self._use_amixer:
            try:
                result = self._run(["amixer", "sset", "Master", "mute"])
                if result.returncode == 0:
                    self._record("mute", True, "amixer")
                    return True
            except Exception as e:
                logger.debug("amixer mute error: %s", e)

        self._record("mute", False, "no backend available")
        return False

    def unmute(self) -> bool:
        """Unmute system audio."""
        if self._use_pactl:
            try:
                result = self._run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "0"])
                if result.returncode == 0:
                    self._record("unmute", True)
                    return True
            except Exception as e:
                logger.debug("pactl unmute error: %s", e)

        if self._use_amixer:
            try:
                result = self._run(["amixer", "sset", "Master", "unmute"])
                if result.returncode == 0:
                    self._record("unmute", True, "amixer")
                    return True
            except Exception as e:
                logger.debug("amixer unmute error: %s", e)

        self._record("unmute", False, "no backend available")
        return False

    def list_devices(self) -> list[dict[str, Any]]:
        """List audio playback and recording devices."""
        devices: list[dict[str, Any]] = []

        if self._use_pactl:
            try:
                sinks = self._run(["pactl", "list", "short", "sinks"], timeout=10)
                if sinks.returncode == 0:
                    for line in sinks.stdout.strip().splitlines():
                        parts = line.split("\t")
                        if len(parts) >= 2:
                            devices.append({
                                "name": parts[1],
                                "device_id": parts[0],
                                "device_type": "playback",
                                "status": parts[-1] if len(parts) > 2 else "",
                            })

                sources = self._run(["pactl", "list", "short", "sources"], timeout=10)
                if sources.returncode == 0:
                    for line in sources.stdout.strip().splitlines():
                        parts = line.split("\t")
                        if len(parts) >= 2:
                            devices.append({
                                "name": parts[1],
                                "device_id": parts[0],
                                "device_type": "recording",
                                "status": parts[-1] if len(parts) > 2 else "",
                            })
            except Exception as e:
                logger.debug("pactl list_devices error: %s", e)

        elif self._use_amixer:
            try:
                result = self._run(["amixer", "info"], timeout=10)
                if result.returncode == 0:
                    match = re.search(r"Card .+ '(.+)'/", result.stdout)
                    if match:
                        devices.append({
                            "name": match.group(1),
                            "device_id": "0",
                            "device_type": "playback",
                            "status": "RUNNING",
                        })
            except Exception as e:
                logger.debug("amixer list_devices error: %s", e)

        self._record("list_devices", True, f"{len(devices)} devices")
        return devices

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


audio_controller = AudioController()
