#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# Claude Code Linux Setup — Install + MCP Configuration
# ═══════════════════════════════════════════════════════════════
set -euo pipefail

GREEN='\033[0;32m'; CYAN='\033[0;36m'; NC='\033[0m'
log() { echo -e "${GREEN}[CLAUDE]${NC} $*"; }

JARVIS_HOME="${JARVIS_HOME:-$HOME/jarvis}"

# ── Step 1: Install Claude Code ──────────────────────────────
log "Step 1/4: Installing Claude Code..."

if command -v claude &>/dev/null; then
    log "Claude Code already installed: $(claude --version 2>/dev/null || echo 'unknown')"
else
    # Method 1: Official native script (recommended)
    if curl -fsSL https://claude.ai/install.sh | bash; then
        log "Installed via native script"
    else
        # Method 2: npm fallback
        log "Native script failed, trying npm..."
        if ! command -v node &>/dev/null; then
            curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
            sudo apt install -y nodejs
        fi
        npm install -g @anthropic-ai/claude-code
        log "Installed via npm"
    fi
fi

# Ensure PATH
if ! echo "$PATH" | grep -q "$HOME/.local/bin"; then
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
    export PATH="$HOME/.local/bin:$PATH"
fi

claude --version && log "Claude Code OK" || { echo "Claude Code not found in PATH"; exit 1; }

# ── Step 2: Configure MCP servers ────────────────────────────
log "Step 2/4: Configuring MCP servers..."

# JARVIS WS server (main API)
claude mcp add --transport http --scope user jarvis-ws -- http://127.0.0.1:9742/mcp 2>/dev/null || true

# JARVIS Direct Proxy (smart routing)
claude mcp add --transport http --scope user jarvis-proxy -- http://127.0.0.1:18800/mcp 2>/dev/null || true

# OpenClaw Gateway (40 agents)
claude mcp add --transport http --scope user jarvis-openclaw -- http://127.0.0.1:18789/mcp 2>/dev/null || true

# GitHub (PRs, issues)
claude mcp add --transport http --scope user github -- https://api.githubcopilot.com/mcp/ 2>/dev/null || true

log "MCP servers configured"

# ── Step 3: Project-level .mcp.json ─────────────────────────
log "Step 3/4: Project MCP config..."

if [ -f "$JARVIS_HOME/.mcp.json" ]; then
    log ".mcp.json already exists in $JARVIS_HOME"
else
    cp "$(dirname "$0")/.mcp.json" "$JARVIS_HOME/.mcp.json" 2>/dev/null || true
    log "Copied .mcp.json to $JARVIS_HOME"
fi

# ── Step 4: CLAUDE.md for project context ────────────────────
log "Step 4/4: Project instructions..."

if [ ! -f "$JARVIS_HOME/CLAUDE.md" ]; then
    cat > "$JARVIS_HOME/CLAUDE.md" << 'CLAUDEMD'
# JARVIS AI Cluster

## Architecture
- **M1** (127.0.0.1:1234): qwen3-8b, local, fast (46 tok/s)
- **M2** (192.168.1.26:1234): deepseek-r1-0528-qwen3-8b, reasoning
- **M3** (192.168.1.113:1234): deepseek-r1-0528-qwen3-8b, fallback
- **OL1** (127.0.0.1:11434): Ollama, qwen3:1.7b, ultra-fast
- **Gemini**: API direct, flash/pro
- **OpenClaw**: 40 agents gateway (ws://127.0.0.1:18789)

## Key Files
- `python_ws/server.py` — Main FastAPI server (port 9742)
- `canvas/direct-proxy.js` — Smart routing proxy (port 18800)
- `canvas/telegram-bot.js` — Telegram integration
- `scripts/pipeline_engine.py` — Circulating pipeline engine
- `scripts/devops_orchestrator.py` — DevOps orchestrator
- `src/config.py` — Cluster configuration & routing matrix

## Rules
- Always use `127.0.0.1` not `localhost` (IPv6 latency on some systems)
- OL1 cloud models: `think:false` + `/no_think` in prompt obligatory
- M2/M3 deepseek-r1: NO `/nothink`, needs max_tokens >= 4096
- Pipeline sections saved to SQLite after every chunk
CLAUDEMD
    log "Created CLAUDE.md"
fi

# ── Summary ──────────────────────────────────────────────────
echo ""
echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Claude Code configured for JARVIS!${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
echo ""
echo "  MCP servers:"
claude mcp list 2>/dev/null || echo "  (run 'claude mcp list' to verify)"
echo ""
echo "  Usage:"
echo "    cd $JARVIS_HOME"
echo "    claude                    # Interactive session"
echo "    claude -p 'fix bug in server.py'  # One-shot"
echo "    claude -c                 # Continue last session"
echo ""
echo "  First time: authenticate via browser when prompted"
echo ""
