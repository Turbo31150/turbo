@echo off
title JARVIS Full Cluster — All Workers
echo ============================================================
echo  JARVIS — Full Autonomous Cluster Workers
echo ============================================================
echo.
cd /d F:\BUREAU\turbo

echo [1/5] Strategy Evolution Loop (1000 pop, 25 coins, 5min)...
start "JARVIS-Evolution" /MIN C:\Users\franc\.local\bin\uv.exe run python cowork/dev/strategy_evolution_loop.py --pop 1000 --coins 25 --interval 5
timeout /t 2 /nobreak >nul

echo [2/5] Autonomous Orchestrator v3 (30s cycles, dry-run)...
start "JARVIS-Orchestrator" /MIN C:\Users\franc\.local\bin\uv.exe run python cowork/dev/autonomous_orchestrator_v3.py --interval 30 --dry
timeout /t 2 /nobreak >nul

echo [3/5] Cluster Strategy Worker (5min cycles)...
start "JARVIS-StrategyWorker" /MIN C:\Users\franc\.local\bin\uv.exe run python cowork/dev/cluster_strategy_worker.py --interval 5
timeout /t 2 /nobreak >nul

echo [4/5] Cluster Deep Analysis Worker (5min cycles)...
start "JARVIS-DeepAnalysis" /MIN C:\Users\franc\.local\bin\uv.exe run python cowork/dev/cluster_deep_analysis_worker.py --interval 5
timeout /t 2 /nobreak >nul

echo [5/5] MCP Server + Cloudflare Tunnel (Perplexity)...
start "JARVIS-MCP" /MIN C:\Users\franc\.local\bin\uv.exe run python -m src.mcp_server_sse --port 8901 --full
timeout /t 5 /nobreak >nul
start "JARVIS-Tunnel" /MIN "C:\Program Files (x86)\cloudflared\cloudflared.exe" tunnel --url http://127.0.0.1:8901

echo.
echo ============================================================
echo  All 5 workers launched!
echo ============================================================
echo.
echo  1. Evolution Loop      — 1000 strategies evolving
echo  2. Orchestrator v3     — Market scanning + signal detection
echo  3. Strategy Worker     — M1/M2/M3 generating new strategies
echo  4. Deep Analysis       — Market regimes + parameter optimization
echo  5. MCP + Tunnel        — 121 tools exposed to Perplexity
echo.
echo  Press any key to stop all workers.
pause

REM Kill all workers
taskkill /FI "WINDOWTITLE eq JARVIS-*" /F 2>nul
echo Workers stopped.
pause
