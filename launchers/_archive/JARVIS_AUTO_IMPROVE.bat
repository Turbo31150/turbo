@echo off
title JARVIS Auto-Improve Daemon
cd /d /home/turbo/jarvis-m1-ops

echo [JARVIS] Auto-Improve Daemon starting...
echo [JARVIS] Cycle: validate + fix + telegram every 15min

:LOOP
uv run python scripts/production_auto_improve.py --daemon
echo [JARVIS] Daemon exited, restarting in 30s...
timeout /t 30 /nobreak >nul
goto LOOP
