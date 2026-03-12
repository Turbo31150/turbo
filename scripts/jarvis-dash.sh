#!/bin/bash
# JARVIS Dashboard TMUX v2.0 (Ubuntu 22.04)

SESSION="jarvis"
PROJECT_DIR="/home/turbo/jarvis-m1-ops"

# Create session
tmux new-session -d -s $SESSION -n "Monitor"

# Window 1: Monitor
tmux split-window -h "watch -n 1 nvidia-smi"
tmux split-window -v "journalctl --user -u jarvis-* -f"
tmux select-pane -t 0
tmux split-window -v "cd $PROJECT_DIR && .venv/bin/python3 main.py -s"

# Window 2: Core
tmux new-window -n "Core" -t $SESSION
tmux send-keys -t $SESSION:1 "cd $PROJECT_DIR && .venv/bin/activate" C-m

# Window 3: Dashboard
tmux new-window -n "WebUI" -t $SESSION
tmux send-keys -t $SESSION:2 "cd $PROJECT_DIR/electron && npm start" C-m

tmux select-window -t $SESSION:0
tmux attach-session -t $SESSION
