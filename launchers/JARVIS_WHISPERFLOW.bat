@echo off
title JARVIS WhisperFlow
echo ========================================
echo  JARVIS WhisperFlow - Voice Overlay
echo ========================================
echo.

:: Check if Electron is available
where electron >nul 2>&1
if %errorlevel% equ 0 (
    echo [*] Launching Electron overlay...
    cd /d F:\BUREAU\turbo\whisperflow
    electron .
) else (
    echo [*] Electron not found, opening in browser...
    start "" "F:\BUREAU\turbo\whisperflow\index.html"
)
