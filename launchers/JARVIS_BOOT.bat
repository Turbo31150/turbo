@echo off
chcp 65001 >nul
title JARVIS Cluster Boot
echo.
echo  ══════════════════════════════════════════════════════
echo    JARVIS CLUSTER BOOT — LM Studio + Ollama + JARVIS
echo  ══════════════════════════════════════════════════════
echo.

REM ── Step 1: Boot cluster (LM Studio server + models + warmup) ──
echo [1/2] Boot cluster LM Studio...
powershell -ExecutionPolicy Bypass -File "F:\BUREAU\turbo\launchers\LMStudio-ClusterBoot.ps1"

REM ── Step 2: Launch JARVIS Voice mode ──
echo [2/2] Lancement JARVIS Voice...
cd /d F:\BUREAU\turbo
C:\Users\franc\.local\bin\uv.exe run python main.py -v
pause
