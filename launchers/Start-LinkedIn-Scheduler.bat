@echo off
title JARVIS LinkedIn Scheduler
cd /d F:\BUREAU\turbo

:: === SINGLETON GUARD: tue l'instance existante ===
python scripts/singleton_guard.py --name linkedin_scheduler --kill

echo [%date% %time%] LinkedIn Scheduler starting...
:loop
python scripts\linkedin_scheduler.py --interval 60 --hours 8,12,18
echo [%date% %time%] Scheduler crashed, restarting in 15s...
timeout /t 15 /nobreak >nul
goto loop
