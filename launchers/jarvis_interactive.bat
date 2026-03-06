@echo off
title JARVIS v10.1 - Mode Interactif
color 0B
echo.
echo  ==========================================
echo    JARVIS v10.1 - MODE INTERACTIF (clavier)
echo    69 outils MCP ^| 125 commandes ^| Brain IA
echo  ==========================================
echo.
cd /d F:\BUREAU\turbo
"F:\BUREAU\turbo\.venv\Scripts\python.exe" -c "import asyncio; from src.orchestrator import run_interactive; asyncio.run(run_interactive(cwd='F:/BUREAU/turbo'))"
echo.
echo [JARVIS] Session terminee.
pause
