@echo off
title JARVIS Task Orchestrator - Daemon
cd /d F:\BUREAU\turbo

:loop
echo [%date% %time%] Starting JARVIS Task Orchestrator...
python scripts/task_orchestrator.py --daemon
echo [%date% %time%] Orchestrator stopped. Restarting in 10s...
timeout /t 10 /noq
goto loop
