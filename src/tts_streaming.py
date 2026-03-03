"""JARVIS TTS Streaming — Edge TTS with chunked audio playback.

Starts speaking before the full text is generated.
Uses edge-tts async generator for low-latency output.
"""

from __future__ import annotations

import asyncio
import logging
import tempfile
from pathlib import Path

logger = logging.getLogger("jarvis.tts")

VOICE = "fr-FR-HenriNeural"
RATE = "+10%"
_PLAYBACK_TIMEOUT = 60  # max seconds for audio playback


async def speak_streaming(text: str, voice: str = VOICE, rate: str = RATE) -> None:
    """Speak text using Edge TTS with streaming playback."""
    import edge_tts

    communicate = edge_tts.Communicate(text, voice, rate=rate)

    audio_chunks: list[bytes] = []
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_chunks.append(chunk["data"])

    if not audio_chunks:
        return

    audio_data = b"".join(audio_chunks)
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        tmp = Path(f.name)
        f.write(audio_data)
    proc = None
    try:
        try:
            proc = await asyncio.create_subprocess_exec(
                "ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", str(tmp),
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(proc.wait(), timeout=_PLAYBACK_TIMEOUT)
        except FileNotFoundError:
            # Fallback: PowerShell media player — escape path for safety
            safe_path = str(tmp).replace("'", "''")
            proc = await asyncio.create_subprocess_exec(
                "powershell", "-Command",
                f"Add-Type -AssemblyName PresentationCore; $p = New-Object System.Windows.Media.MediaPlayer; $p.Open('{safe_path}'); $p.Play(); Start-Sleep -Seconds 10",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(proc.wait(), timeout=_PLAYBACK_TIMEOUT)
        except asyncio.TimeoutError:
            logger.warning("TTS playback timeout after %ds, killing process", _PLAYBACK_TIMEOUT)
    finally:
        if proc is not None and proc.returncode is None:
            try:
                proc.kill()
                await proc.wait()
            except OSError:
                pass
        tmp.unlink(missing_ok=True)


async def speak_quick(text: str) -> None:
    """Quick TTS for short responses (confirmations, errors)."""
    await speak_streaming(text, rate="+15%")
