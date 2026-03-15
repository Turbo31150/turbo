#!/bin/bash
# JARVIS Unified Boot — Linux Native
export TURBO_DIR="/home/turbo/jarvis"
cd "$TURBO_DIR"
source .venv/bin/activate
python3 scripts/jarvis_unified_boot.py "$@"
if [ $? -ne 0 ]; then
    echo -e "\n\e[31m[ERROR] Boot avec erreurs. Voir data/unified_boot.log\e[0m"
fi
