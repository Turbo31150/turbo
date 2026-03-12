@echo off
title [SESSION 2] JARVIS Telegram Bot — @turboSSebot
color 0A
cd /D /home/turbo/jarvis-m1-ops\canvas
echo ===================================================
echo   SESSION 2 — Telegram Bot (@turboSSebot)
echo   Commandes: 30+  ^|  Proxy: :18800  ^|  Cluster: M1+OL1
echo ===================================================
echo.
echo Demarrage du bot Telegram...
node telegram-bot.js
echo.
echo [!] Bot arrete. Appuyez sur une touche pour relancer...
pause
goto :eof
