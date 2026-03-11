@echo off
title JARVIS Mode Ollama Cloud
cd /d F:\BUREAU\turbo
echo === JARVIS OLLAMA CLOUD ===
echo Modele: minimax-m2.5:cloud
echo Sous-agents + Recherche web natifs
echo ================================
C:\Users\franc\.local\bin\uv.exe run python main.py -o
pause
