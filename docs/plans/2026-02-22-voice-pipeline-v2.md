# Voice Pipeline v2 — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reduce JARVIS voice command latency from ~15s to <2s via streaming architecture, local-first routing, and OL1 fast correction.

**Architecture:** Replace sequential Record-Whisper-M1-TTS pipeline with streaming wake word detection, chunk-by-chunk Whisper transcription (beam=1), local-first command matching with IA bypass for high-confidence matches, and streaming TTS output.

**Tech Stack:** OpenWakeWord (wake word), faster-whisper (STT), OL1/qwen3:1.7b (correction IA), edge-tts (TTS streaming), asyncio (orchestration)

---

### Task 1: Install dependencies

**Files:**
- Modify: `F:/BUREAU/turbo/pyproject.toml`

**Step 1: Add new dependencies to pyproject.toml**

Add to `[project.dependencies]`:
```toml
"openwakeword>=0.6.0",
"edge-tts>=6.1.0",
```

Note: `faster-whisper` is already installed system-wide via Python 3.12. `edge-tts` replaces batch TTS. `openwakeword` provides local wake word detection.

**Step 2: Install dependencies**

Run: `cd F:/BUREAU/turbo && uv pip install openwakeword edge-tts`
Expected: packages installed successfully

**Step 3: Verify imports work**

Run: `cd F:/BUREAU/turbo && python -c "import openwakeword; import edge_tts; print('OK')"`
Expected: `OK`

**Step 4: Commit**

```bash
cd F:/BUREAU/turbo
git add pyproject.toml
git commit -m "feat(voice): add openwakeword + edge-tts dependencies for pipeline v2"
```

---

### Task 2: Create wake_word.py — Local "Jarvis" detection

**Files:**
- Create: `F:/BUREAU/turbo/src/wake_word.py`

**Step 1: Create wake_word.py with OpenWakeWord listener**

A background thread listens to the microphone continuously. When "jarvis" is detected above threshold 0.7, it fires a callback. CPU-only, ~50ms latency.

Key design: WakeWordDetector class with start/stop lifecycle, daemon thread, 1s cooldown to avoid double triggers.

**Step 2: Smoke test — verify module imports**

Run: `cd F:/BUREAU/turbo && python -c "from src.wake_word import WakeWordDetector; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
cd F:/BUREAU/turbo
git add src/wake_word.py
git commit -m "feat(voice): add wake word detector with OpenWakeWord"
```

---

### Task 3: Upgrade whisper_worker.py — Streaming mode + beam=1

**Files:**
- Modify: `F:/BUREAU/turbo/src/whisper_worker.py`

**Step 1: Modify whisper_worker.py**

Changes:
1. Reduce `beam_size` from 5 to 1
2. Reduce `min_silence_duration_ms` from 500 to 300
3. Add streaming segment protocol: `SEGMENT: partial text` then `DONE: full text`
4. Keep backward compatibility (non-streaming mode still works)

The transcription loop emits `SEGMENT: text` for each VAD segment as it arrives, then `DONE: full text` when complete.

**Step 2: Verify worker still starts**

Run: `echo "QUIT" | C:/Users/franc/AppData/Local/Programs/Python/Python312/python.exe F:/BUREAU/turbo/src/whisper_worker.py`
Expected: `WHISPER_READY ...` then `WHISPER_LOADED ...` then exits cleanly

**Step 3: Commit**

```bash
cd F:/BUREAU/turbo
git add src/whisper_worker.py
git commit -m "feat(voice): whisper streaming segments + beam=1 for 3x speedup"
```

---

### Task 4: Create tts_streaming.py — Edge TTS streaming playback

**Files:**
- Create: `F:/BUREAU/turbo/src/tts_streaming.py`

**Step 1: Create tts_streaming.py**

Uses edge-tts async generator to collect audio chunks, writes to temp mp3, plays via ffplay (low latency). Fallback to PowerShell SoundPlayer. Voice: fr-FR-HenriNeural, rate +10%.

Two functions:
- `speak_streaming(text)` — normal speech
- `speak_quick(text)` — faster rate (+15%) for confirmations

**Step 2: Verify import**

Run: `cd F:/BUREAU/turbo && python -c "from src.tts_streaming import speak_streaming; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
cd F:/BUREAU/turbo
git add src/tts_streaming.py
git commit -m "feat(voice): add streaming TTS with edge-tts"
```

---

### Task 5: Upgrade voice_correction.py — Confidence-based IA bypass

**Files:**
- Modify: `F:/BUREAU/turbo/src/voice_correction.py`

**Step 1: Add early exit in full_correction_pipeline**

After Step 3 (local voice corrections) and BEFORE Step 4 (IA correction), insert:
- Call `match_command(intent)` early
- If score >= 0.85: return immediately with `method="local_fast"`, skip IA call
- Also handle implicit commands with `method="implicit_fast"` and confidence 0.95

This means ~80% of known commands (438 indexed) skip the network call entirely.

**Step 2: Verify module still imports**

Run: `cd F:/BUREAU/turbo && python -c "from src.voice_correction import full_correction_pipeline; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
cd F:/BUREAU/turbo
git add src/voice_correction.py
git commit -m "feat(voice): bypass IA for high-confidence local matches (>85%)"
```

---

### Task 6: Upgrade voice.py — Streaming pipeline + cache + OL1

**Files:**
- Modify: `F:/BUREAU/turbo/src/voice.py`

**Step 1: Replace M1 with OL1 in constants**

```python
# Old:
LM_STUDIO_URL = "http://10.5.0.2:1234/api/v1/chat"
LM_CORRECTION_MODEL = "qwen/qwen3-30b-a3b-2507"

# New:
OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
OLLAMA_MODEL = "qwen3:1.7b"
```

**Step 2: Add LRU command cache (200 entries)**

Dict-based cache with `_cache_get(text)` and `_cache_set(text, result)`. Evicts oldest when full.

**Step 3: Rewrite analyze_with_lm to use OL1**

Use Ollama API format with `think: false`, timeout 3s (vs 8s on M1).

**Step 4: Update WhisperWorker.transcribe for streaming protocol**

Read lines until `DONE:` prefix, handle `SEGMENT:` lines.

**Step 5: Add OL1 warm-up ping (every 60s)**

Background async task that sends a minimal request to keep the model in GPU memory.

**Step 6: Verify**

Run: `cd F:/BUREAU/turbo && python -c "from src.voice import listen_voice; print('OK')"`
Expected: `OK`

**Step 7: Commit**

```bash
cd F:/BUREAU/turbo
git add src/voice.py
git commit -m "feat(voice): streaming pipeline v2 - OL1, cache, warm-up, beam=1"
```

---

### Task 7: Integration — Wire wake word into main voice loop

**Files:**
- Modify: `F:/BUREAU/turbo/src/voice.py`

**Step 1: Add listen_voice_v2 function**

New async function that orchestrates:
1. Wait for wake word (OpenWakeWord) or PTT fallback
2. Record audio with silence detection (auto-stop after 1.5s silence)
3. Transcribe via Whisper worker (streaming protocol)
4. Check cache first
5. Run full_correction_pipeline (local-first)
6. Cache results for future use

Also add `_record_timed()` helper for post-wake-word recording with silence detection.

**Step 2: Verify**

Run: `cd F:/BUREAU/turbo && python -c "from src.voice import listen_voice_v2; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
cd F:/BUREAU/turbo
git add src/voice.py
git commit -m "feat(voice): integrate wake word + cache + silence detection into v2 pipeline"
```

---

### Task 8: Config update — Add voice v2 constants

**Files:**
- Modify: `F:/BUREAU/turbo/src/config.py`

**Step 1: Add voice v2 config to JarvisConfig dataclass**

```python
    # Voice Pipeline v2
    voice_wake_word: str = "jarvis"
    voice_wake_threshold: float = 0.7
    voice_beam_size: int = 1
    voice_vad_silence_ms: int = 300
    voice_cache_size: int = 200
    voice_ollama_timeout: float = 3.0
    voice_warmup_interval: float = 60.0
    voice_max_record_duration: float = 5.0
    voice_silence_threshold: int = 200
    voice_tts_voice: str = "fr-FR-HenriNeural"
    voice_tts_rate: str = "+10%"
```

**Step 2: Commit**

```bash
cd F:/BUREAU/turbo
git add src/config.py
git commit -m "feat(voice): add voice pipeline v2 config constants"
```

---

### Task 9: End-to-end integration test

**Step 1: Create test script**

Create: `F:/BUREAU/turbo/test_voice_v2.py`

Test 7 things:
1. WakeWordDetector imports
2. TTS streaming imports
3. Whisper worker starts
4. Local match "ouvre chrome" works (method=local_fast or direct)
5. Implicit "youtube" works
6. Cache set/get works
7. OL1 is reachable (ping)

**Step 2: Run integration test**

Run: `cd F:/BUREAU/turbo && python test_voice_v2.py`
Expected: All 7 tests OK (or SKIP for CUDA if not on GPU machine)

**Step 3: Commit**

```bash
cd F:/BUREAU/turbo
git add test_voice_v2.py
git commit -m "test(voice): add voice pipeline v2 integration test"
```

---

## Summary

| Task | Description | Est. Time |
|------|------------|-----------|
| 1 | Install dependencies | 2 min |
| 2 | Create wake_word.py | 5 min |
| 3 | Upgrade whisper_worker.py (streaming + beam=1) | 5 min |
| 4 | Create tts_streaming.py | 5 min |
| 5 | Upgrade voice_correction.py (IA bypass) | 5 min |
| 6 | Upgrade voice.py (OL1 + cache + warm-up) | 10 min |
| 7 | Integration (wire wake word into pipeline) | 10 min |
| 8 | Config update | 3 min |
| 9 | End-to-end integration test | 5 min |

**Total: ~50 min | Expected latency: 15s -> <2s**
