"""JARVIS Proactive Agent — Context-aware automatic suggestions.

Analyzes system state (time, GPU, cluster health, usage patterns) and proposes
relevant actions without being asked.

Usage:
    from src.proactive_agent import proactive_agent
    suggestions = await proactive_agent.analyze()
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from typing import Any

logger = logging.getLogger("jarvis.proactive")


class ProactiveAgent:
    """Generates contextual suggestions based on system state."""

    def __init__(self) -> None:
        self._last_suggestions: list[dict[str, Any]] = []
        self._dismissed: set[str] = set()  # dismissed suggestion keys
        self._cooldown: dict[str, float] = {}
        self._cooldown_s = 1800.0  # 30 min between same suggestion

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
            })

        if hour >= 2 and hour < 5:
            suggestions.append({
                "key": "night_maintenance",
                "message": "Heures creuses — bon moment pour maintenance DB et cleanup",
                "action": "db_maintenance",
                "priority": "low",
                "category": "maintenance",
            })

        if now.weekday() == 0 and hour == 9:
            suggestions.append({
                "key": "monday_report",
                "message": "Lundi matin — generer le rapport hebdomadaire du cluster ?",
                "action": "weekly_report",
                "priority": "medium",
                "category": "reporting",
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
                })
            elif health < 70:
                suggestions.append({
                    "key": "cluster_warning",
                    "message": f"Sante cluster degradee ({health}/100) — {len(alerts)} alertes",
                    "action": "health_check",
                    "priority": "medium",
                    "category": "health",
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
                            })
                        if vram_pct >= 90:
                            suggestions.append({
                                "key": f"gpu{parts[0]}_vram",
                                "message": f"GPU {parts[0]} VRAM {vram_pct:.0f}% — liberer de la memoire ?",
                                "action": "gpu_cleanup",
                                "priority": "medium",
                                "category": "resources",
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
        }


# Global singleton
proactive_agent = ProactiveAgent()
