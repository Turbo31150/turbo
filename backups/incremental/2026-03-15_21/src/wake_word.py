"""JARVIS Wake Word Detector — Multi-modèle avec scoring de confiance.

Écoute en continu le micro en arrière-plan.
Supporte plusieurs modèles simultanément (hey_jarvis, ok_jarvis, etc.).
Prend le score max pour le déclenchement, cooldown configurable.
CPU-only, ~50ms latence, aucun réseau requis.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field

logger = logging.getLogger("jarvis.wake_word")

import numpy as np
import sounddevice as sd

# ── Configuration multi-modèle ──────────────────────────────────────────
WAKE_WORDS: list[str] = [
    "hey_jarvis_v0.1",
]

# Seuils par défaut
DEFAULT_THRESHOLD = 0.7
SAMPLE_RATE = 16000
CHUNK_SIZE = 1280  # 80ms chunks (OpenWakeWord attend 80ms)
DEFAULT_COOLDOWN = 1.5  # Secondes entre deux détections


@dataclass
class WakeWordEvent:
    """Événement de détection de wake word."""
    model: str
    score: float
    timestamp: float
    all_scores: dict[str, float] = field(default_factory=dict)


class WakeWordDetector:
    """Détecteur multi-modèle avec scoring de confiance et analytics."""

    def __init__(
        self,
        callback: Callable[[WakeWordEvent], None] | Callable[[], None] | None = None,
        threshold: float = DEFAULT_THRESHOLD,
        models: list[str] | None = None,
        cooldown: float = DEFAULT_COOLDOWN,
    ):
        self._callback = callback
        self._threshold = threshold
        self._models = models or list(WAKE_WORDS)
        self._cooldown = cooldown
        self._running = False
        self._thread: threading.Thread | None = None
        self._model = None
        self._last_fire: float = 0.0
        self._lock = threading.Lock()

        # Stats de détection
        self._detections: list[WakeWordEvent] = []
        self._total_chunks: int = 0
        self._false_rejects: int = 0  # Cooldown rejects

    def start(self, device: int | None = None) -> bool:
        """Démarre l'écoute multi-modèle en arrière-plan."""
        if self._running:
            return True
        try:
            from openwakeword.model import Model
            self._model = Model(
                wakeword_models=self._models,
                inference_framework="onnx",
            )
        except (ImportError, OSError, RuntimeError) as e:
            logger.warning("Wake word model load failed: %s", e)
            return False

        self._running = True
        self._thread = threading.Thread(
            target=self._listen_loop, args=(device,), daemon=True
        )
        self._thread.start()
        names = ", ".join(self._models)
        print(f"  [WAKE] Listening for: {names} (threshold={self._threshold})", flush=True)
        return True

    def stop(self):
        """Arrête l'écoute."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)
        self._model = None

    def _listen_loop(self, device: int | None):
        """Boucle d'écoute continue (thread arrière-plan)."""
        try:
            with sd.InputStream(
                device=device,
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype="int16",
                blocksize=CHUNK_SIZE,
            ) as stream:
                while self._running:
                    audio, _ = stream.read(CHUNK_SIZE)
                    audio_flat = audio.flatten().astype(np.int16)
                    prediction = self._model.predict(audio_flat)
                    self._total_chunks += 1
                    self._process_prediction(prediction)
        except (sd.PortAudioError, OSError, RuntimeError) as e:
            logger.warning("Wake word listen loop error: %s", e)
            self._running = False

    def _process_prediction(self, prediction: dict[str, float]):
        """Traite les scores de prédiction multi-modèle."""
        if not prediction:
            return

        # Trouver le meilleur score parmi tous les modèles
        best_model = max(prediction, key=prediction.get)
        best_score = prediction[best_model]

        if best_score < self._threshold:
            return

        now = time.monotonic()
        if now - self._last_fire < self._cooldown:
            self._false_rejects += 1
            return

        self._last_fire = now
        self._model.reset()

        # Créer l'événement
        event = WakeWordEvent(
            model=best_model,
            score=best_score,
            timestamp=time.time(),
            all_scores=dict(prediction),
        )

        with self._lock:
            self._detections.append(event)
            # Garder les 100 dernières détections
            if len(self._detections) > 100:
                self._detections = self._detections[-100:]

        # Logger la détection
        logger.info(
            "Wake word detected: model=%s score=%.3f (cooldown=%.1fs)",
            best_model, best_score, self._cooldown,
        )

        # Loguer dans voice_analytics si disponible
        self._log_analytics(event)

        # Callback — supporte les deux signatures
        if self._callback:
            try:
                import inspect
                sig = inspect.signature(self._callback)
                if len(sig.parameters) >= 1:
                    self._callback(event)
                else:
                    self._callback()
            except (TypeError, ValueError):
                self._callback()

    def _log_analytics(self, event: WakeWordEvent):
        """Log la détection dans voice_analytics (best-effort)."""
        try:
            from src.voice_analytics import log_voice_event
            log_voice_event(
                event_type="wake_word",
                data={
                    "model": event.model,
                    "score": round(event.score, 4),
                    "all_scores": {k: round(v, 4) for k, v in event.all_scores.items()},
                },
            )
        except (ImportError, Exception):
            pass  # Analytics non critique

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def detections(self) -> list[WakeWordEvent]:
        """Historique des détections."""
        with self._lock:
            return list(self._detections)

    @property
    def stats(self) -> dict:
        """Statistiques de détection."""
        with self._lock:
            total = len(self._detections)
            model_counts: dict[str, int] = {}
            for d in self._detections:
                model_counts[d.model] = model_counts.get(d.model, 0) + 1
            avg_score = (
                sum(d.score for d in self._detections) / total if total else 0.0
            )
            return {
                "total_detections": total,
                "total_chunks_processed": self._total_chunks,
                "cooldown_rejects": self._false_rejects,
                "model_distribution": model_counts,
                "avg_confidence": round(avg_score, 4),
                "models_loaded": list(self._models),
                "threshold": self._threshold,
                "cooldown_s": self._cooldown,
            }

    def update_threshold(self, threshold: float):
        """Met à jour le seuil de détection à chaud."""
        if 0.0 < threshold <= 1.0:
            self._threshold = threshold
            logger.info("Wake word threshold updated to %.2f", threshold)

    def update_cooldown(self, cooldown: float):
        """Met à jour le cooldown à chaud."""
        if cooldown >= 0.0:
            self._cooldown = cooldown
            logger.info("Wake word cooldown updated to %.1fs", cooldown)
