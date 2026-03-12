@echo off
title JARVIS Mode Ollama Cloud
cd /d /home/turbo/jarvis-m1-ops
echo === JARVIS OLLAMA CLOUD ===
echo Modele: minimax-m2.5:cloud
echo Sous-agents + Recherche web natifs
echo ================================
/home/turbo\.local\bin\uv.exe run python main.py -o
pause
