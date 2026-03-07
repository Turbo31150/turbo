@echo off
title JARVIS Cluster Autonomy Engine - Daemon
cd /d F:\BUREAU\turbo

:loop
echo [%date% %time%] Starting JARVIS Autonomy Engine...
python scripts/cluster_autonomy.py --daemon
echo [%date% %time%] Autonomy Engine stopped. Restarting in 15s...
timeout /t 15 /noq
goto loop
