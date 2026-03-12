@echo off
title J.A.R.V.I.S. Turbo — Mode Clavier
color 0E
echo ============================================
echo   J.A.R.V.I.S. TURBO v10.1
echo   Mode Clavier (Hybride)
echo   450 commandes / 34 scripts / IAs actives
echo   Tape tes commandes comme si tu parlais
echo ============================================
echo.
cd /d /home/turbo/jarvis-m1-ops
/home/turbo\.local\bin\uv.exe run python main.py -k
pause
