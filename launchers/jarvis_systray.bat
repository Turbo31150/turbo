@echo off
title JARVIS v10.1 - Systray
cd /d F:\BUREAU\turbo
"F:\BUREAU\turbo\.venv\Scripts\python.exe" -c "from src.systray import run_systray; run_systray()"
