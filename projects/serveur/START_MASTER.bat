@echo off
title MASTER SERVER - Trading AI Cluster
echo ========================================
echo   MASTER SERVER - Trading AI Cluster
echo   Machine: %COMPUTERNAME% (192.168.1.85)
echo ========================================
echo.

cd /d /CLAUDE_WORKSPACE\SERVER_MANAGER\scripts

python master_server.py

pause
