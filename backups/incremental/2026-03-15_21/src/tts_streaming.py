"""JARVIS TTS Streaming v4 — Edge TTS + Piper offline fallback.

v4 improvements:
- Piper TTS offline fallback when Edge TTS fails (network down)
- Voice selection (Denise, Henri, Vivienne)
- Adaptive rate based on text length
- Linux-native audio playback (ffplay/paplay)
- Interruptible playback
- LRU cache for frequent responses (mp3 for Edge, wav for Piper)
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import shutil
import struct
import tempfile
from pathlib import Path

logger = logging.getLogger("jarvis.tts")

# ---------------------------------------------------------------------------
# Voice configuration
# ---------------------------------------------------------------------------
VOICES: dict[str, str] = {
    "denise": "fr-FR-DeniseNeural",          # Female (default)
    "henri": "fr-FR-HenriNeural",            # Male
    "vivienne": "fr-FR-VivienneMultilingualNeural",  # Female multilingual
}
DEFAULT_VOICE = "denise"

VOICE = VOICES[DEFAULT_VOICE]
VOICE_FAST = VOICES[DEFAULT_VOICE]

# ---------------------------------------------------------------------------
# Adaptive rate thresholds
# ---------------------------------------------------------------------------
RATE_FAST = "+20%"   # Short text (<50 chars)
RATE = "+10%"        # Medium text (50-200 chars)
RATE_SLOW = "+5%"    # Long text (>200 chars)

_PLAYBACK_TIMEOUT = 60  # max seconds for audio playback
_CACHE_DIR = Path(__file__).parent.parent / "data" / "tts_cache"
_CACHE_MAX_FILES = 100

# ---------------------------------------------------------------------------
# Piper TTS configuration
# ---------------------------------------------------------------------------
_PIPER_BINARY = Path("/home/turbo/jarvis/.venv/bin/piper")
_PIPER_MODEL = Path("/home/turbo/jarvis/data/piper/fr_FR-siwis-medium.onnx")
_PIPER_SAMPLE_RATE = 22050
_PIPER_CHANNELS = 1
_PIPER_SAMPLE_WIDTH = 2  # S16_LE = 2 bytes


def _find_piper() -> str | None:
    """Locate the Piper binary. Returns path or None."""
    if _PIPER_BINARY.exists():
        return str(_PIPER_BINARY)
    found = shutil.which("piper")
    return found


def _adaptive_rate(text: str) -> str:
    """Select TTS rate based on text length."""
    length = len(text.strip())
    if length < 50:
        return RATE_FAST
    elif length <= 200:
        return RATE
    else:
        return RATE_SLOW


def _resolve_voice(voice: str) -> str:
    """Resolve a voice name or alias to the Edge TTS voice ID."""
    # If it's already a full Edge TTS voice ID, return as-is
    if "-" in voice and "Neural" in voice:
        return voice
    # Look up alias
    return VOICES.get(voice.lower(), VOICES[DEFAULT_VOICE])


# ---------------------------------------------------------------------------
# Cache management
# ---------------------------------------------------------------------------

def _ensure_cache_dir():
    """Ensure TTS cache directory exists."""
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _cache_key(text: str, voice: str, rate: str) -> str:
    """Generate a cache key for a TTS request."""
    h = hashlib.md5(f"{text}|{voice}|{rate}".encode()).hexdigest()[:12]
    return h


def _get_cached(text: str, voice: str, rate: str, ext: str = ".mp3") -> Path | None:
    """Check if a TTS result is cached. Checks both .mp3 and .wav."""
    _ensure_cache_dir()
    key = _cache_key(text, voice, rate)
    # Check requested extension first, then the other
    for suffix in [ext, ".mp3", ".wav"]:
        cached = _CACHE_DIR / f"{key}{suffix}"
        if cached.exists():
            return cached
    return None


def _save_to_cache(text: str, voice: str, rate: str, audio_data: bytes,
                   ext: str = ".mp3") -> Path:
    """Save TTS audio to cache."""
    _ensure_cache_dir()
    key = _cache_key(text, voice, rate)
    cached = _CACHE_DIR / f"{key}{ext}"
    cached.write_bytes(audio_data)

    # Evict old cache files if over limit
    files = sorted(
        list(_CACHE_DIR.glob("*.mp3")) + list(_CACHE_DIR.glob("*.wav")),
        key=lambda f: f.stat().st_mtime,
    )
    while len(files) > _CACHE_MAX_FILES:
        oldest = files.pop(0)
        oldest.unlink(missing_ok=True)

    return cached


def _pcm_to_wav(pcm_data: bytes, sample_rate: int = _PIPER_SAMPLE_RATE,
                channels: int = _PIPER_CHANNELS,
                sample_width: int = _PIPER_SAMPLE_WIDTH) -> bytes:
    """Wrap raw PCM data in a WAV header."""
    data_size = len(pcm_data)
    # WAV header (44 bytes)
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + data_size,           # ChunkSize
        b"WAVE",
        b"fmt ",
        16,                       # Subchunk1Size (PCM)
        1,                        # AudioFormat (PCM)
        channels,
        sample_rate,
        sample_rate * channels * sample_width,  # ByteRate
        channels * sample_width,  # BlockAlign
        sample_width * 8,         # BitsPerSample
        b"data",
        data_size,
    )
    return header + pcm_data


# ---------------------------------------------------------------------------
# Text splitting
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Audio playback
# ---------------------------------------------------------------------------

async def _play_audio(audio_path: Path, timeout: float = _PLAYBACK_TIMEOUT) -> None:
    """Play an audio file using ffplay, paplay, or aplay fallback."""
    proc = None
    suffix = audio_path.suffix.lower()

    try:
        # Try ffplay first (handles mp3 + wav)
        try:
            proc = await asyncio.create_subprocess_exec(
                "ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet",
                str(audio_path),
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(proc.wait(), timeout=timeout)
            if proc.returncode == 0:
                return
        except (FileNotFoundError, asyncio.TimeoutError):
            pass

        # Fallback: paplay (PulseAudio — handles wav and mp3)
        try:
            proc = await asyncio.create_subprocess_exec(
                "paplay", str(audio_path),
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(proc.wait(), timeout=timeout)
            if proc.returncode == 0:
                return
        except (FileNotFoundError, asyncio.TimeoutError):
            pass

        # Fallback: aplay (ALSA — wav only)
        if suffix == ".wav":
            try:
                proc = await asyncio.create_subprocess_exec(
                    "aplay", "-q", str(audio_path),
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                await asyncio.wait_for(proc.wait(), timeout=timeout)
                return
            except (FileNotFoundError, asyncio.TimeoutError):
                pass

        logger.warning("No audio player available for %s", audio_path)

    except asyncio.TimeoutError:
        logger.warning("TTS playback timeout after %ds", timeout)
    finally:
        if proc is not None and proc.returncode is None:
            try:
                proc.kill()
                await proc.wait()
            except OSError:
                pass


async def _play_raw_pcm(pcm_data: bytes, timeout: float = _PLAYBACK_TIMEOUT) -> None:
    """Play raw PCM audio via aplay (Linux ALSA)."""
    proc = None
    try:
        proc = await asyncio.create_subprocess_exec(
            "aplay", "-r", str(_PIPER_SAMPLE_RATE), "-f", "S16_LE",
            "-t", "raw", "-c", str(_PIPER_CHANNELS), "-q",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await asyncio.wait_for(proc.communicate(input=pcm_data), timeout=timeout)
    except FileNotFoundError:
        logger.warning("aplay not found, cannot play raw PCM")
    except asyncio.TimeoutError:
        logger.warning("Raw PCM playback timeout after %ds", timeout)
    finally:
        if proc is not None and proc.returncode is None:
            try:
                proc.kill()
                await proc.wait()
            except OSError:
                pass


# ---------------------------------------------------------------------------
# Piper TTS (offline)
# ---------------------------------------------------------------------------

async def speak_piper(text: str) -> bool:
    """Speak using local Piper TTS (100% offline).

    Returns True if playback succeeded, False otherwise.
    """
    if not text or not text.strip():
        return True

    text = text.replace("\n", " ").strip()
    if len(text) > 2000:
        text = text[:1997] + "..."

    piper_bin = _find_piper()
    if not piper_bin:
        logger.error("Piper binary not found")
        return False

    if not _PIPER_MODEL.exists():
        logger.error("Piper model not found: %s", _PIPER_MODEL)
        return False

    # Check cache (use "piper" as voice identifier)
    rate = _adaptive_rate(text)
    cached = _get_cached(text, "piper", rate, ext=".wav")
    if cached:
        logger.debug("Piper cache hit: %s", cached.name)
        await _play_audio(cached)
        return True

    # Generate with Piper (outputs raw PCM to stdout)
    try:
        proc = await asyncio.create_subprocess_exec(
            piper_bin,
            "--model", str(_PIPER_MODEL),
            "--output-raw",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        pcm_data, _ = await asyncio.wait_for(
            proc.communicate(input=text.encode("utf-8")),
            timeout=30,
        )
    except FileNotFoundError:
        logger.error("Piper binary not executable: %s", piper_bin)
        return False
    except asyncio.TimeoutError:
        logger.error("Piper TTS generation timeout")
        return False
    except Exception as exc:
        logger.error("Piper TTS error: %s", exc)
        return False

    if not pcm_data:
        logger.warning("Piper produced no audio data")
        return False

    # Convert to WAV and cache
    wav_data = _pcm_to_wav(pcm_data)
    cached_path = _save_to_cache(text, "piper", rate, wav_data, ext=".wav")
    logger.debug("Piper TTS cached: %s (%d bytes)", cached_path.name, len(wav_data))

    # Play the audio
    await _play_audio(cached_path)
    return True


# ---------------------------------------------------------------------------
# Edge TTS (online) with Piper fallback
# ---------------------------------------------------------------------------

async def speak_streaming(text: str, voice: str = VOICE, rate: str | None = None) -> None:
    """Speak text using Edge TTS with cached + streaming playback.

    Falls back to Piper TTS if Edge TTS fails (network error, etc.).
    If rate is None, adaptive rate is used based on text length.
    """
    if not text or not text.strip():
        return

    # Clean text
    text = text.replace("\n", " ").strip()
    if len(text) > 2000:
        text = text[:1997] + "..."

    # Resolve voice alias
    voice = _resolve_voice(voice)

    # Adaptive rate if not specified
    if rate is None:
        rate = _adaptive_rate(text)

    # Check cache first (sub-50ms for cached responses)
    cached = _get_cached(text, voice, rate)
    if cached:
        logger.debug("TTS cache hit: %s", cached.name)
        await _play_audio(cached)
        return

    # Try Edge TTS (online)
    try:
        import edge_tts

        communicate = edge_tts.Communicate(text, voice, rate=rate)

        audio_chunks: list[bytes] = []
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_chunks.append(chunk["data"])

        if not audio_chunks:
            logger.warning("Edge TTS returned no audio, falling back to Piper")
            await speak_piper(text)
            return

        audio_data = b"".join(audio_chunks)

        # Save to cache for future use
        cached_path = _save_to_cache(text, voice, rate, audio_data, ext=".mp3")

        # Play the audio
        await _play_audio(cached_path)

    except ImportError:
        logger.warning("edge_tts not installed, falling back to Piper")
        await speak_piper(text)
    except Exception as exc:
        logger.warning("Edge TTS failed (%s), falling back to Piper", exc)
        await speak_piper(text)


async def _generate_audio(text: str, voice: str = VOICE,
                          rate: str | None = None) -> Path | None:
    """Generate TTS audio file without playing it. Returns cached file path."""
    if not text or not text.strip():
        return None

    text = text.replace("\n", " ").strip()
    if len(text) > 2000:
        text = text[:1997] + "..."

    voice = _resolve_voice(voice)
    if rate is None:
        rate = _adaptive_rate(text)

    # Check cache first
    cached = _get_cached(text, voice, rate)
    if cached:
        return cached

    # Try Edge TTS
    try:
        import edge_tts
        communicate = edge_tts.Communicate(text, voice, rate=rate)
        audio_chunks: list[bytes] = []
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_chunks.append(chunk["data"])
        if audio_chunks:
            audio_data = b"".join(audio_chunks)
            return _save_to_cache(text, voice, rate, audio_data, ext=".mp3")
    except ImportError:
        pass
    except Exception as exc:
        logger.debug("Edge TTS generate failed: %s", exc)

    # Piper fallback — generate and cache
    piper_bin = _find_piper()
    if piper_bin and _PIPER_MODEL.exists():
        try:
            proc = await asyncio.create_subprocess_exec(
                piper_bin, "--model", str(_PIPER_MODEL), "--output-raw",
                stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            pcm_data, _ = await asyncio.wait_for(
                proc.communicate(input=text.encode("utf-8")), timeout=30,
            )
            if pcm_data:
                wav_data = _pcm_to_wav(pcm_data)
                return _save_to_cache(text, "piper", rate or "+10%", wav_data, ext=".wav")
        except Exception:
            pass

    return None


async def speak_sentence_streaming(text: str, voice: str = VOICE,
                                   rate: str | None = None) -> None:
    """Speak text sentence-by-sentence with pre-fetch pipeline.

    While sentence N is playing, sentence N+1 is being generated.
    Reduces inter-sentence latency from ~500ms to ~50ms.
    """
    if not text or not text.strip():
        return

    sentences = [s.strip() for s in _split_sentences(text) if s.strip()]
    if not sentences:
        return

    # Single sentence → no pipeline needed
    if len(sentences) == 1:
        await speak_streaming(sentences[0], voice=voice, rate=rate)
        return

    # Pre-fetch pipeline: generate next while playing current
    next_audio_task: asyncio.Task | None = None

    for i, sentence in enumerate(sentences):
        # Wait for current audio (pre-fetched or generate now)
        if next_audio_task is not None:
            audio_path = await next_audio_task
            next_audio_task = None
        else:
            audio_path = await _generate_audio(sentence, voice=voice, rate=rate)

        # Start pre-fetching next sentence
        if i + 1 < len(sentences):
            next_audio_task = asyncio.create_task(
                _generate_audio(sentences[i + 1], voice=voice, rate=rate)
            )

        # Play current
        if audio_path:
            await _play_audio(audio_path)
        else:
            # Fallback to full speak_streaming
            await speak_streaming(sentence, voice=voice, rate=rate)

    # Cancel any remaining pre-fetch
    if next_audio_task is not None:
        next_audio_task.cancel()


async def speak_quick(text: str) -> None:
    """Quick TTS for short responses (confirmations, errors)."""
    await speak_streaming(text, rate=RATE_FAST)


async def speak_interruptible(text: str, interrupt_event: asyncio.Event | None = None,
                               voice: str = VOICE, rate: str | None = None) -> bool:
    """Speak with interrupt support + pre-fetch pipeline.

    Returns True if completed, False if interrupted.
    """
    if not text or not text.strip():
        return True

    sentences = [s.strip() for s in _split_sentences(text) if s.strip()]
    if not sentences:
        return True

    next_audio_task: asyncio.Task | None = None

    for i, sentence in enumerate(sentences):
        if interrupt_event and interrupt_event.is_set():
            if next_audio_task:
                next_audio_task.cancel()
            return False

        # Get current audio
        if next_audio_task is not None:
            audio_path = await next_audio_task
            next_audio_task = None
        else:
            audio_path = await _generate_audio(sentence, voice=voice, rate=rate)

        # Pre-fetch next
        if i + 1 < len(sentences):
            next_audio_task = asyncio.create_task(
                _generate_audio(sentences[i + 1], voice=voice, rate=rate)
            )

        # Play
        if audio_path:
            await _play_audio(audio_path)
        else:
            await speak_streaming(sentence, voice=voice, rate=rate)

    if next_audio_task:
        next_audio_task.cancel()

    return True


def clear_tts_cache() -> int:
    """Clear the TTS cache. Returns number of files removed."""
    if not _CACHE_DIR.exists():
        return 0
    files = list(_CACHE_DIR.glob("*.mp3")) + list(_CACHE_DIR.glob("*.wav"))
    for f in files:
        f.unlink(missing_ok=True)
    return len(files)
