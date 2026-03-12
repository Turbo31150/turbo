@echo off
title JARVIS MCP Remote Server (port 8901)
cd /d /home/turbo/jarvis-m1-ops

:: === SINGLETON GUARD ===
python scripts/singleton_guard.py --name mcp_sse --kill

echo ======================================
echo  JARVIS MCP Remote Server
echo  Port: 8901 - Transport: Streamable HTTP
echo  URL locale: http://127.0.0.1:8901/mcp/
echo ======================================
echo.

echo [1/2] Demarrage du serveur MCP Streamable HTTP...
start /b "MCP-Remote" cmd /c "uv run python -m src.mcp_server_sse --port 8901"
timeout /t 3 /nobreak >nul

echo [2/2] Demarrage du tunnel cloudflared...
echo Copiez l'URL HTTPS affichee ci-dessous dans Perplexity.
echo Ajoutez /mcp/ a la fin de l'URL cloudflared.
echo Exemple: https://xxxx-xx-xx.trycloudflare.com/mcp/
echo.
"/Program Files (x86)\cloudflared\cloudflared.exe" tunnel --url http://127.0.0.1:8901

pause
