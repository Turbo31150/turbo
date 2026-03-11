@echo off
title JARVIS WhisperFlow
cd /d F:\BUREAU\turbo

:: === SINGLETON GUARD ===
python scripts/singleton_guard.py --name whisperflow --kill

echo ========================================
echo  JARVIS WhisperFlow - Voice Overlay
echo ========================================
echo.

:: Start backend WebSocket server — kill existant + restart
echo [*] WS Backend :9742 — kill existant + restart...
python scripts/singleton_guard.py --name jarvis_ws --kill --port 9742
start /min "JARVIS-WS-Backend" cmd /c "cd /d F:\BUREAU\turbo && C:\Users\franc\.local\bin\uv.exe run python -m python_ws.server"
echo [*] Waiting for backend startup...
timeout /t 3 /nobreak >nul

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
