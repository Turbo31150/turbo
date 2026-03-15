"""JARVIS Voice Interface v3 — VAD + Streaming Whisper + OL1 correction + Cache.

Flow:
1. Wake word 'jarvis/hey jarvis/ok jarvis' or Ctrl PTT → record audio
2. VAD (Silero) filters silence → speech-only audio
3. Streaming transcribe via persistent faster-whisper worker (CUDA, beam=1)
4. Local-first routing: cache → fuzzy match → OL1/qwen3:1.7b correction
5. Command execution + streaming TTS

v3 changes:
- Silero VAD integration (60-80% less Whisper load)
- Multi wake-word support
- Smart end-of-speech detection
- Sub-1s latency for cached commands
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import subprocess
import tempfile
import threading
import time
import wave
from pathlib import Path

import numpy as np
import sounddevice as sd


__all__ = [
    "WhisperWorker",
    "_split_multi_intent",
    "check_microphone",
    "get_cached_input_device",
    "get_confidence_thresholds",
    "start_whisper",
    "stop_whisper",
]

logger = logging.getLogger("jarvis.voice")

try:
    import keyboard as kb
    HAS_KEYBOARD = True
except ImportError:
    HAS_KEYBOARD = False

# ── Voice pipeline analytics ──────────────────────────────────────────────

def _log_voice_event(stage: str, text: str = "", confidence: float = 0.0,
                     method: str = "", latency_ms: float = 0.0, success: bool = True):
    """Log a voice pipeline event to voice_analytics."""
    try:
        import sqlite3
        db_path = Path(__file__).parent.parent / "data" / "jarvis.db"
        with sqlite3.connect(str(db_path), timeout=2) as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS voice_analytics ("
                "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "  timestamp REAL DEFAULT (unixepoch()),"
                "  stage TEXT NOT NULL,"
                "  text TEXT DEFAULT '',"
                "  confidence REAL DEFAULT 0,"
                "  method TEXT DEFAULT '',"
                "  latency_ms REAL DEFAULT 0,"
                "  success INTEGER DEFAULT 1"
                ")"
            )
            conn.execute(
                "INSERT INTO voice_analytics (stage, text, confidence, method, latency_ms, success) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (stage, text[:200], confidence, method, latency_ms, int(success))
            )
    except Exception:
        pass  # Never block voice pipeline for logging


# ── Voice conversation context ─────────────────────────────────────────
_voice_context: list[dict] = []  # Ring buffer of last 5 interactions
_CONTEXT_MAX = 5
_CONTEXT_TTL = 120.0  # Seconds before context expires

# Follow-up keywords that reference previous commands
_FOLLOWUP_PATTERNS = {
    "refais": "repeat",        # Repeat last command
    "recommence": "repeat",
    "encore": "repeat",
    "annule": "undo",          # Undo / cancel
    "stop": "stop",
    "arrete": "stop",
    "et aussi": "chain",       # Chain with previous
    "en plus": "chain",
    "egalement": "chain",
    "pareil": "repeat",
    "la meme chose": "repeat",
    "le contraire": "inverse",  # Inverse action
    "inverse": "inverse",
}

# Inverse action map (for "le contraire" / "inverse")
_INVERSE_MAP = {
    "mute": "unmute", "unmute": "mute",
    "monte le volume": "baisse le volume", "baisse le volume": "monte le volume",
    "ouvre": "ferme", "ferme": "ouvre",
    "lance": "arrete", "arrete": "lance",
    "active": "desactive", "desactive": "active",
}


def _push_context(text: str, result: dict):
    """Push a voice interaction into the context ring buffer."""
    entry = {
        "text": text,
        "intent": result.get("intent", text),
        "command": result.get("command"),
        "method": result.get("method", ""),
        "confidence": result.get("confidence", 0),
        "timestamp": time.monotonic(),
    }
    _voice_context.append(entry)
    if len(_voice_context) > _CONTEXT_MAX:
        del _voice_context[0]


def _resolve_followup(text: str) -> dict | None:
    """Check if text is a follow-up referencing the previous context.

    Returns a modified result dict if follow-up resolved, None otherwise.
    """
    if not _voice_context:
        return None

    # Check context TTL
    last = _voice_context[-1]
    if time.monotonic() - last["timestamp"] > _CONTEXT_TTL:
        _voice_context.clear()
        return None

    text_lower = text.lower().strip()

    # Check each follow-up pattern
    for keyword, action_type in _FOLLOWUP_PATTERNS.items():
        if keyword in text_lower:
            if action_type == "repeat" and last.get("command"):
                print(f"  [CTX] Repeat: {last['intent']}", flush=True)
                _log_voice_event("context", text=text, method="repeat")
                return {
                    "text": text,
                    "corrected": last.get("intent", text),
                    "intent": last["intent"],
                    "command": last["command"],
                    "confidence": 0.90,
                    "method": "context_repeat",
                    "context_ref": last["intent"],
                }

            if action_type == "inverse":
                last_intent = last.get("intent", "").lower()
                for original, inverse in _INVERSE_MAP.items():
                    if original in last_intent:
                        new_intent = last_intent.replace(original, inverse)
                        print(f"  [CTX] Inverse: {last_intent} → {new_intent}", flush=True)
                        _log_voice_event("context", text=text, method="inverse")
                        return {
                            "text": text,
                            "corrected": new_intent,
                            "intent": new_intent,
                            "command": None,
                            "confidence": 0.80,
                            "method": "context_inverse",
                            "context_ref": last_intent,
                        }

            if action_type == "stop":
                return None  # Let the stop command flow through normally

    return None


# ── Multi-intent decomposition ───────────────────────────────────────────
_SPLIT_CONJUNCTIONS = re.compile(
    r"\s+(?:et\s+(?:aussi|ensuite|puis|apres)|et|puis|ensuite|apres\s+ca)\s+",
    re.IGNORECASE,
)


def _split_multi_intent(text: str) -> list[str]:
    """Split a multi-command utterance into individual intents.

    "ouvre chrome et lance spotify" → ["ouvre chrome", "lance spotify"]
    Returns [text] unchanged if no split is detected or segments are too short.
    """
    parts = _SPLIT_CONJUNCTIONS.split(text.strip())
    # Filter out tiny fragments (likely false positives)
    parts = [p.strip() for p in parts if len(p.strip()) >= 3]
    if len(parts) <= 1:
        return [text.strip()]
    return parts


async def _execute_multi_intent(
    parts: list[str],
    pipeline_fn,
    use_cache: bool = True,
) -> list[dict]:
    """Execute multiple intents sequentially, return list of results."""
    results = []
    for i, part in enumerate(parts):
        logger.info("Multi-intent [%d/%d]: %s", i + 1, len(parts), part)
        result = await _process_single_intent(part, pipeline_fn, use_cache)
        if result:
            results.append(result)
            _push_context(part, result)
    return results


async def _process_single_intent(
    text: str,
    pipeline_fn,
    use_cache: bool = True,
) -> dict | None:
    """Process a single intent through cache → correction → VCC → domino."""
    from src.voice_correction import full_correction_pipeline

    # Cache check
    if use_cache:
        cached = _cache_get(text)
        if cached:
            cached = dict(cached)
            cached["method"] = "cache"
            return cached

    # Correction pipeline
    result = await pipeline_fn(text, use_ia=True)
    _log_voice_event("correction", text=result.get("intent", text),
                     confidence=result.get("confidence", 0),
                     method=result.get("method", ""))

    # Voice Router — pilotage Linux complet (desktop + souris + dictee + fenetres + ecran)
    if not result.get("command"):
        try:
            from src.voice_router import route_voice_command
            routed = route_voice_command(text)
            if routed and routed.get("success"):
                result["command"] = text
                result["method"] = routed.get("method", "voice_control")
                result["confidence"] = routed.get("confidence", 0.85)
                result["vcc_output"] = routed.get("result", "")
                result["voice_module"] = routed.get("module", "")
        except Exception:
            pass

    # Domino execution
    if result.get("method") == "domino" and result.get("domino"):
        try:
            from src.voice_correction import execute_domino_result
            domino_result = await asyncio.to_thread(execute_domino_result, result)
            if domino_result and "error" not in domino_result:
                result["domino_result"] = domino_result
        except (ImportError, OSError, ValueError):
            pass

    # Cache result
    if use_cache and result.get("command"):
        _cache_set(text, result)

    return result


# ── Command cache (thread-safe) ─────────────────────────────────────────
_command_cache: dict[str, dict] = {}
_cache_lock = threading.Lock()
_CACHE_MAX = 200


def _cache_get(text: str) -> dict | None:
    with _cache_lock:
        return _command_cache.get(text.lower().strip())


def _cache_set(text: str, result: dict):
    key = text.lower().strip()
    with _cache_lock:
        if len(_command_cache) >= _CACHE_MAX:
            oldest = next(iter(_command_cache))
            del _command_cache[oldest]
        _command_cache[key] = result


# ── Voice shortcuts (ultra-fast commands) ─────────────────────────────────
# Auto-populated from voice_analytics: top N most-used commands bypass
# the full correction pipeline for <10ms latency.
_voice_shortcuts: dict[str, dict] = {}
_shortcuts_lock = threading.Lock()
_SHORTCUTS_MAX = 30
_shortcuts_last_refresh = 0.0
_SHORTCUTS_REFRESH_INTERVAL = 600.0  # Refresh every 10 minutes


def _refresh_voice_shortcuts():
    """Rebuild shortcuts from voice_analytics top commands."""
    global _shortcuts_last_refresh
    now = time.monotonic()
    if now - _shortcuts_last_refresh < _SHORTCUTS_REFRESH_INTERVAL:
        return
    _shortcuts_last_refresh = now

    try:
        import sqlite3
        db_path = Path(__file__).parent.parent / "data" / "jarvis.db"
        if not db_path.exists():
            return
        conn = sqlite3.connect(str(db_path), timeout=2)
        rows = conn.execute(
            "SELECT text, method, confidence FROM voice_analytics "
            "WHERE stage = 'execution' AND success = 1 AND text != '' "
            "GROUP BY text ORDER BY COUNT(*) DESC LIMIT ?",
            (_SHORTCUTS_MAX,),
        ).fetchall()
        conn.close()

        with _shortcuts_lock:
            _voice_shortcuts.clear()
            for text, method, confidence in rows:
                key = text.lower().strip()
                if key and confidence and float(confidence) >= 0.80:
                    _voice_shortcuts[key] = {
                        "intent": text,
                        "method": "shortcut",
                        "confidence": 1.0,
                        "original_method": method,
                    }
        logger.debug("Voice shortcuts refreshed: %d entries", len(_voice_shortcuts))
    except Exception:
        pass  # Never block pipeline


def get_voice_shortcuts() -> dict[str, dict]:
    """Get current voice shortcuts (read-only copy)."""
    with _shortcuts_lock:
        return dict(_voice_shortcuts)


def _shortcut_match(text: str) -> dict | None:
    """Check if text matches a voice shortcut. Returns result or None."""
    key = text.lower().strip()
    with _shortcuts_lock:
        return _voice_shortcuts.get(key)


# ── Confidence auto-tuning ─────────────────────────────────────────────
# Adaptive thresholds that adjust based on pipeline success rates

_confidence_thresholds = {
    "fuzzy_min": 0.55,       # Minimum for fuzzy matching
    "phonetic_min": 0.60,    # Minimum for phonetic matching
    "ia_trigger": 0.85,      # Below this → call IA correction
    "execute_min": 0.75,     # Minimum to auto-execute command
}
_tuning_last_check = 0.0
_TUNING_INTERVAL = 300.0  # Re-tune every 5 minutes


def get_confidence_thresholds() -> dict[str, float]:
    """Get current adaptive confidence thresholds."""
    return dict(_confidence_thresholds)


def _auto_tune_thresholds():
    """Adjust confidence thresholds based on recent voice_analytics success rates.

    Called periodically during voice_loop. Analyzes last 50 events:
    - If success rate > 90%: can lower thresholds slightly (more permissive)
    - If success rate < 70%: raise thresholds (more conservative)
    - If IA corrections dominate: lower ia_trigger to invoke IA sooner
    """
    global _tuning_last_check
    now = time.monotonic()
    if now - _tuning_last_check < _TUNING_INTERVAL:
        return
    _tuning_last_check = now

    try:
        import sqlite3
        db_path = Path(__file__).parent.parent / "data" / "jarvis.db"
        conn = sqlite3.connect(str(db_path), timeout=2)
        rows = conn.execute(
            "SELECT method, confidence, success FROM voice_analytics "
            "WHERE stage = 'correction' ORDER BY id DESC LIMIT 50"
        ).fetchall()
        conn.close()

        if len(rows) < 10:
            return  # Not enough data

        total = len(rows)
        successes = sum(1 for r in rows if r[2])
        success_rate = successes / total

        # Count by method
        methods = {}
        for r in rows:
            m = r[0] or "unknown"
            methods[m] = methods.get(m, 0) + 1

        ia_ratio = methods.get("ia", 0) / total
        phonetic_ratio = methods.get("phonetic_bidirectional", 0) / total

        # Adjust thresholds
        if success_rate > 0.90:
            # High success → slightly more permissive
            _confidence_thresholds["fuzzy_min"] = max(0.45, _confidence_thresholds["fuzzy_min"] - 0.02)
            _confidence_thresholds["execute_min"] = max(0.65, _confidence_thresholds["execute_min"] - 0.02)
        elif success_rate < 0.70:
            # Low success → more conservative
            _confidence_thresholds["fuzzy_min"] = min(0.70, _confidence_thresholds["fuzzy_min"] + 0.03)
            _confidence_thresholds["execute_min"] = min(0.90, _confidence_thresholds["execute_min"] + 0.03)

        if ia_ratio > 0.40:
            # IA used too often → lower trigger to catch more locally
            _confidence_thresholds["ia_trigger"] = max(0.70, _confidence_thresholds["ia_trigger"] - 0.03)

        if phonetic_ratio > 0.30:
            # Phonetic matching working well → can be slightly less strict
            _confidence_thresholds["phonetic_min"] = max(0.50, _confidence_thresholds["phonetic_min"] - 0.02)

        logger.debug("Auto-tune: success=%.0f%% thresholds=%s", success_rate * 100, _confidence_thresholds)

    except Exception:
        pass  # Never block voice pipeline for tuning


# ── Smart confidence confirmation ─────────────────────────────────────────
_CONFIRM_MIN = 0.60   # Below this → reject silently
_CONFIRM_MAX = 0.80   # Above this → auto-execute
_CONFIRM_YES = re.compile(
    r"^(?:oui|ouais|yes|ok|go|exactement|exact|c'est ca|affirmatif|valide|correct)\b",
    re.IGNORECASE,
)
_CONFIRM_NO = re.compile(
    r"^(?:non|no|nope|pas ca|annule|stop|arrete|pas du tout|incorrect)\b",
    re.IGNORECASE,
)


def needs_confirmation(confidence: float) -> bool:
    """Check if a result falls in the confirmation zone (grey area)."""
    return _CONFIRM_MIN <= confidence < _CONFIRM_MAX


def parse_confirmation(text: str) -> bool | None:
    """Parse user's yes/no response. Returns True/False/None (ambiguous)."""
    t = text.strip().lower()
    if _CONFIRM_YES.search(t):
        return True
    if _CONFIRM_NO.search(t):
        return False
    return None


# Push-to-talk config
PTT_KEY = "ctrl"

# Audio recording config
SAMPLE_RATE = 16000
CHANNELS = 1

# Whisper worker config
WHISPER_WORKER_SCRIPT = Path(__file__).parent / "whisper_worker.py"


def _find_system_python() -> Path:
    """Find system Python — dynamic version detection for Linux."""
    import shutil
    for name in ("python3", "python"):
        found = shutil.which(name)
        if found:
            p = Path(found)
            # Use /usr/bin/python3 as primary choice on Linux
            if "/usr/bin" in str(p):
                return p
    return Path("/usr/bin/python3")


SYSTEM_PYTHON = _find_system_python()

# OL1 config for voice correction (fast, 192 tok/s, always loaded)
try:
    from src.config import config as _cfg
    _ol_url = _cfg.ollama_nodes[0].url if _cfg.ollama_nodes else "http://127.0.0.1:11434"
except ImportError:
    _ol_url = "http://127.0.0.1:11434"
OLLAMA_URL = f"{_ol_url}/api/chat"
OLLAMA_MODEL = "qwen3:1.7b"


# ── Mic detection ─────────────────────────────────────────────────────────

def _get_input_device() -> int | None:
    """Find the best available input device by testing each one."""
    devices = sd.query_devices()
    default_input = sd.default.device[0]
    candidates = []
    for i, d in enumerate(devices):
        if d['max_input_channels'] > 0:
            name_lower = d['name'].lower()
            if i == default_input and default_input >= 0:
                priority = 0
            elif 'casque' in name_lower or 'headset' in name_lower:
                priority = 1
            elif 'microphone' in name_lower:
                priority = 2
            else:
                priority = 3
            candidates.append((priority, i, d))
    candidates.sort()
    for _, idx, d in candidates:
        try:
            with sd.InputStream(device=idx, samplerate=SAMPLE_RATE, channels=1,
                                dtype='int16', blocksize=1024):
                return idx
        except (sd.PortAudioError, OSError):
            continue
    return None


_mic_cache: dict = {"ok": False, "ts": None, "device": None}


def check_microphone() -> bool:
    """Check if any working microphone is available (cached 30s)."""
    import time
    now = time.monotonic()
    if _mic_cache["ts"] and (now - _mic_cache["ts"]) < 30.0:
        return _mic_cache["ok"]
    dev = _get_input_device()
    _mic_cache["ok"] = dev is not None
    _mic_cache["ts"] = now
    _mic_cache["device"] = dev
    return _mic_cache["ok"]


def get_cached_input_device() -> int | None:
    if _mic_cache["device"] is not None:
        return _mic_cache["device"]
    return _get_input_device()


HAS_MICROPHONE = check_microphone()


# ── Persistent Whisper Worker ─────────────────────────────────────────────

class WhisperWorker:
    """Manages a persistent faster-whisper subprocess (model loaded once)."""

    def __init__(self):
        self._process: subprocess.Popen | None = None
        self._lock = threading.Lock()
        self._ready = False

    def start(self) -> bool:
        """Start the whisper worker process. Returns True when model is loaded."""
        if self._process and self._process.poll() is None:
            return self._ready

        if not SYSTEM_PYTHON.exists() or not WHISPER_WORKER_SCRIPT.exists():
            return False

        try:
            self._process = subprocess.Popen(
                [str(SYSTEM_PYTHON), str(WHISPER_WORKER_SCRIPT)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                encoding="utf-8",
                errors="replace",
                bufsize=1,  # Line buffered
            )
            # Wait for WHISPER_READY
            line1 = self._process.stdout.readline().strip()
            if "WHISPER_READY" in line1:
                print(f"  [WHISPER] {line1}", flush=True)
            # Wait for WHISPER_LOADED
            line2 = self._process.stdout.readline().strip()
            if "WHISPER_LOADED" in line2:
                print(f"  [WHISPER] {line2}", flush=True)
                self._ready = True
            if not self._ready:
                # Kill the process if it didn't start properly
                self._process.kill()
                self._process = None
            return self._ready
        except (OSError, subprocess.SubprocessError) as e:
            logger.debug("Whisper worker start failed: %s", e)
            if self._process:
                try:
                    self._process.kill()
                except OSError:
                    pass
                self._process = None
            return False

    def transcribe(self, wav_path: str, on_segment=None) -> str | None:
        """Send a WAV path to the worker and get transcription back.

        Args:
            wav_path: Path to WAV file
            on_segment: Optional callback(segment_text) for streaming segments
        """
        with self._lock:
            if not self._process or self._process.poll() is not None:
                if not self.start():
                    return None

            try:
                self._process.stdin.write(wav_path + "\n")
                self._process.stdin.flush()
                full_text = ""
                while True:
                    line = self._process.stdout.readline().strip()
                    if line.startswith("DONE:"):
                        full_text = line[5:].strip()
                        break
                    elif line.startswith("SEGMENT:"):
                        segment = line[8:].strip()
                        if on_segment and segment:
                            on_segment(segment)
                    elif line == "":
                        break  # Empty = error or EOF
                return full_text if full_text else None
            except (OSError, BrokenPipeError) as e:
                logger.debug("Whisper transcribe error: %s", e)
                self._ready = False
                return None

    def stop(self):
        """Shutdown the worker."""
        if self._process and self._process.poll() is None:
            try:
                self._process.stdin.write("QUIT\n")
                self._process.stdin.flush()
                self._process.wait(timeout=5)
            except (OSError, BrokenPipeError):
                self._process.kill()
        self._ready = False


# Global worker instance
_whisper_worker = WhisperWorker()


# ── OL1 voice correction ─────────────────────────────────────────────────

async def analyze_with_lm(raw_text: str) -> dict:
    """Ask OL1/qwen3:1.7b to analyze/correct voice transcription.

    Returns: {"corrected": str, "intent": str, "confidence": float}
    """
    import httpx

    prompt = (
        f"Transcription vocale brute: \"{raw_text}\"\n\n"
        "Tu es un correcteur vocal pour JARVIS (assistant IA). "
        "Corrige les erreurs de transcription et identifie l'intention.\n"
        "Reponds UNIQUEMENT en JSON:\n"
        '{"corrected": "texte corrige", "intent": "commande claire", "confidence": 0.95}\n'
        "Pas de markdown, pas d'explication."
    )

    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.post(OLLAMA_URL, json={
                "model": OLLAMA_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "think": False,
                "options": {"temperature": 0.1, "num_predict": 150},
            })
            if resp.status_code == 200:
                content = resp.json().get("message", {}).get("content", "").strip()
                if content.startswith("```"):
                    content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()
                data = json.loads(content)
                return {
                    "corrected": data.get("corrected", raw_text),
                    "intent": data.get("intent", raw_text),
                    "confidence": float(data.get("confidence", 0.5)),
                }
    except (httpx.HTTPError, asyncio.TimeoutError, json.JSONDecodeError, OSError) as exc:
        logger.debug("analyze_with_lm failed: %s", exc)

    return {"corrected": raw_text, "intent": raw_text, "confidence": 0.5}


# ── PTT + Recording ──────────────────────────────────────────────────────

async def wait_for_ptt(key: str = PTT_KEY, timeout: float = 30.0) -> bool:
    """Wait for push-to-talk key press."""
    if not HAS_KEYBOARD:
        return True
    event = threading.Event()

    def on_press(e):
        if e.name == key:
            event.set()

    hook = kb.on_press(on_press)
    try:
        return await asyncio.to_thread(event.wait, timeout)
    finally:
        kb.unhook(hook)


def _record_while_key_held(key: str = PTT_KEY, max_duration: float = 30.0) -> np.ndarray | None:
    """Record audio while the PTT key is held down."""
    frames: list[np.ndarray] = []
    stop_event = threading.Event()

    if HAS_KEYBOARD:
        def on_release(e):
            if e.name == key:
                stop_event.set()
        hook = kb.on_release(on_release)
    else:
        hook = None

    def audio_callback(indata, frame_count, time_info, status):
        if not stop_event.is_set():
            frames.append(indata.copy())

    device = get_cached_input_device()
    if device is None:
        return None

    try:
        with sd.InputStream(device=device, samplerate=SAMPLE_RATE, channels=CHANNELS,
                            dtype='int16', callback=audio_callback,
                            blocksize=1024):
            stop_event.wait(timeout=max_duration)
    finally:
        if hook is not None:
            kb.unhook(hook)

    if not frames:
        return None
    return np.concatenate(frames, axis=0)


def _save_wav(audio: np.ndarray, path: str) -> None:
    """Save numpy int16 audio to WAV file."""
    with wave.open(path, 'wb') as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(audio.tobytes())


# ── Noise Gate (adaptive) ─────────────────────────────────────────────────

class NoiseGate:
    """Adaptive noise gate that calibrates to ambient noise level.

    Measures the noise floor during a calibration period, then applies
    a gate that suppresses audio below floor + margin.
    """

    def __init__(self, calibration_chunks: int = 8, margin_db: float = 6.0):
        self.calibration_chunks = calibration_chunks
        self.margin_db = margin_db
        self._noise_floor: float = 0.0
        self._threshold: float = 0.0
        self._calibration_buffer: list[float] = []
        self._calibrated = False

    def calibrate_chunk(self, chunk: np.ndarray) -> bool:
        """Feed a calibration chunk. Returns True when calibration is done."""
        rms = float(np.sqrt(np.mean(chunk.astype(np.float64) ** 2)))
        self._calibration_buffer.append(rms)
        if len(self._calibration_buffer) >= self.calibration_chunks:
            self._noise_floor = sum(self._calibration_buffer) / len(self._calibration_buffer)
            # Threshold = noise floor * margin (in linear scale from dB)
            linear_margin = 10 ** (self.margin_db / 20)
            self._threshold = self._noise_floor * linear_margin
            self._calibrated = True
            logger.debug("NoiseGate calibrated: floor=%.1f threshold=%.1f",
                         self._noise_floor, self._threshold)
            return True
        return False

    @property
    def is_calibrated(self) -> bool:
        return self._calibrated

    @property
    def noise_floor(self) -> float:
        return self._noise_floor

    def apply(self, chunk: np.ndarray) -> np.ndarray:
        """Apply noise gate: zero out audio below threshold."""
        if not self._calibrated:
            return chunk
        rms = float(np.sqrt(np.mean(chunk.astype(np.float64) ** 2)))
        if rms < self._threshold:
            return np.zeros_like(chunk)
        return chunk


# ── Timed recording (post wake-word) ─────────────────────────────────────

def _record_timed(max_duration: float = 5.0, use_vad: bool = True) -> np.ndarray | None:
    """Record audio for a fixed duration with VAD-based end-of-speech detection.

    v4: Noise gate calibration + Silero VAD + amplitude fallback.
    """
    import time
    frames: list[np.ndarray] = []
    device = get_cached_input_device()
    if device is None:
        return None

    # Initialize VAD
    vad = None
    if use_vad:
        try:
            from src.vad import VoiceActivityDetector
            vad = VoiceActivityDetector(
                min_speech_ms=200,
                min_silence_ms=700,
            )
            vad.start()
        except (ImportError, Exception) as exc:
            logger.debug("VAD unavailable, falling back to amplitude: %s", exc)
            vad = None

    # Initialize noise gate
    noise_gate = NoiseGate(calibration_chunks=8, margin_db=6.0)

    try:
        with sd.InputStream(device=device, samplerate=SAMPLE_RATE, channels=CHANNELS,
                            dtype='int16', blocksize=1024) as stream:
            start = time.monotonic()
            silence_count = 0

            # Phase 1: Calibrate noise gate (~500ms)
            while not noise_gate.is_calibrated:
                if time.monotonic() - start > 1.0:
                    break  # Don't spend more than 1s calibrating
                data, _ = stream.read(1024)
                noise_gate.calibrate_chunk(data)

            # Phase 2: Record with noise gate + VAD
            while time.monotonic() - start < max_duration:
                data, _ = stream.read(1024)
                gated = noise_gate.apply(data)
                frames.append(data.copy())  # Keep original for quality

                if vad is not None:
                    result = vad.process_chunk(gated)
                    if result["utterance_complete"] and result["speech_audio"] is not None:
                        return result["speech_audio"]
                else:
                    amplitude = np.abs(gated).mean()
                    if amplitude < 200:
                        silence_count += 1
                    else:
                        silence_count = 0
                    if silence_count > 23:
                        break
    except (sd.PortAudioError, OSError) as exc:
        logger.debug("_record_timed audio error: %s", exc)

    if not frames:
        return None

    raw_audio = np.concatenate(frames, axis=0)

    # Post-process with VAD: strip silence from recording
    if vad is not None:
        speech = vad.extract_speech(raw_audio)
        if speech is not None and len(speech) > SAMPLE_RATE * 0.3:
            return speech

    return raw_audio


# ── Main listen function ─────────────────────────────────────────────────

async def listen_voice(timeout: float = 15.0, keyboard_fallback: bool = True, use_ptt: bool = False) -> str | None:
    """Record voice → Whisper transcribe → OL1 analyze.

    Returns the analyzed/corrected text, or None.
    """
    if not check_microphone():
        if keyboard_fallback:
            try:
                text = await asyncio.to_thread(input, "[JARVIS] > ")
                return text.strip() if text and text.strip() else None
            except (EOFError, KeyboardInterrupt):
                return None
        return None

    # PTT: wait for Ctrl press
    if use_ptt and HAS_KEYBOARD:
        print(f"  [Maintiens {PTT_KEY.upper()} pour parler...]", flush=True)
        pressed = await wait_for_ptt(timeout=30.0)
        if not pressed:
            return None
        print("  [Enregistrement... relache CTRL]", flush=True)

    # Record while key held
    audio = await asyncio.to_thread(_record_while_key_held, PTT_KEY, timeout)

    if audio is None or len(audio) < SAMPLE_RATE * 0.3:
        return None

    duration = len(audio) / SAMPLE_RATE
    print(f"  [Enregistre {duration:.1f}s — transcription Whisper...]", flush=True)

    # Save WAV
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        wav_path = tmp.name
    _save_wav(audio, wav_path)

    # Transcribe via persistent worker
    try:
        text = await asyncio.to_thread(_whisper_worker.transcribe, wav_path)
    finally:
        Path(wav_path).unlink(missing_ok=True)

    if not text:
        print("  [Pas de parole detectee]", flush=True)
        return None

    print(f"  [STT] {text}", flush=True)

    # LM Studio analysis/correction
    print(f"  [Analyse IA...]", flush=True)
    analysis = await analyze_with_lm(text)
    corrected = analysis["intent"]
    confidence = analysis["confidence"]

    if corrected != text:
        print(f"  [IA] {corrected} (conf={confidence:.0%})", flush=True)

    return corrected


# ── Voice Learning Handler ────────────────────────────────────────────────

_LEARN_PATTERNS = [
    re.compile(r"(?:apprends|retiens|quand je dis)\s+['\"]?(.+?)['\"]?\s*(?:fais|lance|execute|fait)\s+['\"]?(.+?)['\"]?$", re.IGNORECASE),
    re.compile(r"(?:associe|mappe|lie)\s+['\"]?(.+?)['\"]?\s*(?:a|à|avec)\s+['\"]?(.+?)['\"]?$", re.IGNORECASE),
    re.compile(r"(?:oublie|supprime le trigger|desapprends)\s+['\"]?(.+?)['\"]?$", re.IGNORECASE),
]


def _handle_voice_learning(text: str) -> dict | None:
    """Detect and handle voice learning commands.

    Patterns:
      - "apprends [trigger] fais [action]"
      - "quand je dis [trigger] lance [commande]"
      - "oublie [trigger]"

    Returns a result dict if a learning command was detected, None otherwise.
    """
    normalized = text.lower().strip()

    # Pattern: learn/associate
    for pattern in _LEARN_PATTERNS[:2]:
        m = pattern.search(normalized)
        if m:
            trigger = m.group(1).strip()
            target = m.group(2).strip()
            from src.commands import learn_voice_command, match_command
            # Try mapping to existing command first
            matched_cmd, _, score = match_command(target, threshold=0.5)
            if matched_cmd and score >= 0.5:
                result = learn_voice_command(trigger, target_command=matched_cmd.name)
            else:
                result = learn_voice_command(trigger, action=target, action_type="bash")

            if result["success"]:
                msg = f"OK. '{trigger}' → {result['command']} ({result['method']})"
                print(f"  [LEARN] {msg}", flush=True)
                _log_voice_event("learn", text=trigger, method=result["method"], success=True)
                return {
                    "text": text, "corrected": text, "intent": msg,
                    "confidence": 1.0, "method": "voice_learning",
                    "command": None, "learn_result": result,
                }
            else:
                msg = f"Echec: {result.get('error', 'inconnu')}"
                print(f"  [LEARN] {msg}", flush=True)
                _log_voice_event("learn", text=trigger, success=False)
                return {
                    "text": text, "corrected": text, "intent": msg,
                    "confidence": 1.0, "method": "voice_learning",
                    "command": None, "learn_result": result,
                }

    # Pattern: unlearn
    m = _LEARN_PATTERNS[2].search(normalized)
    if m:
        trigger = m.group(1).strip()
        from src.commands import unlearn_voice_command
        result = unlearn_voice_command(trigger)
        if result["success"]:
            msg = f"Trigger '{trigger}' supprime."
            _log_voice_event("unlearn", text=trigger, success=True)
        else:
            msg = f"Echec: {result.get('error', 'inconnu')}"
            _log_voice_event("unlearn", text=trigger, success=False)
        print(f"  [UNLEARN] {msg}", flush=True)
        return {
            "text": text, "corrected": text, "intent": msg,
            "confidence": 1.0, "method": "voice_unlearning",
            "command": None, "learn_result": result,
        }

    return None


# ── Voice Pipeline v2 ────────────────────────────────────────────────────

async def listen_voice_v2(
    use_wake_word: bool = True,
    use_cache: bool = True,
    timeout: float = 30.0,
) -> dict | None:
    """Voice Pipeline v2 — Wake word + streaming STT + local-first routing.

    Returns full correction result dict, or None.
    """
    t0 = time.monotonic()

    # Step 1: Wait for wake word or PTT
    wake_method = "ptt"
    if use_wake_word:
        wake_event = asyncio.Event()

        def on_wake():
            wake_event.set()

        from src.wake_word import WakeWordDetector
        detector = WakeWordDetector(callback=on_wake)
        device = get_cached_input_device()
        if detector.start(device=device):
            print("  [En attente de 'Jarvis'...]", flush=True)
            try:
                await asyncio.wait_for(wake_event.wait(), timeout=timeout)
                print("  [Wake word detecte! Parle...]", flush=True)
                wake_method = "wake"
            except asyncio.TimeoutError:
                detector.stop()
                return None
            finally:
                detector.stop()
        else:
            # Fallback to PTT if wake word fails
            print(f"  [Wake word indisponible, maintiens {PTT_KEY.upper()}...]", flush=True)
            if not await wait_for_ptt(timeout=timeout):
                return None

        # Record after wake word (timed with silence detection)
        audio = await asyncio.to_thread(_record_timed, 5.0)
    else:
        # PTT mode
        if not await wait_for_ptt(timeout=timeout):
            return None
        audio = await asyncio.to_thread(_record_while_key_held, PTT_KEY, 15.0)

    _log_voice_event("wake_word", method=wake_method)

    if audio is None or len(audio) < SAMPLE_RATE * 0.3:
        return None

    # Step 2: Save + transcribe with streaming segments
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        wav_path = tmp.name
    _save_wav(audio, wav_path)

    t_stt_start = time.monotonic()

    def _on_segment(segment_text: str):
        print(f"  [STT...] {segment_text}", flush=True)

    try:
        text = await asyncio.to_thread(
            _whisper_worker.transcribe, wav_path, _on_segment
        )
    finally:
        Path(wav_path).unlink(missing_ok=True)

    stt_latency_ms = (time.monotonic() - t_stt_start) * 1000

    if not text:
        print("  [Pas de parole detectee]", flush=True)
        _log_voice_event("stt", latency_ms=stt_latency_ms, success=False)
        return None

    print(f"  [STT] {text}", flush=True)
    _log_voice_event("stt", text=text, latency_ms=stt_latency_ms)

    # Step 2.5: Check for voice learning commands
    learn_result = _handle_voice_learning(text)
    if learn_result is not None:
        return learn_result

    # Step 2.6: Check for contextual follow-ups ("refais", "annule", "le contraire")
    followup = _resolve_followup(text)
    if followup is not None:
        _push_context(text, followup)
        return followup

    # Step 2.7: Voice shortcuts (ultra-fast, <10ms)
    _refresh_voice_shortcuts()
    shortcut = _shortcut_match(text)
    if shortcut is not None:
        shortcut = dict(shortcut)  # Copy
        # Resolve command from commands index
        from src.commands import _trigger_exact
        trigger_match = _trigger_exact.get(text.lower().strip())
        if trigger_match:
            shortcut["command"] = trigger_match[0]
        print(f"  [SHORTCUT] {shortcut['intent']}", flush=True)
        _log_voice_event("correction", text=shortcut["intent"],
                         confidence=1.0, method="shortcut")
        _push_context(text, shortcut)
        return shortcut

    # Step 3: Multi-intent decomposition
    from src.voice_correction import full_correction_pipeline
    parts = _split_multi_intent(text)

    if len(parts) > 1:
        # Multi-intent: "ouvre chrome et lance spotify"
        print(f"  [MULTI] {len(parts)} intents detectes: {parts}", flush=True)
        results = await _execute_multi_intent(parts, full_correction_pipeline, use_cache)
        _log_voice_event("execution", text=text,
                         success=any(r.get("command") for r in results),
                         method="multi_intent",
                         latency_ms=(time.monotonic() - t0) * 1000)
        if results:
            # Return combined result
            combined = {
                "intent": text,
                "method": "multi_intent",
                "confidence": min(r.get("confidence", 0) for r in results),
                "command": results[0].get("command"),
                "sub_results": results,
            }
            _push_context(text, combined)
            return combined
        return None

    # Step 4: Single intent — cache → correction → VCC → domino
    result = await _process_single_intent(text, full_correction_pipeline, use_cache)
    if result:
        print(f"  [MATCH] method={result['method']}, confidence={result['confidence']:.0%}", flush=True)

    if not result:
        result = {"intent": text, "method": "none", "confidence": 0.0, "command": None}

    # Step 5: Record action for prediction engine
    if result.get("command"):
        try:
            from src.prediction_engine import prediction_engine
            from datetime import datetime as _dt
            _now = _dt.now()
            prediction_engine.record_action(result["command"], {
                "source": "voice",
                "method": result.get("method", ""),
                "confidence": result.get("confidence", 0),
                "hour": _now.hour,
                "weekday": _now.weekday(),
            })
        except Exception:
            pass

    _log_voice_event("execution", text=result.get("intent", ""),
                     success=bool(result.get("command")),
                     latency_ms=(time.monotonic() - t0) * 1000)

    # Step 6: Push to conversation context for follow-ups
    _push_context(text, result)

    return result


# ── TTS ───────────────────────────────────────────────────────────────────

async def speak_text(text: str, voice: str = "fr-FR") -> bool:
    """Speak text using Edge TTS streaming (Linux-native)."""
    if not text or not text.strip():
        return False
    try:
        from src.tts_streaming import speak_streaming
        await speak_streaming(text)
        return True
    except Exception as exc:
        logger.debug("speak_text failed: %s", exc)
        return False


async def _warmup_ollama():
    """Ping OL1 to keep model warm. Exponential backoff on failure."""
    import httpx
    delay = 60  # Start at 60s
    max_delay = 600  # Max 10 minutes between retries
    consecutive_failures = 0

    while True:
        try:
            async with httpx.AsyncClient(timeout=2) as c:
                resp = await c.post(OLLAMA_URL, json={
                    "model": OLLAMA_MODEL,
                    "messages": [{"role": "user", "content": "ping"}],
                    "stream": False, "think": False,
                    "options": {"num_predict": 1},
                })
                if resp.status_code == 200:
                    consecutive_failures = 0
                    delay = 60  # Reset on success
                else:
                    consecutive_failures += 1
        except (httpx.HTTPError, OSError) as exc:
            consecutive_failures += 1
            if consecutive_failures <= 3:
                logger.debug("Ollama warmup failed (%d): %s", consecutive_failures, exc)
            elif consecutive_failures == 4:
                logger.warning("Ollama warmup: 4 consecutive failures, backing off")

        if consecutive_failures > 0:
            delay = min(delay * 2, max_delay)

        await asyncio.sleep(delay)


# ── Startup / Shutdown ────────────────────────────────────────────────────

def start_whisper() -> bool:
    """Start the persistent Whisper worker (call at JARVIS startup)."""
    return _whisper_worker.start()


def stop_whisper():
    """Stop the Whisper worker (call at JARVIS shutdown)."""
    _whisper_worker.stop()


async def voice_loop(callback, use_wake_word: bool = True) -> None:
    """Continuous voice listening loop (v2 with wake word support)."""
    from src.voice_session import start_voice_session, end_voice_session

    mode = "wake word" if use_wake_word else "PTT"
    session = start_voice_session(
        mode="wake" if use_wake_word else "ptt",
        voice="denise",
    )
    print(f"[JARVIS] Mode vocal v2 actif ({mode}). Session: {session.session_id}", flush=True)

    warmup_task = asyncio.create_task(_warmup_ollama())
    interrupt_event = asyncio.Event()

    try:
        while True:
            interrupt_event.clear()
            _auto_tune_thresholds()
            result = await listen_voice_v2(use_wake_word=use_wake_word, timeout=30.0)
            if result:
                intent = result.get("intent", "")
                if intent.lower().strip() in ("stop", "arrete", "exit", "quitter"):
                    from src.tts_streaming import speak_quick
                    await speak_quick("Session vocale terminee.")
                    break

                cmd = result.get("command")
                conf = result.get("confidence", 0)

                # Smart confirmation for grey-zone confidence
                if cmd and needs_confirmation(conf):
                    from src.tts_streaming import speak_quick
                    cmd_name = cmd.triggers[0] if hasattr(cmd, "triggers") else str(cmd)
                    await speak_quick(f"Tu veux dire {cmd_name} ?")
                    print(f"[VOICE] Confirmation? '{cmd_name}' (conf={conf:.0%})", flush=True)

                    # Listen for yes/no
                    confirm_result = await listen_voice_v2(
                        use_wake_word=False, use_cache=False, timeout=8.0
                    )
                    if confirm_result:
                        answer = parse_confirmation(confirm_result.get("intent", ""))
                        if answer is True:
                            print(f"[VOICE] Confirme: {cmd_name}", flush=True)
                            _log_voice_event("confirmation", text=intent,
                                             confidence=conf, success=True)
                            session.record_confirmation(accepted=True)
                        else:
                            print(f"[VOICE] Annule: {cmd_name}", flush=True)
                            _log_voice_event("confirmation", text=intent,
                                             confidence=conf, success=False)
                            session.record_confirmation(accepted=False)
                            continue
                    else:
                        # No response → treat as cancel
                        print(f"[VOICE] Pas de reponse, annule.", flush=True)
                        session.record_confirmation(accepted=False)
                        continue

                if cmd:
                    print(f"[VOICE] {cmd.triggers[0] if hasattr(cmd, 'triggers') else cmd} (conf={conf:.0%})", flush=True)
                else:
                    print(f"[VOICE] Freeform: {intent}", flush=True)

                # Record to session
                session.record_command(
                    intent=intent,
                    method=result.get("method", "unknown"),
                    confidence=conf,
                    success=bool(cmd),
                )

                response = await callback(intent)

                if response:
                    from src.tts_streaming import speak_interruptible
                    await speak_interruptible(str(response), interrupt_event=interrupt_event)
    finally:
        warmup_task.cancel()
        final_stats = end_voice_session()
        if final_stats:
            logger.info("Session ended: %d commands, %.0f%% success",
                        final_stats["stats"]["total_commands"],
                        final_stats["stats"]["success_rate"])
