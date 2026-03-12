@echo off
title JARVIS Canvas — Direct Proxy :18800
echo ========================================
echo  JARVIS Canvas Direct Proxy
echo  Port: 18800 (no OpenClaw)
echo ========================================
echo.
echo  [1] Navigateur  (http://127.0.0.1:18800)
echo  [2] Electron    (fenetre native)
echo  [3] Proxy seul  (sans UI)
echo.
set /p mode="Choix (1/2/3): "
if "%mode%"=="2" (
  echo Lancement Electron...
  "%~dp0..\electron\node_modules\.bin\electron.cmd" "%~dp0."
) else if "%mode%"=="3" (
  echo Proxy seul...
  node "%~dp0direct-proxy.js"
) else (
  echo Lancement proxy + navigateur...
  start /B node "%~dp0direct-proxy.js"
  timeout /t 2 /nobreak >nul
  start http://127.0.0.1:18800
  echo Proxy actif. Ctrl+C pour arreter.
  pause
)
