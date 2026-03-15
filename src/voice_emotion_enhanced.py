"""JARVIS Voice Emotion Enhanced — Détection d'émotion par analyse textuelle.

Complète voice_emotion.py (analyse audio) avec une détection par mots-clés
sur le texte transcrit. Adapte les réponses de JARVIS au ton de l'utilisateur.

Émotions détectées : frustration, urgence, satisfaction, question, fatigue.

Usage:
    from src.voice_emotion_enhanced import VoiceEmotionDetector

    detector = VoiceEmotionDetector()
    result = detector.detect_emotion("bordel ça marche toujours pas")
    # => {"emotion": "frustration", "confidence": 0.85, "keywords_found": [...]}

    style = detector.get_response_style("frustration")
    adapted = detector.adapt_response("Voici le résultat détaillé...", "frustration")
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger("jarvis.voice_emotion_enhanced")

# Chemin racine JARVIS
JARVIS_HOME = Path(__file__).resolve().parent.parent
HISTORY_PATH = JARVIS_HOME / "data" / "emotion_history.jsonl"

# Nombre max d'entrées à conserver en mémoire
MAX_HISTORY_MEMORY = 500


# ── Dictionnaires de mots-clés par émotion ──────────────────────────────────

EMOTION_KEYWORDS: dict[str, list[str]] = {
    "frustration": [
        "bordel", "merde", "putain", "ça marche pas", "encore",
        "toujours pas", "fait chier", "n'importe quoi", "ras le bol",
        "ça bug", "plantage", "crash", "bloqué",
    ],
    "urgency": [
        "vite", "urgent", "maintenant", "dépêche", "emergency",
        "critique", "tout de suite", "immédiatement", "asap",
        "en urgence", "sans attendre", "prioritaire",
    ],
    "satisfaction": [
        "super", "génial", "bravo", "parfait", "merci",
        "bien joué", "excellent", "top", "nickel", "impeccable",
        "formidable", "cool", "magnifique", "chapeau",
    ],
    "question": [
        "pourquoi", "comment", "qu'est-ce", "c'est quoi", "explique",
        "quel est", "quelle est", "qu'est ce", "dis-moi",
        "peux-tu expliquer", "je comprends pas", "c'est quoi",
    ],
    "fatigue": [
        "bonne nuit", "je suis fatigué", "assez", "stop", "pause",
        "j'arrête", "on arrête", "fatigué", "épuisé", "dodo",
        "je vais dormir", "à demain", "fin de journée",
    ],
}

# Poids de confiance par mot-clé (les expressions longues pèsent plus)
# Calculé dynamiquement : expressions multi-mots = poids plus élevé


# ── Styles de réponse par émotion ────────────────────────────────────────────

RESPONSE_STYLES: dict[str, dict[str, Any]] = {
    "frustration": {
        "verbosity": "short",
        "confirm": False,
        "tone": "direct",
        "max_sentences": 2,
        "suffix_suggestion": "Besoin d'aide pour débloquer ça ?",
    },
    "urgency": {
        "verbosity": "minimal",
        "confirm": False,
        "tone": "efficient",
        "max_sentences": 1,
        "suffix_suggestion": None,
    },
    "satisfaction": {
        "verbosity": "normal",
        "confirm": True,
        "tone": "warm",
        "max_sentences": 4,
        "suffix_suggestion": "Autre chose que je peux faire ?",
    },
    "question": {
        "verbosity": "detailed",
        "confirm": True,
        "tone": "explanatory",
        "max_sentences": 8,
        "suffix_suggestion": None,
    },
    "fatigue": {
        "verbosity": "minimal",
        "confirm": False,
        "tone": "calm",
        "max_sentences": 1,
        "suffix_suggestion": "Mode nuit activé. Bonne nuit.",
    },
    "neutral": {
        "verbosity": "normal",
        "confirm": True,
        "tone": "standard",
        "max_sentences": 4,
        "suffix_suggestion": None,
    },
}


@dataclass
class EmotionResult:
    """Résultat de détection d'émotion."""

    emotion: str
    confidence: float
    keywords_found: list[str]
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "emotion": self.emotion,
            "confidence": round(self.confidence, 3),
            "keywords_found": self.keywords_found,
            "timestamp": self.timestamp,
        }


class VoiceEmotionDetector:
    """Détecteur d'émotion textuelle pour le pipeline vocal JARVIS.

    Analyse le texte transcrit par STT pour détecter l'émotion dominante
    et adapter le comportement de JARVIS en conséquence.
    """

    def __init__(
        self,
        history_path: str | Path | None = None,
        keywords: dict[str, list[str]] | None = None,
    ) -> None:
        self._history_path = Path(history_path) if history_path else HISTORY_PATH
        self._keywords = keywords or EMOTION_KEYWORDS
        self._history: list[EmotionResult] = []
        self._stats: dict[str, int] = {e: 0 for e in self._keywords}
        self._stats["neutral"] = 0
        self._total_detections = 0

        # Pré-compiler les patterns regex pour chaque émotion
        self._patterns: dict[str, list[re.Pattern[str]]] = {}
        for emotion, kws in self._keywords.items():
            # Trier par longueur décroissante pour matcher les expressions longues d'abord
            sorted_kws = sorted(kws, key=len, reverse=True)
            self._patterns[emotion] = [
                re.compile(re.escape(kw), re.IGNORECASE) for kw in sorted_kws
            ]

        # Charger l'historique existant
        self._load_history()

    # ── API publique ─────────────────────────────────────────────────────

    def detect_emotion(self, text: str) -> dict[str, Any]:
        """Détecte l'émotion dominante dans le texte transcrit.

        Args:
            text: Texte transcrit par STT.

        Returns:
            Dict avec emotion, confidence (0-1), keywords_found.
        """
        if not text or not text.strip():
            return EmotionResult(
                emotion="neutral", confidence=1.0, keywords_found=[]
            ).to_dict()

        text_lower = text.lower().strip()

        # Scorer chaque émotion
        scores: dict[str, float] = {}
        found: dict[str, list[str]] = {}

        for emotion, patterns in self._patterns.items():
            emotion_score = 0.0
            emotion_keywords: list[str] = []

            for i, pattern in enumerate(patterns):
                keyword = self._keywords[emotion][
                    # Les patterns sont triés par longueur décroissante
                    self._keywords[emotion].index(
                        sorted(self._keywords[emotion], key=len, reverse=True)[i]
                    )
                ]
                matches = pattern.findall(text_lower)
                if matches:
                    # Les expressions multi-mots ont un poids plus élevé
                    word_count = len(keyword.split())
                    weight = 1.0 + (word_count - 1) * 0.5
                    emotion_score += weight * len(matches)
                    emotion_keywords.append(keyword)

            scores[emotion] = emotion_score
            found[emotion] = emotion_keywords

        # Trouver l'émotion dominante
        max_score = max(scores.values()) if scores else 0.0

        if max_score == 0.0:
            result = EmotionResult(
                emotion="neutral", confidence=1.0, keywords_found=[]
            )
        else:
            dominant = max(scores, key=lambda e: scores[e])
            # Confiance basée sur le score relatif et absolu
            # Score absolu : plafonné à 1.0 quand ≥ 3 points
            abs_confidence = min(1.0, max_score / 3.0)
            # Score relatif : proportion du score dominant vs total
            total = sum(scores.values())
            rel_confidence = max_score / total if total > 0 else 1.0
            # Confiance combinée
            confidence = 0.6 * abs_confidence + 0.4 * rel_confidence
            confidence = min(1.0, max(0.1, confidence))

            result = EmotionResult(
                emotion=dominant,
                confidence=round(confidence, 3),
                keywords_found=found[dominant],
            )

        # Enregistrer dans l'historique
        self._record(result, text)

        return result.to_dict()

    def get_response_style(self, emotion: str) -> dict[str, Any]:
        """Retourne le style de réponse adapté à l'émotion.

        Args:
            emotion: Émotion détectée (frustration, urgency, etc.).

        Returns:
            Dict avec verbosity, confirm, tone, max_sentences, suffix_suggestion.
        """
        return dict(RESPONSE_STYLES.get(emotion, RESPONSE_STYLES["neutral"]))

    def adapt_response(self, text: str, emotion: str) -> str:
        """Adapte un texte de réponse selon l'émotion détectée.

        Tronque ou enrichit la réponse selon le style émotionnel.

        Args:
            text: Texte de réponse original.
            emotion: Émotion détectée.

        Returns:
            Texte adapté.
        """
        if not text:
            return text

        style = self.get_response_style(emotion)
        max_sentences = style.get("max_sentences", 4)
        suffix = style.get("suffix_suggestion")

        # Découper en phrases
        sentences = re.split(r'(?<=[.!?])\s+', text.strip())
        sentences = [s for s in sentences if s.strip()]

        # Tronquer si nécessaire
        if len(sentences) > max_sentences:
            sentences = sentences[:max_sentences]

        adapted = " ".join(sentences)

        # Ajouter le suffixe contextuel si défini
        if suffix and emotion in ("frustration", "satisfaction", "fatigue"):
            adapted = f"{adapted} {suffix}"

        return adapted

    def get_emotion_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """Retourne les dernières détections d'émotion.

        Args:
            limit: Nombre max d'entrées à retourner.

        Returns:
            Liste de dicts (les plus récents en premier).
        """
        return [
            entry.to_dict() for entry in reversed(self._history[-limit:])
        ]

    def get_stats(self) -> dict[str, Any]:
        """Retourne les statistiques agrégées de détection.

        Returns:
            Dict avec total, par émotion, et distribution en pourcentage.
        """
        total = self._total_detections
        distribution: dict[str, float] = {}
        if total > 0:
            for emotion, count in self._stats.items():
                distribution[emotion] = round(count / total * 100, 1)

        return {
            "total_detections": total,
            "counts": dict(self._stats),
            "distribution_pct": distribution,
            "history_size": len(self._history),
            "history_path": str(self._history_path),
        }

    # ── Méthodes internes ────────────────────────────────────────────────

    def _record(self, result: EmotionResult, original_text: str) -> None:
        """Enregistre une détection dans l'historique mémoire et fichier."""
        self._history.append(result)
        self._stats[result.emotion] = self._stats.get(result.emotion, 0) + 1
        self._total_detections += 1

        # Limiter la taille en mémoire
        if len(self._history) > MAX_HISTORY_MEMORY:
            self._history = self._history[-MAX_HISTORY_MEMORY:]

        # Persister dans le fichier JSONL
        self._append_to_file(result, original_text)

    def _append_to_file(self, result: EmotionResult, original_text: str) -> None:
        """Ajoute une entrée au fichier JSONL de persistance."""
        try:
            self._history_path.parent.mkdir(parents=True, exist_ok=True)
            entry = result.to_dict()
            entry["text"] = original_text[:200]  # Tronquer pour la vie privée
            with open(self._history_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError as exc:
            logger.warning("Impossible d'écrire l'historique émotion : %s", exc)

    def _load_history(self) -> None:
        """Charge l'historique depuis le fichier JSONL au démarrage."""
        if not self._history_path.exists():
            return
        try:
            with open(self._history_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        result = EmotionResult(
                            emotion=data.get("emotion", "neutral"),
                            confidence=data.get("confidence", 0.0),
                            keywords_found=data.get("keywords_found", []),
                            timestamp=data.get("timestamp", 0.0),
                        )
                        self._history.append(result)
                        emotion = result.emotion
                        self._stats[emotion] = self._stats.get(emotion, 0) + 1
                        self._total_detections += 1
                    except (json.JSONDecodeError, KeyError):
                        continue

            # Limiter la taille en mémoire
            if len(self._history) > MAX_HISTORY_MEMORY:
                self._history = self._history[-MAX_HISTORY_MEMORY:]

            logger.info(
                "Historique émotion chargé : %d entrées", len(self._history)
            )
        except OSError as exc:
            logger.warning("Impossible de charger l'historique émotion : %s", exc)


# ── Fonctions utilitaires pour le pipeline vocal ─────────────────────────────

def get_pipeline_adjustments(emotion: str) -> dict[str, Any]:
    """Retourne les ajustements pipeline pour une émotion donnée.

    Utilisé par le pipeline vocal pour adapter TTS, confirmation, etc.

    Args:
        emotion: Émotion détectée.

    Returns:
        Dict avec tts_verbosity, skip_confirm, priority_boost, night_mode.
    """
    style = RESPONSE_STYLES.get(emotion, RESPONSE_STYLES["neutral"])

    return {
        "tts_verbosity": style["verbosity"],
        "skip_confirm": not style["confirm"],
        "priority_boost": emotion == "urgency",
        "night_mode": emotion == "fatigue",
        "tone": style["tone"],
    }


def quick_detect(text: str) -> str:
    """Détection rapide sans persistance — retourne juste le nom de l'émotion.

    Utile pour un check rapide dans le pipeline sans instancier la classe.
    """
    text_lower = text.lower()
    for emotion, keywords in EMOTION_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:
                return emotion
    return "neutral"
