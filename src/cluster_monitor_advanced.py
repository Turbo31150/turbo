"""JARVIS Cluster Monitor Advanced — Monitoring du cluster IA avec historique et alertes.

Polling toutes les 30s des noeuds M1/M2/M3/OL1. Historique en ring buffer,
résumés horaires en JSONL, alertes multi-niveaux, routing intelligent par type de tâche.

Usage:
    from src.cluster_monitor_advanced import ClusterMonitorAdvanced
    monitor = ClusterMonitorAdvanced()
    await monitor.start()
    dashboard = monitor.get_cluster_dashboard()
    best = monitor.get_best_node("code")
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import httpx
except ImportError:
    httpx = None  # type: ignore[assignment]

__all__ = [
    "ClusterMonitorAdvanced",
    "NodeConfig",
    "NodeMeasurement",
    "ClusterAlert",
]

logger = logging.getLogger("jarvis.cluster_monitor_advanced")

# Chemin historique JSONL
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
HISTORY_FILE = DATA_DIR / "cluster_history.jsonl"

# ── Configuration des noeuds ────────────────────────────────────────────────

POLL_INTERVAL_S = 30
RING_BUFFER_SIZE = 1000
OFFLINE_ALERT_THRESHOLD_S = 300  # 5 minutes
LATENCY_WARNING_S = 2.0
LATENCY_CRITICAL_S = 5.0
VRAM_WARNING_PCT = 90.0


@dataclass
class NodeConfig:
    """Configuration d'un noeud du cluster."""
    name: str
    host: str
    port: int
    node_type: str  # "lmstudio" ou "ollama"
    has_vram: bool = True
    expected_models: list[str] = field(default_factory=list)
    task_types: list[str] = field(default_factory=list)
    priority: int = 1  # 1 = plus prioritaire


# Définition des noeuds du cluster
DEFAULT_NODES: list[NodeConfig] = [
    NodeConfig(
        name="M1",
        host="127.0.0.1",
        port=1234,
        node_type="lmstudio",
        has_vram=True,
        expected_models=["qwen3-8b"],
        task_types=["code", "fast", "translation"],
        priority=1,
    ),
    NodeConfig(
        name="M2",
        host="192.168.1.26",
        port=1234,
        node_type="lmstudio",
        has_vram=True,
        expected_models=["deepseek-r1-0528-qwen3-8b"],
        task_types=["reasoning", "code"],
        priority=2,
    ),
    NodeConfig(
        name="M3",
        host="192.168.1.113",
        port=1234,
        node_type="lmstudio",
        has_vram=False,
        expected_models=["deepseek-r1-0528-qwen3-8b"],
        task_types=["reasoning"],
        priority=3,
    ),
    NodeConfig(
        name="OL1",
        host="127.0.0.1",
        port=11434,
        node_type="ollama",
        has_vram=False,
        expected_models=["qwen3:1.7b"],
        task_types=["fast", "translation"],
        priority=2,
    ),
]


@dataclass
class NodeMeasurement:
    """Une mesure ponctuelle d'un noeud."""
    timestamp: float
    node_name: str
    online: bool
    latency_s: float
    models: list[str] = field(default_factory=list)
    vram_used_mb: float = 0.0
    vram_total_mb: float = 0.0
    vram_pct: float = 0.0
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "ts": self.timestamp,
            "node": self.node_name,
            "online": self.online,
            "latency_s": round(self.latency_s, 3),
            "models": self.models,
            "vram_used_mb": round(self.vram_used_mb, 1),
            "vram_total_mb": round(self.vram_total_mb, 1),
            "vram_pct": round(self.vram_pct, 1),
            "error": self.error,
        }


@dataclass
class ClusterAlert:
    """Alerte du moniteur cluster."""
    timestamp: float
    node_name: str
    level: str  # "info", "warning", "critical"
    alert_type: str
    message: str
    resolved: bool = False
    resolved_at: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "ts": self.timestamp,
            "node": self.node_name,
            "level": self.level,
            "type": self.alert_type,
            "message": self.message,
            "resolved": self.resolved,
            "resolved_at": self.resolved_at,
        }


class ClusterMonitorAdvanced:
    """Moniteur avancé du cluster IA avec historique, alertes et routing."""

    def __init__(self, nodes: list[NodeConfig] | None = None) -> None:
        self._nodes: dict[str, NodeConfig] = {}
        for nc in (nodes or DEFAULT_NODES):
            self._nodes[nc.name] = nc

        # Ring buffers par noeud (1000 mesures)
        self._history: dict[str, deque[NodeMeasurement]] = {
            name: deque(maxlen=RING_BUFFER_SIZE) for name in self._nodes
        }

        # Dernière mesure par noeud
        self._latest: dict[str, NodeMeasurement | None] = {
            name: None for name in self._nodes
        }

        # Alertes actives et historique
        self._active_alerts: list[ClusterAlert] = []
        self._alert_history: list[ClusterAlert] = []
        self._max_alert_history = 500

        # Timestamp première mise offline par noeud (pour alerte >5min)
        self._offline_since: dict[str, float] = {}

        # Dernier résumé horaire écrit
        self._last_hourly_summary: float = 0.0

        # Contrôle du polling
        self._running = False
        self._task: asyncio.Task[None] | None = None

        # Client HTTP partagé
        self._client: httpx.AsyncClient | None = None

    # ── Démarrage / Arrêt ────────────────────────────────────────────────────

    async def start(self) -> None:
        """Démarre le polling asynchrone."""
        if self._running:
            logger.warning("Moniteur déjà en cours d'exécution")
            return

        if httpx is None:
            logger.error("httpx non disponible — impossible de démarrer le moniteur")
            return

        self._running = True
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(10.0))
        self._task = asyncio.create_task(self._poll_loop())
        logger.info("ClusterMonitorAdvanced démarré — polling toutes les %ds", POLL_INTERVAL_S)

    async def stop(self) -> None:
        """Arrête le polling."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self._client:
            await self._client.aclose()
            self._client = None
        logger.info("ClusterMonitorAdvanced arrêté")

    # ── Boucle de polling principale ─────────────────────────────────────────

    async def _poll_loop(self) -> None:
        """Boucle principale — poll tous les noeuds toutes les 30s."""
        while self._running:
            try:
                await self._poll_all_nodes()
                self._evaluate_alerts()
                self._maybe_write_hourly_summary()
            except Exception:
                logger.exception("Erreur dans la boucle de polling")

            await asyncio.sleep(POLL_INTERVAL_S)

    async def _poll_all_nodes(self) -> None:
        """Interroge tous les noeuds en parallèle."""
        tasks = [self._poll_node(nc) for nc in self._nodes.values()]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for nc, result in zip(self._nodes.values(), results):
            if isinstance(result, Exception):
                measurement = NodeMeasurement(
                    timestamp=time.time(),
                    node_name=nc.name,
                    online=False,
                    latency_s=0.0,
                    error=str(result),
                )
            else:
                measurement = result

            self._history[nc.name].append(measurement)
            self._latest[nc.name] = measurement

    async def _poll_node(self, nc: NodeConfig) -> NodeMeasurement:
        """Interroge un noeud spécifique — mesure latence, modèles, VRAM."""
        if not self._client:
            return NodeMeasurement(
                timestamp=time.time(), node_name=nc.name,
                online=False, latency_s=0.0, error="client HTTP non initialisé",
            )

        base_url = f"http://{nc.host}:{nc.port}"
        start = time.monotonic()

        try:
            if nc.node_type == "lmstudio":
                resp = await self._client.get(f"{base_url}/v1/models")
            else:
                resp = await self._client.get(f"{base_url}/api/tags")

            latency = time.monotonic() - start
            resp.raise_for_status()
            data = resp.json()

            # Extraire les modèles
            models: list[str] = []
            if nc.node_type == "lmstudio":
                for m in data.get("data", []):
                    mid = m.get("id", "")
                    if mid:
                        models.append(mid)
            else:
                for m in data.get("models", []):
                    mname = m.get("name", "")
                    if mname:
                        models.append(mname)

            # VRAM (si disponible — LM Studio expose parfois /v1/system)
            vram_used = 0.0
            vram_total = 0.0
            vram_pct = 0.0
            if nc.has_vram:
                vram_used, vram_total, vram_pct = await self._get_vram(base_url, nc.node_type)

            return NodeMeasurement(
                timestamp=time.time(),
                node_name=nc.name,
                online=True,
                latency_s=latency,
                models=models,
                vram_used_mb=vram_used,
                vram_total_mb=vram_total,
                vram_pct=vram_pct,
            )

        except Exception as e:
            latency = time.monotonic() - start
            return NodeMeasurement(
                timestamp=time.time(),
                node_name=nc.name,
                online=False,
                latency_s=latency,
                error=str(e),
            )

    async def _get_vram(self, base_url: str, node_type: str) -> tuple[float, float, float]:
        """Tente de récupérer les infos VRAM via l'API du noeud."""
        if not self._client:
            return 0.0, 0.0, 0.0

        try:
            if node_type == "lmstudio":
                # LM Studio : /v1/system ou /lmstudio/diagnostics
                resp = await self._client.get(f"{base_url}/lmstudio/diagnostics", timeout=5.0)
                if resp.status_code == 200:
                    data = resp.json()
                    gpu_info = data.get("gpuInfo", {})
                    if isinstance(gpu_info, list) and gpu_info:
                        total = sum(g.get("vram_total", 0) for g in gpu_info)
                        used = sum(g.get("vram_used", 0) for g in gpu_info)
                    elif isinstance(gpu_info, dict):
                        total = gpu_info.get("vram_total", 0)
                        used = gpu_info.get("vram_used", 0)
                    else:
                        return 0.0, 0.0, 0.0
                    # Convertir en MB si nécessaire
                    total_mb = total / (1024 * 1024) if total > 1_000_000 else total
                    used_mb = used / (1024 * 1024) if used > 1_000_000 else used
                    pct = (used_mb / total_mb * 100) if total_mb > 0 else 0.0
                    return used_mb, total_mb, pct
        except Exception:
            pass

        return 0.0, 0.0, 0.0

    # ── Alertes ──────────────────────────────────────────────────────────────

    def _evaluate_alerts(self) -> None:
        """Évalue les conditions d'alerte pour tous les noeuds."""
        now = time.time()

        for name, nc in self._nodes.items():
            m = self._latest.get(name)
            if m is None:
                continue

            # Noeud offline
            if not m.online:
                if name not in self._offline_since:
                    self._offline_since[name] = now
                offline_duration = now - self._offline_since[name]

                if offline_duration >= OFFLINE_ALERT_THRESHOLD_S:
                    self._fire_alert(
                        name, "critical", "node_offline",
                        f"{name} offline depuis {offline_duration:.0f}s (>{OFFLINE_ALERT_THRESHOLD_S}s)",
                    )
            else:
                # Résoudre l'alerte offline si le noeud revient
                if name in self._offline_since:
                    del self._offline_since[name]
                    self._resolve_alerts(name, "node_offline")

                # Latence
                if m.latency_s > LATENCY_CRITICAL_S:
                    self._fire_alert(
                        name, "critical", "latency_critical",
                        f"{name} latence critique: {m.latency_s:.2f}s (>{LATENCY_CRITICAL_S}s)",
                    )
                elif m.latency_s > LATENCY_WARNING_S:
                    self._fire_alert(
                        name, "warning", "latency_warning",
                        f"{name} latence élevée: {m.latency_s:.2f}s (>{LATENCY_WARNING_S}s)",
                    )
                else:
                    self._resolve_alerts(name, "latency_critical")
                    self._resolve_alerts(name, "latency_warning")

                # VRAM
                if m.vram_pct > VRAM_WARNING_PCT:
                    self._fire_alert(
                        name, "warning", "vram_high",
                        f"{name} VRAM élevée: {m.vram_pct:.1f}% (>{VRAM_WARNING_PCT}%)",
                    )
                else:
                    self._resolve_alerts(name, "vram_high")

                # Modèle non chargé sur M1
                if name == "M1" and nc.expected_models:
                    loaded = set(m.models)
                    for expected in nc.expected_models:
                        # Vérifier si le modèle attendu est dans les modèles chargés (match partiel)
                        found = any(expected.lower() in ml.lower() for ml in loaded)
                        if not found:
                            self._fire_alert(
                                name, "critical", "model_missing",
                                f"Modèle attendu '{expected}' non chargé sur {name}",
                            )
                        else:
                            self._resolve_alerts(name, "model_missing")

    def _fire_alert(self, node: str, level: str, alert_type: str, message: str) -> None:
        """Déclenche ou met à jour une alerte."""
        # Vérifier si alerte déjà active
        existing = self._find_active_alert(node, alert_type)
        if existing:
            existing.timestamp = time.time()
            existing.message = message
            return

        alert = ClusterAlert(
            timestamp=time.time(),
            node_name=node,
            level=level,
            alert_type=alert_type,
            message=message,
        )
        self._active_alerts.append(alert)
        logger.warning("ALERTE [%s] %s: %s", level.upper(), node, message)

    def _resolve_alerts(self, node: str, alert_type: str) -> None:
        """Résout les alertes correspondantes."""
        now = time.time()
        remaining: list[ClusterAlert] = []
        for a in self._active_alerts:
            if a.node_name == node and a.alert_type == alert_type and not a.resolved:
                a.resolved = True
                a.resolved_at = now
                self._alert_history.append(a)
                if len(self._alert_history) > self._max_alert_history:
                    self._alert_history = self._alert_history[-self._max_alert_history:]
                logger.info("Alerte résolue: [%s] %s — %s", a.level, node, a.alert_type)
            else:
                remaining.append(a)
        self._active_alerts = remaining

    def _find_active_alert(self, node: str, alert_type: str) -> ClusterAlert | None:
        """Cherche une alerte active pour un noeud et type donné."""
        for a in self._active_alerts:
            if a.node_name == node and a.alert_type == alert_type and not a.resolved:
                return a
        return None

    # ── Résumé horaire ───────────────────────────────────────────────────────

    def _maybe_write_hourly_summary(self) -> None:
        """Écrit un résumé horaire dans le fichier JSONL si une heure s'est écoulée."""
        now = time.time()
        if now - self._last_hourly_summary < 3600:
            return

        self._last_hourly_summary = now
        summary = self._build_hourly_summary()

        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            with open(HISTORY_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(summary, ensure_ascii=False) + "\n")
            logger.info("Résumé horaire écrit dans %s", HISTORY_FILE)
        except Exception:
            logger.exception("Erreur écriture résumé horaire")

    def _build_hourly_summary(self) -> dict[str, Any]:
        """Construit le résumé horaire de tous les noeuds."""
        now = time.time()
        one_hour_ago = now - 3600
        summary: dict[str, Any] = {
            "ts": now,
            "type": "hourly_summary",
            "nodes": {},
        }

        for name, buf in self._history.items():
            recent = [m for m in buf if m.timestamp >= one_hour_ago]
            if not recent:
                summary["nodes"][name] = {"samples": 0, "online": False}
                continue

            online_count = sum(1 for m in recent if m.online)
            online_measurements = [m for m in recent if m.online]
            latencies = [m.latency_s for m in online_measurements]
            vram_pcts = [m.vram_pct for m in online_measurements if m.vram_pct > 0]

            node_summary: dict[str, Any] = {
                "samples": len(recent),
                "online_pct": round(online_count / len(recent) * 100, 1) if recent else 0,
                "avg_latency_s": round(sum(latencies) / len(latencies), 3) if latencies else 0,
                "max_latency_s": round(max(latencies), 3) if latencies else 0,
                "min_latency_s": round(min(latencies), 3) if latencies else 0,
            }

            if vram_pcts:
                node_summary["avg_vram_pct"] = round(sum(vram_pcts) / len(vram_pcts), 1)
                node_summary["max_vram_pct"] = round(max(vram_pcts), 1)

            if online_measurements:
                node_summary["models"] = online_measurements[-1].models

            summary["nodes"][name] = node_summary

        return summary

    # ── API publique — Statut ────────────────────────────────────────────────

    def get_node_status(self, node: str) -> dict[str, Any]:
        """Retourne le statut détaillé d'un noeud."""
        if node not in self._nodes:
            return {"error": f"Noeud inconnu: {node}"}

        m = self._latest.get(node)
        if m is None:
            return {
                "node": node,
                "status": "unknown",
                "message": "Aucune mesure disponible",
            }

        result = m.to_dict()
        result["status"] = "online" if m.online else "offline"

        # Alertes actives pour ce noeud
        result["alerts"] = [
            a.to_dict() for a in self._active_alerts
            if a.node_name == node and not a.resolved
        ]

        # Stats du ring buffer
        buf = self._history[node]
        if buf:
            online_count = sum(1 for x in buf if x.online)
            result["history_samples"] = len(buf)
            result["history_online_pct"] = round(online_count / len(buf) * 100, 1)

        return result

    def get_all_status(self) -> dict[str, Any]:
        """Retourne le statut de tous les noeuds."""
        result: dict[str, Any] = {
            "ts": time.time(),
            "nodes": {},
            "active_alerts": len(self._active_alerts),
        }
        for name in self._nodes:
            result["nodes"][name] = self.get_node_status(name)
        return result

    # ── API publique — Uptime ────────────────────────────────────────────────

    def get_uptime_report(self, hours: int = 24) -> dict[str, Any]:
        """Calcule le % de disponibilité par noeud sur les N dernières heures."""
        now = time.time()
        cutoff = now - (hours * 3600)
        report: dict[str, Any] = {
            "ts": now,
            "period_hours": hours,
            "nodes": {},
        }

        for name, buf in self._history.items():
            recent = [m for m in buf if m.timestamp >= cutoff]
            if not recent:
                report["nodes"][name] = {
                    "uptime_pct": 0.0,
                    "samples": 0,
                    "status": "no_data",
                }
                continue

            online_count = sum(1 for m in recent if m.online)
            uptime_pct = round(online_count / len(recent) * 100, 1)

            online_measurements = [m for m in recent if m.online]
            latencies = [m.latency_s for m in online_measurements]

            report["nodes"][name] = {
                "uptime_pct": uptime_pct,
                "samples": len(recent),
                "online_samples": online_count,
                "avg_latency_s": round(sum(latencies) / len(latencies), 3) if latencies else 0,
                "status": "healthy" if uptime_pct >= 99 else (
                    "degraded" if uptime_pct >= 90 else "unhealthy"
                ),
            }

        return report

    # ── API publique — Routing intelligent ───────────────────────────────────

    def get_best_node(self, task_type: str) -> str:
        """Choisit le meilleur noeud pour un type de tâche donné.

        Basé sur : disponibilité, latence, VRAM libre, modèle adapté.
        task_types supportés: "code", "reasoning", "fast", "translation"
        """
        candidates: list[tuple[str, float]] = []

        for name, nc in self._nodes.items():
            # Le noeud doit supporter ce type de tâche
            if task_type not in nc.task_types:
                continue

            m = self._latest.get(name)
            if m is None or not m.online:
                continue

            # Score composite (plus haut = meilleur)
            score = 100.0

            # Pénalité latence (0-40 points)
            if m.latency_s < 0.5:
                score += 20
            elif m.latency_s < 1.0:
                score += 10
            elif m.latency_s > 2.0:
                score -= 20
            elif m.latency_s > 5.0:
                score -= 40

            # Bonus VRAM libre (0-20 points)
            if m.vram_pct > 0:
                free_pct = 100 - m.vram_pct
                score += free_pct * 0.2

            # Priorité du noeud (1=meilleur)
            score -= (nc.priority - 1) * 5

            # Bonus si pas d'alertes actives
            node_alerts = [a for a in self._active_alerts if a.node_name == name]
            score -= len(node_alerts) * 10

            candidates.append((name, score))

        if not candidates:
            # Fallback : retourner le premier noeud disponible
            for name in self._nodes:
                m = self._latest.get(name)
                if m and m.online:
                    return name
            return "M1"  # Dernier recours

        # Trier par score décroissant
        candidates.sort(key=lambda x: x[1], reverse=True)
        best_name = candidates[0][0]
        logger.debug(
            "Routing %s → %s (score %.1f, candidats: %s)",
            task_type, best_name, candidates[0][1],
            [(n, f"{s:.1f}") for n, s in candidates],
        )
        return best_name

    # ── API publique — Dashboard ─────────────────────────────────────────────

    def get_cluster_dashboard(self) -> dict[str, Any]:
        """Données complètes pour le portail/dashboard.

        Inclut : état par noeud, uptime, latence, modèles, alertes actives.
        """
        now = time.time()

        # Statut par noeud
        nodes_status: dict[str, Any] = {}
        total_online = 0
        total_nodes = len(self._nodes)

        for name, nc in self._nodes.items():
            m = self._latest.get(name)
            node_info: dict[str, Any] = {
                "name": name,
                "host": f"{nc.host}:{nc.port}",
                "type": nc.node_type,
                "status": "unknown",
                "latency_s": 0,
                "models": [],
                "vram_pct": 0,
                "alerts": [],
            }

            if m:
                node_info["status"] = "online" if m.online else "offline"
                node_info["latency_s"] = round(m.latency_s, 3)
                node_info["models"] = m.models
                node_info["vram_pct"] = round(m.vram_pct, 1)
                node_info["last_seen"] = m.timestamp
                if m.online:
                    total_online += 1

            # Alertes pour ce noeud
            node_info["alerts"] = [
                a.to_dict() for a in self._active_alerts
                if a.node_name == name and not a.resolved
            ]

            nodes_status[name] = node_info

        # Uptime sur 24h
        uptime = self.get_uptime_report(hours=24)

        # Résumé des alertes
        critical_alerts = [a for a in self._active_alerts if a.level == "critical"]
        warning_alerts = [a for a in self._active_alerts if a.level == "warning"]

        # Santé globale
        if critical_alerts:
            cluster_health = "critical"
        elif warning_alerts:
            cluster_health = "degraded"
        elif total_online == total_nodes:
            cluster_health = "healthy"
        elif total_online > 0:
            cluster_health = "partial"
        else:
            cluster_health = "down"

        return {
            "ts": now,
            "cluster_health": cluster_health,
            "nodes_online": total_online,
            "nodes_total": total_nodes,
            "nodes": nodes_status,
            "uptime_24h": uptime.get("nodes", {}),
            "alerts": {
                "active_count": len(self._active_alerts),
                "critical": [a.to_dict() for a in critical_alerts],
                "warnings": [a.to_dict() for a in warning_alerts],
            },
            "routing": {
                "best_code": self.get_best_node("code"),
                "best_reasoning": self.get_best_node("reasoning"),
                "best_fast": self.get_best_node("fast"),
                "best_translation": self.get_best_node("translation"),
            },
        }


# ── Singleton ────────────────────────────────────────────────────────────────

_instance: ClusterMonitorAdvanced | None = None


def get_cluster_monitor() -> ClusterMonitorAdvanced:
    """Retourne l'instance singleton du moniteur cluster."""
    global _instance
    if _instance is None:
        _instance = ClusterMonitorAdvanced()
    return _instance


# ── Point d'entrée autonome (pour le service systemd) ───────────────────────

async def _main() -> None:
    """Point d'entrée pour exécution en service."""
    import signal

    monitor = get_cluster_monitor()
    await monitor.start()

    # Attendre signal d'arrêt
    stop_event = asyncio.Event()

    def _handle_signal() -> None:
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _handle_signal)

    logger.info("Service cluster monitor démarré — Ctrl+C pour arrêter")
    await stop_event.wait()

    await monitor.stop()
    logger.info("Service cluster monitor arrêté proprement")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    asyncio.run(_main())
