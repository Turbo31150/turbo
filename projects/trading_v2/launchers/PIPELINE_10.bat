@echo off
title J.A.R.V.I.S. Turbo — Pipeline 10 Cycles
color 0A
echo ============================================
echo   PIPELINE 10 CYCLES via JARVIS Turbo
echo   Auto Scan + DB + IAs (M1+M2+Claude)
echo ============================================
echo.
cd /d /home/turbo/jarvis-m1-ops
/home/turbo\.local\bin\uv.exe run python main.py "Lance le script auto_cycle_10 (pipeline 10 cycles). Execute-le avec run_script et rapporte les resultats en francais."
pause
