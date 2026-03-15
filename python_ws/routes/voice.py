"""Voice route — Audio processing, Whisper transcription, TTS."""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import re
import struct
import time

logger = logging.getLogger("jarvis.voice")

# ── Voice → JARVIS Tool triggers (fallback when no domino match) ─────────
# Same patterns as telegram-bot.js intents, adapted for French voice input.
_VOICE_TOOL_TRIGGERS: list[tuple[re.Pattern, str]] = [
    # Order matters: more specific patterns first to avoid false positives.
    (re.compile(r"\b(#?boot|statut\s*(du\s*)?boot|d[eé]marrage|boot\s*status)\b", re.I), "jarvis_boot_status"),
    (re.compile(r"\b(#?db[\s-]*health|sant[eé]\s*(des?\s*)?base|db\s*health|bases?\s*de\s*donn[eé]es)\b", re.I), "jarvis_db_health"),
    (re.compile(r"\b(#?orchestr|orchestrat(eur|or)\s*(health|sant[eé]))\b", re.I), "jarvis_orchestrator_health"),
    (re.compile(r"\b(#?health|sant[eé]\s*(du\s*)?cluster|cluster\s*health|[eé]tat\s*(du\s*)?cluster)\b", re.I), "jarvis_cluster_health"),
    (re.compile(r"\b(#?gpu|statut\s*(du\s*)?gpu|gpu\s*status|temp[eé]rature\s*gpu|vram)\b", re.I), "jarvis_gpu_status"),
    (re.compile(r"\b(#?audit|diagnostic\s*(rapide|quick|complet)?|diag\s*rapide)\b", re.I), "jarvis_diagnostics_quick"),
    (re.compile(r"(#?autonome|boucle\s*autonome|t[aâ]che\w*\s*autonome\w*|taches?\s*autonome|autonomous)", re.I), "jarvis_autonomous_status"),
    (re.compile(r"\b(#?alertes?|alerte[s]?\s*active|alertes?\s*en\s*cours)\b", re.I), "jarvis_alerts_active"),
]


def _match_voice_tool(text: str) -> str | None:
    """Match transcribed text against JARVIS tool triggers. Returns tool_name or None."""
    for pattern, tool_name in _VOICE_TOOL_TRIGGERS:
        if pattern.search(text):
            return tool_name
    return None


async def _execute_voice_tool(tool_name: str) -> dict | None:
    """Call a JARVIS tool and return result formatted for voice/TTS."""
    try:
        from src.ia_tool_executor import execute_tool_call
        result = await execute_tool_call(tool_name, {}, caller="voice")
        if not result.get("ok"):
            return {"tool": tool_name, "ok": False, "error": result.get("error", "unknown")}
        data = result.get("result", {})
        summary = _format_tool_for_tts(tool_name, data)
        return {"tool": tool_name, "ok": True, "summary": summary, "raw": data}
    except Exception as e:
        logger.error("Voice tool %s failed: %s", tool_name, e)
        return {"tool": tool_name, "ok": False, "error": str(e)}


def _format_tool_for_tts(tool_name: str, data: dict) -> str:
    """Format tool result as short spoken French text for TTS."""
    if not isinstance(data, dict):
        return str(data)[:200]

    if tool_name == "jarvis_boot_status":
        nodes = data.get("nodes", {})
        svcs = data.get("services", {})
        node_parts = [f"{n} {s.get('status', '?')}" for n, s in nodes.items()]
        svc_ok = sum(1 for s in svcs.values() if s == "OK")
        return f"Boot: {', '.join(node_parts)}. {svc_ok} services sur {len(svcs)} actifs."

    if tool_name == "jarvis_cluster_health":
        score = data.get("health_score", "?")
        stats = data.get("node_stats", {})
        parts = []
        for n, s in stats.items():
            if s.get("total_calls", 0) > 0:
                parts.append(f"{n} {s.get('avg_latency_ms', 0):.0f} ms")
        return f"Cluster score {score}. {', '.join(parts) if parts else 'Aucun appel recent'}."

    if tool_name == "jarvis_gpu_status":
        orch = data.get("orchestrator", {})
        score = orch.get("health_score", "?")
        auto = data.get("autonomous_loop", {})
        tasks = auto.get("task_count", 0)
        runs = auto.get("total_runs", 0)
        return f"GPU health score {score}. Boucle autonome: {tasks} taches, {runs} executions."

    if tool_name == "jarvis_diagnostics_quick":
        return json.dumps(data, ensure_ascii=False, default=str)[:300]

    if tool_name == "jarvis_autonomous_status":
        running = data.get("running", False)
        tasks = data.get("tasks", {})
        if isinstance(tasks, dict):
            enabled = sum(1 for t in tasks.values() if isinstance(t, dict) and t.get("enabled"))
            failed = sum(1 for t in tasks.values() if isinstance(t, dict) and t.get("fail_count", 0) > 0)
            status = "active" if running else "arretee"
            fail_msg = f", {failed} en erreur" if failed else ""
            return f"Boucle autonome {status}: {enabled} taches actives sur {len(tasks)}{fail_msg}."
        elif isinstance(tasks, list):
            enabled = sum(1 for t in tasks if t.get("enabled"))
            return f"Boucle autonome: {enabled} taches actives sur {len(tasks)}."
        return f"Boucle autonome: {tasks} taches."

    if tool_name == "jarvis_alerts_active":
        alerts = data.get("alerts", data.get("active", []))
        if isinstance(alerts, list):
            if not alerts:
                return "Aucune alerte active."
            return f"{len(alerts)} alertes actives: {', '.join(a.get('message', a.get('type', '?'))[:40] for a in alerts[:3])}."
        return f"Alertes: {str(data)[:200]}"

    if tool_name == "jarvis_db_health":
        dbs = {k: v for k, v in data.items() if isinstance(v, dict) and "ok" in v}
        if dbs:
            parts = [f"{k} {'OK' if v['ok'] else 'ERREUR'}" for k, v in dbs.items()]
            return f"Bases de donnees: {', '.join(parts)}."
        return f"DB health: {str(data)[:200]}"

    if tool_name == "jarvis_orchestrator_health":
        score = data.get("health_score", "?")
        return f"Orchestrateur score {score}."

    # Generic fallback
    return json.dumps(data, ensure_ascii=False, default=str)[:300]

# Background task references (prevents GC of fire-and-forget tasks)
_bg_tasks: set[asyncio.Task] = set()

# Lazy-loaded Whisper worker (avoids blocking server startup)
_whisper = None
_whisper_init_attempted = False


def _get_whisper() -> object | None:
    """Lazily initialize WhisperWorker on first use."""
    global _whisper, _whisper_init_attempted
    if _whisper_init_attempted:
        return _whisper
    _whisper_init_attempted = True
    try:
        from src.whisper_worker import WhisperWorker
        _whisper = WhisperWorker()
        logger.info("WhisperWorker loaded successfully")
    except (ImportError, RuntimeError) as e:
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


MAX_AUDIO_BUFFER = 30 * 16000 * 2  # 30s of 16kHz 16-bit mono = ~960KB
MAX_TRANSCRIPTIONS = 200


class AudioBuffer:
    """Accumulates audio chunks for transcription.

    Frontend sends PCM int16 base64 chunks (16kHz mono).
    We concatenate them, wrap in a WAV header, then pass to Whisper.
    """

    def __init__(self):
        self.chunks: list[bytes] = []
        self._total_bytes = 0
        self.recording = False
        self.format = "pcm_16bit"
        self.sample_rate = 16000
        self.channels = 1

    def start(self, fmt: str = "pcm_16bit", sample_rate: int = 16000,
              channels: int = 1):
        self.chunks.clear()
        self._total_bytes = 0
        self.recording = True
        self.format = fmt
        self.sample_rate = sample_rate
        self.channels = channels

    def add_chunk(self, b64_data: str):
        if not self.recording:
            return
        if not isinstance(b64_data, str):
            logger.warning("audio_chunk: expected str, got %s", type(b64_data).__name__)
            return
        try:
            decoded = base64.b64decode(b64_data, validate=True)
        except (ValueError, TypeError) as exc:
            logger.warning("audio_chunk: invalid base64 data — %s", exc)
            return
        if self._total_bytes + len(decoded) > MAX_AUDIO_BUFFER:
            logger.warning("Audio buffer limit reached (%d bytes), ignoring chunk", MAX_AUDIO_BUFFER)
            return
        self.chunks.append(decoded)
        self._total_bytes += len(decoded)

    def stop(self) -> bytes:
        """Return audio bytes ready for Whisper (WAV with header)."""
        self.recording = False
        self._stop_ts = time.time()
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
        try:
            sample_rate = int(payload.get("sample_rate", 16000))
            channels = int(payload.get("channels", 1))
        except (ValueError, TypeError):
            return {"error": "Invalid sample_rate or channels (must be integers)"}
        if not (8000 <= sample_rate <= 48000):
            return {"error": f"Invalid sample_rate: {sample_rate} (8000-48000)"}
        if channels not in (1, 2):
            return {"error": f"Invalid channels: {channels} (1 or 2)"}
        _buffer.start(
            fmt=payload.get("format", "pcm_16bit"),
            sample_rate=sample_rate,
            channels=channels,
        )
        return {"recording": True}
    elif action == "tts_speak":
        return await _handle_tts(payload)
    elif action == "get_transcriptions":
        return {"transcriptions": _transcriptions[-50:]}
    elif action == "learn_command":
        return _handle_learn(payload)
    elif action == "unlearn_command":
        return _handle_unlearn(payload)
    elif action == "voice_analytics":
        return _handle_voice_analytics(payload)
    elif action == "list_voices":
        return _handle_list_voices()
    elif action == "session_stats":
        return _handle_session_stats()
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
        except (RuntimeError, OSError, ValueError) as e:
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
            result = await asyncio.wait_for(full_correction_pipeline(text), timeout=15.0)
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
                        execution = await asyncio.wait_for(
                            _execute_matched_command(cmd, params), timeout=8.0
                        )
            elif isinstance(result, str):
                corrected = result
        except asyncio.TimeoutError:
            logger.warning("Voice correction/execution timeout — using raw text")
            corrected = text
        except (ValueError, RuntimeError) as e:
            logger.warning("Voice correction error: %s", e)
            corrected = text

    # ── Fallback: JARVIS tool matching (when no domino executed) ─────────
    tool_result = None
    if execution is None:
        matched_tool = _match_voice_tool(corrected or text)
        if matched_tool:
            logger.info("Voice tool fallback: '%s' -> %s", (corrected or text)[:60], matched_tool)
            try:
                tool_result = await asyncio.wait_for(
                    _execute_voice_tool(matched_tool), timeout=10.0
                )
                if tool_result and tool_result.get("ok"):
                    execution = {
                        "executed": True,
                        "command_name": matched_tool,
                        "description": f"JARVIS tool (voice fallback)",
                        "output": tool_result.get("summary", ""),
                    }
            except asyncio.TimeoutError:
                logger.warning("Voice tool %s timeout", matched_tool)
            except Exception as e:
                logger.warning("Voice tool %s error: %s", matched_tool, e)

    # v2: record voice pipeline metrics in orchestrator_v2
    try:
        from src.orchestrator_v2 import orchestrator_v2
        orchestrator_v2.record_call(
            "voice_pipeline", latency_ms=(time.time() - _buffer._stop_ts) * 1000 if hasattr(_buffer, '_stop_ts') else 0,
            success=bool(text and not text.startswith("[")),
            tokens=len(corrected.split()) if corrected else 0,
        )
    except Exception:
        pass

    entry = {
        "timestamp": time.time(),
        "original": text,
        "corrected": corrected,
        "domino": domino,
        "execution": execution,
        "tool_result": tool_result,
    }
    _transcriptions.append(entry)
    # Keep bounded to prevent memory leak
    if len(_transcriptions) > MAX_TRANSCRIPTIONS:
        del _transcriptions[:len(_transcriptions) - MAX_TRANSCRIPTIONS]

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
    except (asyncio.TimeoutError, RuntimeError, OSError) as e:
        logger.error("Voice command execution error: %s", e)
        return {"executed": False, "error": str(e)}


async def _fallback_cloud_stt(audio_data: bytes) -> str:
    """Fallback: cloud STT via OL1/Whisper REST or Azure Speech.

    Priority: 1) Local Whisper CLI  2) Groq Whisper API  3) Azure Speech
    """
    import tempfile
    import pathlib

    # Save audio to temp WAV for API upload
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.write(audio_data)
    tmp.close()
    tmp_path = pathlib.Path(tmp.name)

    try:
        # Strategy 1: Local faster-whisper CLI (if installed system-wide)
        text = await _cloud_stt_local_cli(tmp_path)
        if text:
            return text

        # Strategy 2: Groq Whisper API (free tier, fast)
        text = await _cloud_stt_groq(tmp_path)
        if text:
            return text

    finally:
        tmp_path.unlink(missing_ok=True)

    return ""


async def _cloud_stt_local_cli(wav_path) -> str:
    """Try transcribing via faster-whisper CLI as subprocess."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "faster-whisper", str(wav_path),
            "--model", "tiny", "--language", "fr",
            "--output_format", "txt",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10.0)
        text = stdout.decode("utf-8", errors="replace").strip()
        if text and len(text) > 1:
            logger.info("Cloud STT (local CLI): %s", text[:80])
            return text
    except (FileNotFoundError, asyncio.TimeoutError, OSError):
        pass
    return ""


async def _cloud_stt_groq(wav_path) -> str:
    """Transcribe via Groq Whisper API (whisper-large-v3-turbo, free tier)."""
    import os
    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        return ""

    try:
        import httpx
        async with httpx.AsyncClient(timeout=15.0) as client:
            with open(wav_path, "rb") as f:
                resp = await client.post(
                    "https://api.groq.com/openai/v1/audio/transcriptions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    files={"file": ("audio.wav", f, "audio/wav")},
                    data={"model": "whisper-large-v3-turbo", "language": "fr"},
                )
            if resp.status_code == 200:
                text = resp.json().get("text", "").strip()
                if text:
                    logger.info("Cloud STT (Groq): %s", text[:80])
                    return text
    except (ImportError, httpx.HTTPError, asyncio.TimeoutError, OSError) as e:
        logger.debug("Groq STT failed: %s", e)
    return ""


async def _handle_tts(payload: dict) -> dict:
    """Text-to-speech via Edge TTS with fallback."""
    text = payload.get("text", "").strip()
    if not text:
        return {"error": "Empty text"}
    if len(text) > 5000:
        return {"error": f"Text too long: {len(text)} chars (max 5000)"}

    try:
        import edge_tts
        import tempfile
        _ALLOWED_VOICES = {"fr-FR-HenriNeural", "fr-FR-DeniseNeural", "en-US-GuyNeural", "en-US-JennyNeural"}
        voice = payload.get("voice", "fr-FR-DeniseNeural")
        if voice not in _ALLOWED_VOICES:
            voice = "fr-FR-DeniseNeural"
        comm = edge_tts.Communicate(text, voice)
        tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        tmp.close()
        try:
            await comm.save(tmp.name)
        except Exception:
            import pathlib as _pl
            _pl.Path(tmp.name).unlink(missing_ok=True)
            raise

        # Read MP3 and return as base64 for client-side playback
        import pathlib
        mp3_bytes = pathlib.Path(tmp.name).read_bytes()
        audio_b64 = base64.b64encode(mp3_bytes).decode("ascii")
        pathlib.Path(tmp.name).unlink(missing_ok=True)

        # Broadcast tts_finished after a delay (estimated playback time)
        async def _notify_finished():
            # Rough estimate: 150 chars/s speech rate → duration in seconds
            await asyncio.sleep(max(1.0, len(text) / 15))
            try:
                from python_ws.server import _broadcast_event
                await _broadcast_event("voice", "tts_finished", {"text": text})
            except Exception:
                pass

        task = asyncio.create_task(_notify_finished())
        _bg_tasks.add(task)
        task.add_done_callback(_bg_tasks.discard)
        return {
            "spoken": True, "text": text, "voice": voice, "engine": "edge_tts",
            "audio": audio_b64, "format": "mp3",
        }
    except (ImportError, RuntimeError, OSError) as e:
        logger.warning("Edge TTS failed: %s — trying Windows SAPI fallback", e)

    # Fallback: signal client to use browser Web Speech API (speechSynthesis)
    return {"spoken": False, "text": text, "fallback": "web_speech_api"}


# ── Voice Learning (teach/forget commands via WebSocket) ─────────────────

def _handle_learn(payload: dict) -> dict:
    """Teach JARVIS a new voice trigger via WebSocket.

    Payload:
        trigger: str — the voice phrase (e.g. "montre les positions")
        target_command: str? — existing command name to map to
        action: str? — bash/script action for new command
        action_type: str? — "bash", "script", "browser" (default "bash")
    """
    trigger = payload.get("trigger", "").strip()
    if not trigger:
        return {"success": False, "error": "trigger requis"}

    try:
        from src.commands import learn_voice_command
        result = learn_voice_command(
            trigger=trigger,
            target_command=payload.get("target_command"),
            action=payload.get("action"),
            action_type=payload.get("action_type", "bash"),
            category=payload.get("category", "learned"),
            description=payload.get("description", ""),
            confirm=payload.get("confirm", False),
        )
        return result
    except Exception as e:
        logger.error("learn_command error: %s", e)
        return {"success": False, "error": str(e)}


def _handle_unlearn(payload: dict) -> dict:
    """Remove a voice trigger via WebSocket.

    Payload:
        trigger: str — the voice phrase to forget
    """
    trigger = payload.get("trigger", "").strip()
    if not trigger:
        return {"success": False, "error": "trigger requis"}

    try:
        from src.commands import unlearn_voice_command
        return unlearn_voice_command(trigger)
    except Exception as e:
        logger.error("unlearn_command error: %s", e)
        return {"success": False, "error": str(e)}


def _handle_voice_analytics(payload: dict) -> dict:
    """Return voice pipeline analytics from voice_analytics table.

    Payload:
        limit: int — max rows to return (default 100)
        stage: str? — filter by stage (stt, correction, execution, learn)
    """
    import sqlite3
    from pathlib import Path

    db_path = Path(__file__).resolve().parent.parent.parent / "data" / "jarvis.db"
    limit = min(int(payload.get("limit", 100)), 500)
    stage_filter = payload.get("stage", "")

    try:
        conn = sqlite3.connect(str(db_path), timeout=3)
        conn.row_factory = sqlite3.Row

        if stage_filter:
            rows = conn.execute(
                "SELECT * FROM voice_analytics WHERE stage = ? ORDER BY id DESC LIMIT ?",
                (stage_filter, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM voice_analytics ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        conn.close()

        events = [dict(r) for r in rows]

        # Compute summary stats
        total = len(events)
        stages = {}
        for e in events:
            s = e.get("stage", "?")
            stages[s] = stages.get(s, 0) + 1

        avg_latency = {}
        for stage_name in ("stt", "correction"):
            latencies = [e["latency_ms"] for e in events
                         if e.get("stage") == stage_name and e.get("latency_ms", 0) > 0]
            if latencies:
                avg_latency[stage_name] = round(sum(latencies) / len(latencies), 1)

        success_rate = 0.0
        if total > 0:
            success_rate = round(sum(1 for e in events if e.get("success")) / total * 100, 1)

        return {
            "events": events[:50],
            "total": total,
            "stages": stages,
            "avg_latency_ms": avg_latency,
            "success_rate": success_rate,
        }
    except Exception as e:
        return {"events": [], "error": str(e)}


def _handle_list_voices() -> dict:
    """List available TTS voices."""
    try:
        from src.tts_streaming import VOICES
        return {"voices": VOICES, "default": "denise"}
    except ImportError:
        return {
            "voices": {
                "denise": "fr-FR-DeniseNeural",
                "henri": "fr-FR-HenriNeural",
            },
            "default": "denise",
        }


def _handle_session_stats() -> dict:
    """Return current voice session stats."""
    try:
        from src.voice_session import get_voice_session
        session = get_voice_session()
        return session.to_dict()
    except Exception as e:
        return {"error": str(e)}
