#!/bin/bash
# vram_reporter.sh - Met à jour le statut VRAM pour le prompt Zsh sans ralentir le terminal
STATUS_FILE="/tmp/vram_status"

while true; do
  used=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | awk '{sum+=$1} END {print sum}')
  total=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits | awk '{sum+=$1} END {print sum}')
  echo "$used:$total" > $STATUS_FILE
  sleep 5
done
