#!/bin/bash
# JARVIS Resilient Dashboard Wrapper
SESSION="JARVIS_DASH"
DASH_SCRIPT="/home/turbo/jarvis/scripts/jarvis_dashboard_v4.sh"

while true; do
    # Check if tmux session exists
    tmux has-session -t $SESSION 2>/dev/null
    if [ $? != 0 ]; then
        echo "[RESILIENCE] Dashboard DOWN. Restarting..."
        $DASH_SCRIPT
        # Alert Discord (using gpu_watcher logic)
        python3 -c "import os, requests; url=os.getenv('DISCORD_WEBHOOK_URL'); requests.post(url, json={'content': '⚠️ **JARVIS Dashboard Restarted**'}) if url else None"
    fi

    # Check NVIDIA SMI health
    nvidia-smi > /dev/null 2>&1
    if [ $? != 0 ]; then
        echo "[RESILIENCE] NVIDIA-SMI Failed. Attempting driver recovery sequence..."
        # Note: real recovery might need sudo, but we alert first
        python3 -c "import os, requests; url=os.getenv('DISCORD_WEBHOOK_URL'); requests.post(url, json={'content': '🚨 **CRITICAL: NVIDIA DRIVER FAILURE**'}) if url else None"
    fi

    sleep 10
done
