@echo off
title JARVIS LinkedIn Scheduler
echo [%date% %time%] LinkedIn Scheduler starting...
cd /d F:\BUREAU\turbo
:loop
python scripts\linkedin_scheduler.py --interval 60 --hours 8,12,18
echo [%date% %time%] Scheduler crashed, restarting in 15s...
timeout /t 15 /nobreak >nul
goto loop
