@echo off
title JARVIS MCP Server + Cloudflare Tunnel (Perplexity)
echo ================================================
echo  JARVIS MCP Server — Perplexity Connector
echo ================================================
echo.
echo  Mode: FULL (121 outils)
echo  Port: 8901
echo  Tunnel: Cloudflare Quick Tunnel
echo ================================================
echo.

cd /d /home/turbo/jarvis-m1-ops

REM Start MCP server in background
echo [1/2] Starting MCP SSE server on port 8901...
start /B /home/turbo\.local\bin\uv.exe run python -m src.mcp_server_sse --port 8901 --full 2>&1 | findstr /V "^$"

REM Wait for server to be ready
timeout /t 5 /nobreak >nul

REM Start Cloudflare tunnel
echo [2/2] Starting Cloudflare tunnel...
echo.
echo  The tunnel URL will appear below. Copy it to Perplexity.
echo  Format: https://xxx-xxx-xxx-xxx.trycloudflare.com/mcp/
echo.
"/Program Files (x86)\cloudflared\cloudflared.exe" tunnel --url http://127.0.0.1:8901

pause
