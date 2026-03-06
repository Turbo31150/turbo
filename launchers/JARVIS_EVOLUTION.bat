@echo off
title JARVIS Strategy Evolution Loop
echo ================================================
echo  JARVIS — Strategy Evolution Loop (Autonome)
echo ================================================
echo.
cd /d F:\BUREAU\turbo
C:\Users\franc\.local\bin\uv.exe run python cowork/dev/strategy_evolution_loop.py --pop 1000 --coins 25 --interval 30
pause
