#!/bin/bash
# JARVIS Boot Optimizer
# Apply ZRAM and Sysctl settings

# ZRAM 12GB zstd
modprobe zram
zramctl --find --size 12G --algorithm zstd
mkswap /dev/zram0
swapon /dev/zram0 -p 100

# NVIDIA Persistence
nvidia-smi -pm 1

# Fans (Safe mode 75% for all)
# Requires X server or root depending on driver version
# for i in {0..5}; do nvidia-settings -a "[gpu:$i]/GPUFanControlState=1" -a "[fan:$i]/GPUTargetFanSpeed=75" 2>/dev/null; done

echo "[JARVIS] System Optimized."
