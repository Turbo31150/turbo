@echo off
title JARVIS v10.6 - Mode Vocal
color 0A
echo.
echo  ==========================================
echo    JARVIS v10.6 - MODE VOCAL
echo    76 outils MCP ^| 2332 commandes ^| Brain IA
echo  ==========================================
echo.
cd /d /home/turbo/jarvis-m1-ops
"/home/turbo/jarvis-m1-ops\.venv\Scripts\python.exe" -c "import asyncio; from src.orchestrator import run_voice; asyncio.run(run_voice(cwd='/home/turbo/jarvis-m1-ops'))"
echo.
echo [JARVIS] Session terminee.
pause
