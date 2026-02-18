@echo off
echo ============================================
echo  JARVIS Turbo v10.1 - LM Studio M2 Startup
echo  3 GPU, 24GB VRAM - Optimized Config
echo ============================================
echo.
echo INSTRUCTIONS: Copier ce script sur M2 et l'executer.
echo Ajuster le chemin de lms.exe si necessaire.
echo.

set LMS="C:\Users\franc\.lmstudio\bin\lms.exe"

echo [1/4] Starting LM Studio server (accessible reseau)...
%LMS% server start -p 1234 --bind 0.0.0.0

echo [2/4] Loading deepseek-coder-v2-lite (primary, ~7GB)...
%LMS% load "deepseek-coder-v2-lite-instruct" --gpu max -c 16384 --parallel 4 -y

echo [3/4] Loading nomic-embed (embeddings, 84MB)...
%LMS% load "nomic" --gpu max -y

echo [4/4] Verifying loaded models...
%LMS% ps

echo.
echo ============================================
echo  M2 READY - deepseek-coder-v2 (16K ctx, 4p)
echo  Server: http://0.0.0.0:1234
echo ============================================
pause
