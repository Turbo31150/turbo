#!/bin/bash
BIP="/home/turbo/jarvis-m1-ops/voice_assets/wake_bip.wav"
BRIDGE="/home/turbo/jarvis-m1-ops/voice_pipeline/jarvis_voice_bridge.py"

# Joue le bip
aplay "$BIP" >/dev/null 2>&1

# Capture 5 secondes de voix et envoie au bridge
echo "🎤 ÉCOUTE ACTIVE (5s)..."
# Utilisation de Whisper via EasySpeak ou direct (ici on simule le déclenchement du plugin)
# Pour le test, on va juste demander à l'utilisateur de parler dans le micro
python3 "$BRIDGE" "Quelle est la santé du cluster ?" # Test automatique
