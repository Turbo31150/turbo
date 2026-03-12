@echo off
title JARVIS Sniper Scanner - REALTIME
cd /d /home/turbo/jarvis-m1-ops

:: === SINGLETON GUARD ===
python scripts/singleton_guard.py --name sniper --kill

echo ============================================
echo  JARVIS SNIPER SCANNER - REALTIME MODE
echo  Surveille 750+ coins toutes les 30s
echo  Detecte mouvements explosifs EN COURS
echo  Alerte Telegram + vocal si signal valide
echo ============================================
echo.

/home/turbo\.local\bin\uv.exe run python cowork/dev/sniper_scanner.py --realtime --notify --voice --min-move 0.4

pause
