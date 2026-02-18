@echo off
title JARVIS Dashboard
cd /d F:\BUREAU\turbo
echo ========================================
echo   JARVIS Cluster Dashboard
echo   http://127.0.0.1:8080
echo ========================================
"C:\Users\franc\.local\bin\uv.exe" run python dashboard/server.py
pause
