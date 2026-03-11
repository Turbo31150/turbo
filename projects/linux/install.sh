#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# JARVIS Linux Installer — Full cluster deployment
# ═══════════════════════════════════════════════════════════════
set -euo pipefail

JARVIS_HOME="${JARVIS_HOME:-$HOME/jarvis}"
REPO_URL="https://github.com/Turbo31150/turbo.git"
PYTHON_MIN="3.11"
NODE_MIN="18"

RED='\033[0;31m'; GREEN='\033[0;32m'; ORANGE='\033[0;33m'; CYAN='\033[0;36m'; NC='\033[0m'

log()  { echo -e "${GREEN}[JARVIS]${NC} $*"; }
warn() { echo -e "${ORANGE}[WARN]${NC} $*"; }
err()  { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# ── Step 1: System dependencies ──────────────────────────────
log "Step 1/7: System dependencies..."

if command -v apt-get &>/dev/null; then
    sudo apt-get update -qq
    sudo apt-get install -y -qq git curl wget python3 python3-pip python3-venv nodejs npm sqlite3 jq
elif command -v dnf &>/dev/null; then
    sudo dnf install -y git curl wget python3 python3-pip nodejs npm sqlite jq
elif command -v pacman &>/dev/null; then
    sudo pacman -Syu --noconfirm git curl wget python python-pip nodejs npm sqlite jq
else
    warn "Unknown package manager — install git, python3, nodejs, sqlite3 manually"
fi

# ── Step 2: uv (Python package manager) ─────────────────────
log "Step 2/7: Installing uv..."
if ! command -v uv &>/dev/null; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi
uv --version && log "uv OK" || err "uv installation failed"

# ── Step 3: Clone repo ──────────────────────────────────────
log "Step 3/7: Cloning JARVIS to $JARVIS_HOME..."
if [ -d "$JARVIS_HOME/.git" ]; then
    log "Repo exists — pulling latest..."
    cd "$JARVIS_HOME" && git pull
else
    git clone "$REPO_URL" "$JARVIS_HOME"
fi
cd "$JARVIS_HOME"

# ── Step 4: Python venv + dependencies ───────────────────────
log "Step 4/7: Python environment..."
uv venv .venv --python python3
source .venv/bin/activate
uv pip install -r requirements.txt 2>/dev/null || uv pip install \
    fastapi uvicorn websockets httpx aiohttp pydantic \
    google-genai anthropic openai \
    aiosqlite python-dotenv edge-tts \
    pytest pytest-asyncio

# ── Step 5: Node dependencies ────────────────────────────────
log "Step 5/7: Node.js dependencies..."
if [ -f "package.json" ]; then
    npm install --production 2>/dev/null || true
fi
if [ -f "electron/package.json" ]; then
    cd electron && npm install && cd ..
fi

# ── Step 6: Environment config ───────────────────────────────
log "Step 6/7: Environment configuration..."

ENV_FILE="$JARVIS_HOME/.env"
if [ ! -f "$ENV_FILE" ]; then
    cat > "$ENV_FILE" << 'ENVEOF'
# JARVIS Linux Configuration
TURBO=/home/$USER/jarvis

# ── LM Studio nodes (adjust IPs for your network) ──
M1_HOST=127.0.0.1
M1_PORT=1234
M2_HOST=192.168.1.26
M2_PORT=1234
M3_HOST=192.168.1.113
M3_PORT=1234

# ── Ollama ──
OLLAMA_HOST=127.0.0.1
OLLAMA_PORT=11434

# ── API Keys (fill in) ──
# GEMINI_API_KEY=
# HF_TOKEN=
# TELEGRAM_BOT_TOKEN=
# TELEGRAM_CHAT_ID=

# ── Services ──
WS_PORT=9742
PROXY_PORT=18800
OPENCLAW_PORT=18789
ENVEOF
    log "Created .env — edit $ENV_FILE with your API keys"
else
    log ".env already exists"
fi

# ── Step 7: Systemd services ────────────────────────────────
log "Step 7/7: Creating systemd services..."

SYSTEMD_DIR="$HOME/.config/systemd/user"
mkdir -p "$SYSTEMD_DIR"

# Main WS server
cat > "$SYSTEMD_DIR/jarvis-ws.service" << EOF
[Unit]
Description=JARVIS WebSocket Server
After=network.target

[Service]
Type=simple
WorkingDirectory=$JARVIS_HOME
ExecStart=$JARVIS_HOME/.venv/bin/python -m python_ws.server
Restart=always
RestartSec=5
Environment=TURBO=$JARVIS_HOME

[Install]
WantedBy=default.target
EOF

# Direct proxy
cat > "$SYSTEMD_DIR/jarvis-proxy.service" << EOF
[Unit]
Description=JARVIS Direct Proxy
After=network.target jarvis-ws.service

[Service]
Type=simple
WorkingDirectory=$JARVIS_HOME/canvas
ExecStart=/usr/bin/node direct-proxy.js
Restart=always
RestartSec=5
Environment=TURBO=$JARVIS_HOME

[Install]
WantedBy=default.target
EOF

# OpenClaw gateway
cat > "$SYSTEMD_DIR/jarvis-openclaw.service" << EOF
[Unit]
Description=JARVIS OpenClaw Gateway
After=network.target jarvis-ws.service

[Service]
Type=simple
WorkingDirectory=$JARVIS_HOME
ExecStart=$JARVIS_HOME/.venv/bin/python -m src.openclaw_bridge
Restart=always
RestartSec=10
Environment=TURBO=$JARVIS_HOME

[Install]
WantedBy=default.target
EOF

# Pipeline daemon
cat > "$SYSTEMD_DIR/jarvis-pipeline.service" << EOF
[Unit]
Description=JARVIS Pipeline Engine Daemon
After=network.target jarvis-ws.service

[Service]
Type=simple
WorkingDirectory=$JARVIS_HOME
ExecStart=$JARVIS_HOME/.venv/bin/python scripts/pipeline_engine.py --daemon
Restart=always
RestartSec=30
Environment=TURBO=$JARVIS_HOME

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
log "Systemd services created (not started yet)"

# ── Summary ──────────────────────────────────────────────────
echo ""
echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  JARVIS installed at: $JARVIS_HOME${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
echo ""
echo "  Next steps:"
echo "    1. Edit $ENV_FILE with your API keys"
echo "    2. Start services:"
echo "       systemctl --user enable --now jarvis-ws"
echo "       systemctl --user enable --now jarvis-proxy"
echo "       systemctl --user enable --now jarvis-openclaw"
echo "       systemctl --user enable --now jarvis-pipeline"
echo ""
echo "    3. Or start manually:"
echo "       cd $JARVIS_HOME && source .venv/bin/activate"
echo "       python -m python_ws.server"
echo ""
echo "    4. Electron app (dev mode):"
echo "       cd $JARVIS_HOME/electron && npm run dev"
echo ""
echo "    5. Check health:"
echo "       curl http://127.0.0.1:9742/health"
echo ""
echo -e "${GREEN}  Done!${NC}"
