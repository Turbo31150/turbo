"""Auto-Healer Linux — Détection et réparation automatique des problèmes système.

Surveille en continu les services JARVIS, les ports critiques, le cluster,
les bases de données, l'espace disque et les GPUs. Répare automatiquement
les problèmes détectés et alerte si la réparation échoue.

Usage:
    from src.auto_healer_linux import auto_healer
    auto_healer.start()
    report = auto_healer.get_health_report()
    auto_healer.stop()
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import sqlite3
import subprocess
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

__all__ = [
    "AutoHealerLinux",
    "HealingEvent",
    "auto_healer",
]

logger = logging.getLogger("jarvis.auto_healer")

# --- Constantes ---

DATA_DIR = Path("/home/turbo/jarvis/data")
HEALING_LOG = DATA_DIR / "healing_history.jsonl"
BACKUP_DIR = DATA_DIR / "backups"
SNAPSHOT_DIR = DATA_DIR / "snapshots"

# Polling et limites
POLL_INTERVAL_S: float = 30.0
RESTART_COOLDOWN_S: float = 300.0  # 5 min entre tentatives sur le même service
MAX_RESTART_ATTEMPTS: int = 3

# Services JARVIS surveillés
JARVIS_SERVICES: list[str] = [
    "jarvis-mcp.service",
    "jarvis-auditor.service",
    "jarvis-health-watcher.service",
    "jarvis-lms-guard.service",
    "jarvis-perf-monitor.service",
    "jarvis-proxy.service",
    "jarvis-watchdog.service",
    "jarvis-ws.service",
]

# Ports critiques à surveiller
CRITICAL_PORTS: dict[str, tuple[str, int, str]] = {
    # clé → (hôte, port, service à redémarrer)
    "dashboard_web": ("127.0.0.1", 8088, "jarvis-dashboard-web.service"),
    "mcp_server": ("127.0.0.1", 8080, "jarvis-mcp.service"),
}

# Cluster nodes
CLUSTER_NODES: dict[str, tuple[str, int]] = {
    "M1_LMStudio": ("127.0.0.1", 1234),
    "M2_LMStudio": ("192.168.1.26", 1234),
    "OL1_Ollama": ("127.0.0.1", 11434),
}

# Bases de données à surveiller
DB_FILES: list[Path] = [p for p in DATA_DIR.glob("*.db") if p.is_file()]

# Seuils GPU
GPU_TEMP_WARN: int = 85
GPU_TEMP_CRITICAL: int = 90

# Seuils disque
DISK_WARN_PCT: int = 90
DISK_CRITICAL_PCT: int = 95

# Intervalle integrity check DB (1 heure)
DB_CHECK_INTERVAL_S: float = 3600.0

# Intervalle VACUUM hebdomadaire (7 jours)
VACUUM_INTERVAL_S: float = 7 * 24 * 3600.0


@dataclass
class HealingEvent:
    """Enregistrement d'une action de réparation."""

    ts: float = field(default_factory=time.time)
    category: str = ""          # service, port, cluster, db, disk, gpu
    target: str = ""            # nom du service/port/node/db
    problem: str = ""           # description du problème
    action: str = ""            # action entreprise
    success: bool = False
    details: str = ""
    attempt: int = 1


class AutoHealerLinux:
    """Système d'auto-healing pour JARVIS sur Linux."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._running = False
        self._thread: threading.Thread | None = None
        self._force_check = threading.Event()

        # Compteurs de tentatives de restart par service (clé → (count, last_ts))
        self._restart_tracker: dict[str, tuple[int, float]] = {}

        # Timestamps pour les checks périodiques
        self._last_db_check: float = 0.0
        self._last_vacuum: float = 0.0

        # Historique des réparations (en mémoire)
        self._history: list[HealingEvent] = []
        self._max_history: int = 500

        # Suivi des downtimes cluster (node → ts_début_downtime)
        self._node_downtime: dict[str, float] = {}

        # Santé globale
        self._health: dict[str, Any] = {
            "status": "unknown",
            "last_check": 0.0,
            "services": {},
            "ports": {},
            "cluster": {},
            "db": {},
            "disk": {},
            "gpu": {},
        }

        # Initialise les répertoires
        DATA_DIR.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Méthodes publiques
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Lance le thread de surveillance (polling 30s)."""
        with self._lock:
            if self._running:
                logger.warning("Auto-healer déjà en cours d'exécution")
                return
            self._running = True
            self._thread = threading.Thread(
                target=self._main_loop,
                name="auto-healer",
                daemon=True,
            )
            self._thread.start()
            logger.info("Auto-healer démarré (polling=%ss)", POLL_INTERVAL_S)

    def stop(self) -> None:
        """Arrête le thread de surveillance."""
        with self._lock:
            if not self._running:
                return
            self._running = False
            self._force_check.set()  # Débloquer le wait
        if self._thread:
            self._thread.join(timeout=10)
            self._thread = None
        logger.info("Auto-healer arrêté")

    def get_health_report(self) -> dict[str, Any]:
        """Retourne le rapport de santé courant."""
        with self._lock:
            return dict(self._health)

    def get_healing_history(self) -> list[dict[str, Any]]:
        """Retourne l'historique des réparations."""
        with self._lock:
            return [asdict(e) for e in self._history]

    def force_check(self) -> None:
        """Force un check immédiat."""
        self._force_check.set()
        logger.info("Check immédiat demandé")

    # ------------------------------------------------------------------
    # Boucle principale
    # ------------------------------------------------------------------

    def _main_loop(self) -> None:
        """Boucle de surveillance principale."""
        logger.info("Boucle de surveillance démarrée")
        while self._running:
            try:
                self._run_all_checks()
            except Exception:
                logger.exception("Erreur dans la boucle de surveillance")

            # Attendre le prochain cycle ou un force_check
            self._force_check.wait(timeout=POLL_INTERVAL_S)
            self._force_check.clear()

    def _run_all_checks(self) -> None:
        """Exécute tous les checks de santé."""
        now = time.time()

        # Checks à chaque cycle (30s)
        self._check_services()
        self._check_ports()
        self._check_cluster_nodes()
        self._check_gpu()
        self._check_disk()

        # Check DB toutes les heures
        if now - self._last_db_check >= DB_CHECK_INTERVAL_S:
            self._check_databases()
            self._last_db_check = now

        # VACUUM hebdomadaire
        if now - self._last_vacuum >= VACUUM_INTERVAL_S:
            self._vacuum_databases()
            self._last_vacuum = now

        # Mise à jour du statut global
        self._update_global_status(now)

    # ------------------------------------------------------------------
    # 1. Services JARVIS
    # ------------------------------------------------------------------

    def _check_services(self) -> None:
        """Détecte les services JARVIS en échec et tente un restart."""
        failed = self._get_failed_services()
        status: dict[str, str] = {}

        for svc in JARVIS_SERVICES:
            if svc in failed:
                status[svc] = "failed"
                self._try_restart_service(svc, reason="service failed détecté par systemctl")
            else:
                status[svc] = "ok"
                # Réinitialiser le tracker si le service est revenu
                self._restart_tracker.pop(svc, None)

        with self._lock:
            self._health["services"] = status

    def _get_failed_services(self) -> set[str]:
        """Récupère la liste des services JARVIS en échec."""
        try:
            result = subprocess.run(
                ["systemctl", "list-units", "--type=service", "--state=failed",
                 "--no-legend", "--no-pager"],
                capture_output=True, text=True, timeout=10,
            )
            failed: set[str] = set()
            for line in result.stdout.strip().splitlines():
                parts = line.split()
                if parts:
                    unit = parts[0]
                    if unit in JARVIS_SERVICES:
                        failed.add(unit)
            return failed
        except Exception:
            logger.exception("Impossible de lister les services failed")
            return set()

    def _try_restart_service(self, service: str, reason: str) -> None:
        """Tente de redémarrer un service avec cooldown et limite de tentatives."""
        now = time.time()
        count, last_ts = self._restart_tracker.get(service, (0, 0.0))

        # Cooldown de 5 min entre tentatives
        if now - last_ts < RESTART_COOLDOWN_S and count > 0:
            return

        # Maximum 3 tentatives
        if count >= MAX_RESTART_ATTEMPTS:
            # Alerte critique après 3 échecs
            self._send_alert(
                f"Auto-Heal ÉCHEC: {service}",
                f"{service} n'a pas pu être réparé après {MAX_RESTART_ATTEMPTS} tentatives. "
                f"Raison initiale: {reason}",
                level="critical",
            )
            return

        # Tentative de restart
        new_count = count + 1
        logger.info("Restart tentative %d/%d pour %s", new_count, MAX_RESTART_ATTEMPTS, service)

        success = self._systemctl_restart(service)
        event = HealingEvent(
            category="service",
            target=service,
            problem=reason,
            action=f"systemctl restart {service}",
            success=success,
            attempt=new_count,
            details="restart réussi" if success else "restart échoué",
        )
        self._record_event(event)
        self._restart_tracker[service] = (new_count, now)

        if not success and new_count >= MAX_RESTART_ATTEMPTS:
            self._send_alert(
                f"Auto-Heal ÉCHEC: {service}",
                f"{service} n'a pas pu être redémarré après {MAX_RESTART_ATTEMPTS} tentatives.",
                level="critical",
            )

    def _systemctl_restart(self, service: str) -> bool:
        """Exécute systemctl restart et retourne True si succès."""
        try:
            result = subprocess.run(
                ["sudo", "systemctl", "restart", service],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0:
                logger.info("Service %s redémarré avec succès", service)
                return True
            logger.warning("Échec restart %s: %s", service, result.stderr.strip())
            return False
        except Exception:
            logger.exception("Exception lors du restart de %s", service)
            return False

    # ------------------------------------------------------------------
    # 2 & 3. Dashboard web et MCP server (ports)
    # ------------------------------------------------------------------

    def _check_ports(self) -> None:
        """Vérifie que les ports critiques répondent."""
        status: dict[str, str] = {}

        for key, (host, port, service) in CRITICAL_PORTS.items():
            alive = self._check_port(host, port)
            if alive:
                status[key] = "ok"
                self._restart_tracker.pop(f"port_{key}", None)
            else:
                status[key] = "down"
                logger.warning("Port %s:%d (%s) ne répond pas", host, port, key)
                self._try_restart_service(
                    service,
                    reason=f"port {host}:{port} ({key}) ne répond pas",
                )

        with self._lock:
            self._health["ports"] = status

    def _check_port(self, host: str, port: int) -> bool:
        """Vérifie si un port répond via curl."""
        try:
            result = subprocess.run(
                ["curl", "-sf", "--connect-timeout", "5",
                 f"http://{host}:{port}/"],
                capture_output=True, text=True, timeout=10,
            )
            return result.returncode == 0
        except Exception:
            return False

    # ------------------------------------------------------------------
    # 4. Cluster nodes
    # ------------------------------------------------------------------

    def _check_cluster_nodes(self) -> None:
        """Vérifie la connectivité des nœuds du cluster."""
        status: dict[str, dict[str, Any]] = {}
        now = time.time()

        for name, (host, port) in CLUSTER_NODES.items():
            alive = self._check_port(host, port)

            if alive:
                # Calculer le temps de downtime si le node revient
                if name in self._node_downtime:
                    downtime_s = now - self._node_downtime.pop(name)
                    logger.info("Node %s revenu après %.0fs de downtime", name, downtime_s)
                    status[name] = {"status": "ok", "recovered_after_s": round(downtime_s, 1)}
                else:
                    status[name] = {"status": "ok"}
            else:
                # Enregistrer le début du downtime
                if name not in self._node_downtime:
                    self._node_downtime[name] = now
                downtime_s = now - self._node_downtime[name]
                status[name] = {"status": "down", "downtime_s": round(downtime_s, 1)}

                # Tentatives de réparation spécifiques
                self._heal_cluster_node(name, host, port, downtime_s)

        with self._lock:
            self._health["cluster"] = status

    def _heal_cluster_node(self, name: str, host: str, port: int, downtime_s: float) -> None:
        """Tente de réparer un nœud de cluster en panne."""
        tracker_key = f"cluster_{name}"
        count, last_ts = self._restart_tracker.get(tracker_key, (0, 0.0))
        now = time.time()

        if now - last_ts < RESTART_COOLDOWN_S and count > 0:
            return

        if count >= MAX_RESTART_ATTEMPTS:
            return

        new_count = count + 1
        success = False
        action = ""

        if name == "M1_LMStudio":
            # Tenter de restart LM Studio
            action = "restart LM Studio via lms server start"
            success = self._run_command(["lms", "server", "start"])
        elif name == "OL1_Ollama":
            # Tenter de restart ollama serve
            action = "restart ollama serve"
            success = self._run_command(["systemctl", "--user", "restart", "ollama.service"])
            if not success:
                # Fallback : lancement direct
                success = self._run_command_bg(["ollama", "serve"])
                action = "ollama serve (lancement direct)"
        elif name == "M2_LMStudio":
            # M2 est un nœud distant, on ne peut pas le restart localement
            action = "alerte — M2 distant inaccessible"
            if new_count >= MAX_RESTART_ATTEMPTS:
                self._send_alert(
                    "Cluster: M2 inaccessible",
                    f"M2 ({host}:{port}) est down depuis {downtime_s:.0f}s",
                    level="warning",
                )

        event = HealingEvent(
            category="cluster",
            target=name,
            problem=f"node {host}:{port} down (downtime: {downtime_s:.0f}s)",
            action=action,
            success=success,
            attempt=new_count,
        )
        self._record_event(event)
        self._restart_tracker[tracker_key] = (new_count, now)

    # ------------------------------------------------------------------
    # 5. Bases de données
    # ------------------------------------------------------------------

    def _check_databases(self) -> None:
        """Vérifie l'intégrité de toutes les bases de données SQLite."""
        # Rafraîchir la liste des DB
        db_files = list(DATA_DIR.glob("*.db"))
        status: dict[str, str] = {}

        for db_path in db_files:
            if not db_path.is_file():
                continue
            integrity = self._check_db_integrity(db_path)
            if integrity:
                status[db_path.name] = "ok"
            else:
                status[db_path.name] = "corrupt"
                logger.error("Base de données corrompue: %s", db_path)
                self._restore_database(db_path)

        with self._lock:
            self._health["db"] = status

    def _check_db_integrity(self, db_path: Path) -> bool:
        """Exécute PRAGMA integrity_check sur une base SQLite."""
        try:
            conn = sqlite3.connect(str(db_path), timeout=10)
            cursor = conn.execute("PRAGMA integrity_check")
            result = cursor.fetchone()
            conn.close()
            return result is not None and result[0] == "ok"
        except Exception:
            logger.exception("Erreur integrity_check sur %s", db_path)
            return False

    def _restore_database(self, db_path: Path) -> None:
        """Restaure une base de données depuis le dernier snapshot ou backup."""
        snapshot_candidates = sorted(
            SNAPSHOT_DIR.glob(f"database_*.db"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        ) if SNAPSHOT_DIR.exists() else []

        restored = False

        # Tenter restauration depuis snapshots
        for snap in snapshot_candidates:
            if self._check_db_integrity(snap):
                try:
                    # Sauvegarder le fichier corrompu
                    corrupt_backup = db_path.with_suffix(".db.corrupt")
                    shutil.copy2(str(db_path), str(corrupt_backup))
                    # Restaurer depuis le snapshot
                    shutil.copy2(str(snap), str(db_path))
                    logger.info("Base %s restaurée depuis %s", db_path.name, snap.name)
                    restored = True
                    break
                except Exception:
                    logger.exception("Échec restauration depuis %s", snap)

        event = HealingEvent(
            category="db",
            target=db_path.name,
            problem="corruption détectée (PRAGMA integrity_check)",
            action="restauration depuis snapshot" if restored else "aucun snapshot valide trouvé",
            success=restored,
        )
        self._record_event(event)

        if not restored:
            self._send_alert(
                f"DB corrompue: {db_path.name}",
                f"La base {db_path.name} est corrompue et aucun backup valide n'a été trouvé.",
                level="critical",
            )

    def _vacuum_databases(self) -> None:
        """Exécute VACUUM sur toutes les bases de données (hebdomadaire)."""
        db_files = list(DATA_DIR.glob("*.db"))
        for db_path in db_files:
            if not db_path.is_file():
                continue
            try:
                conn = sqlite3.connect(str(db_path), timeout=30)
                conn.execute("VACUUM")
                conn.close()
                logger.info("VACUUM effectué sur %s", db_path.name)
            except Exception:
                logger.warning("Échec VACUUM sur %s", db_path.name, exc_info=True)

        event = HealingEvent(
            category="db",
            target="all",
            problem="maintenance hebdomadaire",
            action="VACUUM sur toutes les bases",
            success=True,
        )
        self._record_event(event)

    # ------------------------------------------------------------------
    # 6. Espace disque
    # ------------------------------------------------------------------

    def _check_disk(self) -> None:
        """Vérifie l'espace disque et nettoie si nécessaire."""
        usage = shutil.disk_usage("/")
        used_pct = int((usage.used / usage.total) * 100)
        free_gb = round(usage.free / (1024 ** 3), 1)

        disk_status: dict[str, Any] = {
            "used_pct": used_pct,
            "free_gb": free_gb,
        }

        if used_pct >= DISK_CRITICAL_PCT:
            disk_status["level"] = "critical"
            logger.critical("Espace disque critique: %d%% utilisé (%.1f GB libre)", used_pct, free_gb)
            self._aggressive_cleanup()
            self._send_alert(
                "Espace disque CRITIQUE",
                f"Disque utilisé à {used_pct}% — seulement {free_gb} GB libre. "
                "Nettoyage agressif effectué.",
                level="critical",
            )
        elif used_pct >= DISK_WARN_PCT:
            disk_status["level"] = "warning"
            logger.warning("Espace disque élevé: %d%% utilisé (%.1f GB libre)", used_pct, free_gb)
            self._standard_cleanup()
        else:
            disk_status["level"] = "ok"

        with self._lock:
            self._health["disk"] = disk_status

    def _standard_cleanup(self) -> None:
        """Nettoyage standard : apt clean, journal vacuum, tmp."""
        actions = [
            (["sudo", "apt-get", "clean"], "apt clean"),
            (["sudo", "journalctl", "--vacuum-time=3d"], "journal vacuum 3j"),
        ]
        for cmd, desc in actions:
            success = self._run_command(cmd)
            self._record_event(HealingEvent(
                category="disk",
                target="/",
                problem=f"espace disque > {DISK_WARN_PCT}%",
                action=desc,
                success=success,
            ))

        # Nettoyage des fichiers tmp de plus de 7 jours
        self._cleanup_tmp(days=7)

    def _aggressive_cleanup(self) -> None:
        """Nettoyage agressif : tout le standard + nettoyage profond."""
        self._standard_cleanup()

        actions = [
            (["sudo", "apt-get", "autoremove", "-y"], "apt autoremove"),
            (["sudo", "journalctl", "--vacuum-size=100M"], "journal vacuum 100M"),
        ]
        for cmd, desc in actions:
            success = self._run_command(cmd)
            self._record_event(HealingEvent(
                category="disk",
                target="/",
                problem=f"espace disque > {DISK_CRITICAL_PCT}%",
                action=desc,
                success=success,
            ))

        # Nettoyage des fichiers tmp de plus de 1 jour
        self._cleanup_tmp(days=1)

    def _cleanup_tmp(self, days: int) -> None:
        """Supprime les fichiers temporaires de plus de N jours."""
        try:
            result = subprocess.run(
                ["find", "/tmp", "-type", "f", "-mtime", f"+{days}", "-delete"],
                capture_output=True, text=True, timeout=30,
            )
            logger.info("Nettoyage /tmp (+%dj) terminé (rc=%d)", days, result.returncode)
        except Exception:
            logger.warning("Échec nettoyage /tmp", exc_info=True)

    # ------------------------------------------------------------------
    # 7. GPU
    # ------------------------------------------------------------------

    def _check_gpu(self) -> None:
        """Surveille les températures GPU et agit si nécessaire."""
        temps = self._get_gpu_temps()
        gpu_status: dict[str, Any] = {"temps": temps}

        if not temps:
            gpu_status["status"] = "unknown"
            with self._lock:
                self._health["gpu"] = gpu_status
            return

        max_temp = max(temps.values())

        if max_temp >= GPU_TEMP_CRITICAL:
            gpu_status["status"] = "critical"
            logger.critical("Température GPU critique: %d°C", max_temp)
            self._gpu_emergency_action(temps)
            self._send_alert(
                "GPU TEMPÉRATURE CRITIQUE",
                f"GPU max: {max_temp}°C — arrêt des modèles non-essentiels.",
                level="critical",
            )
        elif max_temp >= GPU_TEMP_WARN:
            gpu_status["status"] = "warning"
            logger.warning("Température GPU élevée: %d°C", max_temp)
            self._gpu_reduce_load(temps)
        else:
            gpu_status["status"] = "ok"

        with self._lock:
            self._health["gpu"] = gpu_status

    def _get_gpu_temps(self) -> dict[str, int]:
        """Récupère les températures de tous les GPUs via nvidia-smi."""
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=index,temperature.gpu",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode != 0:
                return {}
            temps: dict[str, int] = {}
            for line in result.stdout.strip().splitlines():
                parts = line.split(",")
                if len(parts) == 2:
                    idx = parts[0].strip()
                    temp = int(parts[1].strip())
                    temps[f"gpu_{idx}"] = temp
            return temps
        except Exception:
            logger.warning("Impossible de lire les températures GPU", exc_info=True)
            return {}

    def _gpu_reduce_load(self, temps: dict[str, int]) -> None:
        """Réduit la charge GPU en déchargeant les modèles non-essentiels (> 85°C)."""
        hot_gpus = [k for k, v in temps.items() if v >= GPU_TEMP_WARN]
        if not hot_gpus:
            return

        # Tenter de décharger les modèles via ollama
        success = self._run_command(
            ["curl", "-sf", "--connect-timeout", "5", "-X", "DELETE",
             "http://127.0.0.1:11434/api/generate"],
        )
        event = HealingEvent(
            category="gpu",
            target=",".join(hot_gpus),
            problem=f"température > {GPU_TEMP_WARN}°C",
            action="réduction charge (déchargement modèles non-essentiels)",
            success=success,
        )
        self._record_event(event)

    def _gpu_emergency_action(self, temps: dict[str, int]) -> None:
        """Action d'urgence GPU : stop modèles non-essentiels (> 90°C)."""
        # Stop ollama models
        self._run_command(["ollama", "stop", "--all"])

        # Tenter d'arrêter LM Studio pour réduire la charge
        self._run_command(["lms", "server", "stop"])

        event = HealingEvent(
            category="gpu",
            target="all",
            problem=f"température critique > {GPU_TEMP_CRITICAL}°C",
            action="arrêt modèles non-essentiels (ollama stop, lms server stop)",
            success=True,
        )
        self._record_event(event)

    # ------------------------------------------------------------------
    # Utilitaires internes
    # ------------------------------------------------------------------

    def _run_command(self, cmd: list[str], timeout: int = 30) -> bool:
        """Exécute une commande et retourne True si succès."""
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout,
            )
            return result.returncode == 0
        except Exception:
            logger.warning("Échec commande: %s", " ".join(cmd), exc_info=True)
            return False

    def _run_command_bg(self, cmd: list[str]) -> bool:
        """Lance une commande en arrière-plan."""
        try:
            subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            return True
        except Exception:
            logger.warning("Échec lancement bg: %s", " ".join(cmd), exc_info=True)
            return False

    def _record_event(self, event: HealingEvent) -> None:
        """Enregistre un événement de réparation en mémoire et sur disque."""
        with self._lock:
            self._history.append(event)
            # Limiter la taille de l'historique en mémoire
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]

        # Écrire dans le fichier JSONL
        try:
            with open(HEALING_LOG, "a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(event), ensure_ascii=False) + "\n")
        except Exception:
            logger.warning("Impossible d'écrire dans %s", HEALING_LOG, exc_info=True)

    def _send_alert(self, title: str, message: str, level: str = "warning") -> None:
        """Envoie une alerte via smart_notifications."""
        try:
            from src.smart_notifications import notification_manager
            notification_manager.send_notification(
                title=title,
                message=message,
                level=level,
                speak=(level == "critical"),
                source="auto_healer",
            )
        except Exception:
            logger.warning(
                "Impossible d'envoyer l'alerte via smart_notifications: %s — %s",
                title, message,
            )

    def _update_global_status(self, now: float) -> None:
        """Met à jour le statut global de santé."""
        with self._lock:
            self._health["last_check"] = now

            # Déterminer le statut global
            problems: list[str] = []

            # Vérifier les services
            for svc, st in self._health.get("services", {}).items():
                if st != "ok":
                    problems.append(f"service:{svc}")

            # Vérifier les ports
            for key, st in self._health.get("ports", {}).items():
                if st != "ok":
                    problems.append(f"port:{key}")

            # Vérifier le cluster
            for node, info in self._health.get("cluster", {}).items():
                if isinstance(info, dict) and info.get("status") != "ok":
                    problems.append(f"cluster:{node}")

            # Vérifier le disque
            disk_level = self._health.get("disk", {}).get("level", "ok")
            if disk_level != "ok":
                problems.append(f"disk:{disk_level}")

            # Vérifier les GPU
            gpu_status = self._health.get("gpu", {}).get("status", "ok")
            if gpu_status not in ("ok", "unknown"):
                problems.append(f"gpu:{gpu_status}")

            if not problems:
                self._health["status"] = "healthy"
            elif any("critical" in p for p in problems):
                self._health["status"] = "critical"
            else:
                self._health["status"] = "degraded"

            self._health["problems"] = problems


# --- Singleton ---
auto_healer = AutoHealerLinux()


# --- Point d'entrée CLI ---
if __name__ == "__main__":
    import signal
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    healer = auto_healer
    healer.start()

    def _shutdown(signum: int, frame: Any) -> None:
        logger.info("Signal %d reçu, arrêt en cours...", signum)
        healer.stop()
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    logger.info("Auto-healer en cours d'exécution. Ctrl+C pour arrêter.")

    # Garder le processus en vie
    try:
        while True:
            time.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        healer.stop()
