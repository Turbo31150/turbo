@echo off
title [SESSION 3] JARVIS Windows Integration — Deep OS Layer
color 0D
cd /D F:\BUREAU\turbo
echo ===================================================
echo   SESSION 3 — Windows Deep Integration
echo   Tasks: Supervisor(5min) SelfImprove(15min)
echo   Context Menu + Protocol jarvis:// + Notifications
echo ===================================================
echo.
echo --- Scheduled Tasks Status ---
schtasks /Query /TN "JARVIS_Supervisor" /FO LIST 2>nul | findstr "Statut Prochaine"
schtasks /Query /TN "JARVIS_SelfImprove" /FO LIST 2>nul | findstr "Statut Prochaine"
schtasks /Query /TN "JARVIS_Notifications" /FO LIST 2>nul | findstr "Statut Prochaine"
schtasks /Query /TN "JARVIS_Boot" /FO LIST 2>nul | findstr "Statut Prochaine"
echo.
echo --- Windows Toast Notification Daemon ---
echo Starting notification daemon (polling every 5s)...
python scripts\jarvis_windows_notify.py --daemon
echo.
echo [!] Daemon arrete. Appuyez sur une touche...
pause
goto :eof
