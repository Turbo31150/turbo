"""Tests for src/tts_streaming.py — Edge TTS with chunked streaming playback.

Covers: _cache_key, _get_cached, _save_to_cache, _split_sentences,
speak_streaming, speak_sentence_streaming, speak_quick, speak_interruptible,
clear_tts_cache.
Edge TTS and subprocess calls are mocked.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.tts_streaming import (
    _cache_key, _get_cached, _save_to_cache, _split_sentences,
    speak_streaming, speak_sentence_streaming, speak_quick,
    speak_interruptible, clear_tts_cache,
)


# ===========================================================================
# _cache_key
# ===========================================================================

class TestCacheKey:
    def test_deterministic(self):
        k1 = _cache_key("hello", "voice1", "+10%")
        k2 = _cache_key("hello", "voice1", "+10%")
        assert k1 == k2

    def test_different_text(self):
        k1 = _cache_key("hello", "voice1", "+10%")
        k2 = _cache_key("world", "voice1", "+10%")
        assert k1 != k2


# ===========================================================================
# _get_cached / _save_to_cache
# ===========================================================================

class TestCache:
    def test_get_cached_miss(self, tmp_path):
        with patch("src.tts_streaming._CACHE_DIR", tmp_path):
            result = _get_cached("uncached text", "voice", "+10%")
        assert result is None

    def test_save_and_get(self, tmp_path):
        with patch("src.tts_streaming._CACHE_DIR", tmp_path):
            saved = _save_to_cache("hello", "voice", "+10%", b"audio_data")
            assert saved.exists()
            result = _get_cached("hello", "voice", "+10%")
            assert result is not None
            assert result.read_bytes() == b"audio_data"

    def test_cache_eviction(self, tmp_path):
        with patch("src.tts_streaming._CACHE_DIR", tmp_path), \
             patch("src.tts_streaming._CACHE_MAX_FILES", 3):
            for i in range(5):
                _save_to_cache(f"text{i}", "voice", "+10%", b"data")
            files = list(tmp_path.glob("*.mp3"))
            assert len(files) <= 3


# ===========================================================================
# _split_sentences
# ===========================================================================

class TestSplitSentences:
    def test_single_sentence(self):
        result = _split_sentences("Hello world.")
        assert len(result) == 1

    def test_multiple_sentences(self):
        result = _split_sentences("First sentence. Second sentence! Third one?")
        assert len(result) >= 1  # may merge short ones

    def test_empty(self):
        result = _split_sentences("")
        assert result == [""]

    def test_merges_short(self):
        result = _split_sentences("Hi. Ok. Sure.")
        # Short sentences get merged (all < 80 chars combined)
        assert len(result) == 1


# ===========================================================================
# speak_streaming (mocked)
# ===========================================================================

class TestSpeakStreaming:
    @pytest.mark.asyncio
    async def test_empty_text(self):
        await speak_streaming("")  # should not crash

    @pytest.mark.asyncio
    async def test_cached_text(self, tmp_path):
        cached_file = tmp_path / "abc123.mp3"
        cached_file.write_bytes(b"audio")
        with patch("src.tts_streaming._get_cached", return_value=cached_file), \
             patch("src.tts_streaming._play_audio", new_callable=AsyncMock):
            await speak_streaming("cached text")

    @pytest.mark.asyncio
    async def test_generate_and_cache(self, tmp_path):
        mock_communicate = MagicMock()

        async def fake_stream():
            yield {"type": "audio", "data": b"chunk1"}
            yield {"type": "audio", "data": b"chunk2"}

        mock_communicate.stream = fake_stream
        with patch("src.tts_streaming._get_cached", return_value=None), \
             patch("src.tts_streaming._save_to_cache", return_value=tmp_path / "out.mp3"), \
             patch("src.tts_streaming._play_audio", new_callable=AsyncMock), \
             patch("edge_tts.Communicate", return_value=mock_communicate):
            await speak_streaming("Hello world")


# ===========================================================================
# speak_sentence_streaming
# ===========================================================================

class TestSpeakSentenceStreaming:
    @pytest.mark.asyncio
    async def test_empty(self):
        await speak_sentence_streaming("")  # no crash

    @pytest.mark.asyncio
    async def test_calls_speak_streaming(self):
        with patch("src.tts_streaming.speak_streaming", new_callable=AsyncMock) as mock:
            await speak_sentence_streaming("First. Second.")
        assert mock.call_count >= 1


# ===========================================================================
# speak_quick
# ===========================================================================

class TestSpeakQuick:
    @pytest.mark.asyncio
    async def test_calls_speak_streaming(self):
        with patch("src.tts_streaming.speak_streaming", new_callable=AsyncMock) as mock:
            await speak_quick("OK")
        mock.assert_called_once()


# ===========================================================================
# speak_interruptible
# ===========================================================================

class TestSpeakInterruptible:
    @pytest.mark.asyncio
    async def test_completes(self):
        with patch("src.tts_streaming.speak_streaming", new_callable=AsyncMock):
            result = await speak_interruptible("Hello world.")
        assert result is True

    @pytest.mark.asyncio
    async def test_interrupted(self):
        event = asyncio.Event()
        event.set()  # already interrupted
        result = await speak_interruptible("Hello world.", interrupt_event=event)
        assert result is False

    @pytest.mark.asyncio
    async def test_empty_text(self):
        result = await speak_interruptible("")
        assert result is True


# ===========================================================================
# clear_tts_cache
# ===========================================================================

class TestClearCache:
    def test_clear(self, tmp_path):
        (tmp_path / "a.mp3").write_bytes(b"x")
        (tmp_path / "b.mp3").write_bytes(b"x")
        with patch("src.tts_streaming._CACHE_DIR", tmp_path):
            removed = clear_tts_cache()
        assert removed == 2

    def test_clear_nonexistent(self, tmp_path):
        with patch("src.tts_streaming._CACHE_DIR", tmp_path / "nonexistent"):
            removed = clear_tts_cache()
        assert removed == 0
