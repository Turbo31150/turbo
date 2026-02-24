@echo off
title JARVIS Desktop v1.0
color 0B
echo.
echo  ========================================
echo   JARVIS TURBO - Desktop Unified App
echo   Electron + React + Python WS Backend
echo  ========================================
echo.

:: Kill any existing process on port 9742
echo [1/3] Cleaning port 9742...
powershell -ExecutionPolicy Bypass -File "F:\BUREAU\turbo\electron\kill-port.ps1" 2>nul
echo.

:: Change to electron directory
cd /d F:\BUREAU\turbo\electron

:: Start development server (Vite + Electron + Python)
echo [2/3] Starting JARVIS Desktop...
echo       Vite: localhost:5173
echo       Python WS: 127.0.0.1:9742
echo.
echo [3/3] Launching Electron...
npm run dev

echo.
echo JARVIS Desktop stopped.
pause
