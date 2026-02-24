@echo off
title JARVIS Turbo — Unified Desktop
color 0B
echo.
echo  ============================================
echo   JARVIS TURBO v10.3 — Desktop Unified App
echo   Dashboard + Chat + Trading + Voice + Widgets
echo  ============================================
echo.

:: Check for portable exe first
set "PORTABLE=F:\BUREAU\turbo\electron\dist-release\JARVIS Turbo 1.0.0.exe"
set "ELECTRON_DIR=F:\BUREAU\turbo\electron"

if exist "%PORTABLE%" (
    echo [MODE] Portable executable detected
    echo [START] Launching JARVIS Turbo...
    echo.
    start "" "%PORTABLE%"
    echo JARVIS Turbo launched.
    timeout /t 2 >nul
    exit /b 0
)

:: Fallback to dev mode
echo [MODE] Dev mode (npm run dev)
echo.

:: Kill any existing process on port 9742
echo [1/3] Cleaning port 9742...
powershell -ExecutionPolicy Bypass -File "%ELECTRON_DIR%\kill-port.ps1" 2>nul
echo.

cd /d "%ELECTRON_DIR%"

echo [2/3] Starting JARVIS Desktop...
echo       Vite: 127.0.0.1:5173
echo       Python WS: 127.0.0.1:9742
echo.
echo [3/3] Launching Electron...
npm run dev

echo.
echo JARVIS Desktop stopped.
pause
