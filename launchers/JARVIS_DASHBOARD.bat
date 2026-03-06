@echo off
title JARVIS v10.1 - Dashboard TUI
color 0E
echo.
echo  ==========================================
echo    JARVIS v10.1 - DASHBOARD UNIFIE
echo    Cluster ^| Trading ^| Skills ^| Brain
echo  ==========================================
echo.
cd /d F:\BUREAU\turbo
"F:\BUREAU\turbo\.venv\Scripts\python.exe" -c "from src.dashboard import run_dashboard; run_dashboard()"
echo.
echo [JARVIS] Dashboard ferme.
pause
