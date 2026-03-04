"""JARVIS Alert Manager — Unified alert system with escalation and rules.

Centralizes alerts from all modules with deduplication, cooldown per source,
escalation rules (info→warning→critical), and integration with notifier+event_bus.

Usage:
    from src.alert_manager import alert_manager
    await alert_manager.fire("gpu_hot", "GPU 0 at 85C", level="warning", source="gpu_monitor")
    alerts = alert_manager.get_active()
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("jarvis.alerts")


@dataclass
class Alert:
    """A single alert."""
    id: str
    key: str
    message: str
    level: str  # info, warning, critical
    source: str
    created_at: float
    updated_at: float
    count: int = 1
    acknowledged: bool = False
    resolved: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


class AlertManager:
    """Unified alert system with deduplication and escalation."""

    def __init__(self) -> None:
        self._alerts: dict[str, Alert] = {}  # key -> Alert
        self._history: list[dict[str, Any]] = []
        self._max_history = 500
        self._cooldown: dict[str, float] = {}
        self._cooldown_s = 120.0  # 2min between same alert
        self._alert_counter = 0

        # Escalation rules: if an alert fires N times, escalate level
        self._escalation_rules: dict[str, int] = {
            "info": 5,       # info fires 5x → warning
            "warning": 3,    # warning fires 3x → critical
        }

    async def fire(self, key: str, message: str, level: str = "info",
                   source: str = "", metadata: dict[str, Any] | None = None) -> bool:
        """Fire an alert. Returns True if processed, False if deduplicated/cooled."""
        now = time.time()

        # Cooldown check
        cooldown_key = f"{key}:{source}"
        if cooldown_key in self._cooldown:
            if (now - self._cooldown[cooldown_key]) < self._cooldown_s:
                # Update existing alert count silently
                if key in self._alerts:
                    self._alerts[key].count += 1
                    self._alerts[key].updated_at = now
                return False

        self._cooldown[cooldown_key] = now

        if key in self._alerts and not self._alerts[key].resolved:
            # Dedup: update existing alert
            alert = self._alerts[key]
            alert.count += 1
            alert.updated_at = now
            alert.message = message

            # Escalation
            threshold = self._escalation_rules.get(alert.level, 999)
            if alert.count >= threshold:
                old_level = alert.level
                if alert.level == "info":
                    alert.level = "warning"
                elif alert.level == "warning":
                    alert.level = "critical"
                if old_level != alert.level:
                    logger.warning("Alert %s escalated: %s → %s (count: %d)",
                                   key, old_level, alert.level, alert.count)
        else:
            # New alert
            self._alert_counter += 1
            alert = Alert(
                id=f"alert_{self._alert_counter}",
                key=key, message=message, level=level, source=source,
                created_at=now, updated_at=now,
                metadata=metadata or {},
            )
            self._alerts[key] = alert

        # Record in history
        self._history.append({
            "ts": now, "key": key, "level": alert.level,
            "message": message, "source": source, "count": alert.count,
        })
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

        # Emit on event bus
        try:
            from src.event_bus import event_bus
            await event_bus.emit(f"alert.{alert.level}", {
                "key": key, "message": message, "level": alert.level,
                "source": source, "count": alert.count,
            })
        except Exception:
            pass

        # Send notification for warnings and criticals
        if alert.level in ("warning", "critical"):
            try:
                from src.notifier import notifier
                if alert.level == "critical":
                    await notifier.alert(message, source=source)
                else:
                    await notifier.warn(message, source=source)
            except Exception:
                pass

        return True

    def acknowledge(self, key: str) -> bool:
        """Acknowledge an alert."""
        if key in self._alerts:
            self._alerts[key].acknowledged = True
            return True
        return False

    def resolve(self, key: str) -> bool:
        """Resolve an alert."""
        if key in self._alerts:
            self._alerts[key].resolved = True
            self._alerts[key].updated_at = time.time()
            return True
        return False

    def get_active(self, level: str | None = None) -> list[dict[str, Any]]:
        """Get active (unresolved) alerts."""
        result = []
        for alert in self._alerts.values():
            if alert.resolved:
                continue
            if level and alert.level != level:
                continue
            result.append(self._alert_to_dict(alert))
        result.sort(key=lambda a: a["updated_at"], reverse=True)
        return result

    def get_all(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get all alerts (including resolved)."""
        alerts = [self._alert_to_dict(a) for a in self._alerts.values()]
        alerts.sort(key=lambda a: a["updated_at"], reverse=True)
        return alerts[:limit]

    def get_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get alert history."""
        return self._history[-limit:]

    @staticmethod
    def _alert_to_dict(alert: Alert) -> dict[str, Any]:
        return {
            "id": alert.id, "key": alert.key, "message": alert.message,
            "level": alert.level, "source": alert.source,
            "created_at": alert.created_at, "updated_at": alert.updated_at,
            "count": alert.count, "acknowledged": alert.acknowledged,
            "resolved": alert.resolved, "metadata": alert.metadata,
        }

    def get_stats(self) -> dict[str, Any]:
        """Alert stats."""
        active = [a for a in self._alerts.values() if not a.resolved]
        by_level: dict[str, int] = {}
        for a in active:
            by_level[a.level] = by_level.get(a.level, 0) + 1
        return {
            "total_alerts": len(self._alerts),
            "active_alerts": len(active),
            "by_level": by_level,
            "history_size": len(self._history),
        }

    def clear_resolved(self) -> int:
        """Remove resolved alerts."""
        resolved_keys = [k for k, a in self._alerts.items() if a.resolved]
        for k in resolved_keys:
            del self._alerts[k]
        return len(resolved_keys)


# Global singleton
alert_manager = AlertManager()
