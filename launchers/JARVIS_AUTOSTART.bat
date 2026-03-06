@echo off
chcp 65001 >nul
title JARVIS — Autostart Watchdog v10.6
color 0B
cd /d F:\BUREAU\turbo

echo.
echo  ============================================
echo   JARVIS AUTOSTART WATCHDOG v10.6
echo   Boot 6 phases + surveillance permanente
echo  ============================================
echo.

:: Attendre 20s que Windows finisse de booter (reseau, GPU, services)
echo [JARVIS] Attente 20s pour stabilisation systeme...
timeout /t 20 /nobreak >nul

:LOOP
echo.
echo [JARVIS] === Lancement %date% %time% ===
echo.

:: Boot complet phases 1-6 PUIS watchdog permanent (check toutes les 60s)
C:\Users\franc\.local\bin\uv.exe run python scripts/jarvis_unified_boot.py --watch --watch-interval 60

:: Si le script crash ou est tue, on relance apres 15s
echo.
echo [JARVIS] Processus termine — restart dans 15s...
echo [JARVIS] Fermer cette fenetre pour arreter definitivement.
echo.
timeout /t 15 /nobreak >nul
goto LOOP
