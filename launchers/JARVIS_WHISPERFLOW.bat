@echo off
title JARVIS WhisperFlow
echo ========================================
echo  JARVIS WhisperFlow - Voice Overlay
echo ========================================
echo.

:: Start backend WebSocket server if not already running
echo [*] Checking backend on port 9742...
netstat -ano | findstr "127.0.0.1:9742" | findstr "LISTENING" >nul 2>&1
if %errorlevel% neq 0 (
    echo [*] Starting WebSocket backend...
    start /min "JARVIS-WS-Backend" cmd /c "cd /d F:\BUREAU\turbo && python -m python_ws.server"
    echo [*] Waiting for backend startup...
    timeout /t 3 /nobreak >nul
) else (
    echo [+] Backend already running on port 9742
)

:: Verify backend is up
curl -s --max-time 2 http://127.0.0.1:9742/health >nul 2>&1
if %errorlevel% equ 0 (
    echo [+] Backend OK
) else (
    echo [!] Backend may still be starting, waiting 3s more...
    timeout /t 3 /nobreak >nul
)

echo.

:: Check if Electron is available
where electron >nul 2>&1
if %errorlevel% equ 0 (
    echo [*] Launching Electron overlay...
    cd /d F:\BUREAU\turbo\whisperflow
    electron .
) else (
    echo [*] Opening WhisperFlow via HTTP backend...
    start "" "http://127.0.0.1:9742/whisperflow/"
)
