#!/bin/bash
# JARVIS Wave Runner — Cluster Task Orchestration
# Usage: ./jarvis-wave.sh [1-6]

WAVE=$1
JARVIS_HOME="/home/turbo/jarvis"
source "$JARVIS_HOME/.venv/bin/activate"

case "$WAVE" in
    1)
        echo "🚀 Launching Wave 1: Infrastructure & Health"
        python3 "$JARVIS_HOME/src/jarvis-cluster-health.py"
        ;;
    2)
        echo "🚀 Launching Wave 2: Database & Logs Audit"
        python3 "$JARVIS_HOME/src/database.py" --audit
        ;;
    3)
        echo "🚀 Launching Wave 3: Code Improvement & Auto-fix"
        python3 "$JARVIS_HOME/src/self_improve_engine.py" --cycle 1
        ;;
    4)
        echo "🚀 Launching Wave 4: Crypto Trading Scanner"
        python3 "$JARVIS_HOME/projects/trading_v2/trading_mcp_ultimate_v3.py" --scan
        ;;
    5)
        echo "🚀 Launching Wave 5: Cluster Sync"
        cd "$JARVIS_HOME" && ./jarvis-ctl.sh sync
        ;;
    6)
        echo "🚀 Launching Wave 6: Full System Backup"
        cd "$JARVIS_HOME" && ./scripts/jarvis-backup.sh
        ;;
    *)
        echo "Usage: $0 [1-6]"
        exit 1
esac
