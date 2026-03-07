"""Tests for src/voice.py — Voice interface: cache, WhisperWorker, TTS, analysis.

Covers: _cache_get/_cache_set, _find_system_python, WhisperWorker,
analyze_with_lm, speak_text, _save_wav, check_microphone.
"""

from __future__ import annotations

import asyncio
import sys
import tempfile
import wave
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import numpy as np
import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.voice import (
    _cache_get, _cache_set, _command_cache, _cache_lock, _CACHE_MAX,
    _find_system_python, _save_wav,
    WhisperWorker,
    SAMPLE_RATE, CHANNELS,
)


# ===========================================================================
# Cache
# ===========================================================================

class TestCache:
    def setup_method(self):
        with _cache_lock:
            _command_cache.clear()

    def test_cache_miss(self):
        assert _cache_get("nonexistent") is None

    def test_cache_set_and_get(self):
        _cache_set("hello jarvis", {"intent": "hello", "confidence": 0.9})
        result = _cache_get("hello jarvis")
        assert result is not None
        assert result["intent"] == "hello"

    def test_cache_case_insensitive(self):
        _cache_set("HELLO", {"intent": "hi"})
        assert _cache_get("hello") is not None
        assert _cache_get("  HELLO  ") is not None

    def test_cache_strips_whitespace(self):
        _cache_set("  test  ", {"v": 1})
        assert _cache_get("test") is not None

    def test_cache_eviction(self):
        for i in range(_CACHE_MAX + 5):
            _cache_set(f"cmd_{i}", {"i": i})
        with _cache_lock:
            assert len(_command_cache) <= _CACHE_MAX

    def test_cache_overwrite(self):
        _cache_set("key", {"v": 1})
        _cache_set("key", {"v": 2})
        assert _cache_get("key")["v"] == 2


# ===========================================================================
# _find_system_python
# ===========================================================================

class TestFindSystemPython:
    def test_returns_path(self):
        result = _find_system_python()
        assert isinstance(result, Path)

    def test_finds_via_which(self):
        with patch("shutil.which", return_value="C:\\Python313\\python.exe"):
            result = _find_system_python()
        assert "python" in str(result).lower()

    def test_skips_venv(self):
        def fake_which(name):
            if name == "python3":
                return "C:\\project\\.venv\\Scripts\\python.exe"
            if name == "python":
                return "C:\\Python313\\python.exe"
            return None
        with patch("shutil.which", side_effect=fake_which):
            result = _find_system_python()
        assert ".venv" not in str(result)

    def test_fallback_appdata(self):
        with patch("shutil.which", return_value=None):
            result = _find_system_python()
        assert isinstance(result, Path)


# ===========================================================================
# _save_wav
# ===========================================================================

class TestSaveWav:
    def test_creates_valid_wav(self):
        audio = np.zeros(16000, dtype=np.int16)  # 1s silence
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            path = f.name
        try:
            _save_wav(audio, path)
            with wave.open(path, 'rb') as wf:
                assert wf.getnchannels() == CHANNELS
                assert wf.getframerate() == SAMPLE_RATE
                assert wf.getsampwidth() == 2
                assert wf.getnframes() == 16000
        finally:
            Path(path).unlink(missing_ok=True)

    def test_short_audio(self):
        audio = np.array([100, -100, 200], dtype=np.int16)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            path = f.name
        try:
            _save_wav(audio, path)
            assert Path(path).stat().st_size > 44  # WAV header is 44 bytes
        finally:
            Path(path).unlink(missing_ok=True)


# ===========================================================================
# WhisperWorker
# ===========================================================================

class TestWhisperWorker:
    def test_init(self):
        w = WhisperWorker()
        assert w._process is None
        assert w._ready is False

    def test_start_missing_files(self):
        w = WhisperWorker()
        with patch("src.voice.SYSTEM_PYTHON", Path("C:\\nonexistent\\python.exe")):
            assert w.start() is False

    def test_start_success(self):
        w = WhisperWorker()
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_proc.stdout.readline.side_effect = [
            "WHISPER_READY model=large-v3-turbo\n",
            "WHISPER_LOADED in 2.5s\n",
        ]
        with patch("src.voice.SYSTEM_PYTHON", Path(__file__)), \
             patch("src.voice.WHISPER_WORKER_SCRIPT", Path(__file__)), \
             patch("subprocess.Popen", return_value=mock_proc):
            assert w.start() is True
            assert w._ready is True

    def test_start_failure_kills_process(self):
        w = WhisperWorker()
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_proc.stdout.readline.side_effect = ["SOMETHING_ELSE\n", "NO_LOADED\n"]
        with patch("src.voice.SYSTEM_PYTHON", Path(__file__)), \
             patch("src.voice.WHISPER_WORKER_SCRIPT", Path(__file__)), \
             patch("subprocess.Popen", return_value=mock_proc):
            assert w.start() is False
            mock_proc.kill.assert_called_once()

    def test_start_os_error(self):
        w = WhisperWorker()
        with patch("src.voice.SYSTEM_PYTHON", Path(__file__)), \
             patch("src.voice.WHISPER_WORKER_SCRIPT", Path(__file__)), \
             patch("subprocess.Popen", side_effect=OSError("No python")):
            assert w.start() is False

    def test_transcribe_no_process(self):
        w = WhisperWorker()
        with patch.object(w, "start", return_value=False):
            assert w.transcribe("test.wav") is None

    def test_transcribe_success(self):
        w = WhisperWorker()
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_proc.stdout.readline.side_effect = [
            "SEGMENT: bonjour\n",
            "DONE: bonjour jarvis\n",
        ]
        w._process = mock_proc
        w._ready = True
        result = w.transcribe("test.wav")
        assert result == "bonjour jarvis"

    def test_transcribe_empty_response(self):
        w = WhisperWorker()
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_proc.stdout.readline.return_value = ""
        w._process = mock_proc
        w._ready = True
        assert w.transcribe("test.wav") is None

    def test_transcribe_broken_pipe(self):
        w = WhisperWorker()
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_proc.stdin.write.side_effect = BrokenPipeError()
        w._process = mock_proc
        w._ready = True
        assert w.transcribe("test.wav") is None
        assert w._ready is False

    def test_stop(self):
        w = WhisperWorker()
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        w._process = mock_proc
        w._ready = True
        w.stop()
        mock_proc.stdin.write.assert_called_with("QUIT\n")
        assert w._ready is False

    def test_stop_broken_pipe(self):
        w = WhisperWorker()
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_proc.stdin.write.side_effect = BrokenPipeError()
        w._process = mock_proc
        w.stop()
        mock_proc.kill.assert_called_once()


# ===========================================================================
# analyze_with_lm (async)
# ===========================================================================

class TestAnalyzeWithLm:
    @pytest.mark.asyncio
    async def test_success(self):
        from src.voice import analyze_with_lm
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "message": {"content": '{"corrected": "ouvre chrome", "intent": "ouvre chrome", "confidence": 0.95}'}
        }
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await analyze_with_lm("ouvre chrome")
        assert result["corrected"] == "ouvre chrome"
        assert result["confidence"] == 0.95

    @pytest.mark.asyncio
    async def test_json_with_markdown(self):
        from src.voice import analyze_with_lm
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "message": {"content": '```json\n{"corrected": "test", "intent": "test", "confidence": 0.8}\n```'}
        }
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await analyze_with_lm("test")
        assert result["corrected"] == "test"

    @pytest.mark.asyncio
    async def test_http_error_fallback(self):
        from src.voice import analyze_with_lm
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await analyze_with_lm("raw text")
        assert result["corrected"] == "raw text"
        assert result["confidence"] == 0.5

    @pytest.mark.asyncio
    async def test_connect_error_fallback(self):
        from src.voice import analyze_with_lm
        import httpx
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("offline"))
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await analyze_with_lm("raw text")
        assert result["corrected"] == "raw text"
        assert result["confidence"] == 0.5

    @pytest.mark.asyncio
    async def test_invalid_json_fallback(self):
        from src.voice import analyze_with_lm
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"message": {"content": "not json at all"}}
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await analyze_with_lm("raw")
        assert result["corrected"] == "raw"


# ===========================================================================
# speak_text (async)
# ===========================================================================

class TestSpeakText:
    @pytest.mark.asyncio
    async def test_empty_text(self):
        from src.voice import speak_text
        assert await speak_text("") is False
        assert await speak_text("   ") is False

    @pytest.mark.asyncio
    async def test_success(self):
        from src.voice import speak_text
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result):
            result = await speak_text("Bonjour")
        assert result is True

    @pytest.mark.asyncio
    async def test_failure(self):
        from src.voice import speak_text
        mock_result = MagicMock()
        mock_result.returncode = 1
        with patch("subprocess.run", return_value=mock_result):
            result = await speak_text("Test")
        assert result is False

    @pytest.mark.asyncio
    async def test_timeout(self):
        import subprocess
        from src.voice import speak_text
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 30)):
            result = await speak_text("Long text")
        assert result is False

    @pytest.mark.asyncio
    async def test_sanitizes_voice(self):
        from src.voice import speak_text
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result):
            result = await speak_text("test", voice="EVIL;DROP TABLE")
        assert result is True  # defaults to fr-FR

    @pytest.mark.asyncio
    async def test_truncates_long_text(self):
        from src.voice import speak_text
        mock_result = MagicMock()
        mock_result.returncode = 0
        long_text = "A" * 1000
        with patch("subprocess.run", return_value=mock_result) as mock:
            await speak_text(long_text)
        # The PS script should have truncated text
        assert mock.called


# ===========================================================================
# check_microphone
# ===========================================================================

class TestCheckMicrophone:
    def test_with_mocked_device(self):
        from src.voice import _mic_cache
        # Reset cache
        _mic_cache["ts"] = None
        with patch("src.voice._get_input_device", return_value=0):
            from src.voice import check_microphone
            assert check_microphone() is True

    def test_no_device(self):
        from src.voice import _mic_cache
        _mic_cache["ts"] = None
        with patch("src.voice._get_input_device", return_value=None):
            from src.voice import check_microphone
            assert check_microphone() is False

    def test_cached_result(self):
        import time
        from src.voice import _mic_cache, check_microphone
        _mic_cache["ok"] = True
        _mic_cache["ts"] = time.monotonic()
        _mic_cache["device"] = 0
        # Should return cached value without calling _get_input_device
        assert check_microphone() is True
