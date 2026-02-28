"""JARVIS Wake Word Detector — Local 'Jarvis' detection via OpenWakeWord.

Listens continuously to microphone in background thread.
Calls callback when 'jarvis' is detected (threshold 0.7).
CPU-only, ~50ms latency, no network required.
"""

from __future__ import annotations

import threading
from collections.abc import Callable

import numpy as np
import sounddevice as sd

WAKE_WORD = "hey_jarvis_v0.1"
THRESHOLD = 0.7
SAMPLE_RATE = 16000
CHUNK_SIZE = 1280  # 80ms chunks (OpenWakeWord expects 80ms)


class WakeWordDetector:
    """Background wake word detector using OpenWakeWord."""

    def __init__(self, callback: Callable[[], None], threshold: float = THRESHOLD):
        self._callback = callback
        self._threshold = threshold
        self._running = False
        self._thread: threading.Thread | None = None
        self._model = None

    def start(self, device: int | None = None) -> bool:
        """Start listening for wake word in background."""
        if self._running:
            return True
        try:
            from openwakeword.model import Model
            self._model = Model(wakeword_models=[WAKE_WORD], inference_framework="onnx")
        except Exception as e:
            print(f"  [WAKE] Failed to load model: {e}", flush=True)
            return False

        self._running = True
        self._thread = threading.Thread(
            target=self._listen_loop, args=(device,), daemon=True
        )
        self._thread.start()
        print(f"  [WAKE] Listening for '{WAKE_WORD}'...", flush=True)
        return True

    def stop(self):
        """Stop listening."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)
        self._model = None

    def _listen_loop(self, device: int | None):
        """Continuous listening loop (runs in background thread)."""
        import time
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
                    for key, score in prediction.items():
                        if score >= self._threshold:
                            self._model.reset()
                            self._callback()
                            time.sleep(1.0)
                            break
        except Exception as e:
            print(f"  [WAKE] Error in listen loop: {e}", flush=True)
            self._running = False

    @property
    def is_running(self) -> bool:
        return self._running
