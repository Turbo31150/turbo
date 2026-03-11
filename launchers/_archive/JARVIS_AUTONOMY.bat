@echo off
title JARVIS Cluster Autonomy Engine - Daemon
cd /d F:\BUREAU\turbo

:: === SINGLETON GUARD: tue l'instance existante ===
python scripts/singleton_guard.py --name autonomy --kill
if %errorlevel% neq 0 (
    echo [SINGLETON] Echec acquisition lock autonomy
    timeout /t 5 /noq
    exit /b 1
)

echo [%date% %time%] Starting JARVIS Autonomy Engine...
python scripts/cluster_autonomy.py --daemon
echo [%date% %time%] Autonomy Engine finished.
pause
