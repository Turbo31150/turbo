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

  seed)
    echo -e "${CYAN}Seeding learned_actions.db...${NC}"
    cd "$JARVIS_HOME"
    LEARNED_DB="$JARVIS_HOME/data/learned_actions.db"
    if [ -f "scripts/seed_learned_actions.py" ]; then
        source .venv/bin/activate 2>/dev/null || true
        python scripts/seed_learned_actions.py
    else
        # Inline seed if script not found
        python3 - "$LEARNED_DB" << 'PYEOF'
import sqlite3, sys
db_path = sys.argv[1]
conn = sqlite3.connect(db_path)
c = conn.cursor()
c.execute("""CREATE TABLE IF NOT EXISTS learned_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action TEXT NOT NULL,
    category TEXT DEFAULT 'general',
    source TEXT DEFAULT 'seed',
    confidence REAL DEFAULT 0.5,
    usage_count INTEGER DEFAULT 0,
    last_used TEXT,
    created_at TEXT DEFAULT (datetime('now'))
)""")
c.execute("""CREATE TABLE IF NOT EXISTS dominos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    steps TEXT,
    enabled INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now'))
)""")
seeds = [
    ("health_check", "Run full cluster health check", '["check_ws", "check_proxy", "check_openclaw", "check_cluster"]'),
    ("daily_audit", "Run daily system audit", '["system_audit", "db_maintenance", "log_rotate"]'),
    ("restart_all", "Restart all JARVIS services", '["stop_services", "wait_5s", "start_services", "health_check"]'),
]
for name, desc, steps in seeds:
    c.execute("INSERT OR IGNORE INTO dominos (name, description, steps) VALUES (?, ?, ?)", (name, desc, steps))
conn.commit()
conn.close()
print(f"Seeded {db_path}")
PYEOF
    fi
    echo -e "${GREEN}Done.${NC}"
    ;;

  timers)
    echo -e "${CYAN}═══ Systemd Timers ═══${NC}"
    systemctl --user list-timers --all --no-pager 2>/dev/null || \
        echo -e "${ORANGE}No user timers found${NC}"
    ;;

  dominos)
    echo -e "${CYAN}═══ Available Dominos ═══${NC}"
    LEARNED_DB="$JARVIS_HOME/data/learned_actions.db"
    if [ -f "$LEARNED_DB" ]; then
        python3 - "$LEARNED_DB" << 'PYEOF'
import sqlite3, sys
conn = sqlite3.connect(sys.argv[1])
c = conn.cursor()
try:
    c.execute("SELECT name, description, enabled FROM dominos ORDER BY name")
    rows = c.fetchall()
    if not rows:
        print("  No dominos found.")
    for name, desc, enabled in rows:
        status = "\033[0;32m●\033[0m" if enabled else "\033[0;31m●\033[0m"
        print(f"  {status} {name:<20} — {desc or 'no description'}")
except sqlite3.OperationalError:
    print("  No dominos table found. Run: jarvis-ctl.sh seed")
conn.close()
PYEOF
    else
        echo -e "${ORANGE}learned_actions.db not found. Run: $0 seed${NC}"
    fi
    ;;

  *)
    echo "Usage: $0 {start|stop|restart|status|logs [service]|health|update|pipeline [args]|seed|timers|dominos}"
    exit 1
    ;;
esac
