@echo off
title J.A.R.V.I.S. Turbo — Electron App
color 0B
echo ============================================
echo   J.A.R.V.I.S. ELECTRON APP via Turbo
echo   API Server (port 5050) + Electron + IAs
echo ============================================
echo.
:: Lancer l'API via Turbo en background
cd /d /home/turbo/jarvis-m1-ops
start /b /home/turbo\.local\bin\uv.exe run python -c "from src.config import SCRIPTS; import subprocess, sys; subprocess.Popen([sys.executable, str(SCRIPTS['jarvis_api'])])"
echo   API Server: starting on port 5050...
timeout /t 3 /nobreak >nul
:: Lancer Electron
cd /d /home/turbo\TRADING_V2_PRODUCTION\electron-app
npm start
