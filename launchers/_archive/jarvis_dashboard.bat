@echo off
title JARVIS v10.6 - Dashboard TUI
color 0E
cd /d /home/turbo/jarvis-m1-ops

:: === SINGLETON GUARD ===
python scripts/singleton_guard.py --name dashboard_tui --kill

echo.
echo  ==========================================
echo    JARVIS v10.6 - DASHBOARD UNIFIE
echo    Cluster ^| Trading ^| Skills ^| Brain
echo  ==========================================
echo.
"/home/turbo/jarvis-m1-ops\.venv\Scripts\python.exe" -c "from src.dashboard import run_dashboard; run_dashboard()"
echo.
echo [JARVIS] Dashboard ferme.
pause
