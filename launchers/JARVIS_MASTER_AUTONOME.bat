@echo off
title JARVIS Master Autonome — Full Stack
echo ============================================================
echo  JARVIS MASTER AUTONOME — Lancement complet
echo  Proxy + Bot Telegram + Pipeline Autonome + Master
echo ============================================================
echo.
cd /d F:\BUREAU\turbo

:: 1. Proxy Canvas (18800)
echo [1/4] Verification du proxy Canvas...
curl -s --max-time 2 http://127.0.0.1:18800/health >nul 2>&1
if %errorlevel% neq 0 (
    echo [*] Demarrage Canvas Direct Proxy :18800...
    start "JARVIS-Proxy" /min cmd /c "cd /d F:\BUREAU\turbo && node canvas\direct-proxy.js"
    timeout /t 3 /nobreak >nul
) else (
    echo [OK] Proxy deja actif sur :18800
)

:: 2. Bot Telegram
echo [2/4] Demarrage du Bot Telegram...
start "JARVIS-Telegram" /min cmd /c "cd /d F:\BUREAU\turbo && node canvas\telegram-bot.js"
timeout /t 2 /nobreak >nul

:: 3. Orchestrateur Autonome (13 taches cron)
echo [3/4] Demarrage de l'Orchestrateur Autonome...
start "JARVIS-Orchestrator" /min cmd /c "cd /d F:\BUREAU\turbo\cowork\dev && python autonomous_orchestrator.py --watch"
timeout /t 2 /nobreak >nul

:: 4. Master Autonome (vagues en cascade)
echo [4/4] Demarrage du Master Autonome (vagues)...
start "JARVIS-Master" /min cmd /c "cd /d F:\BUREAU\turbo && python cowork\dev\jarvis_master_autonome.py"
timeout /t 2 /nobreak >nul

echo.
echo ============================================================
echo  Tous les services lances!
echo ============================================================
echo.
echo  1. Proxy Canvas       :18800 (M1+OL1+M3)
echo  2. Bot Telegram       @turboSSebot (26 commandes)
echo  3. Orchestrateur      13 taches cron (heartbeat 2min)
echo  4. Master Autonome    6 vagues (30m/1h/2h/3h/6h/24h)
echo.
echo  Telegram: /status /menu /hot /scan /domino
echo  Master:   python cowork\dev\jarvis_master_autonome.py --status
echo  Lint:     python cowork\dev\code_lint_agents.py --recent
echo.
echo  Appuyez sur une touche pour arreter TOUS les services.
pause

:: Kill all workers
taskkill /FI "WINDOWTITLE eq JARVIS-*" /F 2>nul
echo Services arretes.
pause
