@echo off
title J.A.R.V.I.S. Turbo — Command Center
color 0A
echo ============================================
echo   J.A.R.V.I.S. COMMAND CENTER via Turbo
echo   GUI Cockpit + IAs (M1+M2+Claude)
echo ============================================
echo.
cd /d /home/turbo/jarvis-m1-ops
/home/turbo\.local\bin\uv.exe run python main.py "Ouvre le Command Center JARVIS. Lance le script jarvis_gui avec run_script."
pause
