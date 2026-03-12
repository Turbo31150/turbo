@echo off
chcp 65001 >nul
title JARVIS Unified Boot
cd /d /home/turbo/jarvis-m1-ops
/home/turbo\.local\bin\uv.exe run python scripts/jarvis_unified_boot.py %*
if errorlevel 1 (
    echo.
    echo Boot avec erreurs. Voir logs\unified_boot.log
)
pause
