"""Tests for JARVIS VAD (Voice Activity Detection) module."""

import numpy as np
import pytest
from src.vad import VoiceActivityDetector, filter_speech


class TestVADAmplitude:
    """Test the amplitude-based VAD fallback (no Silero required)."""

    def test_silence_detection(self):
        vad = VoiceActivityDetector()
        vad._initialized = True  # Skip model loading
        vad._model = None  # Force amplitude fallback

        silence = np.zeros(1600, dtype=np.int16)
        result = vad.process_chunk(silence)
        assert result["is_speech"] is False
        assert result["speech_prob"] < 0.3

    def test_speech_detection(self):
        vad = VoiceActivityDetector()
        vad._initialized = True
        vad._model = None

        # Generate a 440Hz tone (simulates speech)
        t = np.linspace(0, 0.1, 1600, endpoint=False)
        tone = (np.sin(2 * np.pi * 440 * t) * 16000).astype(np.int16)
        result = vad.process_chunk(tone)
        assert result["is_speech"] is True
        assert result["speech_prob"] > 0.5

    def test_utterance_detection(self):
        vad = VoiceActivityDetector(min_speech_ms=100, min_silence_ms=200)
        vad._initialized = True
        vad._model = None

        # Simulate: speech then silence
        t = np.linspace(0, 0.5, 8000, endpoint=False)
        speech = (np.sin(2 * np.pi * 440 * t) * 16000).astype(np.int16)
        silence = np.zeros(8000, dtype=np.int16)

        # Process speech chunks
        for i in range(0, len(speech), 1600):
            vad.process_chunk(speech[i:i+1600])

        # Process silence chunks until utterance complete
        complete = False
        for i in range(0, len(silence), 1600):
            result = vad.process_chunk(silence[i:i+1600])
            if result["utterance_complete"]:
                complete = True
                assert result["speech_audio"] is not None
                break

        assert complete

    def test_reset(self):
        vad = VoiceActivityDetector()
        vad._initialized = True
        vad._model = None
        vad._is_speaking = True
        vad._speech_buffer = [np.zeros(100, dtype=np.int16)]
        vad.reset()
        assert vad._is_speaking is False
        assert len(vad._speech_buffer) == 0

    def test_extract_speech_fallback(self):
        """Without Silero, extract_speech returns the full audio."""
        vad = VoiceActivityDetector()
        vad._initialized = True
        vad._model = None
        audio = np.ones(16000, dtype=np.int16) * 1000
        result = vad.extract_speech(audio)
        assert result is not None
        assert len(result) == len(audio)


class TestVADCallbacks:
    def test_speech_start_callback(self):
        started = []
        vad = VoiceActivityDetector(on_speech_start=lambda: started.append(True))
        vad._initialized = True
        vad._model = None

        t = np.linspace(0, 0.1, 1600, endpoint=False)
        tone = (np.sin(2 * np.pi * 440 * t) * 16000).astype(np.int16)
        vad.process_chunk(tone)
        assert len(started) == 1

    def test_speech_end_callback(self):
        ended = []
        vad = VoiceActivityDetector(
            min_speech_ms=50, min_silence_ms=100,
            on_speech_end=lambda audio: ended.append(len(audio)),
        )
        vad._initialized = True
        vad._model = None

        # Speech
        t = np.linspace(0, 0.2, 3200, endpoint=False)
        speech = (np.sin(2 * np.pi * 440 * t) * 16000).astype(np.int16)
        for i in range(0, len(speech), 1600):
            vad.process_chunk(speech[i:i+1600])

        # Silence
        silence = np.zeros(4800, dtype=np.int16)
        for i in range(0, len(silence), 1600):
            vad.process_chunk(silence[i:i+1600])

        assert len(ended) >= 1
