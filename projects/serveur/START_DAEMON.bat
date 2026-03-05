@echo off
title MASTER DAEMON - Trading AI Cluster
echo.
echo ============================================
echo   MASTER DAEMON - Trading AI Cluster
echo   Machine: %COMPUTERNAME% (192.168.1.85)
echo   Mode: Service/Daemon (non-interactif)
echo ============================================
echo.

cd /d C:\CLAUDE_WORKSPACE\SERVER_MANAGER\scripts
python master_daemon.py

pause
