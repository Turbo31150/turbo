@echo off
title JARVIS Telegram Bot
cd /d F:\BUREAU\turbo

:: === SINGLETON GUARD ===
python scripts/singleton_guard.py --name telegram_bot --kill

echo ============================================
echo   JARVIS Telegram Bot - Launcher
echo ============================================
echo.

:: Verifie si le proxy tourne deja
curl -s --max-time 2 http://127.0.0.1:18800/health >nul 2>&1
if %errorlevel% neq 0 (
    echo [*] Demarrage du Canvas Direct Proxy...
    start "JARVIS Proxy" /min cmd /c "cd /d F:\BUREAU\turbo && node canvas\direct-proxy.js"
    echo [*] Attente 3s pour le proxy...
    timeout /t 3 /nobreak >nul
) else (
    echo [OK] Canvas Proxy deja en cours sur :18800
)

echo [*] Lancement du Telegram Bot...
echo.
node canvas\telegram-bot.js

pause
