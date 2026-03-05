@echo off
title WORKER SERVER - Trading AI Cluster
echo ========================================
echo   WORKER SERVER - Trading AI Cluster
echo   Machine: %COMPUTERNAME%
echo ========================================
echo.

cd /d C:\CLAUDE_WORKSPACE\SERVER_MANAGER\scripts

python worker_server.py

pause
