@echo off
title JARVIS Status
cd /d /home/turbo/jarvis-m1-ops
/home/turbo\.local\bin\uv.exe run python main.py -s
pause
