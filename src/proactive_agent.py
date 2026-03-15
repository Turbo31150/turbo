"""Proactive Agent — Context-aware auto-suggestions and autonomous execution.

Time-based suggestions, confidence thresholds, auto-execute with logging.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from typing import Any

logger = logging.getLogger("jarvis.proactive")

# Confidence thresholds per category for auto-execution
AUTO_EXEC_THRESHOLDS: dict[str, float] = {
    "health": 0.9,
    "thermal": 0.85,
    "backup": 0.8,
    "reporting": 0.7,
    "maintenance": 0.8,
    "cleanup": 0.75,
}


class ProactiveAgent:
    """Context-aware proactive suggestions with auto-execution."""

    def __init__(self, cooldown_s: float = 1800.0) -> None:
        self._last_suggestions: list[dict[str, Any]] = []
        self._dismissed: set[str] = set()
        self._exec_log: list[dict[str, Any]] = []
        self._cooldown_s = cooldown_s
        self._last_scan = 0.0

    def get_last(self) -> list[dict[str, Any]]:
        """Get last suggestions."""
        return self._last_suggestions

    def get_exec_log(self, limit: int = 20) -> list[dict[str, Any]]:
        """Get execution log, most recent first."""
        return self._exec_log[-limit:]

    def get_stats(self) -> dict[str, Any]:
        """Get proactive agent stats."""
        return {
            "last_suggestions_count": len(self._last_suggestions),
            "dismissed_count": len(self._dismissed),
            "auto_executions": len(self._exec_log),
            "cooldown_s": self._cooldown_s,
        }

    def dismiss(self, key: str) -> None:
        """Dismiss a suggestion by key."""
        self._dismissed.add(key)

    @staticmethod
    def _time_suggestions(dt: datetime | None = None) -> list[dict[str, Any]]:
        """Generate time-based suggestions."""
        if dt is None:
            dt = datetime.now()

        suggestions: list[dict[str, Any]] = []
        hour = dt.hour
        weekday = dt.weekday()  # 0=Monday

        # Night backup: 22:00-23:59
        if 22 <= hour <= 23:
            suggestions.append({
                "key": "night_backup",
                "message": "Lancer un backup nocturne des bases de donnees",
                "action": "night_backup",
                "priority": "medium",
                "category": "backup",
                "confidence": 0.85,
            })

        # Night maintenance: 2:00-4:00
        if 2 <= hour <= 4:
            suggestions.append({
                "key": "night_maintenance",
                "message": "Maintenance nocturne: nettoyage logs, optimisation DB",
                "action": "night_maintenance",
                "priority": "medium",
                "category": "maintenance",
                "confidence": 0.8,
            })

        # Monday report: Monday 8:00-10:00
        if weekday == 0 and 8 <= hour <= 10:
            suggestions.append({
                "key": "monday_report",
                "message": "Generer le rapport hebdomadaire du lundi",
                "action": "weekly_report",
                "priority": "high",
                "category": "reporting",
                "confidence": 0.9,
            })

        return suggestions

    async def analyze(self) -> list[dict[str, Any]]:
        """Analyze context and return suggestions."""
        suggestions = self._time_suggestions()
        # Filter dismissed
        suggestions = [s for s in suggestions if s["key"] not in self._dismissed]
        self._last_suggestions = suggestions
        return suggestions

    async def auto_execute(self, suggestion: dict[str, Any]) -> dict[str, Any]:
        """Auto-execute a suggestion if confidence exceeds category threshold."""
        category = suggestion.get("category", "unknown")
        confidence = suggestion.get("confidence", 0.0)
        priority = suggestion.get("priority", "low")

        # High priority gets a confidence boost
        effective_confidence = confidence
        if priority == "high":
            effective_confidence = max(confidence, 0.85)

        threshold = AUTO_EXEC_THRESHOLDS.get(category, 0.95)

        if effective_confidence < threshold:
            return {
                "executed": False,
                "reason": "below_threshold",
                "confidence": effective_confidence,
                "threshold": threshold,
            }

        try:
            result = await self._execute_action(suggestion.get("action", ""))
            self._exec_log.append({
                "key": suggestion.get("key"),
                "action": suggestion.get("action"),
                "category": category,
                "confidence": confidence,
                "success": True,
                "result": result,
                "ts": time.time(),
            })
            return {"executed": True, "result": result}
        except Exception as e:
            self._exec_log.append({
                "key": suggestion.get("key"),
                "action": suggestion.get("action"),
                "category": category,
                "confidence": confidence,
                "success": False,
                "error": str(e),
                "ts": time.time(),
            })
            return {"executed": False, "reason": f"error: {e}"}

    async def _execute_action(self, action: str) -> str:
        """Execute a specific action."""
        if not action:
            return "no_action"

        if action == "health_check":
            try:
                from src.orchestrator_v2 import orchestrator_v2
                score = orchestrator_v2.health_check()
                return f"health_score={score}"
            except Exception as e:
                return f"health_check_error: {e}"

        # Default: enqueue as task
        try:
            from src.task_queue import task_queue
            task_id = task_queue.enqueue(action)
            return f"enqueued: {task_id}"
        except Exception:
            return f"enqueued_placeholder: {action}"

    async def analyze_and_execute(self) -> dict[str, Any]:
        """Analyze suggestions and auto-execute qualifying ones."""
        suggestions = await self.analyze()
        executed: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []

        for s in suggestions:
            result = await self.auto_execute(s)
            if result.get("executed"):
                executed.append({"key": s["key"], **result})
            else:
                skipped.append({"key": s["key"], **result})

        return {
            "total": len(suggestions),
            "executed": executed,
            "skipped": skipped,
        }

    async def run_loop(self) -> None:
        """Main proactive loop."""
        logger.info("Proactive Agent started.")
        while True:
            await self.analyze_and_execute()
            await asyncio.sleep(self._cooldown_s)


if __name__ == "__main__":
    agent = ProactiveAgent()
    asyncio.run(agent.run_loop())
