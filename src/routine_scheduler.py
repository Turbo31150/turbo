"""JARVIS Routine Scheduler — Exécution automatique de routines basées sur l'heure et le jour.

Permet de planifier des skills à des heures/jours spécifiques avec un thread daemon
qui vérifie chaque minute si une routine doit être lancée.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger("jarvis.routine_scheduler")

# --- Chemins ---
_BASE_DIR = Path(__file__).resolve().parent.parent
ROUTINES_FILE = _BASE_DIR / "data" / "routines.json"

# --- Routines par défaut ---
DEFAULT_ROUTINES: list[dict[str, Any]] = [
    {
        "name": "rapport_matin",
        "skill": "rapport_systeme_linux",
        "description": "Rapport système + météo du matin",
        "schedule": {"hours": [7], "minutes": [0], "days": [0, 1, 2, 3, 4]},
        "extras": ["meteo"],
        "enabled": True,
        "auto_execute": True,
        "last_run": None,
    },
    {
        "name": "mode_dev",
        "skill": "mode_dev_linux",
        "description": "Activation mode développeur",
        "schedule": {"hours": [8], "minutes": [0], "days": [0, 1, 2, 3, 4]},
        "extras": [],
        "enabled": True,
        "auto_execute": True,
        "last_run": None,
    },
    {
        "name": "pause_dejeuner",
        "skill": "notification",
        "description": "Notification pause déjeuner",
        "schedule": {"hours": [12], "minutes": [30], "days": [0, 1, 2, 3, 4, 5, 6]},
        "extras": ["message:Pause déjeuner — pense à manger !"],
        "enabled": True,
        "auto_execute": True,
        "last_run": None,
    },
    {
        "name": "backup_vendredi",
        "skill": "backup_jarvis_linux",
        "description": "Backup complet le vendredi soir",
        "schedule": {"hours": [17], "minutes": [0], "days": [4]},
        "extras": [],
        "enabled": True,
        "auto_execute": True,
        "last_run": None,
    },
    {
        "name": "bonne_nuit",
        "skill": "bonne_nuit_linux",
        "description": "Suggestion bonne nuit (pas d'auto-exécution)",
        "schedule": {"hours": [22], "minutes": [0], "days": [0, 1, 2, 3, 4, 5, 6]},
        "extras": [],
        "enabled": True,
        "auto_execute": False,
        "last_run": None,
    },
    {
        "name": "maintenance_dimanche",
        "skill": "maintenance_complete_linux",
        "description": "Maintenance complète le dimanche à 3h",
        "schedule": {"hours": [3], "minutes": [0], "days": [6]},
        "extras": [],
        "enabled": True,
        "auto_execute": True,
        "last_run": None,
    },
    {
        "name": "cluster_check_6h",
        "skill": "cluster_check_linux",
        "description": "Vérification cluster toutes les 6 heures",
        "schedule": {"hours": [0, 6, 12, 18], "minutes": [0], "days": [0, 1, 2, 3, 4, 5, 6]},
        "extras": [],
        "enabled": True,
        "auto_execute": True,
        "last_run": None,
    },
    {
        "name": "brain_learn_hourly",
        "skill": "brain_learn",
        "description": "Cycle d'apprentissage toutes les heures",
        "schedule": {"hours": list(range(24)), "minutes": [0], "days": [0, 1, 2, 3, 4, 5, 6]},
        "extras": [],
        "enabled": True,
        "auto_execute": True,
        "last_run": None,
    },
    {
        "name": "daily_report",
        "skill": "daily_report_generate",
        "description": "Génération du rapport quotidien JARVIS (HTML + JSON)",
        "schedule": {"hours": [23], "minutes": [55], "days": [0, 1, 2, 3, 4, 5, 6]},
        "extras": [],
        "enabled": True,
        "auto_execute": True,
        "last_run": None,
    },
]

# Jours de la semaine (Monday=0 pour correspondre à datetime.weekday())
DAY_NAMES: dict[int, str] = {
    0: "Lun", 1: "Mar", 2: "Mer", 3: "Jeu",
    4: "Ven", 5: "Sam", 6: "Dim",
}


@dataclass
class Routine:
    """Représentation d'une routine planifiée."""

    name: str
    skill: str
    description: str = ""
    schedule: dict[str, list[int]] = field(default_factory=lambda: {"hours": [], "minutes": [0], "days": []})
    extras: list[str] = field(default_factory=list)
    enabled: bool = True
    auto_execute: bool = True
    last_run: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Sérialise la routine en dictionnaire."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Routine:
        """Crée une routine depuis un dictionnaire."""
        # Assurer la rétrocompatibilité
        if "minutes" not in data.get("schedule", {}):
            data.setdefault("schedule", {})["minutes"] = [0]
        return cls(
            name=data["name"],
            skill=data["skill"],
            description=data.get("description", ""),
            schedule=data.get("schedule", {"hours": [], "minutes": [0], "days": []}),
            extras=data.get("extras", []),
            enabled=data.get("enabled", True),
            auto_execute=data.get("auto_execute", True),
            last_run=data.get("last_run"),
        )

    def should_run(self, now: datetime) -> bool:
        """Vérifie si cette routine doit s'exécuter maintenant."""
        if not self.enabled:
            return False

        hours = self.schedule.get("hours", [])
        minutes = self.schedule.get("minutes", [0])
        days = self.schedule.get("days", [])

        # Vérifier jour, heure, minute
        if now.weekday() not in days:
            return False
        if now.hour not in hours:
            return False
        if now.minute not in minutes:
            return False

        # Éviter double exécution : vérifier last_run
        if self.last_run:
            try:
                last = datetime.fromisoformat(self.last_run)
                # Ne pas relancer si déjà exécuté dans les 5 dernières minutes
                if (now - last).total_seconds() < 300:
                    return False
            except (ValueError, TypeError):
                pass

        return True

    def next_run(self, after: datetime | None = None) -> datetime | None:
        """Calcule la prochaine exécution."""
        if not self.enabled:
            return None

        now = after or datetime.now()
        hours = self.schedule.get("hours", [])
        minutes = self.schedule.get("minutes", [0])
        days = self.schedule.get("days", [])

        if not hours or not days:
            return None

        # Chercher dans les 7 prochains jours
        for day_offset in range(8):
            candidate_date = now + timedelta(days=day_offset)
            if candidate_date.weekday() not in days:
                continue

            for h in sorted(hours):
                for m in sorted(minutes):
                    candidate = candidate_date.replace(hour=h, minute=m, second=0, microsecond=0)
                    if candidate > now:
                        return candidate

        return None

    def format_schedule(self) -> str:
        """Retourne une description lisible du planning."""
        days = self.schedule.get("days", [])
        hours = self.schedule.get("hours", [])
        minutes = self.schedule.get("minutes", [0])

        day_str = ", ".join(DAY_NAMES.get(d, "?") for d in sorted(days))
        if len(days) == 7:
            day_str = "tous les jours"

        time_parts: list[str] = []
        for h in sorted(hours):
            for m in sorted(minutes):
                time_parts.append(f"{h:02d}:{m:02d}")

        if len(time_parts) > 4:
            time_str = f"toutes les {24 // len(hours)}h" if len(minutes) == 1 else f"{len(time_parts)} créneaux/jour"
        else:
            time_str = ", ".join(time_parts)

        return f"{time_str} | {day_str}"


class RoutineScheduler:
    """Planificateur de routines automatiques pour JARVIS.

    Vérifie chaque minute si des routines doivent être exécutées
    et les lance via le système de skills.
    """

    def __init__(self, routines_file: str | Path | None = None) -> None:
        self._file = Path(routines_file or ROUTINES_FILE)
        self._routines: list[Routine] = []
        self._thread: threading.Thread | None = None
        self._running = False
        self._lock = threading.Lock()
        self._skill_executor: Any = None  # Injection du skill executor
        self._load()

    # --- Persistance ---

    def _load(self) -> None:
        """Charge les routines depuis le fichier JSON."""
        if self._file.exists():
            try:
                data = json.loads(self._file.read_text(encoding="utf-8"))
                self._routines = [Routine.from_dict(r) for r in data]
                logger.info("Routines chargées : %d depuis %s", len(self._routines), self._file)
                return
            except (json.JSONDecodeError, KeyError) as exc:
                logger.warning("Fichier routines corrompu, réinitialisation : %s", exc)

        # Initialiser avec les routines par défaut
        self._routines = [Routine.from_dict(r) for r in DEFAULT_ROUTINES]
        self._save()
        logger.info("Routines par défaut initialisées : %d", len(self._routines))

    def _save(self) -> None:
        """Persiste les routines sur disque."""
        self._file.parent.mkdir(parents=True, exist_ok=True)
        data = [r.to_dict() for r in self._routines]
        self._file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.debug("Routines sauvegardées : %d", len(self._routines))

    # --- Gestion du cycle de vie ---

    def set_skill_executor(self, executor: Any) -> None:
        """Injecte la fonction d'exécution de skills.

        Le executor doit accepter (skill_name: str, extras: list[str]) -> bool.
        """
        self._skill_executor = executor

    def start(self) -> None:
        """Démarre le thread daemon de vérification des routines."""
        if self._running:
            logger.warning("Scheduler déjà en cours d'exécution")
            return

        self._running = True
        self._thread = threading.Thread(target=self._loop, name="routine-scheduler", daemon=True)
        self._thread.start()
        logger.info("Routine scheduler démarré")

    def stop(self) -> None:
        """Arrête le scheduler."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=10)
        self._thread = None
        logger.info("Routine scheduler arrêté")

    @property
    def is_running(self) -> bool:
        """Vérifie si le scheduler tourne."""
        return self._running and self._thread is not None and self._thread.is_alive()

    def _loop(self) -> None:
        """Boucle principale — vérifie chaque minute."""
        logger.info("Boucle routine scheduler active")
        while self._running:
            try:
                self._tick()
            except Exception:
                logger.exception("Erreur dans le tick du scheduler")

            # Dormir jusqu'au début de la prochaine minute
            now = datetime.now()
            sleep_seconds = 60 - now.second + 0.1
            # Découper le sleep pour permettre un arrêt rapide
            end_time = time.monotonic() + sleep_seconds
            while self._running and time.monotonic() < end_time:
                time.sleep(min(1.0, end_time - time.monotonic()))

    def _tick(self) -> None:
        """Vérifie et exécute les routines dues."""
        now = datetime.now()

        with self._lock:
            for routine in self._routines:
                if not routine.should_run(now):
                    continue

                if routine.auto_execute:
                    logger.info("Exécution routine : %s → skill %s", routine.name, routine.skill)
                    self._execute_routine(routine, now)
                else:
                    # Suggestion uniquement (pas d'exécution auto)
                    logger.info("Suggestion routine : %s → skill %s (auto_execute=False)", routine.name, routine.skill)
                    self._suggest_routine(routine, now)

    def _execute_routine(self, routine: Routine, now: datetime) -> None:
        """Exécute une routine via le skill executor."""
        try:
            if self._skill_executor:
                self._skill_executor(routine.skill, routine.extras)
            else:
                logger.warning("Pas de skill executor configuré — routine %s non exécutée", routine.name)

            routine.last_run = now.isoformat()
            self._save()
        except Exception:
            logger.exception("Erreur exécution routine %s", routine.name)

    def _suggest_routine(self, routine: Routine, now: datetime) -> None:
        """Enregistre une suggestion sans exécuter."""
        try:
            # Tenter d'envoyer une notification via le skill executor
            if self._skill_executor:
                self._skill_executor(
                    "notification",
                    [f"message:Routine suggérée : {routine.description or routine.name} ({routine.skill})"],
                )

            routine.last_run = now.isoformat()
            self._save()
        except Exception:
            logger.exception("Erreur suggestion routine %s", routine.name)

    # --- API publique ---

    def add_routine(
        self,
        name: str,
        skill: str,
        schedule: dict[str, list[int]],
        auto_execute: bool = True,
        description: str = "",
        extras: list[str] | None = None,
    ) -> Routine:
        """Ajoute une nouvelle routine."""
        with self._lock:
            # Vérifier doublon
            if any(r.name == name for r in self._routines):
                raise ValueError(f"Routine '{name}' existe déjà")

            # Assurer les minutes par défaut
            if "minutes" not in schedule:
                schedule["minutes"] = [0]

            routine = Routine(
                name=name,
                skill=skill,
                description=description,
                schedule=schedule,
                extras=extras or [],
                enabled=True,
                auto_execute=auto_execute,
            )
            self._routines.append(routine)
            self._save()
            logger.info("Routine ajoutée : %s", name)
            return routine

    def remove_routine(self, name: str) -> bool:
        """Supprime une routine par son nom."""
        with self._lock:
            before = len(self._routines)
            self._routines = [r for r in self._routines if r.name != name]
            if len(self._routines) < before:
                self._save()
                logger.info("Routine supprimée : %s", name)
                return True
            logger.warning("Routine non trouvée : %s", name)
            return False

    def enable_routine(self, name: str) -> bool:
        """Active une routine."""
        return self._set_enabled(name, True)

    def disable_routine(self, name: str) -> bool:
        """Désactive une routine."""
        return self._set_enabled(name, False)

    def _set_enabled(self, name: str, enabled: bool) -> bool:
        """Change l'état enabled d'une routine."""
        with self._lock:
            for routine in self._routines:
                if routine.name == name:
                    routine.enabled = enabled
                    self._save()
                    state = "activée" if enabled else "désactivée"
                    logger.info("Routine %s : %s", state, name)
                    return True
            logger.warning("Routine non trouvée : %s", name)
            return False

    def list_routines(self) -> list[dict[str, Any]]:
        """Liste toutes les routines avec leur prochaine exécution."""
        result: list[dict[str, Any]] = []
        now = datetime.now()

        with self._lock:
            for routine in self._routines:
                info = routine.to_dict()
                next_run = routine.next_run(now)
                info["next_run"] = next_run.isoformat() if next_run else None
                info["schedule_human"] = routine.format_schedule()
                info["is_running"] = self.is_running
                result.append(info)

        return result

    def get_next_routines(self, hours: int = 1) -> list[dict[str, Any]]:
        """Retourne les routines prévues dans les N prochaines heures."""
        now = datetime.now()
        limit = now + timedelta(hours=hours)
        result: list[dict[str, Any]] = []

        with self._lock:
            for routine in self._routines:
                if not routine.enabled:
                    continue
                next_run = routine.next_run(now)
                if next_run and next_run <= limit:
                    info = routine.to_dict()
                    info["next_run"] = next_run.isoformat()
                    info["schedule_human"] = routine.format_schedule()
                    info["minutes_until"] = int((next_run - now).total_seconds() / 60)
                    result.append(info)

        # Trier par prochaine exécution
        result.sort(key=lambda r: r["next_run"])
        return result

    def get_routine(self, name: str) -> Routine | None:
        """Récupère une routine par son nom."""
        with self._lock:
            for routine in self._routines:
                if routine.name == name:
                    return routine
        return None

    def get_stats(self) -> dict[str, Any]:
        """Statistiques du scheduler."""
        with self._lock:
            total = len(self._routines)
            enabled = sum(1 for r in self._routines if r.enabled)
            auto = sum(1 for r in self._routines if r.auto_execute and r.enabled)
            suggestion = sum(1 for r in self._routines if not r.auto_execute and r.enabled)

        return {
            "total_routines": total,
            "enabled": enabled,
            "disabled": total - enabled,
            "auto_execute": auto,
            "suggestion_only": suggestion,
            "scheduler_running": self.is_running,
            "routines_file": str(self._file),
        }


# --- Singleton global ---
_scheduler: RoutineScheduler | None = None


def get_scheduler() -> RoutineScheduler:
    """Retourne l'instance singleton du scheduler."""
    global _scheduler
    if _scheduler is None:
        _scheduler = RoutineScheduler()
    return _scheduler


# --- Point d'entrée pour exécution standalone ---
def main() -> None:
    """Lance le scheduler en mode standalone (pour systemd)."""
    import signal
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    logger.info("Démarrage JARVIS Routine Scheduler (standalone)")

    scheduler = get_scheduler()

    # Executor par défaut : appel HTTP vers le MCP local
    def default_executor(skill: str, extras: list[str]) -> bool:
        """Exécute un skill via l'API MCP locale."""
        import urllib.request
        import urllib.error

        payload = json.dumps({"skill": skill, "extras": extras}).encode("utf-8")
        req = urllib.request.Request(
            "http://127.0.0.1:8080/api/execute_skill",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                logger.info("Skill %s exécuté : %s", skill, result.get("status", "ok"))
                return True
        except urllib.error.URLError as exc:
            logger.error("Erreur appel MCP pour skill %s : %s", skill, exc)
            return False

    scheduler.set_skill_executor(default_executor)
    scheduler.start()

    # Gestion propre de l'arrêt
    def shutdown(signum: int, frame: Any) -> None:
        logger.info("Signal %d reçu — arrêt du scheduler", signum)
        scheduler.stop()
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    # Garder le process principal vivant
    logger.info("Scheduler actif — %d routines chargées", len(scheduler._routines))
    while scheduler.is_running:
        time.sleep(5)


if __name__ == "__main__":
    main()
