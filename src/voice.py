"""JARVIS Voice Interface — Persistent Whisper + LM Studio analysis + TTS.

Flow:
1. Ctrl press → record audio (sounddevice)
2. Ctrl release → transcribe via persistent faster-whisper worker (CUDA)
3. LM Studio (M1/M2) analyzes intent → proposes corrected command
4. User validates → JARVIS executes
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
import tempfile
import threading
import wave
from pathlib import Path

import numpy as np
import sounddevice as sd

try:
    import keyboard as kb
    HAS_KEYBOARD = True
except ImportError:
    HAS_KEYBOARD = False


# Push-to-talk config
PTT_KEY = "ctrl"

# Audio recording config
SAMPLE_RATE = 16000
CHANNELS = 1

# Whisper worker config
SYSTEM_PYTHON = Path("C:/Users/franc/AppData/Local/Programs/Python/Python312/python.exe")
WHISPER_WORKER_SCRIPT = Path(__file__).parent / "whisper_worker.py"

# LM Studio config for voice correction (M1 fallback, primary is Ollama qwen3:1.7b)
LM_STUDIO_URL = "http://10.5.0.2:1234/api/v1/chat"
LM_CORRECTION_MODEL = "qwen/qwen3-30b-a3b-2507"  # M1 fallback (primary: Ollama qwen3:1.7b)


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
        except Exception:
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
            return self._ready
        except Exception as e:
            print(f"  [WHISPER] Failed to start: {e}", flush=True)
            return False

    def transcribe(self, wav_path: str) -> str | None:
        """Send a WAV path to the worker and get transcription back."""
        with self._lock:
            if not self._process or self._process.poll() is not None:
                if not self.start():
                    return None

            try:
                self._process.stdin.write(wav_path + "\n")
                self._process.stdin.flush()
                result = self._process.stdout.readline().strip()
                return result if result else None
            except Exception as e:
                print(f"  [WHISPER] Error: {e}", flush=True)
                self._ready = False
                return None

    def stop(self):
        """Shutdown the worker."""
        if self._process and self._process.poll() is None:
            try:
                self._process.stdin.write("QUIT\n")
                self._process.stdin.flush()
                self._process.wait(timeout=5)
            except Exception:
                self._process.kill()
        self._ready = False


# Global worker instance
_whisper_worker = WhisperWorker()


# ── LM Studio voice correction ───────────────────────────────────────────

async def analyze_with_lm(raw_text: str) -> dict:
    """Ask LM Studio to analyze/correct voice transcription.

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
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.post(LM_STUDIO_URL, json={
                "model": LM_CORRECTION_MODEL,
                "input": prompt,
                "max_output_tokens": 150,
                "temperature": 0.1,
                "stream": False,
                "store": False,
            })
            if resp.status_code == 200:
                from src.tools import extract_lms_output
                content = extract_lms_output(resp.json()).strip()
                # Parse JSON response
                import json
                # Handle possible markdown wrapping
                if content.startswith("```"):
                    content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()
                data = json.loads(content)
                return {
                    "corrected": data.get("corrected", raw_text),
                    "intent": data.get("intent", raw_text),
                    "confidence": float(data.get("confidence", 0.5)),
                }
    except Exception:
        pass

    # Fallback: return raw text as-is
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


# ── Main listen function ─────────────────────────────────────────────────

async def listen_voice(timeout: float = 15.0, keyboard_fallback: bool = True, use_ptt: bool = False) -> str | None:
    """Record voice → Whisper transcribe → LM Studio analyze.

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


# ── TTS ───────────────────────────────────────────────────────────────────

async def speak_text(text: str, voice: str = "fr-FR") -> bool:
    """Synthesize speech via Windows SAPI (PowerShell)."""
    if not text or not text.strip():
        return False

    clean = text.replace('"', "'").replace("\n", " ").replace("**", "")
    if len(clean) > 500:
        clean = clean[:497] + "..."

    ps_path = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ps1', delete=False, encoding='utf-8') as f:
            f.write(
                'Add-Type -AssemblyName System.Speech\n'
                '$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer\n'
                f'$synth.SelectVoiceByHints("NotSet", 0, 0, '
                f'[System.Globalization.CultureInfo]::GetCultureInfo("{voice}"))\n'
                f'$synth.Speak("{clean}")\n'
            )
            ps_path = f.name

        result = await asyncio.to_thread(
            lambda: subprocess.run(
                ["powershell", "-ExecutionPolicy", "Bypass", "-File", ps_path],
                capture_output=True, text=True, timeout=30,
            )
        )
        return result.returncode == 0
    except Exception:
        return False
    finally:
        if ps_path:
            Path(ps_path).unlink(missing_ok=True)


# ── Startup / Shutdown ────────────────────────────────────────────────────

def start_whisper() -> bool:
    """Start the persistent Whisper worker (call at JARVIS startup)."""
    return _whisper_worker.start()


def stop_whisper():
    """Stop the Whisper worker (call at JARVIS shutdown)."""
    _whisper_worker.stop()


async def voice_loop(callback) -> None:
    """Continuous voice listening loop."""
    print("[JARVIS] Mode vocal actif. Maintiens CTRL pour parler.")
    while True:
        text = await listen_voice(timeout=15.0, use_ptt=True)
        if text:
            if text.lower().strip() in ("stop", "arrete", "exit", "quitter"):
                await speak_text("Session vocale terminee.")
                break
            print(f"[VOICE] {text}")
            response = await callback(text)
            if response:
                await speak_text(response)
