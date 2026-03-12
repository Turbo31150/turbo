#!/bin/bash
echo "🚀 [JARVIS] Début du Preflight Check..."
REPORT="jarvis_preflight_report.md"
echo "# JARVIS Preflight Report - $(date)" > $REPORT
echo "" >> $REPORT

check_cmd() {
    if $1 >/dev/null 2>&1; then
        echo "✅ $2 : OK" | tee -a $REPORT
        return 0
    else
        echo "❌ $2 : ÉCHEC" | tee -a $REPORT
        return 1
    fi
}

check_url() {
    if curl -s --max-time 2 $1 >/dev/null; then
        echo "✅ $2 ($1) : JOIGNABLE" | tee -a $REPORT
        return 0
    else
        echo "❌ $2 ($1) : INJOIGNABLE" | tee -a $REPORT
        return 1
    fi
}

echo "--- INFRASTRUCTURE ---" >> $REPORT
check_cmd "nvidia-smi" "GPU (nvidia-smi)"
check_cmd "docker ps" "Docker Daemon"
check_url "http://127.0.0.1:1234/v1/models" "M1 LM Studio"
check_url "http://192.168.1.26:1234/v1/models" "M2 LM Studio (LMT2)"
check_url "http://127.0.0.1:11434" "Ollama Local"

echo "--- SERVICES JARVIS ---" >> $REPORT
check_url "http://127.0.0.1:8080/mcp" "MCP Flask Server"
check_url "http://127.0.0.1:18790/health" "OpenClaw Gateway"
check_cmd "systemctl --user is-active jarvis-ws.service" "WebSocket Server"
check_cmd "systemctl --user is-active jarvis-lmstudio-debugger.service" "Auto-Debugger Agent"

echo "" >> $REPORT
echo "🚀 Preflight Check terminé. Rapport généré dans $REPORT"
