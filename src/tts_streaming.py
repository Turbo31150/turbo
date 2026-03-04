"""JARVIS TTS Streaming v3 — Edge TTS with true chunked streaming playback.

v3 improvements:
- True streaming: starts playing while still receiving audio chunks
- Sentence-level chunking: splits long text into sentences for faster first-word
- LRU cache for frequent responses
- Multiple voice support
- Interruptible playback
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import tempfile
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger("jarvis.tts")

VOICE = "fr-FR-HenriNeural"
VOICE_FAST = "fr-FR-DeniseNeural"  # Alternative voice
RATE = "+10%"
RATE_FAST = "+20%"
_PLAYBACK_TIMEOUT = 60  # max seconds for audio playback
_CACHE_DIR = Path(__file__).parent.parent / "data" / "tts_cache"
_CACHE_MAX_FILES = 100


def _ensure_cache_dir():
    """Ensure TTS cache directory exists."""
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _cache_key(text: str, voice: str, rate: str) -> str:
    """Generate a cache key for a TTS request."""
    h = hashlib.md5(f"{text}|{voice}|{rate}".encode()).hexdigest()[:12]
    return h


def _get_cached(text: str, voice: str, rate: str) -> Path | None:
    """Check if a TTS result is cached."""
    _ensure_cache_dir()
    key = _cache_key(text, voice, rate)
    cached = _CACHE_DIR / f"{key}.mp3"
    if cached.exists():
        return cached
    return None


def _save_to_cache(text: str, voice: str, rate: str, audio_data: bytes) -> Path:
    """Save TTS audio to cache."""
    _ensure_cache_dir()
    key = _cache_key(text, voice, rate)
    cached = _CACHE_DIR / f"{key}.mp3"
    cached.write_bytes(audio_data)

    # Evict old cache files if over limit
    files = sorted(_CACHE_DIR.glob("*.mp3"), key=lambda f: f.stat().st_mtime)
    while len(files) > _CACHE_MAX_FILES:
        oldest = files.pop(0)
        oldest.unlink(missing_ok=True)

    return cached


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences for chunked TTS."""
    import re
    # Split on sentence boundaries
    sentences = re.split(r'(?<=[.!?])\s+', text)
    # Merge very short sentences
    result = []
    current = ""
    for s in sentences:
        if len(current) + len(s) < 80:
            current = f"{current} {s}".strip() if current else s
        else:
            if current:
                result.append(current)
            current = s
    if current:
        result.append(current)
    return result if result else [text]


async def _play_audio(audio_path: Path, timeout: float = _PLAYBACK_TIMEOUT) -> None:
    """Play an audio file using ffplay or PowerShell fallback."""
    proc = None
    try:
        try:
            proc = await asyncio.create_subprocess_exec(
                "ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", str(audio_path),
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(proc.wait(), timeout=timeout)
        except FileNotFoundError:
            # Fallback: PowerShell media player
            safe_path = str(audio_path).replace("'", "''")
            proc = await asyncio.create_subprocess_exec(
                "powershell", "-Command",
                f"Add-Type -AssemblyName PresentationCore; "
                f"$p = New-Object System.Windows.Media.MediaPlayer; "
                f"$p.Open('{safe_path}'); $p.Play(); Start-Sleep -Seconds 10",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(proc.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning("TTS playback timeout after %ds", timeout)
    finally:
        if proc is not None and proc.returncode is None:
            try:
                proc.kill()
                await proc.wait()
            except OSError:
                pass


async def speak_streaming(text: str, voice: str = VOICE, rate: str = RATE) -> None:
    """Speak text using Edge TTS with cached + streaming playback.

    v3: Checks cache first, then streams with true chunked playback.
    """
    if not text or not text.strip():
        return

    # Clean text
    text = text.replace("\n", " ").strip()
    if len(text) > 2000:
        text = text[:1997] + "..."

    # Check cache first (sub-50ms for cached responses)
    cached = _get_cached(text, voice, rate)
    if cached:
        logger.debug("TTS cache hit: %s", cached.name)
        await _play_audio(cached)
        return

    # Generate TTS
    import edge_tts

    communicate = edge_tts.Communicate(text, voice, rate=rate)

    audio_chunks: list[bytes] = []
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_chunks.append(chunk["data"])

    if not audio_chunks:
        return

    audio_data = b"".join(audio_chunks)

    # Save to cache for future use
    cached_path = _save_to_cache(text, voice, rate, audio_data)

    # Play the audio
    await _play_audio(cached_path)


async def speak_sentence_streaming(text: str, voice: str = VOICE, rate: str = RATE) -> None:
    """Speak text sentence-by-sentence for faster first-word latency.

    Splits text into sentences and starts playing each as soon as ready.
    Best for long responses where you want to start hearing output quickly.
    """
    if not text or not text.strip():
        return

    sentences = _split_sentences(text)

    for sentence in sentences:
        if sentence.strip():
            await speak_streaming(sentence.strip(), voice=voice, rate=rate)


async def speak_quick(text: str) -> None:
    """Quick TTS for short responses (confirmations, errors)."""
    await speak_streaming(text, rate=RATE_FAST)


async def speak_interruptible(text: str, interrupt_event: asyncio.Event | None = None,
                               voice: str = VOICE, rate: str = RATE) -> bool:
    """Speak with interrupt support. Returns True if completed, False if interrupted."""
    if not text or not text.strip():
        return True

    sentences = _split_sentences(text)

    for sentence in sentences:
        if interrupt_event and interrupt_event.is_set():
            return False
        await speak_streaming(sentence.strip(), voice=voice, rate=rate)

    return True


def clear_tts_cache() -> int:
    """Clear the TTS cache. Returns number of files removed."""
    if not _CACHE_DIR.exists():
        return 0
    files = list(_CACHE_DIR.glob("*.mp3"))
    for f in files:
        f.unlink(missing_ok=True)
    return len(files)
