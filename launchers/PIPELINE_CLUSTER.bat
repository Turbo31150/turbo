@echo off
cd /d F:\BUREAU\turbo
"F:\BUREAU\turbo\.venv\Scripts\python.exe" -u cowork\dev\autonomous_cluster_pipeline.py --cycles 1000 --batch 5 --pause 3 --log
