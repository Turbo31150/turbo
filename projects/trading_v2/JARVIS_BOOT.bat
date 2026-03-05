@echo off
TITLE J.A.R.V.I.S. - SYSTEME CENTRAL
color 0B
echo.
echo    =============================================
echo      J.A.R.V.I.S. - Just A Rather Very
echo      Intelligent System - BOOT SEQUENCE
echo    =============================================
echo.
echo    [1/5] Verification Python...
python --version 2>nul
if errorlevel 1 (
    echo    ERREUR: Python non trouve!
    pause
    exit /b 1
)
echo    [2/5] Verification modules...
python -c "import pyautogui, pyttsx3, psutil, pyperclip, requests; print('         OK - tous modules charges')" 2>nul || echo         WARN - modules manquants (mode degrade)
echo    [3/5] Test Neural Engine M2 (192.168.1.26)...
python -c "import requests; r=requests.get('http://192.168.1.26:1234/v1/models',timeout=5); print('         OK -',len(r.json().get('data',[])),'modeles disponibles')" 2>nul || echo         WARN - M2 offline (fallback local actif)
echo    [4/5] Chargement OS Pilot v3.0 + Genesis...
echo         60+ actions OS + auto-coding + STT corrections
echo    [5/5] Selection du mode...
echo.
echo    =============================================
echo      [1] VOCAL  - Pilotage vocal (PTT RIGHT_CTRL)
echo      [2] VOCAL  - Ecoute continue (mains libres)
echo      [3] CLAVIER - Mode commande texte
echo    =============================================
echo.
set /p MODE="    Choix (1/2/3) [defaut=1]: "
if "%MODE%"=="" set MODE=1
cd /d F:\BUREAU\TRADING_V2_PRODUCTION\voice_system
if "%MODE%"=="1" (
    echo    Demarrage mode VOCAL PTT...
    python -u voice_jarvis.py
) else if "%MODE%"=="2" (
    echo    Demarrage mode VOCAL continu...
    python -u voice_jarvis.py --continuous
) else (
    echo    Demarrage mode CLAVIER...
    python -u commander_v2.py
)
pause
