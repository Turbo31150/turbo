"""Smart Notifications — Surveillance intelligente avec alertes desktop et TTS.

Surveille en continu les métriques système (GPU, RAM, disque), les services JARVIS,
le brain (skills auto-appris), le mega-improve, le cluster et le trading.
Envoie des notifications via notify-send et optionnellement Piper TTS.

Usage:
    from src.smart_notifications import notification_manager
    notification_manager.start_monitoring()
    notification_manager.send_notification("Test", "Hello JARVIS", level="info")
    notification_manager.stop_monitoring()
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import threading
import time
from collections import deque
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

__all__ = [
    "SmartNotificationManager",
    "NotificationRecord",
    "notification_manager",
]

logger = logging.getLogger("jarvis.smart_notif")

# --- Constantes ---

DATA_DIR = Path("/home/turbo/jarvis/data")
NOTIF_LOG = DATA_DIR / "notifications.jsonl"
ICON = "/home/turbo/Pictures/JARVIS/jarvis-icon-48.png"
PIPER_BIN = "/home/turbo/jarvis/.venv/bin/piper"
PIPER_MODEL = "/home/turbo/jarvis/data/piper/fr_FR-siwis-medium.onnx"

# Seuils de surveillance
GPU_TEMP_WARN = 75
RAM_WARN_PCT = 90
DISK_WARN_PCT = 90

# Polling et cooldown
POLL_INTERVAL_S = 30.0
COOLDOWN_S = 300.0  # 5 minutes entre alertes identiques

# Historique max
MAX_HISTORY = 100

# Mapping niveau → urgence notify-send
URGENCY_MAP: dict[str, str] = {
    "info": "low",
    "warning": "normal",
    "critical": "critical",
}


@dataclass
class NotificationRecord:
    """Enregistrement d'une notification envoyée."""

    title: str
    message: str
    level: str
    source: str
    ts: float = field(default_factory=time.time)
    spoken: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


class SmartNotificationManager:
    """Gestionnaire de notifications intelligentes avec surveillance continue."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._running = False
        self._thread: threading.Thread | None = None
        self._dnd = False  # Mode ne pas déranger

        # Cooldown par clé d'alerte (clé → timestamp dernier envoi)
        self._cooldowns: dict[str, float] = {}

        # Historique circulaire
        self._history: deque[NotificationRecord] = deque(maxlen=MAX_HISTORY)

        # État précédent pour détection de changements
        self._prev_brain_skills: set[str] = set()
        self._prev_mega_gaps: int = -1
        self._prev_cluster_nodes: set[str] = set()
        self._prev_failed_services: set[str] = set()

        # Initialise le répertoire data
        DATA_DIR.mkdir(parents=True, exist_ok=True)

        # Charge les skills brain existants au démarrage
        self._prev_brain_skills = self._load_brain_skills()

    # ------------------------------------------------------------------
    # Méthodes publiques
    # ------------------------------------------------------------------

    def start_monitoring(self) -> None:
        """Lance le thread de surveillance périodique."""
        with self._lock:
            if self._running:
                logger.warning("Monitoring déjà actif")
                return
            self._running = True
            self._thread = threading.Thread(
                target=self._monitor_loop,
                name="smart-notif-monitor",
                daemon=True,
            )
            self._thread.start()
            logger.info("Surveillance intelligente démarrée (intervalle=%ds)", POLL_INTERVAL_S)

    def stop_monitoring(self) -> None:
        """Arrête le thread de surveillance."""
        with self._lock:
            if not self._running:
                return
            self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=POLL_INTERVAL_S + 5)
            logger.info("Surveillance intelligente arrêtée")
        self._thread = None

    def send_notification(
        self,
        title: str,
        message: str,
        level: str = "info",
        speak: bool = False,
        source: str = "system",
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Envoie une notification desktop + optionnel TTS.

        Retourne True si envoyée, False si bloquée (DND/cooldown).
        """
        # Respecte le mode DND sauf pour les critiques
        if self._dnd and level != "critical":
            logger.debug("DND actif, notification ignorée: %s", title)
            return False

        # Cooldown : clé = source + titre
        cooldown_key = f"{source}:{title}"
        now = time.time()
        with self._lock:
            last = self._cooldowns.get(cooldown_key, 0.0)
            if now - last < COOLDOWN_S:
                logger.debug("Cooldown actif pour %s (reste %ds)", cooldown_key, COOLDOWN_S - (now - last))
                return False
            self._cooldowns[cooldown_key] = now

        # Crée l'enregistrement
        record = NotificationRecord(
            title=title,
            message=message,
            level=level,
            source=source,
            ts=now,
            spoken=speak,
            metadata=metadata or {},
        )

        # Envoi notify-send
        self._send_desktop(record)

        # TTS optionnel (pas en DND, pas pour info simple)
        if speak and not self._dnd:
            self._send_tts(f"{title}. {message}")
            record.spoken = True

        # Enregistre dans l'historique et le log
        with self._lock:
            self._history.append(record)
        self._append_log(record)

        logger.info("[%s] %s — %s", level.upper(), title, message)
        return True

    def get_history(self, limit: int = 20) -> list[dict[str, Any]]:
        """Retourne les dernières notifications (plus récentes d'abord)."""
        with self._lock:
            items = list(self._history)
        items.reverse()
        return [asdict(r) for r in items[:limit]]

    def set_dnd(self, enabled: bool) -> None:
        """Active ou désactive le mode Ne Pas Déranger."""
        self._dnd = enabled
        logger.info("Mode DND %s", "activé" if enabled else "désactivé")

    @property
    def is_monitoring(self) -> bool:
        return self._running

    @property
    def is_dnd(self) -> bool:
        return self._dnd

    # ------------------------------------------------------------------
    # Boucle de surveillance
    # ------------------------------------------------------------------

    def _monitor_loop(self) -> None:
        """Boucle principale de surveillance (tourne dans un thread dédié)."""
        logger.info("Thread de surveillance démarré")
        while self._running:
            try:
                self._check_gpu_temperature()
                self._check_ram_usage()
                self._check_disk_usage()
                self._check_jarvis_services()
                self._check_brain_new_skills()
                self._check_mega_improve()
                self._check_cluster_nodes()
                self._check_trading_signals()
            except Exception:
                logger.exception("Erreur dans la boucle de surveillance")

            # Attend avec vérification d'arrêt toutes les secondes
            for _ in range(int(POLL_INTERVAL_S)):
                if not self._running:
                    break
                time.sleep(1.0)

    # ------------------------------------------------------------------
    # Checks individuels
    # ------------------------------------------------------------------

    def _check_gpu_temperature(self) -> None:
        """Vérifie la température de chaque GPU via nvidia-smi."""
        output = self._run_cmd(
            ["nvidia-smi", "--query-gpu=index,temperature.gpu", "--format=csv,noheader,nounits"]
        )
        if not output:
            return
        for line in output.strip().split("\n"):
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 2:
                continue
            try:
                idx, temp = parts[0], int(parts[1])
            except ValueError:
                continue
            if temp >= GPU_TEMP_WARN:
                level = "critical" if temp >= 85 else "warning"
                self.send_notification(
                    f"GPU {idx} surchauffe",
                    f"Température : {temp}°C",
                    level=level,
                    speak=(level == "critical"),
                    source="gpu_monitor",
                    metadata={"gpu_index": idx, "temperature": temp},
                )

    def _check_ram_usage(self) -> None:
        """Vérifie l'utilisation de la RAM via /proc/meminfo."""
        try:
            meminfo: dict[str, int] = {}
            with open("/proc/meminfo") as f:
                for line in f:
                    parts = line.split()
                    if len(parts) >= 2:
                        key = parts[0].rstrip(":")
                        meminfo[key] = int(parts[1])
            total = meminfo.get("MemTotal", 1)
            available = meminfo.get("MemAvailable", total)
            used_pct = round((1 - available / total) * 100, 1)
        except (OSError, ValueError, ZeroDivisionError):
            return

        if used_pct >= RAM_WARN_PCT:
            self.send_notification(
                "RAM saturée",
                f"Utilisation : {used_pct}%",
                level="critical" if used_pct >= 95 else "warning",
                speak=True,
                source="ram_monitor",
                metadata={"ram_pct": used_pct},
            )

    def _check_disk_usage(self) -> None:
        """Vérifie l'espace disque sur la partition racine."""
        try:
            st = os.statvfs("/")
            total = st.f_blocks * st.f_frsize
            free = st.f_bavail * st.f_frsize
            used_pct = round((1 - free / total) * 100, 1) if total > 0 else 0
        except OSError:
            return

        if used_pct >= DISK_WARN_PCT:
            self.send_notification(
                "Disque presque plein",
                f"Utilisation : {used_pct}%",
                level="critical" if used_pct >= 95 else "warning",
                speak=True,
                source="disk_monitor",
                metadata={"disk_pct": used_pct},
            )

    def _check_jarvis_services(self) -> None:
        """Détecte les services JARVIS en échec via systemctl."""
        output = self._run_cmd(
            "systemctl --user list-units 'jarvis-*' --state=failed --no-pager --no-legend",
            shell=True,
        )
        failed: set[str] = set()
        if output and output.strip():
            for line in output.strip().split("\n"):
                parts = line.split()
                if not parts:
                    continue
                # systemctl préfixe parfois avec ● — on le saute
                name = parts[0]
                if name in ("●", "○"):
                    name = parts[1] if len(parts) > 1 else ""
                name = name.replace(".service", "").strip()
                if name:
                    failed.add(name)

        # Notifie uniquement les nouveaux services tombés
        new_failures = failed - self._prev_failed_services
        if new_failures:
            names = ", ".join(sorted(new_failures))
            self.send_notification(
                "Service JARVIS tombé",
                f"En échec : {names}",
                level="critical",
                speak=True,
                source="service_monitor",
                metadata={"failed_services": sorted(new_failures)},
            )
        self._prev_failed_services = failed

    def _check_brain_new_skills(self) -> None:
        """Détecte les nouveaux skills auto-appris par le brain."""
        current = self._load_brain_skills()
        new_skills = current - self._prev_brain_skills
        if new_skills and self._prev_brain_skills:  # Pas au premier chargement
            for skill in new_skills:
                self.send_notification(
                    "Nouveau skill appris",
                    f"Le brain a appris : {skill}",
                    level="info",
                    speak=False,
                    source="brain",
                    metadata={"skill_name": skill},
                )
        self._prev_brain_skills = current

    def _check_mega_improve(self) -> None:
        """Vérifie les gaps résolus dans le mega-improve loop."""
        state_file = DATA_DIR / "improve_cycles.jsonl"
        if not state_file.exists():
            return
        try:
            # Lit la dernière ligne du fichier
            last_line = ""
            with open(state_file) as f:
                for line in f:
                    if line.strip():
                        last_line = line.strip()
            if not last_line:
                return
            data = json.loads(last_line)
            resolved = data.get("gaps_resolved", 0)
        except (json.JSONDecodeError, OSError):
            return

        if self._prev_mega_gaps == -1:
            self._prev_mega_gaps = resolved
            return

        if resolved > self._prev_mega_gaps:
            delta = resolved - self._prev_mega_gaps
            self.send_notification(
                "Mega-improve : gaps résolus",
                f"{delta} nouveau(x) gap(s) résolu(s) (total: {resolved})",
                level="info",
                speak=False,
                source="mega_improve",
                metadata={"gaps_resolved": resolved, "delta": delta},
            )
        self._prev_mega_gaps = resolved

    def _check_cluster_nodes(self) -> None:
        """Vérifie l'état des noeuds du cluster via le fichier de config."""
        cluster_file = DATA_DIR / "cluster_knowledge.json"
        if not cluster_file.exists():
            return
        try:
            data = json.loads(cluster_file.read_text())
            nodes: dict[str, Any] = data.get("nodes", {})
        except (json.JSONDecodeError, OSError):
            return

        current_online: set[str] = set()
        for name, info in nodes.items():
            if isinstance(info, dict) and info.get("status") in ("online", "active"):
                current_online.add(name)
            elif isinstance(info, dict):
                current_online.discard(name)

        # Détecte les noeuds qui viennent de passer offline
        if self._prev_cluster_nodes:
            gone_offline = self._prev_cluster_nodes - current_online
            for node in gone_offline:
                self.send_notification(
                    "Noeud cluster offline",
                    f"Le noeud {node} n'est plus accessible",
                    level="critical",
                    speak=True,
                    source="cluster_monitor",
                    metadata={"node": node},
                )
        self._prev_cluster_nodes = current_online

    def _check_trading_signals(self) -> None:
        """Vérifie les nouveaux signaux de trading via le fichier sentinel."""
        signals_file = DATA_DIR / "trading_signals.jsonl"
        if not signals_file.exists():
            return
        try:
            # Lit la dernière ligne
            last_line = ""
            with open(signals_file) as f:
                for line in f:
                    if line.strip():
                        last_line = line.strip()
            if not last_line:
                return
            signal = json.loads(last_line)
            ts = signal.get("ts", 0)
            # Notifie uniquement les signaux récents (< 60s)
            if time.time() - ts < 60:
                pair = signal.get("pair", "???")
                action = signal.get("action", "???")
                confidence = signal.get("confidence", 0)
                self.send_notification(
                    f"Signal trading : {pair}",
                    f"{action.upper()} — confiance {confidence:.0%}",
                    level="warning" if confidence >= 0.7 else "info",
                    speak=False,
                    source="trading",
                    metadata=signal,
                )
        except (json.JSONDecodeError, OSError):
            return

    # ------------------------------------------------------------------
    # Utilitaires internes
    # ------------------------------------------------------------------

    def _send_desktop(self, record: NotificationRecord) -> None:
        """Envoie une notification desktop via notify-send."""
        urgency = URGENCY_MAP.get(record.level, "normal")
        cmd = [
            "notify-send",
            "-i", ICON,
            "-u", urgency,
            "-a", "JARVIS OS",
            record.title,
            record.message,
        ]
        try:
            subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError:
            logger.warning("Impossible d'envoyer la notification desktop")

    def _send_tts(self, text: str) -> None:
        """Annonce vocale via Piper TTS si disponible."""
        if not Path(PIPER_BIN).exists():
            logger.debug("Piper non disponible, TTS ignoré")
            return
        if not Path(PIPER_MODEL).exists():
            logger.debug("Modèle Piper non trouvé: %s", PIPER_MODEL)
            return
        try:
            # Piper lit le texte sur stdin et sort du WAV sur stdout → paplay
            piper_proc = subprocess.Popen(
                [PIPER_BIN, "--model", PIPER_MODEL, "--output-raw"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
            play_proc = subprocess.Popen(
                ["paplay", "--raw", "--rate=22050", "--channels=1", "--format=s16le"],
                stdin=piper_proc.stdout,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if piper_proc.stdin:
                piper_proc.stdin.write(text.encode("utf-8"))
                piper_proc.stdin.close()
            play_proc.wait(timeout=15)
            piper_proc.wait(timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            logger.warning("Erreur TTS Piper pour: %s", text[:50])

    def _append_log(self, record: NotificationRecord) -> None:
        """Ajoute la notification dans le fichier JSONL persistant."""
        try:
            with open(NOTIF_LOG, "a") as f:
                f.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")
        except OSError:
            logger.warning("Impossible d'écrire dans %s", NOTIF_LOG)

    def _load_brain_skills(self) -> set[str]:
        """Charge les noms de skills depuis brain_state.json."""
        brain_file = DATA_DIR / "brain_state.json"
        if not brain_file.exists():
            return set()
        try:
            data = json.loads(brain_file.read_text())
            skills = data.get("skills", {})
            if isinstance(skills, dict):
                return set(skills.keys())
            if isinstance(skills, list):
                return {s.get("name", str(s)) if isinstance(s, dict) else str(s) for s in skills}
        except (json.JSONDecodeError, OSError):
            pass
        return set()

    @staticmethod
    def _run_cmd(cmd: str | list[str], shell: bool = False, timeout: int = 10) -> str:
        """Exécute une commande système et retourne stdout."""
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                shell=shell,
            )
            return result.stdout.strip()
        except (OSError, subprocess.TimeoutExpired):
            return ""


# --- Singleton global ---
notification_manager = SmartNotificationManager()


# --- Point d'entrée CLI ---

def main() -> None:
    """Lance le monitoring en mode autonome (pour systemd)."""
    import signal
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    )

    manager = SmartNotificationManager()

    def _shutdown(signum: int, _frame: Any) -> None:
        logger.info("Signal %d reçu, arrêt en cours...", signum)
        manager.stop_monitoring()
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    # Notification de démarrage
    manager.send_notification(
        "JARVIS Smart Notifications",
        "Surveillance intelligente activée",
        level="info",
        speak=False,
        source="startup",
    )

    manager.start_monitoring()

    # Bloque le thread principal jusqu'à l'arrêt
    try:
        while manager.is_monitoring:
            time.sleep(1.0)
    except KeyboardInterrupt:
        manager.stop_monitoring()


if __name__ == "__main__":
    main()
