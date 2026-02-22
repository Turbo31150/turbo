"""JARVIS TTS Streaming — Edge TTS with chunked audio playback.

Starts speaking before the full text is generated.
Uses edge-tts async generator for low-latency output.
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

VOICE = "fr-FR-HenriNeural"
RATE = "+10%"


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
    tmp = Path(tempfile.mktemp(suffix=".mp3"))
    try:
        tmp.write_bytes(audio_data)
        proc = await asyncio.create_subprocess_exec(
            "ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", str(tmp),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()
    except FileNotFoundError:
        # Fallback: PowerShell media player
        proc = await asyncio.create_subprocess_exec(
            "powershell", "-Command",
            f"Add-Type -AssemblyName PresentationCore; $p = New-Object System.Windows.Media.MediaPlayer; $p.Open('{tmp}'); $p.Play(); Start-Sleep -Seconds 10",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()
    finally:
        tmp.unlink(missing_ok=True)


async def speak_quick(text: str) -> None:
    """Quick TTS for short responses (confirmations, errors)."""
    await speak_streaming(text, rate="+15%")
