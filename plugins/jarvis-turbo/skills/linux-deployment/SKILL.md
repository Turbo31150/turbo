---
name: Linux Deployment
description: Use when deploying, managing, or troubleshooting JARVIS on Linux. Covers install.sh, docker-compose, systemd services, jarvis-ctl.sh, and learned actions management.
---

# JARVIS Linux Deployment

## Quick Deploy

### Bare-metal (recommended)
```bash
cd ~/jarvis/projects/linux
chmod +x install.sh jarvis-ctl.sh
./install.sh
```

### Docker
```bash
cd ~/jarvis/projects/linux
docker compose up -d
```

## jarvis-ctl.sh — CLI de contrôle

| Commande | Action |
|----------|--------|
| `./jarvis-ctl.sh start` | Démarre tous les services |
| `./jarvis-ctl.sh stop` | Arrête tous les services |
| `./jarvis-ctl.sh restart` | Redémarre tout |
| `./jarvis-ctl.sh status` | État des services |
| `./jarvis-ctl.sh logs` | Logs récents |
| `./jarvis-ctl.sh health` | Health check cluster |
| `./jarvis-ctl.sh seed` | Seed learned_actions.db |
| `./jarvis-ctl.sh timers` | État des timers systemd |
| `./jarvis-ctl.sh dominos` | Liste des dominos disponibles |

## Services systemd

| Service | Port | Commande |
|---------|------|----------|
| jarvis-ws | 9742 | `systemctl --user {start\|stop\|status} jarvis-ws` |
| jarvis-proxy | 18800 | `systemctl --user {start\|stop\|status} jarvis-proxy` |
| jarvis-openclaw | 18789 | `systemctl --user {start\|stop\|status} jarvis-openclaw` |
| jarvis-pipeline | — | `systemctl --user {start\|stop\|status} jarvis-pipeline` |

## Timers (cron equivalents)

Générer: `uv run python scripts/generate_systemd_timers.py`
Activer: `systemctl --user enable --now jarvis-health.timer`
Vérifier: `systemctl --user list-timers`

## Learned Actions — Commandes vocales

41 dominos disponibles en langage conversationnel. Exemples:
- "santé système" → nvidia-smi + systemctl + df + free
- "état du cluster" → curl les 4 noeuds
- "routine du matin" → check complet système + cluster + GPU + git + trading
- "redémarre {service}" → systemctl restart (paramétrisé)

Seed: `uv run python scripts/seed_learned_actions.py`

## Platform Dispatch

`src/platform_dispatch.py` — dispatch automatique Linux/Windows:
```python
from src.platform_dispatch import get_platform_module
display = get_platform_module("display")  # → linux_display ou win_display
display.get_resolution()
```

21 modules Linux disponibles. Modules manquants retournent un stub NotImplementedError.

## Troubleshooting

| Problème | Fix |
|----------|-----|
| Services ne persistent pas après reboot | `loginctl enable-linger $USER` |
| Port 18800 occupé | `ss -tlnp \| grep 18800` puis `kill` |
| Ollama offline | `systemctl restart ollama` ou `ollama serve` |
| GPU non détecté | `nvidia-smi` — installer nvidia-driver si absent |
| Docker permission denied | `sudo usermod -aG docker $USER` puis relogin |
| Learned actions vide | `uv run python scripts/seed_learned_actions.py` |
