@echo off
title JARVIS v10.6 - Mode Hybride
color 0E
echo.
echo  ==========================================
echo    JARVIS v10.6 - MODE HYBRIDE
echo    Tape comme si tu parlais (clavier+vocal)
echo    69 outils MCP ^| 125 commandes ^| Brain IA
echo  ==========================================
echo.
cd /d /home/turbo/jarvis-m1-ops
"/home/turbo/jarvis-m1-ops\.venv\Scripts\python.exe" -c "import asyncio; from src.orchestrator import run_hybrid; asyncio.run(run_hybrid(cwd='/home/turbo/jarvis-m1-ops'))"
echo.
echo [JARVIS] Session terminee.
pause
