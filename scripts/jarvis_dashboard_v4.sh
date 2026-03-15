#!/bin/bash
# JARVIS Dashboard v4 - Trading & Cognitive Edition
SESSION="JARVIS_DASH"

# Kill existing
tmux kill-session -t $SESSION 2>/dev/null
tmux new-session -d -s $SESSION

# Pane 1: GPU Cluster (Top-Left)
tmux rename-window -t $SESSION:0 'Monitor'
tmux send-keys -t $SESSION:0 'watch -n 1 "nvidia-smi --query-gpu=index,temperature.gpu,utilization.gpu,memory.used --format=csv,noheader"' C-m

# Pane 2: Trading Sentinel (Top-Right)
tmux split-window -h -t $SESSION:0
tmux send-keys -t $SESSION:0 'journalctl --user -f -u jarvis-trading-sentinel' C-m

# Pane 3: Cognitive Reflection (Bottom-Left)
tmux split-window -v -t $SESSION:0.0
tmux send-keys -t $SESSION:0.1 'watch -n 5 "curl -s http://127.0.0.1:9742/api/brain/reflection | jq"' C-m

# Pane 4: Master Logs (Bottom-Right)
tmux split-window -v -t $SESSION:0.1
tmux send-keys -t $SESSION:0.3 'journalctl --user -f -u jarvis-master' C-m

tmux select-layout -t $SESSION:0 tiled
# tmux attach-session -t $SESSION
