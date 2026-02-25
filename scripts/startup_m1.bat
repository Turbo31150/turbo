@echo off
echo ============================================
echo  JARVIS Turbo v10.1 - LM Studio M1 Startup
echo  5 GPU, 43GB VRAM - Optimized Config
echo ============================================
echo.

set LMS="C:\Users\franc\.lmstudio\bin\lms.exe"

echo [1/4] Starting LM Studio server...
%LMS% server start -p 1234

echo [2/4] Loading qwen3-8b (primary brain, fast)...
%LMS% load "qwen/qwen3-8b" --gpu max -c 8192 --parallel 4 -y

echo [3/4] Loading nomic-embed (embeddings, 84MB)...
%LMS% load "nomic" --gpu max -y

echo [4/4] Verifying loaded models...
%LMS% ps

echo.
echo ============================================
echo  M1 READY - qwen3-8b (8K ctx, 4 parallel)
echo  Server: http://10.5.0.2:1234
echo ============================================
pause
