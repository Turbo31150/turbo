@echo off
title JARVIS Auto-Heal Daemon
cd /d F:\BUREAU\turbo

:: === SINGLETON GUARD: tue l'instance existante ===
python scripts/singleton_guard.py --name auto_heal_daemon --kill

echo ========================================
echo  JARVIS Auto-Heal Daemon
echo  10000 cycles, 30s interval
echo  Multi-pipeline: OL1 + M1 + M2
echo  Telegram: ON
echo ========================================
echo.

:LOOP
python scripts/auto_heal_daemon.py --cycles 10000 --interval 30
echo [%date% %time%] Daemon crashed, restarting in 15s...
timeout /t 15 /nobreak >nul
goto LOOP
