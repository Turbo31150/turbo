#!/bin/bash
# JARVIS Dashboard v3 - TMUX Master Control
SESSION="JARVIS_DASH"

# Kill existing if any
tmux kill-session -t $SESSION 2>/dev/null

# Create session
tmux new-session -d -s $SESSION

# Pane 1: 6 GPUs nvidia-smi (Top-Left)
tmux rename-window -t $SESSION:0 'Main'
tmux send-keys -t $SESSION:0 'watch -n 1 "nvidia-smi --query-gpu=index,name,temp,util,mem.used,mem.total --format=csv,noheader"' C-m

# Pane 2: Docker containers (Top-Right)
tmux split-window -h -t $SESSION:0
tmux send-keys -t $SESSION:0 'watch -n 2 "docker ps --format \"table {{.Names}}\t{{.Status}}\t{{.Ports}}\" | grep -i jarvis"' C-m

# Pane 3: Cluster Status M1/M2/Server (Bottom-Left)
tmux split-window -v -t $SESSION:0.0
tmux send-keys -t $SESSION:0.1 'watch -n 5 "python3 /home/turbo/jarvis/scripts/vcluster_gateway.py"' C-m

# Pane 4: Logs temps réel (Bottom-Right)
tmux split-window -v -t $SESSION:0.1
tmux send-keys -t $SESSION:0.3 'journalctl --user -f -u jarvis-ws -u jarvis-mcp -u jarvis-proxy' C-m

# Layout adjustment
tmux select-layout -t $SESSION:0 tiled

# Attach (if running manually)
# tmux attach-session -t $SESSION
