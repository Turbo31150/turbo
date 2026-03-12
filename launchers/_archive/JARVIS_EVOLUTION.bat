@echo off
title JARVIS Strategy Evolution Loop
cd /d /home/turbo/jarvis-m1-ops

:: === SINGLETON GUARD ===
python scripts/singleton_guard.py --name evolution --kill

echo ================================================
echo  JARVIS — Strategy Evolution Loop (Autonome)
echo ================================================
echo.

/home/turbo\.local\bin\uv.exe run python cowork/dev/strategy_evolution_loop.py --pop 1000 --coins 25 --interval 30
pause
