@echo off
title JARVIS GPU Trading Pipeline v2.3
color 0B
echo.
echo  ============================================
echo   TRADING AI v2.3 - GPU Pipeline
echo   Cluster JARVIS - 6 IA Consensus Parallele
echo  ============================================
echo.

set PYTHONIOENCODING=utf-8
cd /d F:\BUREAU\turbo

echo  [1] Scan rapide (50 coins, M3+OL1 quick)
echo  [2] Scan fast (100 coins, 5 IA sans Gemini)
echo  [3] Scan complet (200 coins, 6 IA parallele)
echo  [4] Scan technique (100 coins, sans IA)
echo  [5] Mode continu (200 coins, 5 IA, 5min)
echo  [6] Dashboard (ouvrir HTML)
echo.
set /p choice="Choix [1-6]: "

if "%choice%"=="1" (
    python scripts\trading_v2\gpu_pipeline.py --coins 50 --top 5 --quick --json
) else if "%choice%"=="2" (
    python scripts\trading_v2\gpu_pipeline.py --coins 100 --top 10 --no-gemini --json
) else if "%choice%"=="3" (
    python scripts\trading_v2\gpu_pipeline.py --coins 200 --top 10 --json
) else if "%choice%"=="4" (
    python scripts\trading_v2\gpu_pipeline.py --coins 100 --top 10 --no-ai --json
) else if "%choice%"=="5" (
    python scripts\trading_v2\gpu_pipeline.py --coins 200 --top 10 --no-gemini --cycles 0 --interval 300 --json
) else if "%choice%"=="6" (
    start "" "F:\BUREAU\turbo\scripts\trading_v2\dashboard_pro.html"
) else (
    echo Choix invalide.
)

echo.
pause
