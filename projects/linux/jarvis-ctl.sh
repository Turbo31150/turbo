#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# jarvis-ctl — JARVIS Linux control script
# Usage: ./jarvis-ctl.sh [start|stop|status|restart|logs|health|update]
# ═══════════════════════════════════════════════════════════════

JARVIS_HOME="${JARVIS_HOME:-$HOME/jarvis}"
SERVICES=(jarvis-ws jarvis-proxy jarvis-openclaw jarvis-pipeline)

RED='\033[0;31m'; GREEN='\033[0;32m'; ORANGE='\033[0;33m'; CYAN='\033[0;36m'; NC='\033[0m'

case "${1:-status}" in
  start)
    echo -e "${GREEN}Starting JARVIS services...${NC}"
    for svc in "${SERVICES[@]}"; do
      systemctl --user enable --now "$svc" 2>/dev/null && \
        echo -e "  ${GREEN}+${NC} $svc" || echo -e "  ${RED}x${NC} $svc"
    done
    ;;

  stop)
    echo -e "${ORANGE}Stopping JARVIS services...${NC}"
    for svc in "${SERVICES[@]}"; do
      systemctl --user stop "$svc" 2>/dev/null && \
        echo -e "  ${ORANGE}-${NC} $svc" || echo -e "  ${RED}x${NC} $svc"
    done
    ;;

  restart)
    echo -e "${CYAN}Restarting JARVIS services...${NC}"
    for svc in "${SERVICES[@]}"; do
      systemctl --user restart "$svc" 2>/dev/null && \
        echo -e "  ${GREEN}~${NC} $svc" || echo -e "  ${RED}x${NC} $svc"
    done
    ;;

  status)
    echo -e "${CYAN}═══ JARVIS Service Status ═══${NC}"
    for svc in "${SERVICES[@]}"; do
      state=$(systemctl --user is-active "$svc" 2>/dev/null || echo "inactive")
      if [ "$state" = "active" ]; then
        echo -e "  ${GREEN}●${NC} $svc — ${GREEN}active${NC}"
      else
        echo -e "  ${RED}●${NC} $svc — ${RED}$state${NC}"
      fi
    done
    echo ""

    # Cluster health
    echo -e "${CYAN}═══ Cluster Health ═══${NC}"
    for node in "M1:127.0.0.1:1234" "M2:192.168.1.26:1234" "M3:192.168.1.113:1234"; do
      name="${node%%:*}"
      url="http://${node#*:}/api/v1/models"
      models=$(curl -s --max-time 3 "$url" 2>/dev/null | python3 -c "
import sys,json
try:
    d=json.load(sys.stdin)
    loaded=[m for m in d.get('data',d.get('models',[])) if m.get('loaded_instances')]
    print(len(loaded))
except: print(0)" 2>/dev/null || echo "0")
      if [ "$models" -gt 0 ] 2>/dev/null; then
        echo -e "  ${GREEN}●${NC} $name — ${GREEN}$models models${NC}"
      else
        echo -e "  ${RED}●${NC} $name — ${RED}offline${NC}"
      fi
    done

    # Ollama
    ol_count=$(curl -s --max-time 3 http://127.0.0.1:11434/api/tags 2>/dev/null | python3 -c "
import sys,json
try: print(len(json.load(sys.stdin).get('models',[])))
except: print(0)" 2>/dev/null || echo "0")
    if [ "$ol_count" -gt 0 ] 2>/dev/null; then
      echo -e "  ${GREEN}●${NC} OL1 — ${GREEN}$ol_count models${NC}"
    else
      echo -e "  ${RED}●${NC} OL1 — ${RED}offline${NC}"
    fi

    # WS server
    ws_health=$(curl -s --max-time 3 http://127.0.0.1:9742/health 2>/dev/null)
    if [ -n "$ws_health" ]; then
      echo -e "  ${GREEN}●${NC} WS Server — ${GREEN}healthy${NC}"
    else
      echo -e "  ${RED}●${NC} WS Server — ${RED}offline${NC}"
    fi
    ;;

  logs)
    svc="${2:-jarvis-ws}"
    echo -e "${CYAN}Logs for $svc:${NC}"
    journalctl --user -u "$svc" -f --no-pager -n 50
    ;;

  health)
    echo -e "${CYAN}Full health check...${NC}"
    curl -s http://127.0.0.1:9742/health 2>/dev/null | python3 -m json.tool 2>/dev/null || \
      echo -e "${RED}WS server not responding${NC}"
    ;;

  update)
    echo -e "${CYAN}Updating JARVIS...${NC}"
    cd "$JARVIS_HOME"
    git pull
    source .venv/bin/activate
    uv pip install -r requirements.txt 2>/dev/null || true
    echo -e "${GREEN}Updated. Restart services: $0 restart${NC}"
    ;;

  pipeline)
    shift
    echo -e "${CYAN}Running pipeline...${NC}"
    cd "$JARVIS_HOME"
    source .venv/bin/activate
    python scripts/pipeline_engine.py "$@"
    ;;

  *)
    echo "Usage: $0 {start|stop|restart|status|logs [service]|health|update|pipeline [args]}"
    exit 1
    ;;
esac
