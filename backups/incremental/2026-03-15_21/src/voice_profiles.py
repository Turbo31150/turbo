"""voice_profiles.py — Gestion des profils vocaux pour adapter JARVIS au contexte.

Permet de basculer entre différents modes (dev, trading, gaming, etc.)
qui modifient les catégories de commandes actives, les skills prioritaires
et déclenchent des actions d'activation/désactivation.

Usage:
    from src.voice_profiles import profile_manager
    profile_manager.activate_profile("dev")
    profile_manager.is_command_allowed("git")  # True
    profile_manager.get_priority_skills()  # ["git", "docker", ...]
    profile_manager.deactivate_profile()  # Retour au profil normal
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

logger = logging.getLogger("jarvis.voice_profiles")

# Fichier de persistance des profils et de l'état actif
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
PROFILES_FILE = DATA_DIR / "voice_profiles.json"


@dataclass
class VoiceProfile:
    """Définition d'un profil vocal."""

    name: str
    description: str
    enabled_categories: list[str] = field(default_factory=list)
    disabled_categories: list[str] = field(default_factory=list)
    on_activate: list[dict[str, Any]] = field(default_factory=list)
    on_deactivate: list[dict[str, Any]] = field(default_factory=list)
    priority_skills: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Sérialise le profil en dictionnaire."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VoiceProfile:
        """Reconstruit un profil depuis un dictionnaire."""
        return cls(
            name=data.get("name", "unknown"),
            description=data.get("description", ""),
            enabled_categories=data.get("enabled_categories", []),
            disabled_categories=data.get("disabled_categories", []),
            on_activate=data.get("on_activate", []),
            on_deactivate=data.get("on_deactivate", []),
            priority_skills=data.get("priority_skills", []),
        )


# --- Profils prédéfinis ---

_BUILTIN_PROFILES: list[VoiceProfile] = [
    VoiceProfile(
        name="normal",
        description="Comportement par défaut, toutes les commandes actives",
        enabled_categories=["*"],
        disabled_categories=[],
        on_activate=[
            {"tool": "notif_send", "args": {"message": "Mode normal activé"}},
        ],
        on_deactivate=[],
        priority_skills=[],
    ),
    VoiceProfile(
        name="dev",
        description="Priorité développement : git, docker, pytest, IDE",
        enabled_categories=[
            "git", "docker", "code", "terminal", "debug", "system",
            "navigation", "fichiers", "recherche",
        ],
        disabled_categories=["trading", "loisir", "media"],
        on_activate=[
            {"tool": "app_open", "args": {"name": "cursor"}},
            {"tool": "app_open", "args": {"name": "wt"}},
            {"tool": "notif_send", "args": {"message": "Mode dev activé — focus code"}},
        ],
        on_deactivate=[
            {"tool": "notif_send", "args": {"message": "Mode dev désactivé"}},
        ],
        priority_skills=[
            "git", "docker", "pytest", "code", "terminal", "ssh", "lm_query",
        ],
    ),
    VoiceProfile(
        name="trading",
        description="Priorité trading : scans, alertes, pipelines, graphiques",
        enabled_categories=[
            "trading", "navigation", "system", "alertes", "recherche",
        ],
        disabled_categories=["loisir", "media", "code", "docker"],
        on_activate=[
            {"tool": "app_open", "args": {"name": "chrome"}},
            {"tool": "open_url", "args": {"url": "https://www.tradingview.com"}},
            {"tool": "trading_status", "args": {}},
            {"tool": "notif_send", "args": {"message": "Mode trading activé — focus marchés"}},
        ],
        on_deactivate=[
            {"tool": "notif_send", "args": {"message": "Mode trading désactivé"}},
        ],
        priority_skills=[
            "trading_status", "trading_pipeline_v2", "trading_pending_signals",
            "trading_positions", "trading_strategy_rankings", "ollama_trading_analysis",
        ],
    ),
    VoiceProfile(
        name="gaming",
        description="Mode performance : son max, apps minimales, pas de distractions",
        enabled_categories=["loisir", "system", "media", "navigation"],
        disabled_categories=["trading", "code", "docker", "git", "debug"],
        on_activate=[
            {"tool": "close_app", "args": {"name": "chrome"}},
            {"tool": "app_open", "args": {"name": "steam"}},
            {"tool": "bash_run", "args": {"command": "pactl set-sink-volume @DEFAULT_SINK@ 100%"}},
            {"tool": "notif_send", "args": {"message": "Mode gaming activé — bon jeu !"}},
        ],
        on_deactivate=[
            {"tool": "bash_run", "args": {"command": "pactl set-sink-volume @DEFAULT_SINK@ 60%"}},
            {"tool": "notif_send", "args": {"message": "Mode gaming désactivé"}},
        ],
        priority_skills=["steam", "volume", "performance", "gpu_info"],
    ),
    VoiceProfile(
        name="presentation",
        description="Mode présentation : DND, plein écran, pas de notifications",
        enabled_categories=["navigation", "media", "system"],
        disabled_categories=[
            "trading", "code", "docker", "git", "debug", "loisir",
        ],
        on_activate=[
            {"tool": "bash_run", "args": {"command": "gsettings set org.gnome.desktop.notifications show-banners false"}},
            {"tool": "bash_run", "args": {"command": "xdotool key super+F11 2>/dev/null || true"}},
            {"tool": "notif_send", "args": {"message": "Mode présentation activé — DND on"}},
        ],
        on_deactivate=[
            {"tool": "bash_run", "args": {"command": "gsettings set org.gnome.desktop.notifications show-banners true"}},
            {"tool": "notif_send", "args": {"message": "Mode présentation désactivé"}},
        ],
        priority_skills=["screen", "volume", "navigation"],
    ),
    VoiceProfile(
        name="sleep",
        description="Économie d'énergie : services réduits, écran verrouillé",
        enabled_categories=["system"],
        disabled_categories=[
            "trading", "code", "docker", "git", "debug", "loisir",
            "media", "navigation", "recherche",
        ],
        on_activate=[
            {"tool": "bash_run", "args": {"command": "xset dpms force off 2>/dev/null || true"}},
            {"tool": "bash_run", "args": {"command": "loginctl lock-session 2>/dev/null || true"}},
            {"tool": "notif_send", "args": {"message": "Mode sleep activé — bonne nuit"}},
        ],
        on_deactivate=[
            {"tool": "bash_run", "args": {"command": "xset dpms force on 2>/dev/null || true"}},
            {"tool": "notif_send", "args": {"message": "Mode sleep désactivé — bonjour !"}},
        ],
        priority_skills=["system_info", "health_summary"],
    ),
    VoiceProfile(
        name="debug",
        description="Logs verbeux, monitoring détaillé, diagnostics complets",
        enabled_categories=["*"],
        disabled_categories=[],
        on_activate=[
            {"tool": "bash_run", "args": {"command": "export JARVIS_LOG_LEVEL=DEBUG"}},
            {"tool": "diagnostics_run", "args": {}},
            {"tool": "notif_send", "args": {"message": "Mode debug activé — logs verbeux"}},
        ],
        on_deactivate=[
            {"tool": "bash_run", "args": {"command": "export JARVIS_LOG_LEVEL=INFO"}},
            {"tool": "notif_send", "args": {"message": "Mode debug désactivé"}},
        ],
        priority_skills=[
            "diagnostics_run", "diagnostics_quick", "system_info",
            "gpu_info", "db_health", "metrics_summary", "observability_report",
        ],
    ),
    VoiceProfile(
        name="guest",
        description="Commandes limitées, pas d'actions destructives ni sensibles",
        enabled_categories=["navigation", "media", "recherche"],
        disabled_categories=[
            "trading", "code", "docker", "git", "debug", "system",
            "fichiers", "terminal", "admin",
        ],
        on_activate=[
            {"tool": "notif_send", "args": {"message": "Mode invité activé — accès limité"}},
        ],
        on_deactivate=[
            {"tool": "notif_send", "args": {"message": "Mode invité désactivé"}},
        ],
        priority_skills=["navigation", "volume", "recherche"],
    ),
]


class VoiceProfileManager:
    """Gestionnaire de profils vocaux avec persistance JSON."""

    def __init__(self) -> None:
        # Profils disponibles (nom -> VoiceProfile)
        self._profiles: dict[str, VoiceProfile] = {}
        # Profil actuellement actif
        self._active_profile: str = "normal"
        # Timestamp d'activation
        self._activated_at: float = 0.0
        # Historique des changements de profil
        self._history: list[dict[str, Any]] = []

        # Charger les profils prédéfinis
        for p in _BUILTIN_PROFILES:
            self._profiles[p.name] = p

        # Charger l'état persisté (écrase le profil actif sauvegardé)
        self._load_state()
        logger.info("VoiceProfileManager initialisé — profil actif: %s", self._active_profile)

    # --- Persistance ---

    def _load_state(self) -> None:
        """Charge l'état depuis le fichier JSON (profils custom + profil actif)."""
        if not PROFILES_FILE.exists():
            self._save_state()
            return
        try:
            data = json.loads(PROFILES_FILE.read_text(encoding="utf-8"))
            # Restaurer le profil actif
            saved_active = data.get("active_profile", "normal")
            if saved_active in self._profiles:
                self._active_profile = saved_active
            self._activated_at = data.get("activated_at", 0.0)
            self._history = data.get("history", [])
            # Charger d'éventuels profils custom
            for pdata in data.get("custom_profiles", []):
                profile = VoiceProfile.from_dict(pdata)
                if profile.name not in self._profiles:
                    self._profiles[profile.name] = profile
            logger.debug("État chargé depuis %s", PROFILES_FILE)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Impossible de charger %s: %s", PROFILES_FILE, exc)

    def _save_state(self) -> None:
        """Persiste l'état courant dans le fichier JSON."""
        # Séparer les profils custom (non-builtin)
        builtin_names = {p.name for p in _BUILTIN_PROFILES}
        custom = [
            p.to_dict()
            for name, p in self._profiles.items()
            if name not in builtin_names
        ]
        data = {
            "active_profile": self._active_profile,
            "activated_at": self._activated_at,
            "history": self._history[-50:],  # Garder les 50 derniers changements
            "custom_profiles": custom,
        }
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            PROFILES_FILE.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            logger.debug("État sauvegardé dans %s", PROFILES_FILE)
        except OSError as exc:
            logger.error("Impossible de sauvegarder %s: %s", PROFILES_FILE, exc)

    # --- API publique ---

    def activate_profile(self, name: str) -> dict[str, Any]:
        """Active un profil vocal. Retourne un résumé de l'activation."""
        if name not in self._profiles:
            available = list(self._profiles.keys())
            logger.warning("Profil '%s' inconnu. Disponibles: %s", name, available)
            return {
                "success": False,
                "error": f"Profil '{name}' inconnu",
                "available": available,
            }

        previous = self._active_profile
        profile = self._profiles[name]

        # Désactiver l'ancien profil (exécuter on_deactivate)
        if previous != name and previous in self._profiles:
            old_profile = self._profiles[previous]
            deactivate_actions = old_profile.on_deactivate
        else:
            deactivate_actions = []

        # Activer le nouveau profil
        self._active_profile = name
        self._activated_at = time.time()

        # Enregistrer dans l'historique
        entry = {
            "from": previous,
            "to": name,
            "timestamp": self._activated_at,
        }
        self._history.append(entry)

        # Persister
        self._save_state()

        logger.info("Profil activé: %s → %s", previous, name)

        return {
            "success": True,
            "profile": name,
            "previous": previous,
            "description": profile.description,
            "enabled_categories": profile.enabled_categories,
            "disabled_categories": profile.disabled_categories,
            "priority_skills": profile.priority_skills,
            "deactivate_actions": deactivate_actions,
            "activate_actions": profile.on_activate,
        }

    def deactivate_profile(self) -> dict[str, Any]:
        """Désactive le profil courant et retourne au profil normal."""
        return self.activate_profile("normal")

    def get_current_profile(self) -> str:
        """Retourne le nom du profil actuellement actif."""
        return self._active_profile

    def get_current_profile_details(self) -> dict[str, Any]:
        """Retourne les détails complets du profil actif."""
        profile = self._profiles.get(self._active_profile)
        if not profile:
            return {"name": "normal", "error": "Profil introuvable"}
        return {
            **profile.to_dict(),
            "activated_at": self._activated_at,
        }

    def list_profiles(self) -> list[dict[str, Any]]:
        """Liste tous les profils disponibles avec leur statut."""
        result: list[dict[str, Any]] = []
        for name, profile in self._profiles.items():
            result.append({
                "name": name,
                "description": profile.description,
                "active": name == self._active_profile,
                "enabled_categories": profile.enabled_categories,
                "disabled_categories": profile.disabled_categories,
                "priority_skills": profile.priority_skills,
            })
        return result

    def is_command_allowed(self, category: str) -> bool:
        """Vérifie si une catégorie de commande est autorisée dans le profil actif."""
        profile = self._profiles.get(self._active_profile)
        if not profile:
            return True  # Sécurité : si profil introuvable, tout autoriser

        # Vérifier d'abord les catégories bloquées (prioritaire)
        if category in profile.disabled_categories:
            return False

        # Si le wildcard est dans enabled, tout est autorisé (sauf disabled)
        if "*" in profile.enabled_categories:
            return True

        # Sinon, vérifier que la catégorie est dans enabled
        return category in profile.enabled_categories

    def get_priority_skills(self) -> list[str]:
        """Retourne les skills prioritaires du profil actif."""
        profile = self._profiles.get(self._active_profile)
        if not profile:
            return []
        return list(profile.priority_skills)

    def add_custom_profile(self, profile: VoiceProfile) -> dict[str, Any]:
        """Ajoute un profil personnalisé."""
        self._profiles[profile.name] = profile
        self._save_state()
        logger.info("Profil custom ajouté: %s", profile.name)
        return {"success": True, "profile": profile.name}

    def remove_custom_profile(self, name: str) -> dict[str, Any]:
        """Supprime un profil custom (les builtin ne peuvent pas être supprimés)."""
        builtin_names = {p.name for p in _BUILTIN_PROFILES}
        if name in builtin_names:
            return {"success": False, "error": "Impossible de supprimer un profil prédéfini"}
        if name not in self._profiles:
            return {"success": False, "error": f"Profil '{name}' introuvable"}
        if self._active_profile == name:
            self.deactivate_profile()
        del self._profiles[name]
        self._save_state()
        return {"success": True, "removed": name}

    def get_history(self, limit: int = 20) -> list[dict[str, Any]]:
        """Retourne l'historique des changements de profil."""
        return list(reversed(self._history[-limit:]))


# Singleton global
profile_manager = VoiceProfileManager()
