@echo off
title [SESSION 4] JARVIS Supervisor — Watch All Sessions
color 0E
cd /D /home/turbo/jarvis-m1-ops
echo ===================================================
echo   SESSION 4 — Supervisor (Guide les 3 autres)
echo   Scan toutes les 30s  ^|  Auto-restart  ^|  Alertes TG
echo ===================================================
echo.
echo Monitoring continu de tous les services...
echo   M1(:1234) OL1(:11434) WS(:9742) Proxy(:18800)
echo   Telegram Bot  OpenClaw(:18789)  Dashboard(:8080)
echo.
echo   Si un service tombe: auto-restart + alerte Telegram
echo ===================================================
echo.
python scripts\jarvis_supervisor.py --watch
echo.
echo [!] Supervisor arrete. Appuyez sur une touche...
pause
goto :eof
