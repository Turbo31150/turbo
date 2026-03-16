#!/usr/bin/env bash
# quick_health.sh — Diagnostic rapide JARVIS (<2s)
# Vérifie services, ports, DB, skills.json
# Usage: bash scripts/quick_health.sh

set -uo pipefail

JARVIS_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PASS=0
FAIL=0
WARN=0
START=$(date +%s%N)

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

pass() { echo -e "  ${GREEN}[PASS]${NC} $1"; ((PASS++)); }
fail() { echo -e "  ${RED}[FAIL]${NC} $1"; ((FAIL++)); }
warn() { echo -e "  ${YELLOW}[WARN]${NC} $1"; ((WARN++)); }

echo -e "${BOLD}${CYAN}========================================${NC}"
echo -e "${BOLD}${CYAN}  JARVIS Quick Health Check${NC}"
echo -e "${BOLD}${CYAN}========================================${NC}"
echo ""

# --- 1. Ports ---
echo -e "${BOLD}[Ports]${NC}"
declare -A PORT_NAMES=(
    [8080]="MCP Server"
    [8088]="Canvas/Proxy"
    [8089]="Pipeline API"
    [1234]="LM Studio"
    [11434]="Ollama"
)

for port in 8080 8088 8089 1234 11434; do
    name="${PORT_NAMES[$port]}"
    if timeout 1 bash -c "echo >/dev/tcp/127.0.0.1/$port" 2>/dev/null; then
        pass "$name (port $port) — accessible"
    else
        # Ollama et LM Studio sont optionnels selon le contexte
        if [[ "$port" == "1234" || "$port" == "11434" ]]; then
            warn "$name (port $port) — non accessible"
        else
            fail "$name (port $port) — non accessible"
        fi
    fi
done

# --- 2. Bases de données ---
echo ""
echo -e "${BOLD}[Bases de données]${NC}"

DB_FILES=(
    "data/jarvis.db"
    "data/etoile.db"
    "data/learned_actions.db"
)

for db_rel in "${DB_FILES[@]}"; do
    db_path="$JARVIS_ROOT/$db_rel"
    if [[ ! -f "$db_path" ]]; then
        fail "$db_rel — fichier absent"
        continue
    fi

    size=$(stat --format='%s' "$db_path" 2>/dev/null || echo "0")
    if [[ "$size" -eq 0 ]]; then
        fail "$db_rel — fichier vide (0 octets)"
        continue
    fi

    # Vérification intégrité SQLite
    integrity=$(sqlite3 "$db_path" "PRAGMA integrity_check;" 2>/dev/null || echo "ERROR")
    if [[ "$integrity" == "ok" ]]; then
        size_hr=$(numfmt --to=iec "$size" 2>/dev/null || echo "${size}B")
        pass "$db_rel — intègre ($size_hr)"
    else
        fail "$db_rel — intégrité compromise: $integrity"
    fi
done

# --- 3. skills.json ---
echo ""
echo -e "${BOLD}[Skills]${NC}"

SKILLS_PATH="$JARVIS_ROOT/data/skills.json"
if [[ ! -f "$SKILLS_PATH" ]]; then
    fail "skills.json — fichier absent"
else
    # Vérifier parseable + compter
    skill_count=$(python3 -c "
import json, sys
try:
    with open('$SKILLS_PATH') as f:
        data = json.load(f)
    if isinstance(data, list):
        print(len(data))
    else:
        print('ERROR: not a list')
except Exception as e:
    print(f'ERROR: {e}')
" 2>/dev/null)

    if [[ "$skill_count" =~ ^[0-9]+$ ]]; then
        pass "skills.json — parseable ($skill_count skills)"
    else
        fail "skills.json — $skill_count"
    fi
fi

# --- 4. Services systemd (si disponibles) ---
echo ""
echo -e "${BOLD}[Services systemd]${NC}"

TIMERS=(
    "jarvis-health.timer"
    "jarvis-backup.timer"
    "jarvis-thermal.timer"
)

for timer in "${TIMERS[@]}"; do
    status=$(systemctl --user is-active "$timer" 2>/dev/null || echo "inactive")
    if [[ "$status" == "active" ]]; then
        pass "$timer — actif"
    else
        warn "$timer — $status"
    fi
done

# --- 5. Processus clés ---
echo ""
echo -e "${BOLD}[Processus]${NC}"

if pgrep -f "ollama" >/dev/null 2>&1; then
    pass "Ollama — en cours"
else
    warn "Ollama — non détecté"
fi

if pgrep -f "lms" >/dev/null 2>&1 || pgrep -f "lmstudio" >/dev/null 2>&1; then
    pass "LM Studio — en cours"
else
    warn "LM Studio — non détecté"
fi

# --- 6. Espace disque ---
echo ""
echo -e "${BOLD}[Disque]${NC}"

disk_usage=$(df -h "$JARVIS_ROOT" 2>/dev/null | tail -1 | awk '{print $5}' | tr -d '%')
if [[ -n "$disk_usage" && "$disk_usage" -lt 85 ]]; then
    pass "Espace disque — ${disk_usage}% utilisé"
elif [[ -n "$disk_usage" && "$disk_usage" -lt 95 ]]; then
    warn "Espace disque — ${disk_usage}% utilisé"
else
    fail "Espace disque — ${disk_usage:-?}% utilisé"
fi

# --- 7. GPU ---
echo ""
echo -e "${BOLD}[GPU]${NC}"

if command -v nvidia-smi &>/dev/null; then
    gpu_count=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | wc -l)
    max_temp=$(nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader,nounits 2>/dev/null | sort -rn | head -1)
    if [[ -n "$max_temp" && "$max_temp" -lt 75 ]]; then
        pass "GPU — $gpu_count détectés, max ${max_temp}°C"
    elif [[ -n "$max_temp" && "$max_temp" -lt 85 ]]; then
        warn "GPU — $gpu_count détectés, max ${max_temp}°C (chaud)"
    else
        fail "GPU — $gpu_count détectés, max ${max_temp:-?}°C (critique)"
    fi
else
    warn "nvidia-smi non disponible"
fi

# --- Résumé ---
END=$(date +%s%N)
DURATION_MS=$(( (END - START) / 1000000 ))

echo ""
echo -e "${BOLD}${CYAN}========================================${NC}"
echo -e "${BOLD}  Résumé${NC}"
echo -e "${CYAN}========================================${NC}"
echo -e "  ${GREEN}PASS${NC}: $PASS  ${RED}FAIL${NC}: $FAIL  ${YELLOW}WARN${NC}: $WARN"
echo -e "  Durée: ${DURATION_MS}ms"
echo ""

if [[ "$FAIL" -eq 0 ]]; then
    echo -e "  ${GREEN}${BOLD}JARVIS est en bonne santé.${NC}"
else
    echo -e "  ${RED}${BOLD}$FAIL problème(s) détecté(s) — attention requise.${NC}"
fi

echo ""
exit $FAIL
