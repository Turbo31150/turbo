@echo off
title JARVIS Sniper Scanner - REALTIME
echo ============================================
echo  JARVIS SNIPER SCANNER - REALTIME MODE
echo  Surveille 750+ coins toutes les 30s
echo  Detecte mouvements explosifs EN COURS
echo  Alerte Telegram + vocal si signal valide
echo ============================================
echo.

cd /d F:\BUREAU\turbo
C:\Users\franc\.local\bin\uv.exe run python cowork/dev/sniper_scanner.py --realtime --notify --voice --min-move 0.4

pause
