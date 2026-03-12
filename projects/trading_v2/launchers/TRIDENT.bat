@echo off
title J.A.R.V.I.S. Turbo — Trident Execute
color 0E
echo ============================================
echo   TRIDENT MULTI-ORDERS via JARVIS Turbo
echo   Mode DRY RUN + IAs (M1+M2+Claude)
echo ============================================
echo.
cd /d /home/turbo/jarvis-m1-ops
/home/turbo\.local\bin\uv.exe run python main.py "Lance le script execute_trident en mode dry-run. Execute-le avec run_script et rapporte les resultats en francais."
pause
