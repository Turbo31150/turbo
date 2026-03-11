@echo off
title JARVIS Watchdog Autonome
cd /d F:\BUREAU\turbo

echo ============================================
echo   JARVIS WATCHDOG AUTONOME
echo   Cycle autonome toutes les 5 minutes
echo   Grade monitoring + auto-improve + alertes
echo ============================================

:LOOP
echo.
echo [%date% %time%] Lancement watchdog...
uv run python scripts/watchdog_autonomous.py --once
echo [%date% %time%] Cycle termine. Prochain dans 5 minutes.
timeout /t 300 /nobreak
goto LOOP
