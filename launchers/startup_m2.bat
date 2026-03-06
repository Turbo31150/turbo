@echo off
echo ============================================
echo  JARVIS Turbo v10.6 - LM Studio M2 Startup
echo  3 GPU, 24GB VRAM - Reasoning Config
echo ============================================
echo.
echo INSTRUCTIONS: Copier ce script sur M2 et l'executer.
echo Ajuster le chemin de lms.exe si necessaire.
echo.

set LMS="C:\Users\franc\.lmstudio\bin\lms.exe"

echo [1/4] Starting LM Studio server (accessible reseau)...
%LMS% server start -p 1234 --bind 0.0.0.0

echo [2/4] Loading deepseek-r1-0528-qwen3-8b (reasoning, ~5GB)...
%LMS% load "deepseek/deepseek-r1-0528-qwen3-8b" --gpu max -c 27000 --parallel 2 -y

echo [3/4] Loading nomic-embed (embeddings, 84MB)...
%LMS% load "nomic" --gpu max -y

echo [4/4] Verifying loaded models...
%LMS% ps

echo.
echo ============================================
echo  M2 READY - deepseek-r1 (27K ctx, reasoning)
echo  Server: http://0.0.0.0:1234
echo ============================================
pause
