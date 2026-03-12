@echo off
title J.A.R.V.I.S. Turbo — Monitor RIVER
color 0B
echo ============================================
echo   MONITOR RIVER SCALP via JARVIS Turbo
echo   Scalp 1min + Alerts + IAs (M1+M2+Claude)
echo ============================================
echo.
cd /d /home/turbo/jarvis-m1-ops
/home/turbo\.local\bin\uv.exe run python main.py "Lance le script river_scalp_1min (monitor river). Execute-le avec run_script et rapporte les resultats en francais."
pause
