@echo off
title JARVIS Pipeline Cluster
color 0B
cd /d F:\BUREAU\turbo
:LOOP
echo [%DATE% %TIME%] Starting pipeline...
"F:\BUREAU\turbo\.venv\Scripts\python.exe" -u cowork\dev\autonomous_cluster_pipeline.py --cycles 100 --batch 5 --pause 3
echo [%DATE% %TIME%] Pipeline exited, restarting in 5s...
timeout /t 5 /nobreak >nul
goto LOOP
