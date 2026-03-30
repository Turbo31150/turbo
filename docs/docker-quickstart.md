# Docker Quickstart Guide

Get JARVIS running in Docker in under 5 minutes. This guide covers the Linux deployment stack with the WebSocket server, proxy, pipeline engine, and optional Ollama for local LLMs.

## Prerequisites

Before you begin, ensure you have:

- **Docker** 20.10+ with Docker Compose v2
- **Git** for cloning the repository
- **NVIDIA GPU** (optional, for local LLM acceleration)
  - NVIDIA drivers installed
  - [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html) for GPU passthrough

### Quick Check

```bash
# Verify Docker is running
docker --version
docker compose version

# (Optional) Verify GPU support
nvidia-smi
docker run --rm --gpus all nvidia/cuda:12.8.0-base-ubuntu24.04 nvidia-smi
```

## Step 1: Clone the Repository

```bash
git clone https://github.com/Turbo31150/turbo.git
cd turbo
```

## Step 2: Configure Environment

Copy the example environment file and edit it with your settings:

```bash
cp .env.example .env
```

Edit `.env` with your API keys (optional but recommended):

```env
# Required for cloud AI features
ANTHROPIC_API_KEY=your-anthropic-key

# LM Studio endpoints (if running locally)
LM_STUDIO_1_URL=http://host.docker.internal:1234
LM_STUDIO_DEFAULT_MODEL=qwen/qwen3-30b-a3b-2507

# Telegram notifications (optional)
TELEGRAM_TOKEN=your-bot-token
TELEGRAM_CHAT=your-chat-id

# Trading (optional, dry run by default)
DRY_RUN=true
```

> **Note:** Use `host.docker.internal` to connect to services running on your host machine (like LM Studio or Ollama).

## Step 3: Start the Services

Navigate to the Linux deployment directory and start the stack:

```bash
cd projects/linux
docker compose up -d
```

This starts:

| Service | Port | Description |
|---------|------|-------------|
| `jarvis-ws` | 9742 | Main WebSocket + REST API server |
| `jarvis-proxy` | 18800 | Direct proxy for routing requests |
| `jarvis-pipeline` | — | Background pipeline engine daemon |
| `ollama` | 11434 | Local LLM server (GPU accelerated) |

### Watch the Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f jarvis-ws
```

## Step 4: Verify Services Are Running

### Health Check

```bash
# Check API health
curl http://localhost:9742/health

# Expected response:
# {"status": "ok", "service": "jarvis-ws", ...}
```

### Container Status

```bash
docker compose ps
```

You should see all services with `Up` status:

```
NAME               STATUS          PORTS
jarvis-ws          Up (healthy)    0.0.0.0:9742->9742/tcp
jarvis-proxy       Up              0.0.0.0:18800->18800/tcp
jarvis-pipeline    Up              
jarvis-ollama      Up              0.0.0.0:11434->11434/tcp
```

### Test Ollama (if using local LLMs)

```bash
# Pull a model (first time only)
docker exec jarvis-ollama ollama pull qwen3:8b

# Test a prompt
curl http://localhost:11434/api/generate -d '{
  "model": "qwen3:8b",
  "prompt": "Hello, JARVIS!",
  "stream": false
}'
```

## Step 5: Your First Voice Command

JARVIS supports voice commands via the WebSocket API. Here's a quick test:

### Using curl (REST API)

```bash
curl -X POST http://localhost:9742/api/command \
  -H "Content-Type: application/json" \
  -d '{"command": "status", "source": "docker-test"}'
```

### Using WebSocket (wscat)

```bash
# Install wscat if needed: npm install -g wscat
wscat -c ws://localhost:9742/ws

# Send a command
{"type": "command", "data": {"text": "what is the system status?"}}
```

### Using Python

```python
import asyncio
import websockets
import json

async def test_jarvis():
    async with websockets.connect("ws://localhost:9742/ws") as ws:
        # Send a command
        await ws.send(json.dumps({
            "type": "command",
            "data": {"text": "hello jarvis"}
        }))
        
        # Get response
        response = await ws.recv()
        print(json.loads(response))

asyncio.run(test_jarvis())
```

## Common Commands

```bash
# Stop all services
docker compose down

# Restart a specific service
docker compose restart jarvis-ws

# View resource usage
docker stats

# Rebuild after code changes
docker compose build --no-cache
docker compose up -d

# Full cleanup (including volumes)
docker compose down -v
```

## Troubleshooting

### Services Won't Start

```bash
# Check logs for errors
docker compose logs jarvis-ws

# Verify .env file exists and is readable
cat ../../.env
```

### GPU Not Detected

```bash
# Ensure NVIDIA Container Toolkit is installed
sudo apt install nvidia-container-toolkit
sudo systemctl restart docker

# Test GPU access
docker run --rm --gpus all nvidia/cuda:12.8.0-base-ubuntu24.04 nvidia-smi
```

### Port Already in Use

```bash
# Find what's using the port
sudo lsof -i :9742

# Change ports in docker-compose.yml if needed
```

### Connection Refused

```bash
# Verify the service is running
docker compose ps

# Check if firewall is blocking
sudo ufw allow 9742/tcp
```

## Next Steps

- **Explore the API**: Check the [API documentation](./JARVIS_COMPLETE_REFERENCE.md) for all available endpoints
- **Configure LM Studio**: Set up local LLM inference with your GPU cluster
- **Enable Telegram**: Connect the autonomous bot for mobile notifications
- **Run COWORK scripts**: Explore the 435+ automation scripts in `/cowork`

## Alternative: Windows Docker Setup

For Windows with multiple GPUs, use the Windows-specific compose file:

```bash
cd docker
docker compose up -d
```

This starts Open WebUI (port 3000) and GPU monitoring, connecting to LM Studio and Ollama on the host.

---

Need help? Open an issue on [GitHub](https://github.com/Turbo31150/turbo/issues).
