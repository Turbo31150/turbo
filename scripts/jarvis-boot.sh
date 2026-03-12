#!/bin/bash
# JARVIS Unified Boot Script (Ubuntu 22.04)
# Optimisé pour M1 (6 GPUs)

PROJECT_DIR="/home/turbo/jarvis-m1-ops"
VENV="$PROJECT_DIR/.venv/bin/python3"

export PYTHONPATH="$PROJECT_DIR"
export PYTHONIOENCODING="utf-8"

case "$1" in
    proxy)
        echo "[JARVIS] Lancement Gemini Proxy..."
        node "$PROJECT_DIR/gemini-proxy.js"
        ;;
    mcp)
        echo "[JARVIS] Lancement MCP Server..."
        "$VENV" -m src.mcp_server
        ;;
    voice)
        echo "[JARVIS] Lancement Mode Vocal..."
        "$VENV" "$PROJECT_DIR/main.py" -v
        ;;
    master)
        echo "[JARVIS] Lancement Master Autonome..."
        "$VENV" "$PROJECT_DIR/main.py" -c
        ;;
    dashboard)
        echo "[JARVIS] Lancement Dashboard Electron..."
        cd "$PROJECT_DIR/electron" && npm start
        ;;
    *)
        echo "Usage: $0 {proxy|mcp|voice|master|dashboard}"
        exit 1
        ;;
esac
