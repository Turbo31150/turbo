@echo off
echo ============================================================
echo  JARVIS Fine-Tuning — Installation des dependances
echo ============================================================
echo.

set UV=C:\Users\franc\.local\bin\uv.exe
set TURBO=F:\BUREAU\turbo

echo [1/3] Installation de PyTorch 2.10 avec CUDA 13.0...
echo       (Driver NVIDIA 591.86 / CUDA 13.1 — compatible)
echo.
"%UV%" pip install --directory "%TURBO%" torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu130
if errorlevel 1 (
    echo.
    echo [WARN] cu130 echoue, tentative avec cu128...
    "%UV%" pip install --directory "%TURBO%" torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128
)

echo.
echo [2/3] Installation des libs ML (transformers, peft, trl, bitsandbytes)...
echo.
"%UV%" pip install --directory "%TURBO%" -r "%TURBO%\finetuning\requirements-finetune.txt"

echo.
echo [3/3] Verification de l'installation...
echo.
"%UV%" run --directory "%TURBO%" python -c "import torch; print(f'PyTorch {torch.__version__}'); print(f'CUDA: {torch.cuda.is_available()}'); print(f'GPUs: {torch.cuda.device_count()}')"
"%UV%" run --directory "%TURBO%" python -c "import transformers, peft, trl, bitsandbytes, datasets; print('Toutes les libs ML installees OK')"

echo.
echo ============================================================
echo  Installation terminee !
echo.
echo  Prochaines etapes :
echo    1. Arretez LM Studio (liberer VRAM)
echo    2. cd %TURBO%
echo    3. uv run python finetuning/prepare_dataset.py
echo    4. uv run python finetuning/train.py
echo    5. uv run python finetuning/convert_gguf.py
echo.
echo  Ou lancez directement: launch_training.bat
echo ============================================================
pause
