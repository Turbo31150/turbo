@echo off
title [SESSION 1] JARVIS OpenClaw Gateway — Port 18789
color 0B
cd /D C:\Users\franc\.openclaw
echo ===================================================
echo   SESSION 1 — OpenClaw Gateway (40 agents, 13 skills)
echo   Port: 18789  ^|  Telegram: OFF (bot.js gere)
echo ===================================================
echo.
echo Demarrage du gateway...
set "OPENCLAW_GATEWAY_PORT=18789"
set "OPENCLAW_GATEWAY_TOKEN=ae1cd158a0975c30e7712b274859e202896e7f67203de9d2"
"C:\Program Files\nodejs\node.exe" C:\Users\franc\AppData\Roaming\npm\node_modules\openclaw\dist\index.js gateway --port 18789
echo.
echo [!] Gateway arrete. Appuyez sur une touche pour relancer...
pause
goto :eof
