#!/bin/bash
DIR=~/jarvis-m1-ops
cd $DIR

echo "🔥 [JARVIS] Initialisation du Cluster..."
./jarvis_preflight_check.sh

echo "⚡ Démarrage séquentiel des vagues..."
# Vague 0 : Coeur
systemctl --user start jarvis-ws.service
systemctl --user start jarvis-mcp.service 2>/dev/null || true

# Vague 1 : Intelligence
systemctl --user start jarvis-lmstudio-debugger.service
openclaw gateway restart --port 18790 --mode local --auth none &

echo "✅ Cluster JARVIS prêt."
