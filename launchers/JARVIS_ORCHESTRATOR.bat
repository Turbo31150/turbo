@echo off
title JARVIS Task Orchestrator - Daemon
cd /d F:\BUREAU\turbo

:: === SINGLETON GUARD: tue l'instance existante ===
python scripts/singleton_guard.py --name orchestrator --kill
if %errorlevel% neq 0 (
    echo [SINGLETON] Echec acquisition lock orchestrator
    timeout /t 5 /noq
    exit /b 1
)

:loop
echo [%date% %time%] Starting JARVIS Task Orchestrator...
python scripts/task_orchestrator.py --daemon
echo [%date% %time%] Orchestrator stopped. Restarting in 10s...
timeout /t 10 /noq
goto loop
