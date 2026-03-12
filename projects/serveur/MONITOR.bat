@echo off
title CLUSTER MONITOR
cd /d /CLAUDE_WORKSPACE\SERVER_MANAGER\scripts

if "%1"=="" (
    python cluster_monitor.py
) else (
    python cluster_monitor.py %1
)

pause
