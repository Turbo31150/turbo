@echo off
chcp 65001 >nul
title JARVIS — Autostart Boot v10.7
color 0B
cd /d F:\BUREAU\turbo

echo.
echo  ============================================
echo   JARVIS AUTOSTART BOOT v10.7
echo   Anti-doublon: tue l'ancien, garde le nouveau
echo   Auto-restart: relance si crash
echo  ============================================
echo.

:: Attendre 20s que Windows finisse de booter (reseau, GPU, services)
echo [JARVIS] Attente 20s pour stabilisation systeme...
timeout /t 20 /nobreak >nul

:LOOP
echo.
echo [JARVIS] === Lancement %date% %time% ===
echo.

:: Le boot script gere l'anti-doublon en interne:
::   - Si un ancien tourne, il le TUE puis prend le relais
::   - Plus de "ABORT already running" — le nouveau gagne toujours
::   - Le lock file est auto-libere si crash (Windows file lock)
C:\Users\franc\.local\bin\uv.exe run python scripts/jarvis_unified_boot.py --watch --watch-interval 60

:: Si le script crash, on relance apres 15s
:: Pas de risque de doublon car le boot tue l'existant au demarrage
echo.
echo [JARVIS] Processus termine — restart dans 15s...
echo [JARVIS] Fermer cette fenetre pour arreter definitivement.
echo.
timeout /t 15 /nobreak >nul
goto LOOP
