# Installation JARVIS Turbo v10.1

## Prerequis

- Windows 10/11
- Python 3.13+
- uv (package manager): `pip install uv`
- Git
- LM Studio (sur les 3 machines du cluster)
- n8n (optionnel, pour les workflows automatises)

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
LM_STUDIO_1_URL=http://localhost:1234
LM_STUDIO_2_URL=http://192.168.1.26:1234
LM_STUDIO_3_URL=http://192.168.1.113:1234
LM_STUDIO_DEFAULT_MODEL=qwen/qwen3-30b-a3b-2507

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

## Import Workflows n8n

1. Ouvrir n8n sur http://localhost:5678
2. Aller dans Settings > Import
3. Importer chaque fichier JSON depuis `n8n_workflows/`

## Structure

```
turbo/
├── src/                  # Code source (17 fichiers)
├── data/                 # Skills JSON + historique
├── n8n_workflows/        # 6 workflows n8n
├── docs/                 # Documentation
├── jarvis.bat            # Lanceurs
├── pyproject.toml        # Dependances
└── .env                  # Configuration (a creer)
```
