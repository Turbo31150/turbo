@echo off
title JARVIS v10.3 - Mode Vocal
color 0A
echo.
echo  ==========================================
echo    JARVIS v10.3 - MODE VOCAL
echo    76 outils MCP ^| 2332 commandes ^| Brain IA
echo  ==========================================
echo.
cd /d F:\BUREAU\turbo
"F:\BUREAU\turbo\.venv\Scripts\python.exe" -c "import asyncio; from src.orchestrator import run_voice; asyncio.run(run_voice(cwd='F:/BUREAU/turbo'))"
echo.
echo [JARVIS] Session terminee.
pause
