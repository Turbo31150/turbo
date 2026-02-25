@echo off
echo ============================================
echo    JARVIS Turbo v10.1 — Installation
echo ============================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERREUR] Python non trouve. Installez Python 3.13+
    pause
    exit /b 1
)

REM Check uv
where uv >nul 2>&1
if errorlevel 1 (
    echo [INFO] Installation de uv...
    pip install uv
)

REM Install dependencies
echo [1/4] Installation des dependances...
uv sync
if errorlevel 1 (
    echo [ERREUR] Echec installation dependances
    pause
    exit /b 1
)

REM Create data directory
echo [2/4] Creation des dossiers...
if not exist "data" mkdir data

REM Create .env if not exists
echo [3/4] Configuration...
if not exist ".env" (
    echo LM_STUDIO_1_URL=http://localhost:1234 > .env
    echo LM_STUDIO_2_URL=http://192.168.1.26:1234 >> .env
    echo LM_STUDIO_3_URL=http://192.168.1.113:1234 >> .env
    echo LM_STUDIO_DEFAULT_MODEL=qwen/qwen3-8b >> .env
    echo DRY_RUN=true >> .env
    echo [INFO] .env cree avec valeurs par defaut. Editez-le pour vos cles API.
) else (
    echo [INFO] .env existe deja.
)

REM Verify installation
echo [4/4] Verification...
.venv\Scripts\python.exe -c "from src.config import config; print(f'JARVIS v{config.version} — {len(config.lm_nodes)} noeuds configures')"
if errorlevel 1 (
    echo [ERREUR] Verification echouee
    pause
    exit /b 1
)

echo.
echo ============================================
echo    Installation terminee !
echo ============================================
echo.
echo Commandes disponibles:
echo   jarvis.bat              Dashboard complet
echo   jarvis_interactive.bat  Mode CLI
echo   jarvis_voice.bat        Mode vocal
echo   jarvis_hybrid.bat       Voix + texte
echo.
pause
