@echo off
chcp 65001 >nul
title JARVIS Master Boot v2.0
powershell -ExecutionPolicy Bypass -File "F:\BUREAU\turbo\launchers\JARVIS_MASTER_BOOT.ps1" %*
pause
