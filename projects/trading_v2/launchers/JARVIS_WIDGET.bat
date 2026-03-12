@echo off
title J.A.R.V.I.S. Turbo — Widget
echo   Lancement Widget JARVIS via Turbo...
cd /d /home/turbo/jarvis-m1-ops
start /b /home/turbo\.local\bin\uv.exe run python -c "from src.config import SCRIPTS; import subprocess, sys; subprocess.Popen([sys.executable, str(SCRIPTS['jarvis_widget'])])"
echo   Widget lance.
