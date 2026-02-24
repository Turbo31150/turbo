"""Voice route — Audio processing, Whisper transcription, TTS."""
import asyncio
import base64
import io
import time
import wave
from typing import Any

# Try to import Whisper worker
try:
    from src.whisper_worker import WhisperWorker
    _whisper = WhisperWorker()
except ImportError:
    _whisper = None

try:
    from src.voice_correction import full_correction_pipeline
except ImportError:
    full_correction_pipeline = None


class AudioBuffer:
    """Accumulates audio chunks for transcription."""

    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate
        self.chunks: list[bytes] = []
        self.recording = False

    def start(self):
        self.chunks.clear()
        self.recording = True

    def add_chunk(self, b64_data: str):
        if self.recording:
            self.chunks.append(base64.b64decode(b64_data))

    def stop(self) -> bytes:
        self.recording = False
        if not self.chunks:
            return b""
        return b"".join(self.chunks)

    def to_wav(self, pcm_data: bytes) -> bytes:
        """Convert raw PCM to WAV."""
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(self.sample_rate)
            wf.writeframes(pcm_data)
        return buf.getvalue()


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
    pcm_data = _buffer.stop()
    if not pcm_data:
        return {"error": "No audio data"}

    wav_data = _buffer.to_wav(pcm_data)

    # Transcribe
    text = ""
    if _whisper:
        try:
            text = await asyncio.to_thread(_whisper.transcribe, wav_data)
        except Exception as e:
            text = f"[Erreur Whisper] {e}"
    else:
        text = "[Whisper non disponible — module src.whisper_worker manquant]"

    # Correct
    corrected = text
    if full_correction_pipeline and text:
        try:
            corrected = await asyncio.to_thread(full_correction_pipeline, text)
        except Exception:
            corrected = text

    entry = {
        "timestamp": time.time(),
        "original": text,
        "corrected": corrected,
    }
    _transcriptions.append(entry)

    return {"transcription": entry}


async def _handle_tts(payload: dict) -> dict:
    """Text-to-speech via Windows SAPI (PowerShell)."""
    text = payload.get("text", "").strip()
    if not text:
        return {"error": "Empty text"}

    try:
        # Use Windows SAPI via PowerShell (asyncio.create_subprocess_exec is safe)
        escaped = text.replace('"', '`"').replace("'", "''")
        ps_cmd = (
            "Add-Type -AssemblyName System.Speech; "
            "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            f"$s.Speak('{escaped}')"
        )
        proc = await asyncio.create_subprocess_exec(
            "powershell", "-Command", ps_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await asyncio.wait_for(proc.wait(), timeout=30)
        return {"spoken": True, "text": text}
    except Exception as e:
        return {"error": f"TTS failed: {e}"}
