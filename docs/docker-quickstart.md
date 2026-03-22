# Docker Quickstart Guide

Get JARVIS Etoile running with Docker in minutes — no manual dependency installation required.

**Estimated time:** 10–15 minutes  
**Prerequisites:** Docker & Docker Compose installed, NVIDIA GPU with drivers (optional but recommended)

---

## 1. Prerequisites

### Required
- **Docker** (v20.10+) — [Install guide](https://docs.docker.com/get-docker/)
- **Docker Compose** (v2.0+) — Usually included with Docker Desktop

### Optional (for GPU support)
- **NVIDIA GPU** with drivers installed
- **NVIDIA Container Toolkit** — [Installation guide](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)

Verify Docker:
```bash
docker --version
docker compose version
```

---

## 2. Clone the Repository

```bash
git clone https://github.com/Turbo31150/turbo.git
cd turbo
```

---

## 3. Start the Docker Stack

### Start all services
```bash
cd docker
docker compose up -d
```

### Verify services are running
```bash
docker compose ps
```

You should see:
| Service | Status | Port |
|---------|--------|------|
| `jarvis-webui` | Running | `http://localhost:3000` |
| `jarvis-gpu-monitor` | Running | (GPU monitoring) |

---

## 4. Access the Services

### Open WebUI (Main Interface)
Open your browser and navigate to:
```
http://localhost:3000
```

The interface should connect automatically to your local Ollama instance.

### GPU Monitor (Real-time Stats)
To view GPU monitoring output:
```bash
docker logs -f jarvis-gpu-monitor
```

Sample output:
```
=== JARVIS GPU Monitor ===
GPU0: NVIDIA GeForce RTX 3080 | 45C | 23% | 3420/10000 MiB | 85W
GPU1: NVIDIA GeForce RTX 2060 | 52C | 15% | 2048/12000 MiB | 65W
Updated: 14:30:25
```

---

## 5. Configure API Keys

If you're using cloud providers, create a `.env` file in the `docker/` directory:

```bash
cp docker/.env.example docker/.env
```

Edit `docker/.env` with your API keys:
```env
# Gemini API (recommended for 45 models)
GEMINI_API_KEY=your_gemini_api_key_here

# OpenAI (optional)
OPENAI_API_KEY=your_openai_api_key_here
```

Restart services:
```bash
cd docker
docker compose down
docker compose up -d
```

---

## 6. First Voice Command

Once the Electron desktop app is connected (see [INSTALL.md](../INSTALL.md) for full setup), try:

```
"JARVIS, comment ça va?"
```

JARVIS should respond with status, GPU health, and available models.

---

## 7. Troubleshooting

### Services won't start
```bash
# Check Docker logs
docker compose logs -f

# Restart services
docker compose restart
```

### WebUI won't connect to Ollama
- Ensure Ollama is running on your host machine
- Default: `http://host.docker.internal:11434`
- Edit `docker/docker-compose.yml` if your Ollama runs on a different port

### GPU not detected
```bash
# Check NVIDIA runtime is configured
docker run --rm --gpus all nvidia/cuda:12.8.0-base-ubuntu24.04 nvidia-smi
```

If `nvidia-smi` fails inside Docker, install the NVIDIA Container Toolkit:
```bash
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | \
    sudo tee /etc/apt/sources.list.d/nvidia-docker.list
sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart docker
```

### Port already in use
If port `3000` is occupied:
```bash
# Find and kill the process
lsof -ti:3000 | xargs kill -9

# Or change the port in docker-compose.yml
```

---

## 8. Stopping Services

```bash
cd docker
docker compose down        # Stop containers
docker compose down -v    # Stop and remove volumes
```

---

## Quick Reference

| Command | Description |
|---------|-------------|
| `docker compose up -d` | Start all services |
| `docker compose down` | Stop all services |
| `docker compose restart` | Restart all services |
| `docker logs -f jarvis-webui` | View WebUI logs |
| `docker logs -f jarvis-gpu-monitor` | View GPU monitor |

---

**Need more details?** See [INSTALL.md](../INSTALL.md) for full installation instructions, or [DEPLOY.md](../DEPLOY.md) for production deployment.
