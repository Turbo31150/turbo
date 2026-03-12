@echo off
title JARVIS Pipeline Cluster
color 0B
cd /d /home/turbo/jarvis-m1-ops

:: === SINGLETON GUARD: tue l'instance existante ===
python scripts/singleton_guard.py --name pipeline_cluster --kill

echo [%DATE% %TIME%] Starting pipeline...
"/home/turbo/jarvis-m1-ops\.venv\Scripts\python.exe" -u cowork\dev\autonomous_cluster_pipeline.py --cycles 100 --batch 5 --pause 3
echo [%DATE% %TIME%] Pipeline finished.
pause
