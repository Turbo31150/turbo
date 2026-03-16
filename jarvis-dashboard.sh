#!/bin/bash
# JARVIS Master Dashboard - TMUX Session
SESSION="JARVIS"

tmux has-session -t $SESSION 2>/dev/null
if [ $? != 0 ]; then
  tmux new-session -d -s $SESSION
  
  # Window 1: GPU & System
  tmux rename-window -t $SESSION:0 'System'
  tmux send-keys -t $SESSION:0 'watch -n 1 "nvidia-smi --query-gpu=index,name,temp,util,mem.used,mem.total --format=csv,noheader"' C-m
  tmux split-window -h -t $SESSION:0
  tmux send-keys -t $SESSION:0 'htop' C-m
  
  # Window 2: JARVIS Logs
  tmux new-window -t $SESSION:1 -n 'Logs'
  tmux send-keys -t $SESSION:1 'journalctl --user -f -u jarvis-ws' C-m
  tmux split-window -v -t $SESSION:1
  tmux send-keys -t $SESSION:1 'journalctl --user -f -u jarvis-proxy' C-m
  
  # Window 3: Services Health
  tmux new-window -t $SESSION:2 -n 'Health'
  tmux send-keys -t $SESSION:2 'watch -n 5 "/home/turbo/jarvis/jarvis-ctl.sh health"' C-m
  
  # Window 4: Crypto
  tmux new-window -t $SESSION:3 -n 'Crypto'
  tmux send-keys -t $SESSION:3 'watch -n 10 "uv run python /home/turbo/jarvis/src/jarvis-cluster-health.py"' C-m

  # Window 5: Voice
  tmux new-window -t $SESSION:4 -n 'Voice'
  tmux send-keys -t $SESSION:4 'journalctl --user -f -u jarvis-voice' C-m
fi

tmux attach-session -t $SESSION
