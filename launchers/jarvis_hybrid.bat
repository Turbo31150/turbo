@echo off
title JARVIS v10.1 - Mode Hybride
color 0E
echo.
echo  ==========================================
echo    JARVIS v10.1 - MODE HYBRIDE
echo    Tape comme si tu parlais (clavier+vocal)
echo    69 outils MCP ^| 125 commandes ^| Brain IA
echo  ==========================================
echo.
cd /d F:\BUREAU\turbo
"F:\BUREAU\turbo\.venv\Scripts\python.exe" -c "import asyncio; from src.orchestrator import run_hybrid; asyncio.run(run_hybrid(cwd='F:/BUREAU/turbo'))"
echo.
echo [JARVIS] Session terminee.
pause
