"""JARVIS Proactive Agent v2 — Context-aware auto-suggestions + auto-execution.

Analyzes system state (time, GPU, cluster health, usage patterns) and proposes
relevant actions without being asked. High-confidence suggestions are now
auto-executed based on per-category thresholds.

Usage:
    from src.proactive_agent import proactive_agent
    suggestions = await proactive_agent.analyze()
    executed = await proactive_agent.analyze_and_execute()
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from typing import Any

logger = logging.getLogger("jarvis.proactive")

# Auto-execution thresholds per category — higher = more cautious
AUTO_EXEC_THRESHOLDS: dict[str, float] = {
    "maintenance": 0.8,   # nettoyage, backup → executer auto
    "health": 0.9,        # seulement si critique
    "thermal": 0.95,      # prudent avec le GPU
    "reporting": 0.7,     # rapports → toujours OK
    "budget": 0.85,       # alertes budget
    "resources": 0.9,     # cleanup memoire/VRAM
}


class ProactiveAgent:
    """Generates contextual suggestions and auto-executes high-confidence ones."""

    def __init__(self) -> None:
        self._last_suggestions: list[dict[str, Any]] = []
        self._dismissed: set[str] = set()  # dismissed suggestion keys
        self._cooldown: dict[str, float] = {}
        self._cooldown_s = 1800.0  # 30 min between same suggestion
        self._exec_log: list[dict[str, Any]] = []  # auto-execution history

    async def analyze(self) -> list[dict[str, Any]]:
        """Analyze current context and generate suggestions."""
        suggestions: list[dict[str, Any]] = []
        now = datetime.now()

        # Time-based suggestions
        suggestions.extend(self._time_suggestions(now))

        # Cluster health suggestions
        suggestions.extend(await self._cluster_suggestions())

        # GPU thermal suggestions
        suggestions.extend(await self._gpu_suggestions())

        # Budget suggestions
        suggestions.extend(self._budget_suggestions())

        # Usage pattern suggestions
        suggestions.extend(self._pattern_suggestions())

        # Filter dismissed and cooldown
        filtered = []
        current_time = time.time()
        for s in suggestions:
            key = s.get("key", s["message"][:30])
            if key in self._dismissed:
                continue
            if key in self._cooldown and (current_time - self._cooldown[key]) < self._cooldown_s:
                continue
            self._cooldown[key] = current_time
            filtered.append(s)

        self._last_suggestions = filtered
        return filtered

    def dismiss(self, key: str) -> None:
        """Dismiss a suggestion permanently."""
        self._dismissed.add(key)

    def get_last(self) -> list[dict[str, Any]]:
        """Return last generated suggestions."""
        return self._last_suggestions

    # ── Auto-execution ───────────────────────────────────────────────────

    async def analyze_and_execute(self) -> dict[str, Any]:
        """Analyze + auto-execute suggestions above threshold. Returns report."""
        suggestions = await self.analyze()
        executed = []
        skipped = []
        for s in suggestions:
            result = await self.auto_execute(s)
            if result["executed"]:
                executed.append({"key": s.get("key"), "result": result.get("result")})
            else:
                skipped.append({"key": s.get("key"), "reason": result.get("reason")})
        return {"executed": executed, "skipped": skipped, "total": len(suggestions)}

    async def auto_execute(self, suggestion: dict[str, Any]) -> dict[str, Any]:
        """Execute a suggestion if confidence >= category threshold."""
        cat = suggestion.get("category", "")
        threshold = AUTO_EXEC_THRESHOLDS.get(cat, 0.95)
        confidence = suggestion.get("confidence", 0.75)

        # Priority-based confidence boost
        priority = suggestion.get("priority", "low")
        if priority == "high":
            confidence = max(confidence, 0.85)
        elif priority == "medium":
            confidence = max(confidence, 0.75)

        if confidence >= threshold:
            try:
                result = await self._execute_action(suggestion.get("action", ""))
                self._exec_log.append({
                    "ts": time.time(), "key": suggestion.get("key"),
                    "action": suggestion.get("action"), "success": True,
                })
                # Emit event
                try:
                    from src.event_bus import event_bus
                    await event_bus.emit("proactive.executed", {
                        "key": suggestion.get("key"), "action": suggestion.get("action"),
                        "category": cat, "result": str(result)[:200],
                    })
                except Exception:
                    pass
                return {"executed": True, "result": result}
            except Exception as e:
                logger.warning("Auto-execute failed for %s: %s", suggestion.get("key"), e)
                self._exec_log.append({
                    "ts": time.time(), "key": suggestion.get("key"),
                    "action": suggestion.get("action"), "success": False, "error": str(e),
                })
                return {"executed": False, "reason": f"error: {e}"}
        return {"executed": False, "reason": "below_threshold"}

    async def _execute_action(self, action: str) -> str:
        """Route action to the appropriate module."""
        if not action:
            return "no_action"

        # Light actions — execute directly
        light_actions = {
            "health_check": self._do_health_check,
            "weekly_report": self._do_weekly_report,
            "memory_cleanup": self._do_memory_cleanup,
            "budget_review": self._do_budget_review,
        }
        if action in light_actions:
            return await light_actions[action]()

        # Heavy actions — enqueue in task_queue
        try:
            from src.task_queue import task_queue
            task_id = task_queue.enqueue(action, priority=5)
            return f"enqueued:{task_id}"
        except Exception as e:
            logger.warning("Failed to enqueue action %s: %s", action, e)
            return f"enqueue_failed:{e}"

    @staticmethod
    async def _do_health_check() -> str:
        from src.orchestrator_v2 import orchestrator_v2
        score = orchestrator_v2.health_check()
        return f"health_score={score}"

    @staticmethod
    async def _do_weekly_report() -> str:
        try:
            from src.orchestrator_v2 import orchestrator_v2
            report = orchestrator_v2.get_dashboard()
            return f"report_generated: {len(report)} keys"
        except Exception as e:
            return f"report_error: {e}"

    @staticmethod
    async def _do_memory_cleanup() -> str:
        try:
            from src.agent_memory import agent_memory
            cleaned = agent_memory.cleanup(max_age_days=30)
            return f"cleaned={cleaned}"
        except Exception as e:
            return f"cleanup_error: {e}"

    @staticmethod
    async def _do_budget_review() -> str:
        from src.orchestrator_v2 import orchestrator_v2
        budget = orchestrator_v2.get_budget_report()
        return f"tokens={budget.get('total_tokens', 0)}"

    def get_exec_log(self, limit: int = 20) -> list[dict[str, Any]]:
        """Return recent auto-execution history."""
        return self._exec_log[-limit:]

    # ── Analyzers ───────────────────────────────────────────────────────

    @staticmethod
    def _time_suggestions(now: datetime) -> list[dict[str, Any]]:
        """Suggestions based on time of day."""
        suggestions = []
        hour = now.hour

        if hour == 23 and now.minute < 30:
            suggestions.append({
                "key": "night_backup",
                "message": "Il est 23h — lancer le backup nocturne ?",
                "action": "db_backup",
                "priority": "low",
                "category": "maintenance",
                "confidence": 0.85,
            })

        if hour >= 2 and hour < 5:
            suggestions.append({
                "key": "night_maintenance",
                "message": "Heures creuses — bon moment pour maintenance DB et cleanup",
                "action": "db_maintenance",
                "priority": "low",
                "category": "maintenance",
                "confidence": 0.9,
            })

        if now.weekday() == 0 and hour == 9:
            suggestions.append({
                "key": "monday_report",
                "message": "Lundi matin — generer le rapport hebdomadaire du cluster ?",
                "action": "weekly_report",
                "priority": "medium",
                "category": "reporting",
                "confidence": 0.8,
            })

        return suggestions

    @staticmethod
    async def _cluster_suggestions() -> list[dict[str, Any]]:
        """Suggestions based on cluster health."""
        suggestions = []
        try:
            from src.orchestrator_v2 import orchestrator_v2
            health = orchestrator_v2.health_check()
            alerts = orchestrator_v2.get_alerts()

            if health < 50:
                suggestions.append({
                    "key": "cluster_critical",
                    "message": f"Sante cluster critique ({health}/100) — diagnostic recommande",
                    "action": "system_audit",
                    "priority": "high",
                    "category": "health",
                    "confidence": 0.95,
                })
            elif health < 70:
                suggestions.append({
                    "key": "cluster_warning",
                    "message": f"Sante cluster degradee ({health}/100) — {len(alerts)} alertes",
                    "action": "health_check",
                    "priority": "medium",
                    "category": "health",
                    "confidence": 0.85,
                })
        except Exception:
            pass
        return suggestions

    @staticmethod
    async def _gpu_suggestions() -> list[dict[str, Any]]:
        """Suggestions based on GPU state."""
        suggestions = []
        try:
            import subprocess
            r = await asyncio.to_thread(
                subprocess.run,
                ["nvidia-smi", "--query-gpu=index,temperature.gpu,utilization.gpu,memory.used,memory.total",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5,
            )
            if r.returncode == 0:
                for line in r.stdout.strip().split("\n"):
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) >= 5:
                        temp = int(parts[1])
                        util = int(parts[2])
                        used = int(parts[3])
                        total = int(parts[4])
                        vram_pct = (used / total * 100) if total > 0 else 0

                        if temp >= 80:
                            suggestions.append({
                                "key": f"gpu{parts[0]}_hot",
                                "message": f"GPU {parts[0]} a {temp}C — reduire la charge ou augmenter ventilation",
                                "action": "gpu_cooldown",
                                "priority": "high",
                                "category": "thermal",
                                "confidence": 0.9,
                            })
                        if vram_pct >= 90:
                            suggestions.append({
                                "key": f"gpu{parts[0]}_vram",
                                "message": f"GPU {parts[0]} VRAM {vram_pct:.0f}% — liberer de la memoire ?",
                                "action": "gpu_cleanup",
                                "priority": "medium",
                                "category": "resources",
                                "confidence": 0.85,
                            })
        except Exception:
            pass
        return suggestions

    @staticmethod
    def _budget_suggestions() -> list[dict[str, Any]]:
        """Suggestions based on token budget."""
        suggestions = []
        try:
            from src.orchestrator_v2 import orchestrator_v2
            budget = orchestrator_v2.get_budget_report()
            total = budget.get("total_tokens", 0)
            rate = budget.get("tokens_per_minute", 0)

            if total > 1_000_000:
                suggestions.append({
                    "key": "budget_high",
                    "message": f"Budget tokens eleve: {total:,} ({rate:.0f}/min) — optimiser les requetes ?",
                    "action": "budget_review",
                    "priority": "medium",
                    "category": "budget",
                    "confidence": 0.8,
                })
        except Exception:
            pass
        return suggestions

    @staticmethod
    def _pattern_suggestions() -> list[dict[str, Any]]:
        """Suggestions based on usage patterns from agent memory."""
        suggestions = []
        try:
            from src.agent_memory import agent_memory
            stats = agent_memory.get_stats()
            if stats.get("total", 0) > 100:
                suggestions.append({
                    "key": "memory_cleanup",
                    "message": f"Agent memory a {stats['total']} entries — cleanup recommande",
                    "action": "memory_cleanup",
                    "priority": "low",
                    "category": "maintenance",
                    "confidence": 0.85,
                })
        except Exception:
            pass
        return suggestions

    def get_stats(self) -> dict[str, Any]:
        """Proactive agent stats."""
        return {
            "last_suggestions_count": len(self._last_suggestions),
            "dismissed_count": len(self._dismissed),
            "cooldown_entries": len(self._cooldown),
            "auto_executions": len(self._exec_log),
            "recent_execs": self._exec_log[-5:],
        }


# Global singleton
proactive_agent = ProactiveAgent()
