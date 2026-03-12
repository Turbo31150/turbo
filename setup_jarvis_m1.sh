#!/bin/bash
# JARVIS M1 Setup Script (Reproducible)

echo "[JARVIS] Initialisation..."
PROJECT_DIR="/home/turbo/jarvis-m1-ops"
cd $PROJECT_DIR

# 1. Dépendances Système
sudo apt-get update && sudo apt-get install -y ffmpeg alsa-utils pulseaudio libportaudio2 python3-dev jq curl tmux nodejs npm

# 2. Environnement Python
curl -LsSf https://astral.sh/uv/install.sh | sh
/home/turbo/.local/bin/uv venv .venv
source .venv/bin/activate
/home/turbo/.local/bin/uv pip install -r temp_requirements.txt
/home/turbo/.local/bin/uv pip install openwakeword faster-whisper onnxruntime-gpu --no-deps

# 3. Node.js
cd canvas && npm install && cd ../electron && npm install && cd ..

# 4. Systemd
chmod +x scripts/*.sh
systemctl --user daemon-reload
systemctl --user enable jarvis-proxy jarvis-mcp jarvis-voice jarvis-master jarvis-dashboard

echo "[JARVIS] Installation COMPLETE. Lance './scripts/jarvis-dash.sh' pour le monitoring."
