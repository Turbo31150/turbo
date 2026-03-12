#!/bin/bash
# JARVIS TTS Pipeline (Piper with espeak-ng Fallback)
# Usage: ./scripts/jarvis-tts.sh "Bonjour Monsieur, je suis prêt."

TEXT=$1
VOICE_MODEL="/home/turbo/jarvis-m1-ops/models/piper/fr_FR-denise-low.onnx"
PIPER_BIN="/home/turbo/jarvis-m1-ops/.venv/bin/piper"

# 1. Tenter Piper (Haute qualité)
if [ -f "$PIPER_BIN" ] && [ -f "$VOICE_MODEL" ]; then
    echo "$TEXT" | $PIPER_BIN --model "$VOICE_MODEL" --output_raw | aplay -r 22050 -f S16_LE -t raw
    exit 0
fi

# 2. Tenter espeak-ng (Fallback Rapide)
if command -v espeak-ng &> /dev/null; then
    espeak-ng -v fr "$TEXT"
    exit 0
fi

echo "[ERREUR] Aucun moteur TTS trouvé."
exit 1
