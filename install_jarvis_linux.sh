#!/usr/bin/env bash
###############################################################################
# JARVIS Linux — Installateur complet v1.0
# Usage: bash install_jarvis_linux.sh [--dry-run] [--skip-gpu] [--help]
# Idempotent, relancable sans casser. Log: /tmp/jarvis-install.log
###############################################################################
set -euo pipefail

# ─── Configuration ──────────────────────────────────────────────────────────
JARVIS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="/tmp/jarvis-install.log"
DRY_RUN=false
SKIP_GPU=false
VOSK_MODEL="vosk-model-small-fr-0.22"
VOSK_URL="https://alphacephei.com/vosk/models/${VOSK_MODEL}.zip"
PIPER_MODEL_NAME="fr_FR-siwis-medium"
PIPER_MODEL_URL="https://huggingface.co/rhasspy/piper-voices/resolve/main/fr/fr_FR/siwis/medium/fr_FR-siwis-medium.onnx"
PIPER_MODEL_JSON_URL="https://huggingface.co/rhasspy/piper-voices/resolve/main/fr/fr_FR/siwis/medium/fr_FR-siwis-medium.onnx.json"
MIN_RAM_GB=16
MIN_DISK_GB=20
DASHBOARD_PORT=8088
TOTAL_STEPS=10
CURRENT_STEP=0

# ─── Couleurs ───────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# ─── Fonctions utilitaires ──────────────────────────────────────────────────

usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --dry-run    Afficher ce qui serait fait sans executer"
    echo "  --skip-gpu   Ignorer la verification GPU NVIDIA"
    echo "  --help       Afficher cette aide"
    exit 0
}

log() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] $1"
    echo "$msg" >> "$LOG_FILE"
    echo -e "${CYAN}${msg}${NC}"
}

log_ok() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] [OK] $1"
    echo "$msg" >> "$LOG_FILE"
    echo -e "${GREEN}${msg}${NC}"
}

log_warn() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] [WARN] $1"
    echo "$msg" >> "$LOG_FILE"
    echo -e "${YELLOW}${msg}${NC}"
}

log_err() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] [ERREUR] $1"
    echo "$msg" >> "$LOG_FILE"
    echo -e "${RED}${msg}${NC}"
}

die() {
    log_err "$1"
    exit 1
}

run_cmd() {
    if $DRY_RUN; then
        echo -e "  ${YELLOW}[DRY-RUN]${NC} $*"
        echo "[DRY-RUN] $*" >> "$LOG_FILE"
        return 0
    fi
    "$@" >> "$LOG_FILE" 2>&1
}

progress_bar() {
    CURRENT_STEP=$((CURRENT_STEP + 1))
    local pct=$((CURRENT_STEP * 100 / TOTAL_STEPS))
    local filled=$((pct / 5))
    local empty=$((20 - filled))
    local bar=""
    for ((i = 0; i < filled; i++)); do bar+="█"; done
    for ((i = 0; i < empty; i++)); do bar+="░"; done
    echo ""
    echo -e "${BOLD}[${bar}] ${pct}%  Etape ${CURRENT_STEP}/${TOTAL_STEPS}: $1${NC}"
    echo "[PROGRESS] ${pct}% — Etape ${CURRENT_STEP}/${TOTAL_STEPS}: $1" >> "$LOG_FILE"
    echo ""
}

separator() {
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

# ─── Parse arguments ────────────────────────────────────────────────────────
for arg in "$@"; do
    case "$arg" in
        --dry-run)  DRY_RUN=true ;;
        --skip-gpu) SKIP_GPU=true ;;
        --help)     usage ;;
        *)          die "Argument inconnu: $arg. Utiliser --help." ;;
    esac
done

# ─── Init log ───────────────────────────────────────────────────────────────
echo "=== JARVIS Linux Install — $(date) ===" > "$LOG_FILE"
echo "JARVIS_DIR=$JARVIS_DIR" >> "$LOG_FILE"
echo "DRY_RUN=$DRY_RUN / SKIP_GPU=$SKIP_GPU" >> "$LOG_FILE"

separator
echo -e "${BOLD}${CYAN}"
echo "     ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗"
echo "     ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝"
echo "     ██║███████║██████╔╝██║   ██║██║███████╗"
echo "██   ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║"
echo "╚█████╔╝██║  ██║██║  ██║ ╚████╔╝ ██║███████║"
echo " ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝"
echo -e "${NC}"
echo -e "${BOLD}        Installateur Linux complet v1.0${NC}"
echo ""
$DRY_RUN && echo -e "${YELLOW}        *** MODE DRY-RUN — rien ne sera modifie ***${NC}" && echo ""
separator
echo ""

###############################################################################
# ETAPE 1 : Verifications prealables
###############################################################################
progress_bar "Verifications prealables"

# OS : Ubuntu/Debian
if [ -f /etc/os-release ]; then
    . /etc/os-release
    case "$ID" in
        ubuntu|debian|linuxmint|pop) log_ok "OS detecte: $PRETTY_NAME" ;;
        *) log_warn "OS non-officiel ($ID). L'installateur est prevu pour Ubuntu/Debian." ;;
    esac
else
    die "/etc/os-release introuvable — OS non supporte."
fi

# Python 3.12+
if command -v python3 &>/dev/null; then
    PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
    PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)
    if [ "$PY_MAJOR" -ge 3 ] && [ "$PY_MINOR" -ge 12 ]; then
        log_ok "Python $PY_VERSION detecte"
    else
        die "Python 3.12+ requis (trouve: $PY_VERSION). Installer via: sudo apt install python3.12"
    fi
else
    die "Python3 non trouve. Installer via: sudo apt install python3"
fi

# GPU NVIDIA
if ! $SKIP_GPU; then
    if command -v nvidia-smi &>/dev/null; then
        GPU_INFO=$(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null | head -1)
        log_ok "GPU NVIDIA: $GPU_INFO"
    else
        log_warn "nvidia-smi non trouve. Utiliser --skip-gpu pour ignorer."
        die "GPU NVIDIA requis (ou utiliser --skip-gpu)"
    fi
else
    log_warn "Verification GPU ignoree (--skip-gpu)"
fi

# RAM >= 16GB
TOTAL_RAM_KB=$(grep MemTotal /proc/meminfo | awk '{print $2}')
TOTAL_RAM_GB=$((TOTAL_RAM_KB / 1024 / 1024))
if [ "$TOTAL_RAM_GB" -ge "$MIN_RAM_GB" ]; then
    log_ok "RAM: ${TOTAL_RAM_GB} GB (minimum ${MIN_RAM_GB} GB)"
else
    die "RAM insuffisante: ${TOTAL_RAM_GB} GB (minimum ${MIN_RAM_GB} GB)"
fi

# Espace disque >= 20GB
AVAIL_DISK_KB=$(df --output=avail "$JARVIS_DIR" | tail -1 | tr -d ' ')
AVAIL_DISK_GB=$((AVAIL_DISK_KB / 1024 / 1024))
if [ "$AVAIL_DISK_GB" -ge "$MIN_DISK_GB" ]; then
    log_ok "Espace disque: ${AVAIL_DISK_GB} GB disponibles (minimum ${MIN_DISK_GB} GB)"
else
    die "Espace disque insuffisant: ${AVAIL_DISK_GB} GB (minimum ${MIN_DISK_GB} GB)"
fi

###############################################################################
# ETAPE 2 : Dependances systeme
###############################################################################
progress_bar "Dependances systeme (apt)"

log "Mise a jour de l'index apt..."
run_cmd sudo apt-get update -qq

PKGS_CORE="python3-pip python3-venv git curl wget"
PKGS_DESKTOP="xdotool wmctrl xclip xsel tesseract-ocr tesseract-ocr-fra"
PKGS_AUDIO="ffmpeg sox libsox-dev portaudio19-dev"
PKGS_TOOLS="sqlite3 jq conky-all"
PKGS_GNOME="gnome-screenshot gnome-shell-extensions"

ALL_PKGS="$PKGS_CORE $PKGS_DESKTOP $PKGS_AUDIO $PKGS_TOOLS $PKGS_GNOME"

log "Installation des paquets systeme..."
if $DRY_RUN; then
    echo -e "  ${YELLOW}[DRY-RUN]${NC} sudo apt install -y $ALL_PKGS"
else
    # Installer uniquement les paquets manquants (idempotent)
    MISSING_PKGS=""
    for pkg in $ALL_PKGS; do
        if ! dpkg -s "$pkg" &>/dev/null; then
            MISSING_PKGS="$MISSING_PKGS $pkg"
        fi
    done
    if [ -n "$MISSING_PKGS" ]; then
        log "Paquets manquants:$MISSING_PKGS"
        sudo apt-get install -y $MISSING_PKGS >> "$LOG_FILE" 2>&1
        log_ok "Paquets systeme installes"
    else
        log_ok "Tous les paquets systeme sont deja installes"
    fi
fi

###############################################################################
# ETAPE 3 : Python / uv
###############################################################################
progress_bar "Python / uv + dependances"

# Installer uv si absent
if ! command -v uv &>/dev/null; then
    log "Installation de uv..."
    if $DRY_RUN; then
        echo -e "  ${YELLOW}[DRY-RUN]${NC} curl -LsSf https://astral.sh/uv/install.sh | sh"
    else
        curl -LsSf https://astral.sh/uv/install.sh | sh >> "$LOG_FILE" 2>&1
        # Ajouter uv au PATH pour cette session
        export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
        log_ok "uv installe"
    fi
else
    UV_VER=$(uv --version 2>/dev/null || echo "unknown")
    log_ok "uv deja present ($UV_VER)"
fi

# uv sync dans le repertoire JARVIS
log "Synchronisation des dependances Python (uv sync)..."
if $DRY_RUN; then
    echo -e "  ${YELLOW}[DRY-RUN]${NC} cd $JARVIS_DIR && uv sync"
else
    (cd "$JARVIS_DIR" && uv sync >> "$LOG_FILE" 2>&1)
    log_ok "Dependances Python synchronisees"
fi

###############################################################################
# ETAPE 4 : Vosk model (STT francais)
###############################################################################
progress_bar "Modele Vosk (STT francais)"

VOSK_DIR="$JARVIS_DIR/data/$VOSK_MODEL"
if [ -d "$VOSK_DIR" ]; then
    log_ok "Modele Vosk deja present: $VOSK_DIR"
else
    log "Telechargement du modele Vosk ($VOSK_MODEL)..."
    if $DRY_RUN; then
        echo -e "  ${YELLOW}[DRY-RUN]${NC} wget $VOSK_URL -O /tmp/${VOSK_MODEL}.zip"
        echo -e "  ${YELLOW}[DRY-RUN]${NC} unzip /tmp/${VOSK_MODEL}.zip -d $JARVIS_DIR/data/"
    else
        wget -q --show-progress -O "/tmp/${VOSK_MODEL}.zip" "$VOSK_URL" 2>> "$LOG_FILE"
        unzip -o -q "/tmp/${VOSK_MODEL}.zip" -d "$JARVIS_DIR/data/" >> "$LOG_FILE" 2>&1
        rm -f "/tmp/${VOSK_MODEL}.zip"
        log_ok "Modele Vosk installe"
    fi
fi

###############################################################################
# ETAPE 5 : Piper TTS
###############################################################################
progress_bar "Piper TTS (synthese vocale)"

# Installer piper-tts via pip/uv
if $DRY_RUN; then
    echo -e "  ${YELLOW}[DRY-RUN]${NC} uv pip install piper-tts"
else
    if ! (cd "$JARVIS_DIR" && uv run python -c "import piper" 2>/dev/null); then
        log "Installation de piper-tts..."
        (cd "$JARVIS_DIR" && uv pip install piper-tts >> "$LOG_FILE" 2>&1) || \
            log_warn "piper-tts non installe via uv (peut etre installe globalement)"
    else
        log_ok "piper-tts deja disponible"
    fi
fi

# Telecharger le modele fr_FR-siwis-medium
PIPER_DIR="$JARVIS_DIR/voice_assets"
mkdir -p "$PIPER_DIR"

PIPER_ONNX="$PIPER_DIR/${PIPER_MODEL_NAME}.onnx"
PIPER_JSON="$PIPER_DIR/${PIPER_MODEL_NAME}.onnx.json"

if [ -f "$PIPER_ONNX" ] && [ -f "$PIPER_JSON" ]; then
    log_ok "Modele Piper ${PIPER_MODEL_NAME} deja present"
else
    log "Telechargement du modele Piper ${PIPER_MODEL_NAME}..."
    if $DRY_RUN; then
        echo -e "  ${YELLOW}[DRY-RUN]${NC} wget $PIPER_MODEL_URL -O $PIPER_ONNX"
        echo -e "  ${YELLOW}[DRY-RUN]${NC} wget $PIPER_MODEL_JSON_URL -O $PIPER_JSON"
    else
        [ -f "$PIPER_ONNX" ] || wget -q --show-progress -O "$PIPER_ONNX" "$PIPER_MODEL_URL" 2>> "$LOG_FILE"
        [ -f "$PIPER_JSON" ] || wget -q --show-progress -O "$PIPER_JSON" "$PIPER_MODEL_JSON_URL" 2>> "$LOG_FILE"
        log_ok "Modele Piper installe"
    fi
fi

###############################################################################
# ETAPE 6 : Services systemd
###############################################################################
progress_bar "Services systemd"

SYSTEMD_USER_DIR="$HOME/.config/systemd/user"
mkdir -p "$SYSTEMD_USER_DIR"

# Copier les services depuis le dossier systemd/ du projet (s'il en contient)
SYSTEMD_SRC="$JARVIS_DIR/systemd"
if [ -d "$SYSTEMD_SRC" ]; then
    SYSTEMD_FILES=$(find "$SYSTEMD_SRC" -maxdepth 1 -name '*.service' -o -name '*.timer' -o -name '*.target' 2>/dev/null)
    if [ -n "$SYSTEMD_FILES" ]; then
        log "Copie des fichiers systemd depuis $SYSTEMD_SRC..."
        for f in $SYSTEMD_FILES; do
            run_cmd cp -f "$f" "$SYSTEMD_USER_DIR/"
        done
    fi
fi

# Copier egalement les services deja presents dans ~/.config/systemd/user/ qui sont a jour
# (les fichiers du projet font reference, on s'assure que le daemon est recharge)
JARVIS_SERVICES=$(find "$SYSTEMD_USER_DIR" -maxdepth 1 -name 'jarvis-*.service' -o -name 'jarvis-*.timer' -o -name 'jarvis-*.target' -o -name 'easyspeak-*.service' 2>/dev/null | sort)

if [ -n "$JARVIS_SERVICES" ]; then
    log "Rechargement du daemon systemd utilisateur..."
    run_cmd systemctl --user daemon-reload

    log "Activation des services JARVIS..."
    for svc_path in $JARVIS_SERVICES; do
        svc=$(basename "$svc_path")
        # Ne pas enable les templates (@.service) ni les targets directement
        case "$svc" in
            *@.service|*@.timer) continue ;;
        esac
        if $DRY_RUN; then
            echo -e "  ${YELLOW}[DRY-RUN]${NC} systemctl --user enable $svc"
        else
            systemctl --user enable "$svc" >> "$LOG_FILE" 2>&1 || \
                log_warn "Impossible d'activer $svc"
        fi
    done
    SVC_COUNT=$(echo "$JARVIS_SERVICES" | wc -l)
    log_ok "$SVC_COUNT fichiers systemd configures"
else
    log_warn "Aucun service JARVIS trouve dans $SYSTEMD_USER_DIR"
fi

###############################################################################
# ETAPE 7 : Raccourcis clavier
###############################################################################
progress_bar "Raccourcis clavier"

HOTKEYS_SCRIPT="$JARVIS_DIR/scripts/install_hotkeys.sh"
if [ -f "$HOTKEYS_SCRIPT" ]; then
    log "Installation des raccourcis clavier..."
    run_cmd bash "$HOTKEYS_SCRIPT"
    log_ok "Raccourcis clavier installes"
else
    log_warn "Script $HOTKEYS_SCRIPT introuvable — raccourcis non configures"
fi

###############################################################################
# ETAPE 8 : Conky widgets
###############################################################################
progress_bar "Conky widgets"

CONKY_SRC="$JARVIS_DIR/data"
CONKY_DEST="$HOME/.config/conky"
mkdir -p "$CONKY_DEST"

CONKY_FOUND=false
for conf in "$CONKY_SRC"/jarvis*.conf "$JARVIS_DIR"/conky*.conf; do
    [ -f "$conf" ] || continue
    CONKY_FOUND=true
    dest_file="$CONKY_DEST/$(basename "$conf")"
    if [ -f "$dest_file" ] && cmp -s "$conf" "$dest_file"; then
        continue  # Deja a jour
    fi
    run_cmd cp -f "$conf" "$CONKY_DEST/"
done

# Copier aussi depuis ~/.config/conky s'il y a deja des configs JARVIS
# (pour idempotence, on ne casse pas ce qui existe)
if $CONKY_FOUND; then
    log_ok "Configurations Conky copiees dans $CONKY_DEST"
else
    # Verifier si des configs existent deja dans la destination
    if ls "$CONKY_DEST"/jarvis*.conf &>/dev/null; then
        log_ok "Configurations Conky deja presentes dans $CONKY_DEST"
    else
        log_warn "Aucune configuration Conky JARVIS trouvee"
    fi
fi

###############################################################################
# ETAPE 9 : Base de donnees (commandes vocales, corrections, macros)
###############################################################################
progress_bar "Base de donnees vocale"

DB_SCRIPTS=(
    "scripts/insert_linux_voice_commands.py"
    "scripts/insert_advanced_voice_commands.py"
    "scripts/insert_voice_corrections.py"
    "scripts/insert_voice_macros.py"
)

for script in "${DB_SCRIPTS[@]}"; do
    SCRIPT_PATH="$JARVIS_DIR/$script"
    if [ -f "$SCRIPT_PATH" ]; then
        log "Execution de $script..."
        if $DRY_RUN; then
            echo -e "  ${YELLOW}[DRY-RUN]${NC} cd $JARVIS_DIR && uv run python $SCRIPT_PATH"
        else
            (cd "$JARVIS_DIR" && uv run python "$SCRIPT_PATH" >> "$LOG_FILE" 2>&1) || \
                log_warn "Echec de $script (non bloquant)"
        fi
    else
        log_warn "$script introuvable"
    fi
done

log_ok "Base de donnees vocale configuree"

###############################################################################
# ETAPE 10 : Verification finale
###############################################################################
progress_bar "Verification finale"

ISSUES=0
SERVICES_OK=0
SERVICES_FAIL=0

separator
echo ""
echo -e "${BOLD}${CYAN}  RESUME D'INSTALLATION${NC}"
echo ""

# Tester les services
if ! $DRY_RUN; then
    for svc_path in $JARVIS_SERVICES; do
        svc=$(basename "$svc_path")
        case "$svc" in
            *@.service|*@.timer) continue ;;
        esac
        if systemctl --user is-enabled "$svc" &>/dev/null; then
            SERVICES_OK=$((SERVICES_OK + 1))
        else
            SERVICES_FAIL=$((SERVICES_FAIL + 1))
        fi
    done
    echo -e "  Services systemd actives: ${GREEN}${SERVICES_OK}${NC} | inactifs: ${YELLOW}${SERVICES_FAIL}${NC}"
else
    echo -e "  Services systemd: ${YELLOW}[DRY-RUN — non verifie]${NC}"
fi

# Tester le dashboard web
if ! $DRY_RUN; then
    if curl -s --connect-timeout 3 "http://127.0.0.1:${DASHBOARD_PORT}/" &>/dev/null; then
        echo -e "  Dashboard web (port ${DASHBOARD_PORT}): ${GREEN}ACTIF${NC}"
    else
        echo -e "  Dashboard web (port ${DASHBOARD_PORT}): ${YELLOW}NON DEMARRE${NC} (lancer: systemctl --user start jarvis-dashboard-web.service)"
        ISSUES=$((ISSUES + 1))
    fi
else
    echo -e "  Dashboard web: ${YELLOW}[DRY-RUN — non verifie]${NC}"
fi

# Verifier les composants cles
echo ""
echo -e "  ${BOLD}Composants:${NC}"

# uv
if command -v uv &>/dev/null; then
    echo -e "    uv:          ${GREEN}OK${NC} ($(uv --version 2>/dev/null))"
else
    echo -e "    uv:          ${RED}MANQUANT${NC}"
    ISSUES=$((ISSUES + 1))
fi

# Python venv
if [ -d "$JARVIS_DIR/.venv" ]; then
    echo -e "    venv:        ${GREEN}OK${NC}"
else
    echo -e "    venv:        ${YELLOW}ABSENT${NC} (uv sync le creera)"
fi

# Vosk
if [ -d "$VOSK_DIR" ]; then
    echo -e "    Vosk FR:     ${GREEN}OK${NC}"
else
    echo -e "    Vosk FR:     ${RED}MANQUANT${NC}"
    ISSUES=$((ISSUES + 1))
fi

# Piper model
if [ -f "$PIPER_ONNX" ]; then
    echo -e "    Piper TTS:   ${GREEN}OK${NC} (${PIPER_MODEL_NAME})"
else
    echo -e "    Piper TTS:   ${RED}MANQUANT${NC}"
    ISSUES=$((ISSUES + 1))
fi

# GPU
if ! $SKIP_GPU && command -v nvidia-smi &>/dev/null; then
    GPU_COUNT=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | wc -l)
    echo -e "    GPU NVIDIA:  ${GREEN}OK${NC} (${GPU_COUNT} GPU)"
else
    echo -e "    GPU NVIDIA:  ${YELLOW}IGNORE${NC}"
fi

# Conky
if ls "$CONKY_DEST"/jarvis*.conf &>/dev/null; then
    CONKY_COUNT=$(ls "$CONKY_DEST"/jarvis*.conf 2>/dev/null | wc -l)
    echo -e "    Conky:       ${GREEN}OK${NC} (${CONKY_COUNT} configs)"
else
    echo -e "    Conky:       ${YELLOW}ABSENT${NC}"
fi

# DB vocale
if [ -f "$JARVIS_DIR/jarvis.db" ]; then
    CMD_COUNT=$(sqlite3 "$JARVIS_DIR/jarvis.db" "SELECT COUNT(*) FROM voice_commands;" 2>/dev/null || echo "?")
    echo -e "    DB vocale:   ${GREEN}OK${NC} (${CMD_COUNT} commandes)"
else
    echo -e "    DB vocale:   ${YELLOW}ABSENT${NC}"
fi

echo ""
separator

if [ "$ISSUES" -eq 0 ]; then
    echo ""
    echo -e "${GREEN}${BOLD}  JARVIS installe avec succes !${NC}"
    echo ""
    echo -e "  Commandes utiles:"
    echo -e "    ${CYAN}systemctl --user start jarvis-full.target${NC}   # Demarrer tous les services"
    echo -e "    ${CYAN}systemctl --user status jarvis-master.service${NC} # Status service principal"
    echo -e "    ${CYAN}bash $JARVIS_DIR/jarvis-ctl.sh status${NC}       # Status complet"
    echo ""
else
    echo ""
    echo -e "${YELLOW}${BOLD}  JARVIS installe avec ${ISSUES} avertissement(s).${NC}"
    echo -e "  Consulter le log: ${CYAN}$LOG_FILE${NC}"
    echo ""
fi

separator
echo ""
echo -e "  Log complet: ${CYAN}${LOG_FILE}${NC}"
echo ""
