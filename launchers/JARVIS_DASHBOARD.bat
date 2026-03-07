@echo off
title JARVIS v10.6 - Dashboard TUI
color 0E
cd /d F:\BUREAU\turbo

:: === SINGLETON GUARD ===
python scripts/singleton_guard.py --name dashboard_tui --kill

echo.
echo  ==========================================
echo    JARVIS v10.6 - DASHBOARD UNIFIE
echo    Cluster ^| Trading ^| Skills ^| Brain
echo  ==========================================
echo.
"F:\BUREAU\turbo\.venv\Scripts\python.exe" -c "from src.dashboard import run_dashboard; run_dashboard()"
echo.
echo [JARVIS] Dashboard ferme.
pause
