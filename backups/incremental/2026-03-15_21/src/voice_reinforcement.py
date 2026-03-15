"""voice_reinforcement.py — Apprentissage par renforcement vocal pour JARVIS.

JARVIS apprend des retours utilisateur (implicites et explicites) pour
ajuster dynamiquement la priorité et la fiabilité de chaque commande.

Feedback implicite :
    - Commande réussie sans correction → reward +1
    - Commande échouée → reward -0.5
    - Correction manuelle ("non, plutôt X") → -1 ancienne, +1 correction
    - Re-demande immédiate → reward -0.3 (confusion)

Feedback explicite :
    - "Jarvis c'est bien" / "bravo" → reward +2
    - "Jarvis c'est nul" / "non" → reward -2
    - "Jarvis apprends que X veut dire Y" → correction + reward

Usage:
    from src.voice_reinforcement import VoiceReinforcementLearner
    learner = VoiceReinforcementLearner()
    learner.record_feedback("ouvre firefox", 1.0, {"source": "implicit"})
    score = learner.get_score("ouvre firefox")
    rankings = learner.get_rankings()
"""

from __future__ import annotations

import json
import logging
import math
import re
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

__all__ = [
    "VoiceReinforcementLearner",
    "RewardType",
    "CommandScore",
]

logger = logging.getLogger("jarvis.voice_reinforcement")

# Répertoire de persistance
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SCORES_PATH = DATA_DIR / "reinforcement_scores.json"

# Seuils de score
SCORE_DEFAULT = 0.5
SCORE_MIN = 0.0
SCORE_MAX = 1.0
SCORE_DISABLE_THRESHOLD = 0.2
SCORE_RELIABLE_THRESHOLD = 0.8

# Facteur EMA — alpha plus élevé = poids plus fort aux observations récentes
EMA_ALPHA = 0.15

# Limites de l'historique par commande
MAX_HISTORY_PER_COMMAND = 200


class RewardType:
    """Constantes pour les types de reward (feedback implicite/explicite)."""

    # Feedback implicite
    SUCCESS = 1.0
    FAILURE = -0.5
    CORRECTION = -1.0
    CORRECTION_TARGET = 1.0
    REPEATED = -0.3

    # Feedback explicite
    EXPLICIT_POSITIVE = 2.0
    EXPLICIT_NEGATIVE = -2.0
    EXPLICIT_LEARN = 1.5


@dataclass
class CommandScore:
    """Score d'apprentissage par renforcement pour une commande vocale."""

    command: str
    score: float = SCORE_DEFAULT
    total_rewards: int = 0
    sum_rewards: float = 0.0
    last_reward: float = 0.0
    last_update: float = 0.0
    disabled: bool = False
    reliable: bool = False
    history: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Sérialise en dict pour le JSON (sans historique complet pour alléger)."""
        return {
            "command": self.command,
            "score": round(self.score, 4),
            "total_rewards": self.total_rewards,
            "sum_rewards": round(self.sum_rewards, 4),
            "last_reward": self.last_reward,
            "last_update": self.last_update,
            "disabled": self.disabled,
            "reliable": self.reliable,
            "history_size": len(self.history),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CommandScore:
        """Reconstruit depuis un dict JSON."""
        return cls(
            command=data["command"],
            score=data.get("score", SCORE_DEFAULT),
            total_rewards=data.get("total_rewards", 0),
            sum_rewards=data.get("sum_rewards", 0.0),
            last_reward=data.get("last_reward", 0.0),
            last_update=data.get("last_update", 0.0),
            disabled=data.get("disabled", False),
            reliable=data.get("reliable", False),
            history=data.get("history", []),
        )


class VoiceReinforcementLearner:
    """Apprentissage par renforcement vocal — adapte le routage par feedback.

    Chaque commande vocale accumule un score EMA (exponential moving average)
    calculé à partir des rewards reçus. Les commandes fiables sont boostées,
    les commandes problématiques sont déprioritisées ou désactivées.
    """

    def __init__(
        self,
        scores_path: Path | str | None = None,
        ema_alpha: float = EMA_ALPHA,
        auto_save: bool = True,
    ) -> None:
        self._scores_path = Path(scores_path) if scores_path else SCORES_PATH
        self._alpha = ema_alpha
        self._auto_save = auto_save
        self._lock = threading.Lock()

        # Dictionnaire commande → CommandScore
        self._commands: dict[str, CommandScore] = {}

        # Statistiques globales
        self._total_feedbacks: int = 0
        self._session_start: float = time.time()

        # Patterns de feedback explicite (compilés une seule fois)
        self._positive_patterns: list[re.Pattern[str]] = [
            re.compile(r"(?:jarvis\s+)?(?:c'est\s+bien|bravo|super|parfait|excellent|merci|génial)", re.IGNORECASE),
        ]
        self._negative_patterns: list[re.Pattern[str]] = [
            re.compile(r"(?:jarvis\s+)?(?:c'est\s+nul|non|mauvais|faux|erreur|pas\s+ça)", re.IGNORECASE),
        ]
        self._learn_pattern: re.Pattern[str] = re.compile(
            r"(?:jarvis\s+)?apprends?\s+que\s+(.+?)\s+veut\s+dire\s+(.+)",
            re.IGNORECASE,
        )

        # Chargement des scores persistés
        self._load()
        logger.info(
            "VoiceReinforcementLearner initialisé — %d commandes chargées",
            len(self._commands),
        )

    # ── Feedback principal ──────────────────────────────────────────────

    def record_feedback(
        self,
        command: str,
        reward: float,
        context: dict[str, Any] | None = None,
    ) -> float:
        """Enregistre un feedback (reward) pour une commande.

        Args:
            command: Texte de la commande vocale (normalisé en minuscules).
            reward: Valeur du reward (voir RewardType).
            context: Contexte optionnel (source, timestamp, correction, etc.).

        Returns:
            Nouveau score EMA de la commande.
        """
        command = command.strip().lower()
        if not command:
            logger.warning("record_feedback appelé avec une commande vide")
            return SCORE_DEFAULT

        ctx = context or {}
        now = time.time()

        with self._lock:
            cs = self._commands.get(command)
            if cs is None:
                cs = CommandScore(command=command)
                self._commands[command] = cs

            # Clamp du reward dans [-2, +2]
            reward = max(-2.0, min(2.0, reward))

            # Mise à jour EMA — on normalise le reward dans [0, 1]
            normalized = (reward + 2.0) / 4.0  # -2→0, +2→1
            cs.score = self._alpha * normalized + (1 - self._alpha) * cs.score
            cs.score = max(SCORE_MIN, min(SCORE_MAX, cs.score))

            # Compteurs
            cs.total_rewards += 1
            cs.sum_rewards += reward
            cs.last_reward = reward
            cs.last_update = now
            self._total_feedbacks += 1

            # Historique (borné)
            entry: dict[str, Any] = {
                "reward": reward,
                "score_after": round(cs.score, 4),
                "timestamp": now,
            }
            if ctx:
                entry["context"] = ctx
            cs.history.append(entry)
            if len(cs.history) > MAX_HISTORY_PER_COMMAND:
                cs.history = cs.history[-MAX_HISTORY_PER_COMMAND:]

            # Mise à jour des flags de seuil
            cs.disabled = cs.score < SCORE_DISABLE_THRESHOLD
            cs.reliable = cs.score > SCORE_RELIABLE_THRESHOLD

            new_score = cs.score

        if cs.disabled:
            logger.warning(
                "Commande '%s' désactivée (score=%.3f < %.1f)",
                command, cs.score, SCORE_DISABLE_THRESHOLD,
            )

        # Sauvegarde automatique
        if self._auto_save:
            self._save()

        logger.debug(
            "Feedback enregistré : '%s' reward=%.1f → score=%.4f",
            command, reward, new_score,
        )
        return new_score

    # ── Feedback implicite (helpers) ────────────────────────────────────

    def record_success(self, command: str) -> float:
        """Commande exécutée avec succès, pas de correction."""
        return self.record_feedback(
            command, RewardType.SUCCESS,
            {"source": "implicit", "type": "success"},
        )

    def record_failure(self, command: str, error: str | None = None) -> float:
        """Commande échouée."""
        ctx: dict[str, Any] = {"source": "implicit", "type": "failure"}
        if error:
            ctx["error"] = error
        return self.record_feedback(command, RewardType.FAILURE, ctx)

    def record_correction(self, old_command: str, new_command: str) -> tuple[float, float]:
        """Correction manuelle : pénalise l'ancienne, récompense la nouvelle."""
        old_score = self.record_feedback(
            old_command, RewardType.CORRECTION,
            {"source": "implicit", "type": "correction", "corrected_to": new_command},
        )
        new_score = self.record_feedback(
            new_command, RewardType.CORRECTION_TARGET,
            {"source": "implicit", "type": "correction_target", "corrected_from": old_command},
        )
        return old_score, new_score

    def record_repeated(self, command: str) -> float:
        """Commande re-demandée immédiatement (signe de confusion)."""
        return self.record_feedback(
            command, RewardType.REPEATED,
            {"source": "implicit", "type": "repeated"},
        )

    # ── Feedback explicite ──────────────────────────────────────────────

    def process_explicit_feedback(
        self,
        text: str,
        last_command: str | None = None,
    ) -> dict[str, Any] | None:
        """Analyse un texte pour détecter du feedback explicite.

        Gère :
            - "Jarvis c'est bien" / "bravo" → reward +2
            - "Jarvis c'est nul" / "non" → reward -2
            - "Jarvis apprends que X veut dire Y" → correction + reward

        Args:
            text: Texte brut capturé par le STT.
            last_command: Dernière commande exécutée (pour feedback positif/négatif).

        Returns:
            Dict décrivant l'action prise, ou None si pas de feedback détecté.
        """
        text = text.strip()
        if not text:
            return None

        # Pattern d'apprentissage explicite : "apprends que X veut dire Y"
        match = self._learn_pattern.search(text)
        if match:
            source = match.group(1).strip().lower()
            target = match.group(2).strip().lower()
            # Récompense la cible, pénalise la source si elle existait
            self.record_feedback(
                target, RewardType.EXPLICIT_LEARN,
                {"source": "explicit", "type": "learn", "alias_from": source},
            )
            logger.info("Apprentissage explicite : '%s' → '%s'", source, target)
            return {
                "type": "learn",
                "source": source,
                "target": target,
                "reward": RewardType.EXPLICIT_LEARN,
            }

        # Feedback positif
        for pattern in self._positive_patterns:
            if pattern.search(text):
                if last_command:
                    score = self.record_feedback(
                        last_command, RewardType.EXPLICIT_POSITIVE,
                        {"source": "explicit", "type": "positive", "text": text},
                    )
                    logger.info("Feedback positif explicite pour '%s'", last_command)
                    return {
                        "type": "positive",
                        "command": last_command,
                        "reward": RewardType.EXPLICIT_POSITIVE,
                        "new_score": score,
                    }
                return None

        # Feedback négatif
        for pattern in self._negative_patterns:
            if pattern.search(text):
                if last_command:
                    score = self.record_feedback(
                        last_command, RewardType.EXPLICIT_NEGATIVE,
                        {"source": "explicit", "type": "negative", "text": text},
                    )
                    logger.info("Feedback négatif explicite pour '%s'", last_command)
                    return {
                        "type": "negative",
                        "command": last_command,
                        "reward": RewardType.EXPLICIT_NEGATIVE,
                        "new_score": score,
                    }
                return None

        return None

    # ── Consultation des scores ─────────────────────────────────────────

    def get_score(self, command: str) -> float:
        """Retourne le score EMA actuel d'une commande.

        Retourne SCORE_DEFAULT (0.5) si la commande n'a jamais été vue.
        """
        command = command.strip().lower()
        with self._lock:
            cs = self._commands.get(command)
            return cs.score if cs else SCORE_DEFAULT

    def get_rankings(self) -> list[dict[str, Any]]:
        """Retourne le classement de toutes les commandes triées par score décroissant."""
        with self._lock:
            rankings = [cs.to_dict() for cs in self._commands.values()]
        rankings.sort(key=lambda x: x["score"], reverse=True)
        return rankings

    def get_disabled_commands(self) -> list[str]:
        """Retourne la liste des commandes désactivées (score < seuil)."""
        with self._lock:
            return [
                cs.command
                for cs in self._commands.values()
                if cs.disabled
            ]

    def is_disabled(self, command: str) -> bool:
        """Vérifie si une commande est désactivée."""
        command = command.strip().lower()
        with self._lock:
            cs = self._commands.get(command)
            return cs.disabled if cs else False

    def is_reliable(self, command: str) -> bool:
        """Vérifie si une commande est marquée comme fiable."""
        command = command.strip().lower()
        with self._lock:
            cs = self._commands.get(command)
            return cs.reliable if cs else False

    # ── Routage et priorité ─────────────────────────────────────────────

    def adjust_routing_priority(self, command: str) -> float:
        """Calcule un facteur de priorité pour le routage vocal.

        Le facteur est un multiplicateur appliqué au score de matching :
            - score > 0.8 (fiable)     → boost ×1.5
            - score 0.5-0.8 (normal)   → facteur ×1.0
            - score 0.2-0.5 (faible)   → pénalité ×0.6
            - score < 0.2 (désactivée) → bloqué ×0.0

        Returns:
            Facteur multiplicateur de priorité (0.0 à 1.5).
        """
        score = self.get_score(command)

        if score < SCORE_DISABLE_THRESHOLD:
            return 0.0
        elif score < SCORE_DEFAULT:
            # Interpolation linéaire entre 0.6 et 1.0
            t = (score - SCORE_DISABLE_THRESHOLD) / (SCORE_DEFAULT - SCORE_DISABLE_THRESHOLD)
            return 0.6 + 0.4 * t
        elif score <= SCORE_RELIABLE_THRESHOLD:
            # Zone normale — facteur 1.0
            return 1.0
        else:
            # Interpolation linéaire entre 1.0 et 1.5
            t = (score - SCORE_RELIABLE_THRESHOLD) / (SCORE_MAX - SCORE_RELIABLE_THRESHOLD)
            return 1.0 + 0.5 * min(t, 1.0)

    def get_priority_boost(self, commands: list[str]) -> list[tuple[str, float]]:
        """Trie une liste de commandes candidates par priorité de routage.

        Args:
            commands: Liste de commandes candidates.

        Returns:
            Liste de (commande, facteur_priorité) triée par facteur décroissant.
        """
        scored = [
            (cmd, self.adjust_routing_priority(cmd))
            for cmd in commands
        ]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored

    # ── Statistiques d'apprentissage ────────────────────────────────────

    def get_learning_stats(self) -> dict[str, Any]:
        """Retourne les statistiques globales d'apprentissage.

        Inclut : nombre de commandes, feedbacks totaux, distribution des scores,
        commandes fiables/désactivées, durée de la session.
        """
        with self._lock:
            commands = list(self._commands.values())
            total = len(commands)

        if total == 0:
            return {
                "total_commands": 0,
                "total_feedbacks": self._total_feedbacks,
                "session_duration_s": round(time.time() - self._session_start, 1),
                "score_distribution": {},
                "reliable_count": 0,
                "disabled_count": 0,
                "avg_score": SCORE_DEFAULT,
                "commands_seen": 0,
            }

        scores = [cs.score for cs in commands]
        avg_score = sum(scores) / total
        reliable = sum(1 for cs in commands if cs.reliable)
        disabled = sum(1 for cs in commands if cs.disabled)

        # Distribution par tranches
        distribution: dict[str, int] = {
            "0.0-0.2 (désactivé)": 0,
            "0.2-0.4 (faible)": 0,
            "0.4-0.6 (normal)": 0,
            "0.6-0.8 (bon)": 0,
            "0.8-1.0 (fiable)": 0,
        }
        for s in scores:
            if s < 0.2:
                distribution["0.0-0.2 (désactivé)"] += 1
            elif s < 0.4:
                distribution["0.2-0.4 (faible)"] += 1
            elif s < 0.6:
                distribution["0.4-0.6 (normal)"] += 1
            elif s < 0.8:
                distribution["0.6-0.8 (bon)"] += 1
            else:
                distribution["0.8-1.0 (fiable)"] += 1

        # Top 5 meilleures et pires commandes
        sorted_cmds = sorted(commands, key=lambda c: c.score, reverse=True)
        top_5 = [
            {"command": cs.command, "score": round(cs.score, 4), "feedbacks": cs.total_rewards}
            for cs in sorted_cmds[:5]
        ]
        bottom_5 = [
            {"command": cs.command, "score": round(cs.score, 4), "feedbacks": cs.total_rewards}
            for cs in sorted_cmds[-5:]
        ]

        return {
            "total_commands": total,
            "total_feedbacks": self._total_feedbacks,
            "session_duration_s": round(time.time() - self._session_start, 1),
            "avg_score": round(avg_score, 4),
            "reliable_count": reliable,
            "disabled_count": disabled,
            "score_distribution": distribution,
            "top_commands": top_5,
            "worst_commands": bottom_5,
            "commands_seen": total,
        }

    # ── Gestion manuelle des commandes ──────────────────────────────────

    def reset_command(self, command: str) -> None:
        """Réinitialise le score d'une commande à la valeur par défaut."""
        command = command.strip().lower()
        with self._lock:
            cs = self._commands.get(command)
            if cs:
                cs.score = SCORE_DEFAULT
                cs.disabled = False
                cs.reliable = False
                cs.history.append({
                    "reward": 0,
                    "score_after": SCORE_DEFAULT,
                    "timestamp": time.time(),
                    "context": {"type": "reset"},
                })
        if self._auto_save:
            self._save()
        logger.info("Commande '%s' réinitialisée à %.1f", command, SCORE_DEFAULT)

    def enable_command(self, command: str) -> None:
        """Réactive manuellement une commande désactivée."""
        command = command.strip().lower()
        with self._lock:
            cs = self._commands.get(command)
            if cs:
                cs.disabled = False
                # Remonter le score juste au-dessus du seuil
                if cs.score < SCORE_DISABLE_THRESHOLD:
                    cs.score = SCORE_DISABLE_THRESHOLD + 0.05
        if self._auto_save:
            self._save()
        logger.info("Commande '%s' réactivée manuellement", command)

    # ── Persistance ─────────────────────────────────────────────────────

    def _load(self) -> None:
        """Charge les scores depuis le fichier JSON."""
        if not self._scores_path.exists():
            logger.info("Aucun fichier de scores — démarrage à zéro")
            return

        try:
            raw = self._scores_path.read_text(encoding="utf-8")
            data = json.loads(raw)

            # Format attendu : {"commands": {cmd: {...}}, "metadata": {...}}
            commands_data = data.get("commands", {})
            for cmd_name, cmd_dict in commands_data.items():
                cmd_dict.setdefault("command", cmd_name)
                self._commands[cmd_name] = CommandScore.from_dict(cmd_dict)

            meta = data.get("metadata", {})
            self._total_feedbacks = meta.get("total_feedbacks", 0)

            logger.info(
                "Scores chargés : %d commandes depuis %s",
                len(self._commands), self._scores_path,
            )
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            logger.error("Erreur de chargement des scores : %s", exc)

    def _save(self) -> None:
        """Sauvegarde les scores dans le fichier JSON (thread-safe)."""
        with self._lock:
            commands_data = {
                cmd: cs.to_dict()
                for cmd, cs in self._commands.items()
            }
            # Inclure l'historique pour les commandes actives
            for cmd, cs in self._commands.items():
                commands_data[cmd]["history"] = cs.history[-50:]  # Garder les 50 derniers

            payload = {
                "metadata": {
                    "total_feedbacks": self._total_feedbacks,
                    "last_save": time.time(),
                    "version": "1.0",
                    "total_commands": len(self._commands),
                },
                "commands": commands_data,
            }

        # Écriture atomique : écrire dans un fichier temporaire puis renommer
        tmp_path = self._scores_path.with_suffix(".tmp")
        try:
            self._scores_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            tmp_path.replace(self._scores_path)
        except OSError as exc:
            logger.error("Erreur de sauvegarde des scores : %s", exc)

    def save(self) -> None:
        """Sauvegarde explicite (utile si auto_save=False)."""
        self._save()

    # ── Représentation ──────────────────────────────────────────────────

    def __repr__(self) -> str:
        return (
            f"VoiceReinforcementLearner("
            f"commands={len(self._commands)}, "
            f"feedbacks={self._total_feedbacks})"
        )
