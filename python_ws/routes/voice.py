"""Voice route — Audio processing, Whisper transcription, TTS."""
import asyncio
import base64
import logging
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


class AudioBuffer:
    """Accumulates audio chunks for transcription.

    Browser sends WebM/Opus chunks via base64. We concatenate them
    and pass the raw WebM to faster-whisper (which uses ffmpeg internally).
    """

    def __init__(self):
        self.chunks: list[bytes] = []
        self.recording = False

    def start(self):
        self.chunks.clear()
        self.recording = True

    def add_chunk(self, b64_data: str):
        if self.recording:
            self.chunks.append(base64.b64decode(b64_data))

    def stop(self) -> bytes:
        """Return raw audio bytes (WebM/Opus from browser)."""
        self.recording = False
        if not self.chunks:
            return b""
        return b"".join(self.chunks)


_buffer = AudioBuffer()
_transcriptions: list[dict] = []


async def handle_voice_request(action: str, payload: dict) -> dict:
    """Handle voice channel requests."""
    if action == "audio_chunk":
        return _handle_chunk(payload)
    elif action == "stop_recording":
        return await _handle_stop()
    elif action == "start_recording":
        _buffer.start()
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

    # Transcribe — pass raw bytes (WebM/Opus) to WhisperWorker
    whisper = _get_whisper()
    text = ""
    if whisper:
        try:
            text = await asyncio.to_thread(whisper.transcribe, audio_data)
        except Exception as e:
            logger.error("Whisper error: %s", e)
            text = f"[Erreur Whisper] {e}"
    else:
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


async def _handle_tts(payload: dict) -> dict:
    """Text-to-speech via Edge TTS."""
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
        return {"spoken": True, "text": text, "voice": voice}
    except Exception as e:
        return {"error": f"TTS failed: {e}"}
