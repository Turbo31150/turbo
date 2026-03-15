#!/bin/bash
# JARVIS Master Control (Linux Native) - v12.6.1
# Usage: ./jarvis-ctl.sh [start|stop|restart|status|logs|health]

JARVIS_HOME="/home/turbo/jarvis"
SERVICES=("jarvis-recovery" "jarvis-ws" "jarvis-proxy" "jarvis-openclaw" "jarvis-pipeline" "jarvis-mcp" "jarvis-telegram" "jarvis-watchdog" "jarvis-n8n" "jarvis-dashboard" "jarvis-gemini-openai")

RED='\033[0;31m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'; YELLOW='\033[1;33m'; NC='\033[0m'

case "$1" in
    start)
        echo -e "${CYAN}[JARVIS] Starting all cluster services...${NC}"
        systemctl --user start "${SERVICES[@]}"
        ;;
    stop)
        echo -e "${RED}[JARVIS] Stopping all cluster services...${NC}"
        systemctl --user stop "${SERVICES[@]}"
        ;;
    restart)
        echo -e "${CYAN}[JARVIS] Restarting all cluster services...${NC}"
        systemctl --user restart "${SERVICES[@]}"
        ;;
    status)
        echo -e "${CYAN}═══ JARVIS CLUSTER STATUS ═══${NC}"
        systemctl --user list-units "jarvis-*" --all --no-pager
        ;;
    logs)
        journalctl --user -f -u jarvis-ws
        ;;
    health)
        echo -e "${CYAN}═══ JARVIS HEALTH CHECK ═══${NC}"
        printf "%-20s : " "WebSocket (9742)"
        curl -s --max-time 2 http://127.0.0.1:9742/health | jq -r '.status' || echo -e "${RED}OFFLINE${NC}"
        
        printf "%-20s : " "Proxy (18800)"
        curl -s --max-time 2 http://127.0.0.1:18800/health | jq -r '.ok' || echo -e "${RED}OFFLINE${NC}"
        
        printf "%-20s : " "OpenClaw (18789)"
        curl -s --max-time 2 http://127.0.0.1:18789/health | jq -r '.status' || echo -e "${RED}OFFLINE${NC}"
        
        printf "%-20s : " "n8n (5678)"
        curl -s --max-time 2 http://127.0.0.1:5678/healthz || echo -e "${RED}OFFLINE${NC}"
        
        printf "%-20s : " "Dashboard (8080)"
        curl -s --max-time 2 http://127.0.0.1:8080 > /dev/null && echo -e "${GREEN}UP${NC}" || echo -e "${RED}OFFLINE${NC}"
        ;;
    update)
        echo -e "${YELLOW}[JARVIS] Updating repository and dependencies...${NC}"
        git pull
        source .venv/bin/activate && uv pip install -r requirements.txt
        ;;
    sync)
        echo -e "${CYAN}[JARVIS] Syncing cluster via Ansible...${NC}"
        ansible-playbook -i ansible/hosts.ini ansible/jarvis-sync.yml
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|logs|health}"
        exit 1
esac
