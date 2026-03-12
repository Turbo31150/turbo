@echo off
title JARVIS Gemini OpenAI Proxy (port 18793)
cd /d /home/turbo/jarvis-m1-ops

echo ============================================
echo   GEMINI CLI → OpenAI Proxy
echo   Port: 18793
echo   Models: gemini-3-pro/flash, gemini-2.5-pro/flash
echo ============================================

node gemini-openai-proxy.js
pause
