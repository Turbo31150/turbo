@echo off
REM Launcher JARVIS Benchmark Comparatif
REM Lance le benchmark modèle base vs fine-tuné

cd /d "F:\BUREAU\turbo"
echo.
echo ============================================
echo   JARVIS Benchmark Comparatif
echo   Qwen3-30B Base vs Fine-tuné (LoRA)
echo ============================================
echo.

REM Afficher les informations du système
echo [INFO] Configuration:
echo   Working Directory: %CD%
echo   Python: Python 3.13 (via uv)
echo   Device: CUDA (si disponible)
echo.

REM Lancer le benchmark
echo [DÉMARRAGE] Benchmark en cours...
echo.
powershell -Command "& 'C:\Users\franc\.local\bin\uv.exe' run python finetuning\benchmark.py"

REM Pause pour voir les résultats
echo.
echo ============================================
echo   Benchmark terminé !
echo   Résultats: F:\BUREAU\turbo\finetuning\benchmark_results.json
echo ============================================
pause
