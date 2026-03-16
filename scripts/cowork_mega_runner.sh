#!/bin/bash
# cowork_mega_runner.sh - Orchestre un lot de scripts COWORK
BATCH_ID=$1
JARVIS_HOME="/home/turbo/jarvis"
SCRIPTS_DIR="$JARVIS_HOME/cowork/dev"

if [ -z "$BATCH_ID" ]; then
    echo "Usage: $0 <batch_id>"
    exit 1
fi

echo "[COWORK] Lancement du Mega-Runner Batch #$BATCH_ID..."
# Trouve les scripts du batch (ex: 28-48)
# Pour simplifier, on lance les scripts dont le nom correspond au batch pattern
find "$SCRIPTS_DIR" -name "*.py" | sort | sed -n "${BATCH_ID}p" | xargs -I {} uv run python {} --once

echo "[COWORK] Batch #$BATCH_ID terminé."
