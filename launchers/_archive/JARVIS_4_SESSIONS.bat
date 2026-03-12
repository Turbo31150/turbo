@echo off
title JARVIS — Lanceur 4 Sessions
color 0F
echo ===================================================
echo   JARVIS — Lancement des 4 sessions paralleles
echo ===================================================
echo.

echo [1/4] OpenClaw Gateway...
start "" "/home/turbo/jarvis-m1-ops\launchers\SESSION_1_OPENCLAW.bat"
timeout /T 3 /NOBREAK >nul

echo [2/4] Telegram Bot...
start "" "/home/turbo/jarvis-m1-ops\launchers\SESSION_2_TELEGRAM.bat"
timeout /T 3 /NOBREAK >nul

echo [3/4] Windows Integration...
start "" "/home/turbo/jarvis-m1-ops\launchers\SESSION_3_WINDOWS.bat"
timeout /T 2 /NOBREAK >nul

echo [4/4] Supervisor (Watch)...
start "" "/home/turbo/jarvis-m1-ops\launchers\SESSION_4_SUPERVISOR.bat"

echo.
echo ===================================================
echo   4 sessions lancees ! Fenetre auto-close dans 10s
echo ===================================================
timeout /T 10
