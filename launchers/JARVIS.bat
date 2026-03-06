@echo off
title JARVIS v10.1 - Lancement
color 0E
echo.
echo  ==========================================
echo    JARVIS v10.1 - LANCEMENT COMPLET
echo    Dashboard TUI + Systray
echo  ==========================================
echo.
cd /d F:\BUREAU\turbo

:: Lancer le systray en arriere-plan
start /B "" "F:\BUREAU\turbo\.venv\Scripts\pythonw.exe" -c "from src.systray import run_systray; run_systray()"

:: Lancer le dashboard (bloquant - le terminal reste dessus)
"F:\BUREAU\turbo\.venv\Scripts\python.exe" -c "from src.dashboard import run_dashboard; run_dashboard()"

echo.
echo [JARVIS] Session terminee.
pause
