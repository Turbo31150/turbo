@echo off
echo ============================================================
echo  JARVIS Fine-Tuning — Pipeline complet
echo ============================================================
echo.

set UV=C:\Users\franc\.local\bin\uv.exe
set TURBO=F:\BUREAU\turbo

echo [!!] IMPORTANT: Arretez LM Studio avant de continuer !
echo     Le fine-tuning a besoin de TOUTE la VRAM disponible.
echo.
echo Appuyez sur une touche pour continuer...
pause >nul

echo.
echo ============================================================
echo  ETAPE 1/3 — Preparation du dataset
echo ============================================================
echo.
"%UV%" run --directory "%TURBO%" python finetuning/prepare_dataset.py 50000
if errorlevel 1 (
    echo [ERREUR] Preparation du dataset echouee !
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  ETAPE 2/3 — Fine-tuning QLoRA (peut prendre des heures)
echo ============================================================
echo.
"%UV%" run --directory "%TURBO%" python finetuning/train.py
if errorlevel 1 (
    echo [ERREUR] Fine-tuning echoue !
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  ETAPE 3/3 — Conversion GGUF pour LM Studio
echo ============================================================
echo.
"%UV%" run --directory "%TURBO%" python finetuning/convert_gguf.py Q4_K_M
if errorlevel 1 (
    echo [ERREUR] Conversion echouee !
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  Fine-tuning termine avec succes !
echo  Le modele GGUF est pret pour LM Studio.
echo ============================================================
pause
