# Installation JARVIS Turbo v12.4

## Prerequis

- Windows 10/11
- Python 3.13+ (uv v0.10.2 comme package manager)
- Claude Agent SDK v0.1.35
- Git
- LM Studio (sur les 3 machines du cluster)
- Electron 33 + React 19 + Vite 6 (pour le Desktop)
- CUDA (requis pour Whisper large-v3-turbo, pipeline vocal)
- Ollama v0.17.4 (12 modeles: 2 local + 10 cloud)
- n8n v2.4.8 (optionnel, pour les 63 workflows automatises)

## Installation

```bash
git clone https://github.com/Turbo31150/turbo.git
cd turbo
uv sync
```

## Configuration

Creer un fichier `.env` a la racine:

```env
# LM Studio Cluster
LM_STUDIO_1_URL=http://127.0.0.1:1234    # M1: 6 GPU 46GB, qwen3-8b (+ gpt-oss-20b deep)
LM_STUDIO_2_URL=http://192.168.1.26:1234  # M2: 3 GPU 24GB, deepseek-r1-0528-qwen3-8b
LM_STUDIO_3_URL=http://192.168.1.113:1234 # M3: 1 GPU 8GB, deepseek-r1-0528-qwen3-8b
LM_STUDIO_DEFAULT_MODEL=qwen3-8b

# Ollama (local + cloud)
OLLAMA_URL=http://127.0.0.1:11434
OLLAMA_NUM_PARALLEL=3

# Trading MEXC (optionnel)
MEXC_API_KEY=your_key
MEXC_SECRET_KEY=your_secret
DRY_RUN=true

# Telegram (optionnel)
TELEGRAM_TOKEN=your_token
TELEGRAM_CHAT=your_chat_id
```

## Lancement

| Commande | Description |
|----------|-------------|
| `jarvis.bat` | Dashboard TUI + Systray |
| `jarvis_dashboard.bat` | Dashboard seul |
| `jarvis_systray.bat` | Systray seul |
| `jarvis_interactive.bat` | Mode interactif CLI |
| `jarvis_hybrid.bat` | Voix + texte |
| `jarvis_voice.bat` | Mode vocal |

## Ports utilises

| Port | Service |
|------|---------|
| 1234 | LM Studio (M1/M2/M3) |
| 5678 | n8n (workflows) |
| 8080 | Dashboard JARVIS |
| 9742 | Python WebSocket (FastAPI) |
| 11434 | Ollama (local + cloud) |
| 18789 | OpenClaw |
| 18800 | Direct Proxy |

## Import Workflows n8n

1. Ouvrir n8n sur http://127.0.0.1:5678
2. Aller dans Settings > Import
3. Importer chaque fichier JSON depuis `n8n_workflows/`

## Structure

```
turbo/
├── src/                  # Code source (246 modules)
├── cowork/               # 409 scripts autonomes
├── data/                 # Skills JSON + historique
├── n8n_workflows/        # 63 workflows n8n
├── docs/                 # Documentation
├── jarvis.bat            # Lanceurs
├── pyproject.toml        # Dependances
└── .env                  # Configuration (a creer)
```
