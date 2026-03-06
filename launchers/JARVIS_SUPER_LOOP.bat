@echo off
title JARVIS Super Loop - 1000 Cycles All Domains
echo ============================================
echo  JARVIS SUPER IMPROVEMENT LOOP
echo  1000 cycles continus full cluster
echo  Trading + Performance + Code + Repair
echo  6 noeuds IA en parallele
echo ============================================
echo.

cd /d F:\BUREAU\turbo
C:\Users\franc\.local\bin\uv.exe run python cowork/dev/jarvis_super_loop.py --cycles 1000 --interval 120 --notify

pause
