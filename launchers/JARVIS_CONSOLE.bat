@echo off
chcp 65001 >nul
title JARVIS — Console Unifiee
cd /d /home/turbo/jarvis-m1-ops
/home/turbo\.local\bin\uv.exe run python scripts/jarvis_unified_console.py
pause
