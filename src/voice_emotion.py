"""JARVIS Voice Emotion/Urgency Detection — Analyse audio simple.

Détecte le niveau d'urgence d'une commande vocale via des features audio :
- RMS (énergie vocale)
- Zero-crossing rate (excitation)
- Spectral centroid (tension vocale)

Pas de ML requis, fonctionne avec numpy seul.

Usage:
    from src.voice_emotion import analyze_urgency, UrgencyLevel
    result = analyze_urgency(audio_int16, sample_rate=16000)
    if result.level == UrgencyLevel.HIGH:
        # Exécution prioritaire
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum

import numpy as np

logger = logging.getLogger("jarvis.voice_emotion")

SAMPLE_RATE = 16000


class UrgencyLevel(str, Enum):
    """Niveaux d'urgence détectés."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class UrgencyResult:
    """Résultat de l'analyse d'urgence."""
    level: UrgencyLevel
    score: float  # 0.0 à 1.0
    rms: float
    zcr: float
    spectral_centroid: float
    features: dict

    def to_dict(self) -> dict:
        return {
            "level": self.level.value,
            "score": round(self.score, 3),
            "rms": round(self.rms, 4),
            "zcr": round(self.zcr, 4),
            "spectral_centroid": round(self.spectral_centroid, 1),
            "features": {k: round(v, 4) for k, v in self.features.items()},
        }


def compute_rms(audio: np.ndarray) -> float:
    """Calcule le Root Mean Square (énergie) du signal."""
    if len(audio) == 0:
        return 0.0
    audio_float = audio.astype(np.float64)
    return float(np.sqrt(np.mean(audio_float ** 2)))


def compute_zcr(audio: np.ndarray) -> float:
    """Calcule le Zero-Crossing Rate (taux de passage par zéro).

    Un ZCR élevé indique une voix excitée ou aiguë.
    """
    if len(audio) < 2:
        return 0.0
    signs = np.sign(audio.astype(np.float64))
    # Nombre de changements de signe / nombre total de samples
    crossings = np.sum(np.abs(np.diff(signs)) > 0)
    return float(crossings / (len(audio) - 1))


def compute_spectral_centroid(audio: np.ndarray, sample_rate: int = SAMPLE_RATE) -> float:
    """Calcule le centroïde spectral (centre de gravité fréquentiel).

    Valeur élevée = voix tendue/aiguë = potentiellement urgent.
    """
    if len(audio) < 2:
        return 0.0
    audio_float = audio.astype(np.float64)
    # FFT
    spectrum = np.abs(np.fft.rfft(audio_float))
    freqs = np.fft.rfftfreq(len(audio_float), d=1.0 / sample_rate)

    total_energy = np.sum(spectrum)
    if total_energy < 1e-10:
        return 0.0

    centroid = float(np.sum(freqs * spectrum) / total_energy)
    return centroid


def compute_energy_variance(audio: np.ndarray, frame_size: int = 1600) -> float:
    """Calcule la variance d'énergie par frames.

    Forte variance = parole dynamique/urgente.
    """
    if len(audio) < frame_size:
        return 0.0
    audio_float = audio.astype(np.float64)
    n_frames = len(audio_float) // frame_size
    if n_frames < 2:
        return 0.0
    energies = []
    for i in range(n_frames):
        frame = audio_float[i * frame_size:(i + 1) * frame_size]
        energies.append(float(np.sqrt(np.mean(frame ** 2))))
    return float(np.var(energies))


def analyze_urgency(
    audio: np.ndarray,
    sample_rate: int = SAMPLE_RATE,
    rms_weight: float = 0.35,
    zcr_weight: float = 0.25,
    centroid_weight: float = 0.25,
    variance_weight: float = 0.15,
) -> UrgencyResult:
    """Analyse le niveau d'urgence d'un segment audio.

    Args:
        audio: Audio int16 ou float, mono
        sample_rate: Taux d'échantillonnage
        *_weight: Poids de chaque feature dans le score final

    Returns:
        UrgencyResult avec level, score, et features détaillées
    """
    if len(audio) == 0:
        return UrgencyResult(
            level=UrgencyLevel.LOW,
            score=0.0,
            rms=0.0,
            zcr=0.0,
            spectral_centroid=0.0,
            features={},
        )

    # Normaliser en float si int16
    if audio.dtype == np.int16:
        audio_norm = audio.astype(np.float64) / 32768.0
    else:
        audio_norm = audio.astype(np.float64)

    # Calculer les features
    rms = compute_rms(audio_norm)
    zcr = compute_zcr(audio)  # Pré-normalisation pas nécessaire
    centroid = compute_spectral_centroid(audio_norm, sample_rate)
    variance = compute_energy_variance(audio_norm, frame_size=sample_rate // 10)

    # Normaliser chaque feature en [0, 1]
    # Basé sur des valeurs typiques de parole
    rms_norm = min(1.0, rms / 0.15)  # RMS ~0.15 = voix forte
    zcr_norm = min(1.0, zcr / 0.3)   # ZCR ~0.3 = très excité
    centroid_norm = min(1.0, centroid / 4000.0)  # Centroid ~4kHz = tendu
    variance_norm = min(1.0, variance / 0.005)  # Variance énergie

    # Score composite pondéré
    score = (
        rms_norm * rms_weight
        + zcr_norm * zcr_weight
        + centroid_norm * centroid_weight
        + variance_norm * variance_weight
    )
    score = min(1.0, max(0.0, score))

    # Classifier le niveau
    if score >= 0.75:
        level = UrgencyLevel.CRITICAL
    elif score >= 0.55:
        level = UrgencyLevel.HIGH
    elif score >= 0.30:
        level = UrgencyLevel.NORMAL
    else:
        level = UrgencyLevel.LOW

    return UrgencyResult(
        level=level,
        score=score,
        rms=rms,
        zcr=zcr,
        spectral_centroid=centroid,
        features={
            "rms_norm": rms_norm,
            "zcr_norm": zcr_norm,
            "centroid_norm": centroid_norm,
            "variance_norm": variance_norm,
        },
    )


def should_prioritize(result: UrgencyResult) -> bool:
    """Détermine si la commande doit être exécutée en priorité."""
    return result.level in (UrgencyLevel.HIGH, UrgencyLevel.CRITICAL)
