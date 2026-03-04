"""JARVIS Notification System — Unified alerts via Windows Toast + TTS + logging.

Usage:
    from src.notifier import notifier
    await notifier.alert("GPU overheat!", level="critical")
    await notifier.info("Cluster healthy")
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger("jarvis.notifier")


class Level(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class Notification:
    message: str
    level: Level
    ts: float = field(default_factory=time.time)
    source: str = ""
    delivered: bool = False


class Notifier:
    """Unified notification dispatcher."""

    def __init__(self, max_history: int = 100) -> None:
        self._history: list[Notification] = []
        self._max = max_history
        self._tts_enabled = True
        self._toast_enabled = True
        self._cooldown: dict[str, float] = {}  # prevent spam
        self._cooldown_s = 60.0  # min seconds between same message

    async def alert(self, message: str, level: str = "warning", source: str = "") -> bool:
        """Send a notification. Returns True if delivered."""
        lvl = Level(level) if level in Level.__members__.values() else Level.WARNING

        # Cooldown check
        key = f"{lvl}:{message[:50]}"
        now = time.time()
        if key in self._cooldown and (now - self._cooldown[key]) < self._cooldown_s:
            return False
        self._cooldown[key] = now

        notif = Notification(message=message, level=lvl, source=source)

        # Dispatch based on level
        delivered = False
        if lvl == Level.CRITICAL:
            delivered = await self._send_tts(message) or await self._send_toast(message, "JARVIS ALERTE")
        elif lvl == Level.WARNING:
            delivered = await self._send_toast(message, "JARVIS Warning")
        else:
            delivered = True  # info = log only
            logger.info("[NOTIF] %s", message)

        notif.delivered = delivered
        self._history.append(notif)
        if len(self._history) > self._max:
            self._history = self._history[-self._max:]

        return delivered

    async def info(self, message: str, source: str = "") -> bool:
        return await self.alert(message, level="info", source=source)

    async def warn(self, message: str, source: str = "") -> bool:
        return await self.alert(message, level="warning", source=source)

    async def critical(self, message: str, source: str = "") -> bool:
        return await self.alert(message, level="critical", source=source)

    async def _send_toast(self, message: str, title: str = "JARVIS") -> bool:
        """Windows toast notification."""
        if not self._toast_enabled:
            return False
        try:
            import subprocess
            ps_cmd = (
                f'[Windows.UI.Notifications.ToastNotificationManager,'
                f'Windows.UI.Notifications,ContentType=WindowsRuntime]|Out-Null;'
                f'$xml=[Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent(1);'
                f'$text=$xml.GetElementsByTagName("text");'
                f'$text[0].AppendChild($xml.CreateTextNode("{title}"))|Out-Null;'
                f'$text[1].AppendChild($xml.CreateTextNode("{message[:200]}"))|Out-Null;'
                f'$toast=[Windows.UI.Notifications.ToastNotification]::new($xml);'
                f'[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("JARVIS").Show($toast)'
            )
            await asyncio.to_thread(
                lambda: subprocess.run(
                    ["powershell", "-NoProfile", "-Command", ps_cmd],
                    capture_output=True, timeout=5,
                )
            )
            logger.info("[TOAST] %s: %s", title, message[:80])
            return True
        except Exception as e:
            logger.debug("Toast failed: %s", e)
            return False

    async def _send_tts(self, message: str) -> bool:
        """Speak via Edge TTS (critical alerts only)."""
        if not self._tts_enabled:
            return False
        try:
            import edge_tts
            import tempfile
            comm = edge_tts.Communicate(f"Alerte. {message}", "fr-FR-HenriNeural")
            tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
            tmp.close()
            await comm.save(tmp.name)
            proc = await asyncio.create_subprocess_exec(
                "ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", tmp.name,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            # Don't wait — fire and forget
            asyncio.create_task(self._cleanup_after(proc, tmp.name))
            logger.info("[TTS] %s", message[:80])
            return True
        except Exception as e:
            logger.debug("TTS failed: %s", e)
            return False

    @staticmethod
    async def _cleanup_after(proc, path: str) -> None:
        await proc.wait()
        try:
            import pathlib
            pathlib.Path(path).unlink(missing_ok=True)
        except OSError:
            pass

    def get_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """Return notification history."""
        return [
            {
                "message": n.message,
                "level": n.level.value,
                "ts": n.ts,
                "source": n.source,
                "delivered": n.delivered,
            }
            for n in self._history[-limit:]
        ]

    def get_stats(self) -> dict[str, Any]:
        """Return notification stats."""
        by_level = {}
        for n in self._history:
            by_level[n.level.value] = by_level.get(n.level.value, 0) + 1
        return {
            "total": len(self._history),
            "by_level": by_level,
            "tts_enabled": self._tts_enabled,
            "toast_enabled": self._toast_enabled,
        }


# Global singleton
notifier = Notifier()
