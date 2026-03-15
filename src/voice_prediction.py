"""JARVIS Voice Prediction — Suggestion proactive après wake word.

Après détection du wake word, interroge le PredictionEngine pour
proposer la commande la plus probable selon l'heure et le jour.
Pré-charge les actions probables en arrière-plan.

Usage:
    from src.voice_prediction import get_voice_suggestion, pre_warm_predictions
    suggestion = get_voice_suggestion()
    if suggestion:
        tts(f"Tu veux lancer {suggestion['label']} ?")
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any

logger = logging.getLogger("jarvis.voice_prediction")

# Seuil minimum pour proposer une suggestion vocale
SUGGESTION_THRESHOLD = 0.65

# Cooldown entre suggestions (évite de proposer à chaque wake word)
SUGGESTION_COOLDOWN = 120.0  # 2 min

# Labels français pour les actions connues
ACTION_LABELS: dict[str, str] = {
    "trading_scan": "un scan trading",
    "trading_status": "le statut trading",
    "health_check": "un check santé",
    "cluster_status": "le statut du cluster",
    "gpu_info": "les infos GPU",
    "thermal": "le check thermique",
    "météo": "la météo",
    "musique": "de la musique",
    "lumière": "les lumières",
    "volume": "le volume",
    "agenda": "l'agenda",
    "mail": "les mails",
    "news": "les nouvelles",
    "timer": "un minuteur",
    "rappel": "un rappel",
}

_last_suggestion_ts: float = 0.0


def get_voice_suggestion(
    threshold: float = SUGGESTION_THRESHOLD,
    n: int = 3,
) -> dict[str, Any] | None:
    """Retourne la suggestion vocale la plus probable, ou None.

    Appelé après wake word pour proposer proactivement une commande.
    Respecte le cooldown pour ne pas spammer.
    """
    global _last_suggestion_ts

    now = time.time()
    if now - _last_suggestion_ts < SUGGESTION_COOLDOWN:
        return None

    try:
        from src.prediction_engine import prediction_engine
        predictions = prediction_engine.predict_next(n=n)
    except (ImportError, Exception) as e:
        logger.debug("Prediction engine unavailable: %s", e)
        return None

    if not predictions:
        return None

    top = predictions[0]
    if top["confidence"] < threshold:
        return None

    _last_suggestion_ts = now

    action = top["action"]
    label = ACTION_LABELS.get(action, action.replace("_", " "))

    return {
        "action": action,
        "label": label,
        "confidence": top["confidence"],
        "reason": top.get("reason", ""),
        "alternatives": [
            {
                "action": p["action"],
                "label": ACTION_LABELS.get(p["action"], p["action"].replace("_", " ")),
                "confidence": p["confidence"],
            }
            for p in predictions[1:]
            if p["confidence"] >= threshold * 0.7
        ],
    }


def format_suggestion_text(suggestion: dict[str, Any]) -> str:
    """Formate la suggestion pour le TTS.

    Ex: "Tu veux lancer un scan trading ?"
    Avec alternatives: "Tu veux lancer un scan trading, ou peut-être le statut du cluster ?"
    """
    label = suggestion["label"]
    alts = suggestion.get("alternatives", [])

    if alts:
        alt_label = alts[0]["label"]
        return f"Tu veux lancer {label}, ou peut-être {alt_label} ?"
    return f"Tu veux lancer {label} ?"


async def pre_warm_predictions() -> dict[str, Any]:
    """Pré-charge les actions probables en arrière-plan.

    Appelé au démarrage de session ou après un moment d'inactivité.
    """
    try:
        from src.prediction_engine import prediction_engine
        result = await prediction_engine.pre_warm()
        logger.debug("Pre-warm result: %s", result)
        return result
    except (ImportError, Exception) as e:
        logger.debug("Pre-warm failed: %s", e)
        return {"predictions": 0, "warmed": []}


def get_time_context() -> dict[str, Any]:
    """Retourne le contexte temporel actuel pour enrichir les prédictions."""
    now = datetime.now()
    day_names = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
    period_names = {
        range(5, 9): "matin tôt",
        range(9, 12): "matinée",
        range(12, 14): "midi",
        range(14, 18): "après-midi",
        range(18, 21): "soirée",
        range(21, 24): "nuit",
        range(0, 5): "nuit",
    }
    period = "inconnu"
    for hours, name in period_names.items():
        if now.hour in hours:
            period = name
            break

    return {
        "hour": now.hour,
        "weekday": now.weekday(),
        "day_name": day_names[now.weekday()],
        "period": period,
        "is_weekend": now.weekday() >= 5,
    }


def reset_suggestion_cooldown():
    """Réinitialise le cooldown (pour tests ou après longue inactivité)."""
    global _last_suggestion_ts
    _last_suggestion_ts = 0.0
