@echo off
title J.A.R.V.I.S. Turbo — Mode Vocal PTT
color 0B
echo ============================================
echo   J.A.R.V.I.S. TURBO v10.1
echo   Mode Vocal — Push-to-Talk (CTRL)
echo   450 commandes / 34 scripts / 8 projets
echo   Cluster: M1 + M2 + Ollama Cloud
echo   IAs: Claude + qwen3-30b + gpt-oss-20b
echo ============================================
echo.
cd /d F:\BUREAU\turbo
C:\Users\franc\.local\bin\uv.exe run python main.py -v
pause
