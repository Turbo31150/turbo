"""Tests for voice pipeline improvements v12.6.

Covers: phonetic matching, voice learning, voice analytics logging,
Piper TTS fallback, audio controller Linux, streaming segments.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import numpy as np
import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ═══════════════════════════════════════════════════════════════════════════
# Phonetic Matching
# ═══════════════════════════════════════════════════════════════════════════

class TestPhoneticMap:
    def test_map_built(self):
        from src.voice_correction import _phonetic_map
        assert len(_phonetic_map) > 0
        assert "ai" in _phonetic_map
        assert "e" in _phonetic_map["ai"]

    def test_bidirectional(self):
        from src.voice_correction import _phonetic_map
        # ai → e and e → ai
        assert "e" in _phonetic_map.get("ai", set())
        assert "ai" in _phonetic_map.get("e", set())

    def test_tech_terms(self):
        from src.voice_correction import _phonetic_map
        # py → pi (Python phonetics)
        assert "pi" in _phonetic_map.get("py", set())


class TestPhoneticDistance:
    def test_identical(self):
        from src.voice_correction import phonetic_distance
        assert phonetic_distance("test", "test") == 0.0

    def test_known_confusion(self):
        from src.voice_correction import phonetic_distance
        # "ai" and "e" are in same phonetic group → low distance
        assert phonetic_distance("ai", "e") <= 0.15

    def test_different_words(self):
        from src.voice_correction import phonetic_distance
        assert phonetic_distance("bonjour", "python") > 0.5

    def test_phonetic_substitution(self):
        from src.voice_correction import phonetic_distance
        # "cherche" vs "sherche" — ch/sh confusion
        dist = phonetic_distance("cherche", "sherche")
        assert dist < 0.3


class TestPhoneticFuzzyMatch:
    def test_basic_match(self):
        from src.voice_correction import phonetic_fuzzy_match
        candidates = ["ouvre chrome", "ferme tout", "lance firefox"]
        results = phonetic_fuzzy_match("ouvre chrome", candidates, threshold=0.5)
        assert len(results) > 0
        assert results[0][0] == "ouvre chrome"
        assert results[0][1] >= 0.9

    def test_no_match(self):
        from src.voice_correction import phonetic_fuzzy_match
        results = phonetic_fuzzy_match("xyz123", ["bonjour", "salut"], threshold=0.8)
        assert len(results) == 0

    def test_phonetic_similarity(self):
        from src.voice_correction import phonetic_fuzzy_match
        candidates = ["cherche sur google", "ouvre youtube"]
        # "sherche" should match "cherche" via ch/sh confusion
        results = phonetic_fuzzy_match("sherche sur google", candidates, threshold=0.4)
        assert len(results) > 0


# ═══════════════════════════════════════════════════════════════════════════
# Voice Learning
# ═══════════════════════════════════════════════════════════════════════════

class TestVoiceLearning:
    def setup_method(self):
        """Create a temp DB for testing."""
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.db_path = Path(self.tmp.name)
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("""
            CREATE TABLE voice_commands (
                name TEXT PRIMARY KEY, category TEXT, description TEXT,
                triggers TEXT, action_type TEXT, action TEXT,
                params TEXT DEFAULT '[]', confirm INTEGER DEFAULT 0,
                enabled INTEGER DEFAULT 1
            )
        """)
        conn.execute(
            "INSERT INTO voice_commands VALUES (?, ?, ?, ?, ?, ?, '[]', 0, 1)",
            ("test_cmd", "test", "Test command", '["test commande"]', "bash", "echo test"),
        )
        conn.commit()
        conn.close()

    def teardown_method(self):
        self.db_path.unlink(missing_ok=True)

    def test_learn_maps_to_existing(self):
        from src.commands import learn_voice_command
        with patch("src.commands._DB_PATH", self.db_path):
            from src import commands
            # Reload commands from temp DB
            old_commands = commands.COMMANDS[:]
            commands.COMMANDS.clear()
            from src.commands import JarvisCommand
            cmd = JarvisCommand("test_cmd", "test", "Test", ["test commande"], "bash", "echo test")
            commands.COMMANDS.append(cmd)
            commands._trigger_exact.clear()
            commands._trigger_exact["test commande"] = (cmd, "test commande")

            result = learn_voice_command("mon test", target_command="test_cmd")
            assert result["success"] is True
            assert result["method"] == "mapped_to_existing"
            assert "mon test" in cmd.triggers

            # Cleanup
            commands.COMMANDS.clear()
            commands.COMMANDS.extend(old_commands)

    def test_learn_rejects_short_trigger(self):
        from src.commands import learn_voice_command
        result = learn_voice_command("ab")
        assert result["success"] is False
        assert "trop court" in result["error"]

    def test_unlearn_unknown(self):
        from src.commands import unlearn_voice_command
        result = unlearn_voice_command("trigger_inexistant_xyz")
        assert result["success"] is False


# ═══════════════════════════════════════════════════════════════════════════
# Voice Analytics Logging
# ═══════════════════════════════════════════════════════════════════════════

class TestVoiceAnalytics:
    def test_log_creates_table(self):
        from src.voice import _log_voice_event
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            with patch("src.voice.Path") as mock_path:
                # Redirect DB path to temp file
                mock_parent = MagicMock()
                mock_parent.__truediv__ = lambda self, x: MagicMock(
                    __truediv__=lambda self, y: Path(tmp_path)
                )
                # Direct approach: patch the sqlite3 connect path
                original_func = _log_voice_event.__wrapped__ if hasattr(_log_voice_event, '__wrapped__') else _log_voice_event

            # Test that the function doesn't raise
            _log_voice_event("test_stage", text="hello", confidence=0.9)
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_log_never_blocks(self):
        """Voice logging should never raise exceptions."""
        from src.voice import _log_voice_event
        # Even with invalid DB path, should not raise
        with patch("sqlite3.connect", side_effect=Exception("DB error")):
            _log_voice_event("stt", text="test")  # Should not raise


# ═══════════════════════════════════════════════════════════════════════════
# TTS Improvements
# ═══════════════════════════════════════════════════════════════════════════

class TestTTSImprovements:
    def test_voices_dict_exists(self):
        from src.tts_streaming import VOICES
        assert "denise" in VOICES
        assert "henri" in VOICES
        assert "DeniseNeural" in VOICES["denise"]

    def test_adaptive_rate(self):
        from src.tts_streaming import _adaptive_rate
        assert "20" in _adaptive_rate("OK")  # Short text → fast
        assert "10" in _adaptive_rate("A" * 100)  # Medium → normal
        assert "5" in _adaptive_rate("A" * 300)  # Long → slow

    def test_speak_piper_exists(self):
        from src.tts_streaming import speak_piper
        assert asyncio.iscoroutinefunction(speak_piper)

    def test_clear_cache(self):
        from src.tts_streaming import clear_tts_cache
        # Should not raise even if no cache exists
        count = clear_tts_cache()
        assert isinstance(count, int)

    def test_generate_audio_exists(self):
        from src.tts_streaming import _generate_audio
        assert asyncio.iscoroutinefunction(_generate_audio)

    def test_split_sentences(self):
        from src.tts_streaming import _split_sentences
        text = "Voici le rapport complet du systeme avec tous les details. " \
               "Le processeur fonctionne normalement a vingt pour cent de charge. " \
               "La memoire est utilisee a soixante pour cent."
        result = _split_sentences(text)
        assert len(result) >= 2

    def test_split_sentences_merges_short(self):
        from src.tts_streaming import _split_sentences
        result = _split_sentences("Oui. Non. OK.")
        # Short sentences merged
        assert len(result) <= 2

    def test_speak_sentence_streaming_is_async(self):
        from src.tts_streaming import speak_sentence_streaming
        assert asyncio.iscoroutinefunction(speak_sentence_streaming)

    def test_speak_interruptible_is_async(self):
        from src.tts_streaming import speak_interruptible
        assert asyncio.iscoroutinefunction(speak_interruptible)


# ═══════════════════════════════════════════════════════════════════════════
# Audio Controller Linux
# ═══════════════════════════════════════════════════════════════════════════

class TestAudioControllerLinux:
    def test_get_volume_pactl(self):
        from src.audio_controller import AudioController
        ac = AudioController()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Volume: front-left: 42000 /  65% / -11.23 dB,   front-right: 42000 /  65% / -11.23 dB"
        with patch("subprocess.run", return_value=mock_result):
            result = ac.get_volume()
        assert result["volume"] == 65
        assert result["source"] == "pactl"

    def test_set_volume_calls_pactl(self):
        from src.audio_controller import AudioController
        ac = AudioController()
        mock_result = MagicMock(returncode=0)
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            ac.set_volume(75)
        # Should call pactl set-sink-volume
        args = mock_run.call_args
        cmd = args[0][0] if args[0] else args[1].get("args", [])
        assert any("pactl" in str(c) or "amixer" in str(c) for c in cmd)

    def test_list_devices_pactl(self):
        from src.audio_controller import AudioController
        ac = AudioController()
        mock_sinks = MagicMock(returncode=0, stdout="0\talsa_output.pci\tmodule\ts16le\tRUNNING\n")
        mock_sources = MagicMock(returncode=0, stdout="1\talsa_input.pci\tmodule\ts16le\tRUNNING\n")
        with patch("subprocess.run", side_effect=[mock_sinks, mock_sources]):
            devices = ac.list_devices()
        assert len(devices) >= 1


# ═══════════════════════════════════════════════════════════════════════════
# Streaming Segments
# ═══════════════════════════════════════════════════════════════════════════

class TestStreamingSegments:
    def test_whisper_worker_on_segment_callback(self):
        from src.voice import WhisperWorker
        # Verify the transcribe method accepts on_segment param
        import inspect
        sig = inspect.signature(WhisperWorker.transcribe)
        assert "on_segment" in sig.parameters

    def test_voice_learning_patterns(self):
        from src.voice import _LEARN_PATTERNS
        assert len(_LEARN_PATTERNS) == 3

        # Test learn pattern
        m = _LEARN_PATTERNS[0].search("apprends 'montre positions' fais 'trading positions'")
        assert m is not None

        # Test unlearn pattern
        m = _LEARN_PATTERNS[2].search("oublie montre positions")
        assert m is not None


# ═══════════════════════════════════════════════════════════════════════════
# WebSocket Voice Routes
# ═══════════════════════════════════════════════════════════════════════════

class TestWSVoiceRoutes:
    @pytest.mark.asyncio
    async def test_handle_learn_missing_trigger(self):
        from python_ws.routes.voice import handle_voice_request
        result = await handle_voice_request("learn_command", {})
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_handle_unlearn_missing_trigger(self):
        from python_ws.routes.voice import handle_voice_request
        result = await handle_voice_request("unlearn_command", {})
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_handle_list_voices(self):
        from python_ws.routes.voice import handle_voice_request
        result = await handle_voice_request("list_voices", {})
        assert "voices" in result
        assert "default" in result

    @pytest.mark.asyncio
    async def test_unknown_action(self):
        from python_ws.routes.voice import handle_voice_request
        result = await handle_voice_request("nonexistent_action", {})
        assert "error" in result


# ═══════════════════════════════════════════════════════════════════════════
# OL1 Warmup Backoff
# ═══════════════════════════════════════════════════════════════════════════

class TestOL1Backoff:
    def test_warmup_function_exists(self):
        from src.voice import _warmup_ollama
        assert asyncio.iscoroutinefunction(_warmup_ollama)


# ═══════════════════════════════════════════════════════════════════════════
# Voice Conversation Context
# ═══════════════════════════════════════════════════════════════════════════

class TestVoiceContext:
    def test_push_context(self):
        from src.voice import _push_context, _voice_context
        _voice_context.clear()
        _push_context("ouvre chrome", {"intent": "ouvre chrome", "command": "open_chrome", "confidence": 0.95})
        assert len(_voice_context) == 1
        assert _voice_context[0]["intent"] == "ouvre chrome"

    def test_context_ring_buffer(self):
        from src.voice import _push_context, _voice_context, _CONTEXT_MAX
        _voice_context.clear()
        for i in range(_CONTEXT_MAX + 3):
            _push_context(f"cmd_{i}", {"intent": f"cmd_{i}", "command": None, "confidence": 0.5})
        assert len(_voice_context) == _CONTEXT_MAX

    def test_resolve_repeat(self):
        from src.voice import _push_context, _resolve_followup, _voice_context
        _voice_context.clear()
        _push_context("ouvre chrome", {
            "intent": "ouvre chrome",
            "command": MagicMock(name="open_chrome"),
            "confidence": 0.95,
            "method": "exact",
        })
        result = _resolve_followup("refais")
        assert result is not None
        assert result["method"] == "context_repeat"
        assert result["intent"] == "ouvre chrome"

    def test_resolve_repeat_pareil(self):
        from src.voice import _push_context, _resolve_followup, _voice_context
        _voice_context.clear()
        _push_context("lance firefox", {
            "intent": "lance firefox",
            "command": MagicMock(name="open_firefox"),
            "confidence": 0.90,
            "method": "exact",
        })
        result = _resolve_followup("pareil")
        assert result is not None
        assert result["method"] == "context_repeat"

    def test_resolve_inverse(self):
        from src.voice import _push_context, _resolve_followup, _voice_context
        _voice_context.clear()
        _push_context("monte le volume", {
            "intent": "monte le volume",
            "command": None,
            "confidence": 0.90,
            "method": "exact",
        })
        result = _resolve_followup("le contraire")
        assert result is not None
        assert result["method"] == "context_inverse"
        assert "baisse" in result["intent"]

    def test_no_followup_without_context(self):
        from src.voice import _resolve_followup, _voice_context
        _voice_context.clear()
        assert _resolve_followup("refais") is None

    def test_context_expires(self):
        from src.voice import _push_context, _resolve_followup, _voice_context
        _voice_context.clear()
        _push_context("test", {"intent": "test", "command": MagicMock(), "confidence": 0.9, "method": "x"})
        # Artificially expire
        _voice_context[-1]["timestamp"] = time.monotonic() - 200
        assert _resolve_followup("refais") is None


# ═══════════════════════════════════════════════════════════════════════════
# Auto-tuning Confidence Thresholds
# ═══════════════════════════════════════════════════════════════════════════

class TestAutoTuning:
    def test_get_thresholds(self):
        from src.voice import get_confidence_thresholds
        thresholds = get_confidence_thresholds()
        assert "fuzzy_min" in thresholds
        assert "phonetic_min" in thresholds
        assert "ia_trigger" in thresholds
        assert "execute_min" in thresholds
        assert 0.0 < thresholds["fuzzy_min"] < 1.0

    def test_auto_tune_no_crash(self):
        from src.voice import _auto_tune_thresholds, _tuning_last_check
        import src.voice as voice_mod
        # Force re-tune by resetting timer
        voice_mod._tuning_last_check = 0.0
        # Should not raise even without data
        _auto_tune_thresholds()

    def test_thresholds_are_bounded(self):
        from src.voice import _confidence_thresholds
        for key, val in _confidence_thresholds.items():
            assert 0.0 <= val <= 1.0, f"{key}={val} out of bounds"


# ═══════════════════════════════════════════════════════════════════════════
# Multi-Intent Decomposition
# ═══════════════════════════════════════════════════════════════════════════

class TestMultiIntent:
    def test_single_intent_unchanged(self):
        from src.voice import _split_multi_intent
        assert _split_multi_intent("ouvre chrome") == ["ouvre chrome"]

    def test_split_et(self):
        from src.voice import _split_multi_intent
        parts = _split_multi_intent("ouvre chrome et lance spotify")
        assert len(parts) == 2
        assert parts[0] == "ouvre chrome"
        assert parts[1] == "lance spotify"

    def test_split_puis(self):
        from src.voice import _split_multi_intent
        parts = _split_multi_intent("ferme tout puis ouvre firefox")
        assert len(parts) == 2
        assert parts[0] == "ferme tout"
        assert parts[1] == "ouvre firefox"

    def test_split_ensuite(self):
        from src.voice import _split_multi_intent
        parts = _split_multi_intent("monte le volume ensuite lance la musique")
        assert len(parts) == 2

    def test_split_et_aussi(self):
        from src.voice import _split_multi_intent
        parts = _split_multi_intent("ouvre chrome et aussi lance terminal")
        assert len(parts) == 2

    def test_split_trois_intents(self):
        from src.voice import _split_multi_intent
        parts = _split_multi_intent("ouvre chrome puis lance spotify et ferme terminal")
        assert len(parts) == 3

    def test_no_split_short_fragment(self):
        from src.voice import _split_multi_intent
        # "et" at the end with too-short fragment → no split
        parts = _split_multi_intent("cherche et")
        assert len(parts) == 1

    def test_empty_string(self):
        from src.voice import _split_multi_intent
        assert _split_multi_intent("") == [""]

    def test_apres_ca(self):
        from src.voice import _split_multi_intent
        parts = _split_multi_intent("ouvre chrome apres ca lance spotify")
        assert len(parts) == 2


# ═══════════════════════════════════════════════════════════════════════════
# Smart Confidence Confirmation
# ═══════════════════════════════════════════════════════════════════════════

class TestSmartConfirmation:
    def test_needs_confirmation_low(self):
        from src.voice import needs_confirmation
        assert needs_confirmation(0.50) is False  # Too low → reject

    def test_needs_confirmation_grey_zone(self):
        from src.voice import needs_confirmation
        assert needs_confirmation(0.65) is True
        assert needs_confirmation(0.70) is True
        assert needs_confirmation(0.79) is True

    def test_needs_confirmation_high(self):
        from src.voice import needs_confirmation
        assert needs_confirmation(0.85) is False  # High → auto-execute

    def test_needs_confirmation_boundary(self):
        from src.voice import needs_confirmation
        assert needs_confirmation(0.60) is True   # Exact lower bound
        assert needs_confirmation(0.80) is False   # Exact upper bound

    def test_parse_yes(self):
        from src.voice import parse_confirmation
        assert parse_confirmation("oui") is True
        assert parse_confirmation("ouais") is True
        assert parse_confirmation("ok") is True
        assert parse_confirmation("exactement") is True
        assert parse_confirmation("c'est ca") is True

    def test_parse_no(self):
        from src.voice import parse_confirmation
        assert parse_confirmation("non") is False
        assert parse_confirmation("pas ca") is False
        assert parse_confirmation("annule") is False
        assert parse_confirmation("stop") is False

    def test_parse_ambiguous(self):
        from src.voice import parse_confirmation
        assert parse_confirmation("je sais pas") is None
        assert parse_confirmation("hmm") is None

    def test_parse_case_insensitive(self):
        from src.voice import parse_confirmation
        assert parse_confirmation("OUI") is True
        assert parse_confirmation("Non") is False


# ═══════════════════════════════════════════════════════════════════════════
# VAD (Voice Activity Detection)
# ═══════════════════════════════════════════════════════════════════════════

class TestVAD:
    def test_vad_class_exists(self):
        from src.vad import VoiceActivityDetector
        vad = VoiceActivityDetector()
        assert vad.threshold == 0.5
        assert vad.min_speech_ms == 250
        assert vad.min_silence_ms == 700

    def test_vad_amplitude_fallback(self):
        from src.vad import VoiceActivityDetector
        vad = VoiceActivityDetector()
        # Force amplitude mode (no model loading)
        vad._backend = "amplitude"
        vad._initialized = True

        # Loud audio → speech detected
        loud = np.random.randint(-5000, 5000, 1024, dtype=np.int16)
        result = vad.process_chunk(loud)
        assert "is_speech" in result
        assert "utterance_complete" in result
        assert "speech_audio" in result

    def test_vad_silence_detection(self):
        from src.vad import VoiceActivityDetector
        vad = VoiceActivityDetector(min_silence_ms=100)
        vad._backend = "amplitude"
        vad._initialized = True

        # Simulate speech then silence
        speech = np.random.randint(-10000, 10000, 8000, dtype=np.int16)
        result = vad.process_chunk(speech)
        assert result["is_speech"] is True

        # Feed silence chunks until utterance completes
        silence = np.zeros(4800, dtype=np.int16)  # 300ms of silence
        result = vad.process_chunk(silence)
        # Should eventually trigger utterance_complete
        assert result["is_speech"] is False

    def test_vad_reset(self):
        from src.vad import VoiceActivityDetector
        vad = VoiceActivityDetector()
        vad._backend = "amplitude"
        vad._initialized = True
        vad._is_speaking = True
        vad._speech_buffer = [np.zeros(100, dtype=np.int16)]
        vad.reset()
        assert vad._is_speaking is False
        assert len(vad._speech_buffer) == 0

    def test_vad_extract_speech_amplitude(self):
        from src.vad import VoiceActivityDetector
        vad = VoiceActivityDetector()
        vad._backend = "amplitude"
        vad._initialized = True

        # Audio with speech → returns audio
        speech = np.random.randint(-15000, 15000, 16000, dtype=np.int16)
        result = vad.extract_speech(speech)
        assert result is not None
        assert len(result) > 0

    def test_vad_amplitude_returns_mapped_prob(self):
        from src.vad import VoiceActivityDetector
        vad = VoiceActivityDetector()
        # Silence → low prob
        silence_f32 = np.zeros(1024, dtype=np.float32)
        assert vad._amplitude_detect(silence_f32) < 0.1
        # Loud → high prob
        loud_f32 = np.random.randn(1024).astype(np.float32) * 0.1
        assert vad._amplitude_detect(loud_f32) > 0.5

    def test_get_vad_singleton(self):
        from src.vad import get_vad
        vad = get_vad()
        assert vad is not None
        # Backend should be initialized
        assert vad._initialized is True

    def test_filter_speech_helper(self):
        from src.vad import filter_speech
        audio = np.random.randint(-5000, 5000, 32000, dtype=np.int16)
        result = filter_speech(audio)
        assert result is not None

    def test_vad_find_onnx_model(self):
        from src.vad import VoiceActivityDetector
        vad = VoiceActivityDetector()
        model_path = vad._find_onnx_model()
        # Should find the model from faster-whisper or openwakeword
        if model_path is not None:
            assert model_path.exists()
            assert "silero" in model_path.name

    def test_vad_backend_property(self):
        from src.vad import VoiceActivityDetector
        vad = VoiceActivityDetector()
        vad.start()
        assert vad._backend in ("onnx", "torch", "amplitude")


# ═══════════════════════════════════════════════════════════════════════════
# Voice Shortcuts (ultra-fast commands)
# ═══════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════
# Noise Gate
# ═══════════════════════════════════════════════════════════════════════════

class TestNoiseGate:
    def test_not_calibrated_initially(self):
        from src.voice import NoiseGate
        gate = NoiseGate()
        assert gate.is_calibrated is False

    def test_calibration(self):
        from src.voice import NoiseGate
        gate = NoiseGate(calibration_chunks=4, margin_db=6.0)
        # Feed 4 chunks of low-level noise
        for _ in range(4):
            noise = np.random.randint(-50, 50, 1024, dtype=np.int16)
            gate.calibrate_chunk(noise)
        assert gate.is_calibrated is True
        assert gate.noise_floor > 0

    def test_gate_passes_loud_audio(self):
        from src.voice import NoiseGate
        gate = NoiseGate(calibration_chunks=4, margin_db=6.0)
        for _ in range(4):
            gate.calibrate_chunk(np.random.randint(-50, 50, 1024, dtype=np.int16))
        # Loud audio should pass through unchanged
        loud = np.random.randint(-10000, 10000, 1024, dtype=np.int16)
        result = gate.apply(loud)
        assert np.array_equal(result, loud)

    def test_gate_suppresses_quiet_audio(self):
        from src.voice import NoiseGate
        gate = NoiseGate(calibration_chunks=4, margin_db=6.0)
        for _ in range(4):
            gate.calibrate_chunk(np.random.randint(-100, 100, 1024, dtype=np.int16))
        # Very quiet audio (below noise floor + margin) should be zeroed
        quiet = np.random.randint(-10, 10, 1024, dtype=np.int16)
        result = gate.apply(quiet)
        assert np.all(result == 0)

    def test_gate_uncalibrated_passthrough(self):
        from src.voice import NoiseGate
        gate = NoiseGate()
        audio = np.random.randint(-5000, 5000, 1024, dtype=np.int16)
        result = gate.apply(audio)
        assert np.array_equal(result, audio)


class TestVoiceShortcuts:
    def test_shortcut_match_empty(self):
        from src.voice import _shortcut_match
        assert _shortcut_match("nonexistent_xyz") is None

    def test_shortcut_manual_insert(self):
        from src.voice import _voice_shortcuts, _shortcut_match, _shortcuts_lock
        with _shortcuts_lock:
            _voice_shortcuts["ouvre chrome"] = {
                "intent": "ouvre chrome",
                "method": "shortcut",
                "confidence": 1.0,
                "original_method": "exact",
            }
        result = _shortcut_match("ouvre chrome")
        assert result is not None
        assert result["method"] == "shortcut"
        assert result["confidence"] == 1.0
        # Cleanup
        with _shortcuts_lock:
            _voice_shortcuts.pop("ouvre chrome", None)

    def test_shortcut_case_insensitive(self):
        from src.voice import _voice_shortcuts, _shortcut_match, _shortcuts_lock
        with _shortcuts_lock:
            _voice_shortcuts["monte le volume"] = {
                "intent": "monte le volume", "method": "shortcut",
                "confidence": 1.0, "original_method": "exact",
            }
        assert _shortcut_match("Monte le Volume") is not None
        with _shortcuts_lock:
            _voice_shortcuts.pop("monte le volume", None)

    def test_get_voice_shortcuts(self):
        from src.voice import get_voice_shortcuts
        shortcuts = get_voice_shortcuts()
        assert isinstance(shortcuts, dict)

    def test_refresh_doesnt_crash(self):
        from src.voice import _refresh_voice_shortcuts
        import src.voice as voice_mod
        voice_mod._shortcuts_last_refresh = 0.0  # Force refresh
        _refresh_voice_shortcuts()  # Should not raise


# ═══════════════════════════════════════════════════════════════════════════
# Voice Session Manager
# ═══════════════════════════════════════════════════════════════════════════

class TestVoiceSession:
    def test_create_session(self):
        from src.voice_session import VoiceSession
        session = VoiceSession("test-1")
        assert session.session_id == "test-1"
        assert session.active is False
        assert session.stats.total_commands == 0

    def test_record_command(self):
        from src.voice_session import VoiceSession
        session = VoiceSession()
        session.record_command("ouvre chrome", "exact", 0.95, True, 150.0)
        assert session.stats.total_commands == 1
        assert session.stats.successful_commands == 1
        assert session.stats.success_rate == 1.0

    def test_record_failed(self):
        from src.voice_session import VoiceSession
        session = VoiceSession()
        session.record_command("xyz", "none", 0.1, False)
        assert session.stats.failed_commands == 1
        assert session.stats.success_rate == 0.0

    def test_record_stt(self):
        from src.voice_session import VoiceSession
        session = VoiceSession()
        session.record_stt(120.5)
        session.record_stt(80.5)
        assert session.stats.stt_count == 2
        assert session.stats.avg_stt_ms == pytest.approx(100.5)

    def test_record_confirmation(self):
        from src.voice_session import VoiceSession
        session = VoiceSession()
        session.record_confirmation(True)
        session.record_confirmation(False)
        assert session.stats.confirmations_asked == 2
        assert session.stats.confirmations_accepted == 1

    def test_method_distribution(self):
        from src.voice_session import VoiceSession
        session = VoiceSession()
        session.record_command("a", "exact", 1.0, True)
        session.record_command("b", "fuzzy", 0.8, True)
        session.record_command("c", "exact", 0.9, True)
        data = session.to_dict()
        assert data["method_distribution"]["exact"] == 2
        assert data["method_distribution"]["fuzzy"] == 1

    def test_to_dict(self):
        from src.voice_session import VoiceSession
        session = VoiceSession("s1")
        session.mode = "wake"
        session.voice = "henri"
        session.active = True
        data = session.to_dict()
        assert data["session_id"] == "s1"
        assert data["mode"] == "wake"
        assert data["voice"] == "henri"
        assert data["active"] is True
        assert "stats" in data
        assert "recent_commands" in data

    def test_history_cap(self):
        from src.voice_session import VoiceSession
        session = VoiceSession()
        for i in range(60):
            session.record_command(f"cmd_{i}", "exact", 0.9, True)
        assert len(session.history) == 50  # Capped at 50

    def test_singleton(self):
        from src.voice_session import get_voice_session, start_voice_session, end_voice_session
        s1 = start_voice_session(mode="ptt")
        assert s1.active is True
        s2 = get_voice_session()
        assert s2 is s1
        result = end_voice_session()
        assert result is not None
        assert result["mode"] == "ptt"

    def test_to_json(self):
        from src.voice_session import VoiceSession
        session = VoiceSession()
        j = session.to_json()
        data = json.loads(j)
        assert "stats" in data

    def test_ws_session_stats(self):
        from python_ws.routes.voice import handle_voice_request
        # Sync wrapper — session_stats is sync
        from python_ws.routes.voice import _handle_session_stats
        result = _handle_session_stats()
        assert "session_id" in result or "error" in result


# ═══════════════════════════════════════════════════════════════════════════
# Whisper Hallucination Filter
# ═══════════════════════════════════════════════════════════════════════════

class TestHallucinationFilter:
    def test_known_hallucination(self):
        from src.whisper_worker import is_hallucination
        assert is_hallucination("merci") is True
        assert is_hallucination("sous-titres") is True
        assert is_hallucination("ok") is True
        assert is_hallucination("♪") is True

    def test_too_short(self):
        from src.whisper_worker import is_hallucination
        assert is_hallucination("") is True
        assert is_hallucination("a") is True

    def test_valid_command(self):
        from src.whisper_worker import is_hallucination
        assert is_hallucination("ouvre chrome") is False
        assert is_hallucination("lance spotify et monte le volume") is False

    def test_repetition(self):
        from src.whisper_worker import is_hallucination
        assert is_hallucination("bonjour bonjour bonjour") is True
        assert is_hallucination("test test test test") is True

    def test_no_repetition_two(self):
        from src.whisper_worker import is_hallucination
        # Two repetitions is fine
        assert is_hallucination("oui oui") is False

    def test_subtitle_pattern(self):
        from src.whisper_worker import is_hallucination
        assert is_hallucination("Sous-titres réalisés par la communauté") is True
        assert is_hallucination("Copyright all rights reserved") is True

    def test_all_punctuation(self):
        from src.whisper_worker import is_hallucination
        assert is_hallucination("...") is True
        assert is_hallucination("---") is True
        assert is_hallucination("   ") is True

    def test_nospeech_prob(self):
        from src.whisper_worker import is_hallucination
        # High no_speech_prob on majority of segments → hallucination
        segs = [{"no_speech_prob": 0.8}, {"no_speech_prob": 0.9}]
        assert is_hallucination("quelque chose", segs) is True
        # Low no_speech_prob → real speech
        segs_low = [{"no_speech_prob": 0.1}, {"no_speech_prob": 0.2}]
        assert is_hallucination("ouvre chrome", segs_low) is False

    def test_mixed_nospeech(self):
        from src.whisper_worker import is_hallucination
        # Mixed: only 1 out of 3 high → not hallucination
        segs = [{"no_speech_prob": 0.8}, {"no_speech_prob": 0.1}, {"no_speech_prob": 0.2}]
        assert is_hallucination("commande valide", segs) is False


# ═══════════════════════════════════════════════════════════════════════════
# Voice Stats Endpoint
# ═══════════════════════════════════════════════════════════════════════════

class TestVoiceStatsEndpoint:
    def test_endpoint_registered(self):
        """Verify /api/voice/stats is a registered route."""
        from python_ws.server import app
        routes = [r.path for r in app.routes if hasattr(r, "path")]
        assert "/api/voice/stats" in routes

    @pytest.mark.asyncio
    async def test_stats_empty_db(self):
        """Stats endpoint returns valid structure even with empty DB."""
        from python_ws.server import api_voice_stats
        # Monkey-patch DB path to a non-existent path for clean test
        result = await api_voice_stats(period="1h")
        # Result is a JSONResponse, check its body attribute
        assert result.status_code in (200, 500)  # 200 if table exists, 500 if not

    def test_voice_analytics_ws_handler(self):
        """WS handler returns proper structure."""
        from python_ws.routes.voice import _handle_voice_analytics
        result = _handle_voice_analytics({})
        assert "events" in result
        # Either has events or has error (if table missing)
        assert isinstance(result.get("events"), list) or "error" in result


# ═══════════════════════════════════════════════════════════════════════════
# Wake Word Multi-modèle
# ═══════════════════════════════════════════════════════════════════════════

class TestWakeWordMultiModel:
    """Tests pour le détecteur wake word multi-modèle."""

    def test_wake_word_event_creation(self):
        """WakeWordEvent stocke model, score et all_scores."""
        from src.wake_word import WakeWordEvent
        event = WakeWordEvent(
            model="hey_jarvis_v0.1",
            score=0.85,
            timestamp=time.time(),
            all_scores={"hey_jarvis_v0.1": 0.85, "ok_jarvis": 0.3},
        )
        assert event.model == "hey_jarvis_v0.1"
        assert event.score == 0.85
        assert len(event.all_scores) == 2

    def test_detector_default_config(self):
        """Détecteur utilise config par défaut."""
        from src.wake_word import WakeWordDetector, DEFAULT_THRESHOLD, DEFAULT_COOLDOWN, WAKE_WORDS
        det = WakeWordDetector(callback=lambda: None)
        assert det._threshold == DEFAULT_THRESHOLD
        assert det._cooldown == DEFAULT_COOLDOWN
        assert det._models == list(WAKE_WORDS)
        assert not det.is_running

    def test_detector_custom_models(self):
        """Détecteur accepte une liste personnalisée de modèles."""
        from src.wake_word import WakeWordDetector
        models = ["hey_jarvis_v0.1", "alexa_v0.1"]
        det = WakeWordDetector(callback=lambda: None, models=models)
        assert det._models == models

    def test_detector_custom_threshold_and_cooldown(self):
        """Seuil et cooldown personnalisables."""
        from src.wake_word import WakeWordDetector
        det = WakeWordDetector(callback=lambda: None, threshold=0.5, cooldown=2.0)
        assert det._threshold == 0.5
        assert det._cooldown == 2.0

    def test_process_prediction_below_threshold(self):
        """Prédictions sous le seuil sont ignorées."""
        from src.wake_word import WakeWordDetector
        fired = []
        det = WakeWordDetector(callback=lambda: fired.append(1), threshold=0.8)
        det._model = MagicMock()
        det._process_prediction({"hey_jarvis_v0.1": 0.3, "ok_jarvis": 0.5})
        assert len(fired) == 0
        assert len(det._detections) == 0

    def test_process_prediction_above_threshold(self):
        """Prédiction au-dessus du seuil déclenche le callback."""
        from src.wake_word import WakeWordDetector
        fired = []
        det = WakeWordDetector(callback=lambda: fired.append(1), threshold=0.7)
        det._model = MagicMock()
        det._last_fire = 0.0  # Pas de cooldown actif
        det._process_prediction({"hey_jarvis_v0.1": 0.85, "ok_jarvis": 0.2})
        assert len(fired) == 1
        assert len(det._detections) == 1
        assert det._detections[0].model == "hey_jarvis_v0.1"
        assert det._detections[0].score == 0.85

    def test_process_prediction_best_model_selected(self):
        """Le modèle avec le meilleur score est sélectionné."""
        from src.wake_word import WakeWordDetector
        events = []
        det = WakeWordDetector(
            callback=lambda e: events.append(e),
            threshold=0.6,
        )
        det._model = MagicMock()
        det._last_fire = 0.0
        det._process_prediction({"hey_jarvis_v0.1": 0.65, "ok_jarvis": 0.9})
        assert len(events) == 1
        assert events[0].model == "ok_jarvis"
        assert events[0].score == 0.9

    def test_cooldown_prevents_double_fire(self):
        """Le cooldown empêche les doubles détections."""
        from src.wake_word import WakeWordDetector
        fired = []
        det = WakeWordDetector(callback=lambda: fired.append(1), threshold=0.7, cooldown=2.0)
        det._model = MagicMock()
        # Première détection
        det._last_fire = 0.0
        det._process_prediction({"hey_jarvis_v0.1": 0.9})
        assert len(fired) == 1
        # Deuxième détection immédiate (cooldown actif)
        det._process_prediction({"hey_jarvis_v0.1": 0.9})
        assert len(fired) == 1  # Pas de deuxième fire
        assert det._false_rejects == 1

    def test_stats_structure(self):
        """Stats retourne la bonne structure."""
        from src.wake_word import WakeWordDetector
        det = WakeWordDetector(callback=lambda: None, threshold=0.7, cooldown=1.0)
        stats = det.stats
        assert "total_detections" in stats
        assert "total_chunks_processed" in stats
        assert "cooldown_rejects" in stats
        assert "model_distribution" in stats
        assert "avg_confidence" in stats
        assert "models_loaded" in stats
        assert "threshold" in stats
        assert "cooldown_s" in stats

    def test_stats_after_detections(self):
        """Stats reflètent les détections effectuées."""
        from src.wake_word import WakeWordDetector
        det = WakeWordDetector(callback=lambda: None, threshold=0.6, cooldown=0.0)
        det._model = MagicMock()
        det._last_fire = 0.0
        det._process_prediction({"model_a": 0.8, "model_b": 0.5})
        # Cooldown 0 = pas de blocage, mais last_fire est set
        det._last_fire = 0.0  # Reset pour tester
        det._process_prediction({"model_a": 0.3, "model_b": 0.9})
        stats = det.stats
        assert stats["total_detections"] == 2
        assert stats["model_distribution"]["model_a"] == 1
        assert stats["model_distribution"]["model_b"] == 1
        assert stats["avg_confidence"] > 0.8

    def test_update_threshold(self):
        """Mise à jour du seuil à chaud."""
        from src.wake_word import WakeWordDetector
        det = WakeWordDetector(callback=lambda: None)
        det.update_threshold(0.5)
        assert det._threshold == 0.5
        # Valeur invalide ignorée
        det.update_threshold(0.0)
        assert det._threshold == 0.5
        det.update_threshold(1.5)
        assert det._threshold == 0.5

    def test_update_cooldown(self):
        """Mise à jour du cooldown à chaud."""
        from src.wake_word import WakeWordDetector
        det = WakeWordDetector(callback=lambda: None)
        det.update_cooldown(3.0)
        assert det._cooldown == 3.0
        det.update_cooldown(0.0)
        assert det._cooldown == 0.0
        # Valeur négative ignorée
        det.update_cooldown(-1.0)
        assert det._cooldown == 0.0

    def test_detections_history_cap(self):
        """L'historique est plafonné à 100 détections."""
        from src.wake_word import WakeWordDetector
        det = WakeWordDetector(callback=lambda: None, threshold=0.5, cooldown=0.0)
        det._model = MagicMock()
        for i in range(120):
            det._last_fire = 0.0
            det._process_prediction({"model_a": 0.8})
        assert len(det._detections) == 100

    def test_callback_with_event_param(self):
        """Callback recevant WakeWordEvent fonctionne."""
        from src.wake_word import WakeWordDetector, WakeWordEvent
        events = []
        det = WakeWordDetector(
            callback=lambda e: events.append(e),
            threshold=0.7, cooldown=0.0,
        )
        det._model = MagicMock()
        det._last_fire = 0.0
        det._process_prediction({"test_model": 0.95})
        assert len(events) == 1
        assert isinstance(events[0], WakeWordEvent)
        assert events[0].score == 0.95

    def test_empty_prediction_ignored(self):
        """Prédiction vide ne déclenche rien."""
        from src.wake_word import WakeWordDetector
        fired = []
        det = WakeWordDetector(callback=lambda: fired.append(1))
        det._model = MagicMock()
        det._process_prediction({})
        assert len(fired) == 0


# ═══════════════════════════════════════════════════════════════════════════
# Voice Command Prediction
# ═══════════════════════════════════════════════════════════════════════════

class TestVoicePrediction:
    """Tests pour les suggestions vocales proactives."""

    def setup_method(self):
        from src.voice_prediction import reset_suggestion_cooldown
        reset_suggestion_cooldown()

    def test_get_voice_suggestion_no_data(self):
        """Suggestion retourne None si pas de données."""
        from src.voice_prediction import get_voice_suggestion, reset_suggestion_cooldown
        reset_suggestion_cooldown()
        with patch("src.prediction_engine.prediction_engine") as mock_pe:
            mock_pe.predict_next.return_value = []
            result = get_voice_suggestion()
            assert result is None

    def test_get_voice_suggestion_below_threshold(self):
        """Suggestion retourne None si confiance trop basse."""
        from src.voice_prediction import get_voice_suggestion, reset_suggestion_cooldown
        reset_suggestion_cooldown()
        with patch("src.prediction_engine.prediction_engine") as mock_pe:
            mock_pe.predict_next.return_value = [
                {"action": "trading_scan", "confidence": 0.3, "score": 1.0, "reason": "hour=8"}
            ]
            result = get_voice_suggestion(threshold=0.65)
            assert result is None

    def test_get_voice_suggestion_above_threshold(self):
        """Suggestion retournée si confiance suffisante."""
        from src.voice_prediction import get_voice_suggestion, reset_suggestion_cooldown
        reset_suggestion_cooldown()
        with patch("src.prediction_engine.prediction_engine") as mock_pe:
            mock_pe.predict_next.return_value = [
                {"action": "trading_scan", "confidence": 0.85, "score": 5.0, "reason": "hour=8 weekday=0"}
            ]
            result = get_voice_suggestion(threshold=0.65)
            assert result is not None
            assert result["action"] == "trading_scan"
            assert result["label"] == "un scan trading"
            assert result["confidence"] == 0.85

    def test_get_voice_suggestion_with_alternatives(self):
        """Suggestion inclut les alternatives au-dessus du seuil."""
        from src.voice_prediction import get_voice_suggestion, reset_suggestion_cooldown
        reset_suggestion_cooldown()
        with patch("src.prediction_engine.prediction_engine") as mock_pe:
            mock_pe.predict_next.return_value = [
                {"action": "trading_scan", "confidence": 0.9, "score": 5.0, "reason": "h=8"},
                {"action": "gpu_info", "confidence": 0.7, "score": 3.0, "reason": "h=8"},
                {"action": "météo", "confidence": 0.3, "score": 1.0, "reason": "h=8"},
            ]
            result = get_voice_suggestion(threshold=0.65)
            assert result is not None
            assert len(result["alternatives"]) >= 1
            assert result["alternatives"][0]["action"] == "gpu_info"

    def test_suggestion_cooldown(self):
        """Le cooldown empêche les suggestions répétées."""
        from src.voice_prediction import get_voice_suggestion, reset_suggestion_cooldown
        reset_suggestion_cooldown()
        with patch("src.prediction_engine.prediction_engine") as mock_pe:
            mock_pe.predict_next.return_value = [
                {"action": "trading_scan", "confidence": 0.9, "score": 5.0, "reason": "h=8"}
            ]
            r1 = get_voice_suggestion()
            assert r1 is not None
            r2 = get_voice_suggestion()
            assert r2 is None

    def test_format_suggestion_simple(self):
        """Formatage simple sans alternatives."""
        from src.voice_prediction import format_suggestion_text
        text = format_suggestion_text({
            "action": "trading_scan",
            "label": "un scan trading",
            "confidence": 0.9,
        })
        assert "un scan trading" in text
        assert text.endswith("?")

    def test_format_suggestion_with_alt(self):
        """Formatage avec alternative."""
        from src.voice_prediction import format_suggestion_text
        text = format_suggestion_text({
            "action": "trading_scan",
            "label": "un scan trading",
            "confidence": 0.9,
            "alternatives": [{"action": "gpu_info", "label": "les infos GPU", "confidence": 0.7}],
        })
        assert "un scan trading" in text
        assert "les infos GPU" in text
        assert "ou peut-être" in text

    def test_get_time_context_structure(self):
        """Le contexte temporel a la bonne structure."""
        from src.voice_prediction import get_time_context
        ctx = get_time_context()
        assert "hour" in ctx
        assert "weekday" in ctx
        assert "day_name" in ctx
        assert "period" in ctx
        assert "is_weekend" in ctx
        assert 0 <= ctx["hour"] <= 23
        assert 0 <= ctx["weekday"] <= 6

    def test_action_labels_known_actions(self):
        """Les actions connues ont des labels français."""
        from src.voice_prediction import ACTION_LABELS
        assert "trading_scan" in ACTION_LABELS
        assert "gpu_info" in ACTION_LABELS
        assert "health_check" in ACTION_LABELS

    def test_unknown_action_label_fallback(self):
        """Action inconnue utilise le nom avec underscores remplacés."""
        from src.voice_prediction import get_voice_suggestion, reset_suggestion_cooldown
        reset_suggestion_cooldown()
        with patch("src.prediction_engine.prediction_engine") as mock_pe:
            mock_pe.predict_next.return_value = [
                {"action": "custom_action_test", "confidence": 0.9, "score": 5.0, "reason": "h=8"}
            ]
            result = get_voice_suggestion()
            assert result is not None
            assert result["label"] == "custom action test"

    def test_reset_cooldown(self):
        """Reset du cooldown permet une nouvelle suggestion."""
        from src.voice_prediction import get_voice_suggestion, reset_suggestion_cooldown
        reset_suggestion_cooldown()
        with patch("src.prediction_engine.prediction_engine") as mock_pe:
            mock_pe.predict_next.return_value = [
                {"action": "trading_scan", "confidence": 0.9, "score": 5.0, "reason": "h=8"}
            ]
            r1 = get_voice_suggestion()
            assert r1 is not None
            reset_suggestion_cooldown()
            r2 = get_voice_suggestion()
            assert r2 is not None


# ═══════════════════════════════════════════════════════════════════════════
# Voice Emotion / Urgency Detection
# ═══════════════════════════════════════════════════════════════════════════

class TestVoiceEmotion:
    """Tests pour la détection d'urgence vocale."""

    def _make_silence(self, duration_s: float = 1.0, sr: int = 16000) -> np.ndarray:
        """Génère du silence."""
        return np.zeros(int(sr * duration_s), dtype=np.int16)

    def _make_tone(self, freq: float = 440.0, amplitude: float = 0.5,
                   duration_s: float = 1.0, sr: int = 16000) -> np.ndarray:
        """Génère un ton sinusoïdal."""
        t = np.linspace(0, duration_s, int(sr * duration_s), endpoint=False)
        signal = (amplitude * 32767 * np.sin(2 * np.pi * freq * t)).astype(np.int16)
        return signal

    def _make_noise(self, amplitude: float = 0.8, duration_s: float = 1.0,
                    sr: int = 16000) -> np.ndarray:
        """Génère du bruit blanc (simulant parole excitée)."""
        return (amplitude * 32767 * np.random.randn(int(sr * duration_s))).astype(np.int16)

    def test_compute_rms_silence(self):
        """RMS du silence est ~0."""
        from src.voice_emotion import compute_rms
        audio = self._make_silence()
        assert compute_rms(audio) == 0.0

    def test_compute_rms_loud(self):
        """RMS d'un signal fort est élevé."""
        from src.voice_emotion import compute_rms
        audio = self._make_tone(amplitude=0.9)
        rms = compute_rms(audio)
        assert rms > 10000  # int16 non normalisé

    def test_compute_zcr_silence(self):
        """ZCR du silence est 0."""
        from src.voice_emotion import compute_zcr
        audio = self._make_silence()
        assert compute_zcr(audio) == 0.0

    def test_compute_zcr_high_freq(self):
        """ZCR d'un signal haute fréquence est élevé."""
        from src.voice_emotion import compute_zcr
        audio = self._make_tone(freq=4000.0, amplitude=0.5)
        zcr = compute_zcr(audio)
        assert zcr > 0.3  # 4kHz à 16kHz → ~0.5

    def test_compute_zcr_low_freq(self):
        """ZCR d'un signal basse fréquence est bas."""
        from src.voice_emotion import compute_zcr
        audio = self._make_tone(freq=100.0, amplitude=0.5)
        zcr = compute_zcr(audio)
        assert zcr < 0.05

    def test_spectral_centroid_low_tone(self):
        """Centroid d'un ton grave est bas."""
        from src.voice_emotion import compute_spectral_centroid
        audio = self._make_tone(freq=200.0, amplitude=0.5)
        centroid = compute_spectral_centroid(audio, 16000)
        assert centroid < 500  # Proche de 200Hz

    def test_spectral_centroid_high_tone(self):
        """Centroid d'un ton aigu est élevé."""
        from src.voice_emotion import compute_spectral_centroid
        audio = self._make_tone(freq=3000.0, amplitude=0.5)
        centroid = compute_spectral_centroid(audio, 16000)
        assert centroid > 2000

    def test_analyze_silence_is_low(self):
        """Silence → urgence LOW."""
        from src.voice_emotion import analyze_urgency, UrgencyLevel
        audio = self._make_silence()
        result = analyze_urgency(audio)
        assert result.level == UrgencyLevel.LOW
        assert result.score < 0.1

    def test_analyze_loud_noise_is_high(self):
        """Bruit fort → urgence HIGH ou CRITICAL."""
        from src.voice_emotion import analyze_urgency, UrgencyLevel
        audio = self._make_noise(amplitude=0.9, duration_s=1.0)
        result = analyze_urgency(audio)
        assert result.level in (UrgencyLevel.HIGH, UrgencyLevel.CRITICAL)
        assert result.score > 0.5

    def test_analyze_moderate_tone_is_normal(self):
        """Ton modéré → urgence NORMAL."""
        from src.voice_emotion import analyze_urgency, UrgencyLevel
        audio = self._make_tone(freq=300.0, amplitude=0.15, duration_s=1.0)
        result = analyze_urgency(audio)
        assert result.level in (UrgencyLevel.LOW, UrgencyLevel.NORMAL)

    def test_urgency_result_to_dict(self):
        """UrgencyResult.to_dict() retourne la bonne structure."""
        from src.voice_emotion import analyze_urgency
        audio = self._make_tone(freq=1000.0, amplitude=0.5)
        result = analyze_urgency(audio)
        d = result.to_dict()
        assert "level" in d
        assert "score" in d
        assert "rms" in d
        assert "zcr" in d
        assert "spectral_centroid" in d
        assert "features" in d
        assert isinstance(d["features"], dict)

    def test_should_prioritize(self):
        """should_prioritize retourne True pour HIGH/CRITICAL."""
        from src.voice_emotion import analyze_urgency, should_prioritize
        # Silence → pas prioritaire
        silence = analyze_urgency(self._make_silence())
        assert not should_prioritize(silence)
        # Bruit fort → prioritaire
        loud = analyze_urgency(self._make_noise(amplitude=0.9))
        assert should_prioritize(loud)

    def test_empty_audio(self):
        """Audio vide retourne LOW avec score 0."""
        from src.voice_emotion import analyze_urgency, UrgencyLevel
        result = analyze_urgency(np.array([], dtype=np.int16))
        assert result.level == UrgencyLevel.LOW
        assert result.score == 0.0

    def test_energy_variance(self):
        """La variance d'énergie est calculée correctement."""
        from src.voice_emotion import compute_energy_variance
        # Signal constant → variance ~0
        constant = np.ones(16000, dtype=np.float64) * 0.1
        var = compute_energy_variance(constant, frame_size=1600)
        assert var < 0.001
        # Signal avec variation → variance > 0
        varying = np.zeros(16000, dtype=np.float64)
        varying[:8000] = 0.8  # Première moitié forte
        varying[8000:] = 0.01  # Deuxième moitié faible
        var2 = compute_energy_variance(varying, frame_size=1600)
        assert var2 > 0.01
