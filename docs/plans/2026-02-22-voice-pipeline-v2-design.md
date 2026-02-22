# Voice Pipeline v2 — Design

## Probleme
Latence vocale ~15s : Whisper batch (beam=5) + correction M1 (12s+, timeout 7/10) + TTS batch.

## Objectif
Latence < 2s pour 80% des commandes, < 3s pour les 20% restantes.

## Architecture

```
Micro (stream 16kHz)
  -> Wake Word local (OpenWakeWord, ~50ms)
    -> Whisper Streaming (chunk par chunk, beam=1, CUDA)
      -> Router (local match vs IA)
        -> Local match (>85% confiance) : ~0ms
        -> OL1/qwen3:1.7b : ~0.5s
      -> Command Executor + TTS Streaming (Edge, chunk par chunk)
```

## Composants

### 1. wake_word.py (NOUVEAU)
- OpenWakeWord avec keyword custom "jarvis"
- Ecoute continue du micro en background
- Callback quand detecte -> demarre STT
- Fallback PTT (Ctrl) toujours disponible

### 2. whisper_worker.py (MODIFIER)
- Mode streaming : envoyer segments au fil de l'eau via stdout
- Protocole : `SEGMENT: texte partiel` puis `DONE: texte complet`
- beam_size=1 (suffisant pour commandes francais)
- VAD plus agressif : min_silence_duration_ms=300 (vs 500)

### 3. voice.py (MODIFIER)
- Pipeline async streaming : wake -> record+transcribe simultane -> route -> execute+speak simultane
- Remplacer M1 par OL1 (http://127.0.0.1:11434/api/chat)
- Cache LRU 200 entrees pour commandes frequentes
- Warm-up OL1 toutes les 60s (ping keep-alive)

### 4. voice_correction.py (MODIFIER)
- Ajouter score de confiance au fuzzy match
- Si confiance > 85% : bypass complet de l'appel IA
- Retourner {"command": str, "confidence": float, "source": "local"|"ia"}

### 5. tts_streaming.py (NOUVEAU)
- Edge TTS en mode streaming (edge-tts async generator)
- Commencer playback des le premier chunk audio
- Voix: fr-FR-HenriNeural (deja configure)

## Fallbacks
- OL1 down -> GEMINI proxy -> local-only (fuzzy match)
- Whisper crash -> restart auto worker
- Micro absent -> keyboard fallback
- Wake word miss -> PTT Ctrl backup

## Fichiers impactes
- MODIFIER: src/voice.py, src/whisper_worker.py, src/voice_correction.py
- CREER: src/wake_word.py, src/tts_streaming.py
- CONFIG: src/config.py (ajout constantes OL1 voice)

## Metriques de succes
- Latence commande connue : < 1s (cache ou local match)
- Latence commande IA : < 2s (OL1)
- Latence commande complexe : < 3s (OL1 + execution)
- Wake word detection rate : > 95%
- Faux positifs wake word : < 2%
