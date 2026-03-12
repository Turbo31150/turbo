# JARVIS Linux Deployment

## Quick Install (bare metal)

```bash
curl -sSL https://raw.githubusercontent.com/Turbo31150/turbo/main/projects/linux/install.sh | bash
```

Or clone first:
```bash
git clone https://github.com/Turbo31150/turbo.git ~/jarvis
cd ~/jarvis/projects/linux
chmod +x install.sh jarvis-ctl.sh
./install.sh
```

## Control

```bash
./jarvis-ctl.sh start     # Start all services
./jarvis-ctl.sh stop      # Stop all services
./jarvis-ctl.sh status    # Full status + cluster health
./jarvis-ctl.sh logs      # Follow WS server logs
./jarvis-ctl.sh health    # API health check
./jarvis-ctl.sh update    # Git pull + pip update
./jarvis-ctl.sh pipeline --run "Build auth middleware"  # Run pipeline
```

## Docker

```bash
cd ~/jarvis/projects/linux
docker compose up -d
```

## Services

| Service | Port | Description |
|---------|------|-------------|
| jarvis-ws | 9742 | WebSocket + REST API |
| jarvis-proxy | 18800 | Direct proxy (routing) |
| jarvis-openclaw | 18789 | OpenClaw gateway (40 agents) |
| jarvis-pipeline | - | Pipeline daemon (background) |

## Configuration

Edit `~/jarvis/.env` with your API keys:
- `GEMINI_API_KEY` — Google Gemini
- `HF_TOKEN` — HuggingFace
- `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID`
- LM Studio node IPs (M1, M2, M3)

## GPU Support

For NVIDIA GPUs with Docker:
```bash
sudo apt install nvidia-container-toolkit
sudo systemctl restart docker
```

For bare metal LM Studio:
- Install from https://lmstudio.ai/
- Load models: qwen3-8b (M1), deepseek-r1-0528-qwen3-8b (M2/M3)
- Start API server on port 1234
