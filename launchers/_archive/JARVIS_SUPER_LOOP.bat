@echo off
title JARVIS Super Loop - 1000 Cycles All Domains
cd /d /home/turbo/jarvis-m1-ops

:: === SINGLETON GUARD ===
python scripts/singleton_guard.py --name super_loop --kill

echo ============================================
echo  JARVIS SUPER IMPROVEMENT LOOP
echo  1000 cycles continus full cluster
echo  Trading + Performance + Code + Repair
echo  6 noeuds IA en parallele
echo ============================================
echo.

/home/turbo\.local\bin\uv.exe run python cowork/dev/jarvis_super_loop.py --cycles 1000 --interval 120 --notify

pause
