"""Voice route — Audio processing, Whisper transcription, TTS."""
import asyncio
import base64
import logging
import struct
import time
from typing import Any

logger = logging.getLogger("jarvis.voice")

# Lazy-loaded Whisper worker (avoids blocking server startup)
_whisper = None
_whisper_init_attempted = False


def _get_whisper():
    """Lazily initialize WhisperWorker on first use."""
    global _whisper, _whisper_init_attempted
    if _whisper_init_attempted:
        return _whisper
    _whisper_init_attempted = True
    try:
        from src.whisper_worker import WhisperWorker
        _whisper = WhisperWorker()
        logger.info("WhisperWorker loaded successfully")
    except Exception as e:
        logger.warning("WhisperWorker unavailable: %s", e)
        _whisper = None
    return _whisper


# Voice correction (async function)
try:
    from src.voice_correction import full_correction_pipeline
except ImportError:
    full_correction_pipeline = None


def _pcm_to_wav(pcm_bytes: bytes, sample_rate: int = 16000,
                channels: int = 1, bits_per_sample: int = 16) -> bytes:
    """Wrap raw PCM int16 bytes in a proper WAV header for Whisper/ffmpeg."""
    data_size = len(pcm_bytes)
    block_align = channels * bits_per_sample // 8
    byte_rate = sample_rate * block_align
    header = struct.pack(
        '<4sI4s4sIHHIIHH4sI',
        b'RIFF', 36 + data_size, b'WAVE',
        b'fmt ', 16, 1, channels, sample_rate, byte_rate, block_align, bits_per_sample,
        b'data', data_size,
    )
    return header + pcm_bytes


class AudioBuffer:
    """Accumulates audio chunks for transcription.

    Frontend sends PCM int16 base64 chunks (16kHz mono).
    We concatenate them, wrap in a WAV header, then pass to Whisper.
    """

    def __init__(self):
        self.chunks: list[bytes] = []
        self.recording = False
        self.format = "pcm_16bit"
        self.sample_rate = 16000
        self.channels = 1

    def start(self, fmt: str = "pcm_16bit", sample_rate: int = 16000,
              channels: int = 1):
        self.chunks.clear()
        self.recording = True
        self.format = fmt
        self.sample_rate = sample_rate
        self.channels = channels

    def add_chunk(self, b64_data: str):
        if self.recording:
            self.chunks.append(base64.b64decode(b64_data))

    def stop(self) -> bytes:
        """Return audio bytes ready for Whisper (WAV with header)."""
        self.recording = False
        if not self.chunks:
            return b""
        raw = b"".join(self.chunks)
        # PCM int16 → wrap in WAV header so Whisper/ffmpeg can decode it
        if self.format == "pcm_16bit":
            return _pcm_to_wav(raw, self.sample_rate, self.channels, 16)
        # WebM/Opus or other container — pass through as-is
        return raw


_buffer = AudioBuffer()
_transcriptions: list[dict] = []


async def handle_voice_request(action: str, payload: dict) -> dict:
    """Handle voice channel requests."""
    if action == "audio_chunk":
        return _handle_chunk(payload)
    elif action == "stop_recording":
        return await _handle_stop()
    elif action == "start_recording":
        _buffer.start(
            fmt=payload.get("format", "pcm_16bit"),
            sample_rate=payload.get("sample_rate", 16000),
            channels=payload.get("channels", 1),
        )
        return {"recording": True}
    elif action == "tts_speak":
        return await _handle_tts(payload)
    elif action == "get_transcriptions":
        return {"transcriptions": _transcriptions[-50:]}
    return {"error": f"Unknown voice action: {action}"}


def _handle_chunk(payload: dict) -> dict:
    """Add audio chunk to buffer."""
    data = payload.get("audio", "")
    if data:
        _buffer.add_chunk(data)
    return {"buffered": True}


async def _handle_stop() -> dict:
    """Stop recording and transcribe."""
    audio_data = _buffer.stop()
    if not audio_data:
        return {"error": "No audio data"}

    # Transcribe — audio_data is now a proper WAV (header added by AudioBuffer)
    whisper = _get_whisper()
    text = ""
    if whisper:
        try:
            text = await asyncio.to_thread(whisper.transcribe, audio_data)
        except Exception as e:
            logger.error("Whisper error: %s", e)
            text = await _fallback_cloud_stt(audio_data)
            if not text:
                text = f"[Erreur Whisper] {e}"
    else:
        # Fallback: try cloud STT if Whisper unavailable
        text = await _fallback_cloud_stt(audio_data)
        if not text:
            text = "[Whisper non disponible]"

    # Voice correction (async function — returns dict with corrected text + command)
    corrected = text
    domino = None
    execution = None
    if full_correction_pipeline and text and not text.startswith("["):
        try:
            result = await full_correction_pipeline(text)
            if isinstance(result, dict):
                corrected = result.get("corrected", text)
                cmd = result.get("command")
                confidence = result.get("confidence", 0)
                params = result.get("params", {})
                if cmd and hasattr(cmd, "name"):
                    domino = {
                        "id": cmd.name,
                        "category": getattr(cmd, "category", ""),
                        "description": getattr(cmd, "description", ""),
                        "action_type": getattr(cmd, "action_type", ""),
                        "params": params,
                        "confidence": confidence,
                    }
                    # EXECUTE command directly if high confidence
                    if confidence >= 0.75:
                        execution = await _execute_matched_command(cmd, params)
            elif isinstance(result, str):
                corrected = result
        except Exception as e:
            logger.warning("Voice correction error: %s", e)
            corrected = text

    entry = {
        "timestamp": time.time(),
        "original": text,
        "corrected": corrected,
        "domino": domino,
        "execution": execution,
    }
    _transcriptions.append(entry)

    return {"transcription": entry}


async def _execute_matched_command(cmd, params: dict) -> dict | None:
    """Execute a matched voice command directly. Returns execution result."""
    try:
        from src.executor import execute_command
    except ImportError:
        logger.warning("src.executor not available")
        return None

    try:
        output = await execute_command(cmd, params)
        # Skip special sentinel values
        if isinstance(output, str) and output.startswith("__"):
            return None
        logger.info("Voice executed: %s -> %s", cmd.name, output[:80])
        return {
            "executed": True,
            "command_name": cmd.name,
            "description": cmd.description,
            "output": output[:300],
        }
    except Exception as e:
        logger.error("Voice command execution error: %s", e)
        return {"executed": False, "error": str(e)}


async def _fallback_cloud_stt(audio_data: bytes) -> str:
    """Fallback: send audio to OL1 cloud for transcription (if available)."""
    try:
        import httpx
        # Try using a cloud model for transcription description
        # Since Ollama doesn't have native STT, we describe what we'd need
        # For now, return empty to signal fallback failed
        logger.warning("Cloud STT fallback: no cloud STT available yet")
        return ""
    except Exception as e:
        logger.error("Cloud STT fallback error: %s", e)
        return ""


async def _handle_tts(payload: dict) -> dict:
    """Text-to-speech via Edge TTS with fallback."""
    text = payload.get("text", "").strip()
    if not text:
        return {"error": "Empty text"}

    try:
        import edge_tts
        import tempfile
        voice = payload.get("voice", "fr-FR-HenriNeural")
        comm = edge_tts.Communicate(text, voice)
        tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        tmp.close()
        await comm.save(tmp.name)

        # Play via ffplay (non-blocking)
        proc = await asyncio.create_subprocess_exec(
            "ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", tmp.name,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        # Don't await — let it play in background
        return {"spoken": True, "text": text, "voice": voice, "engine": "edge_tts"}
    except Exception as e:
        logger.warning("Edge TTS failed: %s — signaling browser fallback", e)
        # Signal the frontend to use Web Speech API as fallback
        return {"spoken": False, "text": text, "fallback": "web_speech_api", "error": str(e)}
