"""JARVIS VAD (Voice Activity Detection) — Silero VAD integration.

Filters silence from audio streams before sending to Whisper.
Reduces Whisper load by 60-80% and enables smart end-of-speech detection.

Requirements: pip install silero-vad torch torchaudio
"""

from __future__ import annotations

import logging
import threading
from collections import deque
from typing import Callable

import numpy as np


__all__ = [
    "VoiceActivityDetector",
    "filter_speech",
    "get_vad",
]

logger = logging.getLogger("jarvis.vad")

# ── VAD Configuration ────────────────────────────────────────────────────
VAD_THRESHOLD = 0.5          # Speech probability threshold (0.0-1.0)
VAD_MIN_SPEECH_MS = 250      # Minimum speech duration to trigger
VAD_MIN_SILENCE_MS = 700     # Silence after speech to consider end-of-utterance
VAD_WINDOW_SIZE_MS = 30      # Analysis window (silero supports 30/60/100ms)
SAMPLE_RATE = 16000


class VoiceActivityDetector:
    """Silero VAD wrapper for real-time speech detection.

    Usage:
        vad = VoiceActivityDetector()
        vad.start()
        # Feed audio chunks:
        for chunk in audio_stream:
            segments = vad.process(chunk)
            if segments:
                # segments contains speech-only audio
                whisper_queue.put(segments)
    """

    def __init__(
        self,
        threshold: float = VAD_THRESHOLD,
        min_speech_ms: int = VAD_MIN_SPEECH_MS,
        min_silence_ms: int = VAD_MIN_SILENCE_MS,
        sample_rate: int = SAMPLE_RATE,
        on_speech_start: Callable | None = None,
        on_speech_end: Callable[[np.ndarray], None] | None = None,
    ):
        self.threshold = threshold
        self.min_speech_ms = min_speech_ms
        self.min_silence_ms = min_silence_ms
        self.sample_rate = sample_rate
        self.on_speech_start = on_speech_start
        self.on_speech_end = on_speech_end

        self._model = None
        self._lock = threading.Lock()
        self._is_speaking = False
        self._speech_buffer: list[np.ndarray] = []
        self._silence_samples = 0
        self._speech_samples = 0
        self._min_speech_samples = int(min_speech_ms * sample_rate / 1000)
        self._min_silence_samples = int(min_silence_ms * sample_rate / 1000)
        self._initialized = False

    def _load_model(self) -> bool:
        """Load silero VAD model (lazy, thread-safe)."""
        if self._initialized:
            return self._model is not None

        with self._lock:
            if self._initialized:
                return self._model is not None
            try:
                import torch
                model, utils = torch.hub.load(
                    repo_or_dir='snakers4/silero-vad',
                    model='silero_vad',
                    force_reload=False,
                    onnx=True,  # ONNX is faster on CPU
                )
                self._model = model
                self._get_speech_timestamps = utils[0]
                self._initialized = True
                logger.info("Silero VAD loaded (ONNX mode)")
                return True
            except Exception as exc:
                logger.warning("Failed to load Silero VAD: %s — falling back to amplitude VAD", exc)
                self._model = None
                self._initialized = True
                return False

    def start(self) -> bool:
        """Initialize the VAD model. Returns True if ready."""
        return self._load_model()

    def reset(self):
        """Reset internal state for a new utterance."""
        self._is_speaking = False
        self._speech_buffer.clear()
        self._silence_samples = 0
        self._speech_samples = 0
        if self._model is not None:
            try:
                self._model.reset_states()
            except Exception:
                pass

    def process_chunk(self, audio: np.ndarray) -> dict:
        """Process an audio chunk and detect speech activity.

        Args:
            audio: int16 or float32 numpy array, mono, 16kHz

        Returns:
            dict with:
                - is_speech: bool — whether this chunk contains speech
                - speech_prob: float — probability of speech (0.0-1.0)
                - utterance_complete: bool — True when end-of-speech detected
                - speech_audio: np.ndarray | None — accumulated speech if utterance complete
        """
        result = {
            "is_speech": False,
            "speech_prob": 0.0,
            "utterance_complete": False,
            "speech_audio": None,
        }

        # Convert int16 to float32 if needed
        if audio.dtype == np.int16:
            audio_f32 = audio.astype(np.float32) / 32768.0
        else:
            audio_f32 = audio.astype(np.float32)

        # Flatten to 1D
        if audio_f32.ndim > 1:
            audio_f32 = audio_f32[:, 0]

        if self._model is not None:
            result["speech_prob"] = self._silero_detect(audio_f32)
        else:
            # Fallback: amplitude-based VAD
            result["speech_prob"] = self._amplitude_detect(audio_f32)

        is_speech = result["speech_prob"] >= self.threshold
        result["is_speech"] = is_speech

        if is_speech:
            if not self._is_speaking:
                self._is_speaking = True
                self._speech_buffer.clear()
                self._speech_samples = 0
                if self.on_speech_start:
                    self.on_speech_start()

            self._speech_buffer.append(audio)
            self._speech_samples += len(audio)
            self._silence_samples = 0
        else:
            if self._is_speaking:
                self._silence_samples += len(audio)
                # Keep buffering during short silences (pauses in speech)
                self._speech_buffer.append(audio)

                if self._silence_samples >= self._min_silence_samples:
                    # End of utterance detected
                    if self._speech_samples >= self._min_speech_samples:
                        speech_audio = np.concatenate(self._speech_buffer, axis=0)
                        result["utterance_complete"] = True
                        result["speech_audio"] = speech_audio
                        if self.on_speech_end:
                            self.on_speech_end(speech_audio)

                    self._is_speaking = False
                    self._speech_buffer.clear()
                    self._speech_samples = 0
                    self._silence_samples = 0

        return result

    def _silero_detect(self, audio_f32: np.ndarray) -> float:
        """Run Silero VAD on a float32 audio chunk."""
        import torch
        try:
            tensor = torch.from_numpy(audio_f32)
            prob = self._model(tensor, self.sample_rate).item()
            return prob
        except Exception as exc:
            logger.debug("Silero VAD error: %s", exc)
            return self._amplitude_detect(audio_f32)

    def _amplitude_detect(self, audio_f32: np.ndarray) -> float:
        """Simple amplitude-based VAD fallback."""
        rms = np.sqrt(np.mean(audio_f32 ** 2))
        # Map RMS to probability (tuned for typical speech levels)
        # RMS > 0.02 = likely speech, < 0.005 = likely silence
        if rms > 0.04:
            return 0.95
        elif rms > 0.02:
            return 0.7
        elif rms > 0.01:
            return 0.4
        elif rms > 0.005:
            return 0.2
        return 0.05

    def get_speech_segments(self, audio: np.ndarray) -> list[tuple[int, int]]:
        """Extract speech segments from a complete audio buffer.

        Returns list of (start_sample, end_sample) tuples.
        """
        if self._model is None:
            if not self._load_model():
                # Fallback: return entire audio as one segment
                return [(0, len(audio))]

        if audio.dtype == np.int16:
            audio_f32 = audio.astype(np.float32) / 32768.0
        else:
            audio_f32 = audio

        if audio_f32.ndim > 1:
            audio_f32 = audio_f32[:, 0]

        try:
            import torch
            tensor = torch.from_numpy(audio_f32)
            timestamps = self._get_speech_timestamps(
                tensor, self._model,
                sampling_rate=self.sample_rate,
                threshold=self.threshold,
                min_speech_duration_ms=self.min_speech_ms,
                min_silence_duration_ms=self.min_silence_ms,
            )
            return [(s["start"], s["end"]) for s in timestamps]
        except Exception as exc:
            logger.debug("get_speech_segments error: %s", exc)
            return [(0, len(audio))]

    def extract_speech(self, audio: np.ndarray) -> np.ndarray | None:
        """Extract only speech portions from audio, removing silence.

        Returns concatenated speech segments, or None if no speech found.
        """
        segments = self.get_speech_segments(audio)
        if not segments:
            return None

        speech_parts = [audio[start:end] for start, end in segments]
        if not speech_parts:
            return None

        return np.concatenate(speech_parts, axis=0)


# ── Global VAD instance ──────────────────────────────────────────────────
_vad = VoiceActivityDetector()


def get_vad() -> VoiceActivityDetector:
    """Get the global VAD instance (lazy-loaded)."""
    if not _vad._initialized:
        _vad.start()
    return _vad


def filter_speech(audio: np.ndarray) -> np.ndarray | None:
    """Quick helper: extract speech from audio using global VAD."""
    return get_vad().extract_speech(audio)
