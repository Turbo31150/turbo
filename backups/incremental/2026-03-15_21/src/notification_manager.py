"""Notification Manager — Windows toast notification management.

Send notifications, track history, notification templates.
Uses PowerShell BurntToast or Windows.UI.Notifications (no external deps).
Designed for JARVIS autonomous user notification system.
"""

from __future__ import annotations

import logging
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Any


__all__ = [
    "NotifEvent",
    "Notification",
    "NotificationManager",
]

logger = logging.getLogger("jarvis.notification_manager")

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


@dataclass
class Notification:
    """A notification record."""
    title: str
    message: str
    timestamp: float = field(default_factory=time.time)
    priority: str = "normal"
    source: str = "JARVIS"
    sent: bool = False


@dataclass
class NotifEvent:
    """Record of a notification action."""
    action: str
    detail: str = ""
    timestamp: float = field(default_factory=time.time)
    success: bool = True


class NotificationManager:
    """Windows notification management with history."""

    def __init__(self, max_history: int = 200) -> None:
        self._history: list[Notification] = []
        self._events: list[NotifEvent] = []
        self._max_history = max_history
        self._lock = threading.Lock()
        self._templates: dict[str, dict[str, str]] = {
            "info": {"title": "JARVIS Info", "priority": "normal"},
            "warning": {"title": "JARVIS Warning", "priority": "high"},
            "error": {"title": "JARVIS Error", "priority": "urgent"},
            "success": {"title": "JARVIS", "priority": "normal"},
        }

    # ── Send Notification ──────────────────────────────────────────────

    def send(self, title: str, message: str, priority: str = "normal",
             source: str = "JARVIS") -> bool:
        """Send a Windows toast notification."""
        notif = Notification(
            title=title, message=message, priority=priority, source=source,
        )
        # Try PowerShell toast
        success = self._send_bash(title, message)
        notif.sent = success
        with self._lock:
            self._history.append(notif)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]
        self._record("send", success, f"{title}: {message[:50]}")
        return success

    def _send_bash(self, title: str, message: str) -> bool:
        """Send toast via PowerShell."""
        # Escape single quotes
        title_safe = title.replace("'", "''")
        msg_safe = message.replace("'", "''")
        ps_cmd = (
            f"[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, "
            f"ContentType = WindowsRuntime] | Out-Null; "
            f"$xml = [Windows.UI.Notifications.ToastNotificationManager]"
            f"::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02); "
            f"$texts = $xml.GetElementsByTagName('text'); "
            f"$texts[0].AppendChild($xml.CreateTextNode('{title_safe}')) | Out-Null; "
            f"$texts[1].AppendChild($xml.CreateTextNode('{msg_safe}')) | Out-Null; "
            f"$toast = [Windows.UI.Notifications.ToastNotification]::new($xml); "
            f"[Windows.UI.Notifications.ToastNotificationManager]"
            f"::CreateToastNotifier('JARVIS').Show($toast)"
        )
        try:
            result = subprocess.run(
                ["bash", "-Command", ps_cmd],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10,
                creationflags=_NO_WINDOW,
            )
            return result.returncode == 0
        except Exception:
            return False

    def send_template(self, template: str, message: str) -> bool:
        """Send notification using a template."""
        tmpl = self._templates.get(template, self._templates["info"])
        return self.send(
            title=tmpl["title"],
            message=message,
            priority=tmpl.get("priority", "normal"),
        )

    # ── History ────────────────────────────────────────────────────────

    def get_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get notification history."""
        with self._lock:
            return [
                {
                    "title": n.title, "message": n.message[:200],
                    "timestamp": n.timestamp, "priority": n.priority,
                    "source": n.source, "sent": n.sent,
                }
                for n in self._history[-limit:]
            ]

    def clear_history(self) -> int:
        """Clear notification history."""
        with self._lock:
            count = len(self._history)
            self._history.clear()
            return count

    def search_history(self, query: str) -> list[dict[str, Any]]:
        """Search notifications by title or message."""
        q = query.lower()
        with self._lock:
            return [
                {"title": n.title, "message": n.message[:200],
                 "timestamp": n.timestamp, "priority": n.priority}
                for n in self._history
                if q in n.title.lower() or q in n.message.lower()
            ]

    # ── Templates ──────────────────────────────────────────────────────

    def list_templates(self) -> dict[str, dict[str, str]]:
        """List available notification templates."""
        return dict(self._templates)

    def add_template(self, name: str, title: str, priority: str = "normal") -> None:
        """Add a custom notification template."""
        self._templates[name] = {"title": title, "priority": priority}

    # ── Query ──────────────────────────────────────────────────────────

    def _record(self, action: str, success: bool, detail: str = "") -> None:
        with self._lock:
            self._events.append(NotifEvent(
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
            sent = sum(1 for n in self._history if n.sent)
            return {
                "total_notifications": len(self._history),
                "sent_success": sent,
                "templates": len(self._templates),
                "total_events": len(self._events),
            }


# ── Singleton ───────────────────────────────────────────────────────
notification_manager = NotificationManager()
