"""
health.py — Registre de sante des agents pour orchestrateur multi-agents asyncio.
Concu pour s'integrer avec resilience.py (circuit breaker, retry).
"""

import asyncio
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Literal


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------

@dataclass
class AgentHealth:
    """Snapshot de sante d'un agent a un instant donne."""
    status: Literal["HEALTHY", "DEGRADED", "DOWN"]
    success_rate: float
    avg_latency_ms: float
    total_calls: int
    circuit_state: str  # CLOSED | OPEN | HALF_OPEN


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

WINDOW_SECONDS: int = 300          # Fenetre glissante de 5 minutes
STATUS_HEALTHY_THRESHOLD: float = 0.8
STATUS_DEGRADED_THRESHOLD: float = 0.5


# ---------------------------------------------------------------------------
# Structures internes
# ---------------------------------------------------------------------------

@dataclass
class _AgentStats:
    """Compteurs internes par agent (usage interne uniquement)."""
    success_count: int = 0
    failure_count: int = 0
    timeout_count: int = 0
    total_latency_ms: float = 0.0
    # Chaque entree : (timestamp_float, is_success: bool)
    sliding_window: deque = field(default_factory=deque)


# ---------------------------------------------------------------------------
# Registre central (Singleton)
# ---------------------------------------------------------------------------

class AgentHealthRegistry:
    """
    Registre centralise de sante des agents, thread-safe via asyncio.Lock.
    Singleton : utiliser AgentHealthRegistry.instance().
    """

    _instance: "AgentHealthRegistry | None" = None

    def __init__(self) -> None:
        self._stats: dict[str, _AgentStats] = {}
        self._lock: asyncio.Lock = asyncio.Lock()
        # Etats circuit breaker injectes depuis resilience.py
        self._circuit_states: dict[str, str] = {}

    @classmethod
    def instance(cls) -> "AgentHealthRegistry":
        """Retourne l'instance singleton (cree si absente)."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ------------------------------------------------------------------
    # API d'injection depuis resilience.py
    # ------------------------------------------------------------------

    def set_circuit_state(self, agent_name: str, state: str) -> None:
        """Permet a resilience.py de mettre a jour l'etat du circuit breaker."""
        self._circuit_states[agent_name] = state

    # ------------------------------------------------------------------
    # Enregistrement d'evenements
    # ------------------------------------------------------------------

    async def record_success(self, agent_name: str, latency_ms: float) -> None:
        """Enregistre un appel reussi avec sa latence en millisecondes."""
        async with self._lock:
            stats = self._get_or_create(agent_name)
            now = time.monotonic()
            stats.success_count += 1
            stats.total_latency_ms += latency_ms
            stats.sliding_window.append((now, True))
            self._evict_old(stats, now)

    async def record_failure(self, agent_name: str, error_type: str = "error") -> None:
        """Enregistre un echec (erreur applicative ou reseau)."""
        async with self._lock:
            stats = self._get_or_create(agent_name)
            now = time.monotonic()
            stats.failure_count += 1
            stats.sliding_window.append((now, False))
            self._evict_old(stats, now)

    async def record_timeout(self, agent_name: str) -> None:
        """Enregistre un timeout (compte comme echec dans la fenetre glissante)."""
        async with self._lock:
            stats = self._get_or_create(agent_name)
            now = time.monotonic()
            stats.timeout_count += 1
            stats.failure_count += 1
            stats.sliding_window.append((now, False))
            self._evict_old(stats, now)

    # ------------------------------------------------------------------
    # Lecture de sante
    # ------------------------------------------------------------------

    async def get_health(self, agent_name: str) -> AgentHealth:
        """Retourne le snapshot de sante d'un agent donne."""
        async with self._lock:
            return self._compute_health(agent_name)

    async def get_best_available(self, agent_list: list[str]) -> str:
        """
        Retourne l'agent le plus sain parmi agent_list.
        Critere : statut > success_rate > latence la plus basse.
        """
        async with self._lock:
            status_rank = {"HEALTHY": 0, "DEGRADED": 1, "DOWN": 2}

            def sort_key(name: str):
                h = self._compute_health(name)
                return (
                    status_rank.get(h.status, 3),
                    -h.success_rate,
                    h.avg_latency_ms,
                )

            return min(agent_list, key=sort_key)

    async def get_all_health(self) -> dict[str, AgentHealth]:
        """Retourne le snapshot de sante de tous les agents enregistres."""
        async with self._lock:
            return {name: self._compute_health(name) for name in self._stats}

    async def format_health_table(self) -> str:
        """Retourne un tableau ASCII formate avec l'etat de tous les agents."""
        all_health = await self.get_all_health()
        if not all_health:
            return "Aucun agent enregistre."

        header = f"{'Agent':<24} {'Status':<10} {'Success%':>9} {'Avg Lat':>9} {'Calls':>7} {'Circuit':<12}"
        sep = "-" * len(header)
        lines = [sep, header, sep]

        for name, h in sorted(all_health.items()):
            lines.append(
                f"{name:<24} {h.status:<10} {h.success_rate * 100:>8.1f}%"
                f" {h.avg_latency_ms:>8.1f}ms {h.total_calls:>7} {h.circuit_state:<12}"
            )

        lines.append(sep)
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Methodes internes (sans lock — appelees depuis methodes lockees)
    # ------------------------------------------------------------------

    def _get_or_create(self, agent_name: str) -> _AgentStats:
        if agent_name not in self._stats:
            self._stats[agent_name] = _AgentStats()
        return self._stats[agent_name]

    def _evict_old(self, stats: _AgentStats, now: float) -> None:
        """Supprime les entrees hors de la fenetre glissante."""
        cutoff = now - WINDOW_SECONDS
        while stats.sliding_window and stats.sliding_window[0][0] < cutoff:
            stats.sliding_window.popleft()

    def _compute_health(self, agent_name: str) -> AgentHealth:
        """Calcule AgentHealth sans acquerir de lock (appelee depuis contexte verrouille)."""
        if agent_name not in self._stats:
            return AgentHealth(
                status="HEALTHY",
                success_rate=1.0,
                avg_latency_ms=0.0,
                total_calls=0,
                circuit_state=self._circuit_states.get(agent_name, "CLOSED"),
            )

        stats = self._stats[agent_name]
        total_calls = stats.success_count + stats.failure_count

        # Taux de succes sur la fenetre glissante (priorite) ou global
        window = stats.sliding_window
        if window:
            successes_in_window = sum(1 for _, ok in window if ok)
            success_rate = successes_in_window / len(window)
        elif total_calls > 0:
            success_rate = stats.success_count / total_calls
        else:
            success_rate = 1.0

        avg_latency = (
            stats.total_latency_ms / stats.success_count
            if stats.success_count > 0
            else 0.0
        )

        if success_rate > STATUS_HEALTHY_THRESHOLD:
            status: Literal["HEALTHY", "DEGRADED", "DOWN"] = "HEALTHY"
        elif success_rate >= STATUS_DEGRADED_THRESHOLD:
            status = "DEGRADED"
        else:
            status = "DOWN"

        return AgentHealth(
            status=status,
            success_rate=success_rate,
            avg_latency_ms=avg_latency,
            total_calls=total_calls,
            circuit_state=self._circuit_states.get(agent_name, "CLOSED"),
        )
