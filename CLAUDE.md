# JARVIS Turbo v12.4 — Project Instructions

## Langue
Toujours repondre en francais. Code en anglais, commentaires en francais si pertinent.

## Architecture
- **SDK**: Claude Agent SDK Python v0.1.35 | **Runtime**: uv v0.10.2 + Python 3.13
- **Plateformes**: Windows (natif) + Linux (natif) — dispatch via `src/platform_dispatch.py`
- **Cluster**: 4 noeuds IA (M1/M1B/M2/M3) + cloud (gpt-oss/devstral/glm/minimax) | 10 GPU, 78 GB VRAM
- **Modules**: 246 dans `src/` (93K lignes) dont 21 modules `linux_*.py` | **Outils MCP**: 613 handlers | **REST**: 517 endpoints
- **Canvas**: `canvas/` — UI standalone port 18800 avec autolearn engine
- **COWORK**: 409 scripts dans `cowork/dev/` | Pipeline autonome
- **OpenClaw**: 40 agents + 56 dynamic | 11 crons | Gateway port 18789
- **Learned Actions**: 41 dominos conversationnels dans `data/learned_actions.db` (5 categories)
- **Tests**: 2,281 fonctions (77+ fichiers) dont 40 tests Linux | Couverture src: 85.5%
- **Electron**: 29 pages | **Launchers**: 35 | **n8n**: 63 workflows
- **DBs**: 64 bases (160 MB total) | etoile.db (42 tables, 13.5K rows) | learned_actions.db
- **Deploy Linux**: `projects/linux/` (install.sh + docker-compose.yml + jarvis-ctl.sh)

## Conventions Code
- Python: type hints, async/await, f-strings, dataclasses
- Imports: `from __future__ import annotations` en premier
- Node.js (canvas): CommonJS require, pas d'ESM
- Nommage: snake_case Python, camelCase JS
- Tests: `uv run pytest` — fichiers `test_*.py`

## Fichiers critiques (ne pas casser)
- `src/config.py` — Noeuds cluster, routage, chemins projets
- `src/tools.py` — Outils MCP (pool httpx partagee)
- `src/mcp_server.py` — 613 handlers (6400+ lignes)
- `src/commands.py` — Commandes vocales
- `src/commander.py` — Classification/decomposition taches
- `src/platform_dispatch.py` — Dispatch auto linux_*/win_* avec stub fallback
- `src/learned_actions.py` — Moteur dominos conversationnels (match fuzzy + replay)
- `canvas/direct-proxy.js` — Proxy HTTP cluster + autolearn

## Modules Linux (`src/linux_*.py` — 21 modules)
| Module | Domaine |
|--------|---------|
| `linux_sys.py` | Infos systeme (uname, uptime, memoire) |
| `linux_services.py` | Gestion systemd (start/stop/status) |
| `linux_network.py` | Interfaces reseau, IP, routes |
| `linux_packages.py` / `linux_package_manager.py` | APT/DNF, packages installes |
| `linux_display.py` / `linux_screen.py` | Xrandr, resolution, screenshots |
| `linux_desktop_control.py` | xdotool, controle fenêtres |
| `linux_hotkey_daemon.py` | Raccourcis clavier globaux |
| `linux_power_manager.py` | Suspend, hibernate, shutdown |
| `linux_security_status.py` | UFW, fail2ban, audit |
| `linux_journal_reader.py` | Journalctl, logs systeme |
| `linux_maintenance.py` | Nettoyage, apt autoremove |
| `linux_startup.py` | Autostart XDG, systemd user |
| `linux_update_manager.py` | Mises a jour systeme |
| `linux_swap_manager.py` | Swap, zram config |
| `linux_workspace_manager.py` | Bureaux virtuels |
| `linux_snapshot_manager.py` | Snapshots btrfs/timeshift |
| `linux_config_manager.py` | Fichiers config (/etc) |
| `linux_share_manager.py` | Samba, NFS shares |
| `linux_trash_manager.py` | Corbeille freedesktop |

**Platform dispatch** (`src/platform_dispatch.py`): `get_platform_module("services")` retourne `src.linux_services` sur Linux, `src.win_service_monitor` sur Windows. Si le module n'existe pas, un `_NotImplementedStub` est retourne.

## Learned Actions (Dominos Conversationnels)
- **DB**: `data/learned_actions.db` — 41 dominos
- **Categories**: `system`, `cluster`, `dev`, `trading`, `voice`
- **Moteur**: `src/learned_actions.py` — match fuzzy (SequenceMatcher + Jaccard, seuil 0.75)
- **Auto-learn**: les pipelines reussis sont sauvegardes automatiquement
- **Triggers parametres**: chaque domino a des triggers textuels + contexte requis
- **MCP handlers** (4): `learned_action_list`, `learned_action_match`, `learned_action_save`, `learned_action_stats`
- **Voice corrections**: 73 regles STT specifiques Linux dans les commandes vocales

## Cluster — Acces rapide
| Noeud | URL | Modele | Role | Score |
|-------|-----|--------|------|-------|
| M1 | 127.0.0.1:1234 | qwen3-8b | CHAMPION LOCAL (46tok/s) | 98.4/100 |
| M1B | 127.0.0.1:1234 | gpt-oss-20b | Deep local (9s, ctx25k) | — |
| M2 | 192.168.1.26:1234 | deepseek-r1-0528-qwen3-8b | Reasoning (44tok/s) | — |
| M3 | 192.168.1.113:1234 | deepseek-r1-0528-qwen3-8b | Reasoning fallback | — |
| OL1 cloud | 127.0.0.1:11434 | gpt-oss:120b-cloud | CHAMPION CLOUD (51tok/s) | 100/100 |
| OL1 cloud | 127.0.0.1:11434 | devstral-2:123b-cloud | Code cloud #2 | 94/100 |
| OL1 local | 127.0.0.1:11434 | qwen3:1.7b | Ultra-rapide (84tok/s) | — |

## Regles
- JAMAIS `localhost` → toujours `127.0.0.1` (IPv6 lag Windows)
- Ollama cloud: `think:false` OBLIGATOIRE
- M1: `/nothink` prefix OBLIGATOIRE pour qwen3/gpt-oss (pas deepseek-r1)
- M2/M3: max_output_tokens=2048 minimum (reasoning needs space)
- LM Studio API: `/api/v1/chat` (Responses API) — output[].content
- GPU: warning 75C, critical 85C → re-routage cascade
- Ne pas committer: `data/*.db`, `.env`, credentials, `node_modules/`

## Deploy Linux (`projects/linux/`)
```bash
# Installation complete
cd projects/linux && bash install.sh       # Installe deps, venv, systemd services

# Docker Compose (alternative)
cd projects/linux && docker compose up -d  # MCP server + Canvas + Pipeline

# Controle
bash projects/linux/jarvis-ctl.sh status   # Status tous services
bash projects/linux/jarvis-ctl.sh start     # Demarrer JARVIS
bash projects/linux/jarvis-ctl.sh stop      # Arreter JARVIS
```

### Systemd Timers (5 timers user)
Generes par `scripts/generate_systemd_timers.py` :
| Timer | Frequence | Action |
|-------|-----------|--------|
| `jarvis-health` | 15 min | Cluster health check |
| `jarvis-backup` | Quotidien | Backup bases SQLite |
| `jarvis-thermal` | 5 min | Monitoring GPU temperature |
| `jarvis-log-rotate` | Hebdomadaire | Rotation logs + reports |
| `jarvis-pipeline-check` | 10 min | Watchdog pipeline service |

```bash
# Generer et installer les timers
uv run python scripts/generate_systemd_timers.py
systemctl --user daemon-reload
systemctl --user enable --now jarvis-health.timer
```

## Scripts utiles
```bash
uv run python scripts/system_audit.py --quick          # Audit rapide
uv run python scripts/trading_v2/gpu_pipeline.py --quick --json  # Trading scan
node canvas/direct-proxy.js                             # Canvas proxy
python cowork/dev/autonomous_cluster_pipeline.py        # Pipeline autonome
uv run python scripts/generate_systemd_timers.py        # Generer timers systemd
bash projects/linux/jarvis-ctl.sh status                # Status Linux services
```

## Slash commands (plugin jarvis-turbo, 43 commandes)
`/cluster-check` `/mao-check` `/gpu-status` `/thermal` `/heal-cluster`
`/consensus` `/quick-ask` `/web-search` `/trading-scan` `/trading-feedback`
`/canvas-status` `/canvas-restart` `/audit` `/model-swap` `/deploy`

## Troubleshooting rapide
| Symptome | Fix |
|----------|-----|
| M2/M3 TIMEOUT | max_output_tokens trop bas pour deepseek-r1, minimum 2048 |
| OL1 OFFLINE | `ollama serve` restart |
| Canvas crash | `node canvas/direct-proxy.js` restart (port 18800) |
| GPU >75C | `/thermal`, decharger modeles |
| Context exceeded | Reduire prompt ou max_output_tokens |
| OpenClaw cron spam | Verifier jobs.json, max 11 crons actifs |

### Troubleshooting Linux
| Symptome | Fix |
|----------|-----|
| systemd timer inactif | `systemctl --user enable --now jarvis-health.timer` |
| `linux_*.py` ImportError | Verifier deps: `apt install xdotool xrandr` |
| platform_dispatch stub | Module pas porte — creer `src/linux_<domain>.py` |
| Docker compose fail | `docker compose logs jarvis-mcp` pour diagnostiquer |
| Permissions journalctl | Ajouter user au groupe `systemd-journal` |
| GPU non detecte Linux | Installer `nvidia-driver-xxx` + `nvidia-smi` fonctionnel |
| xdotool echoue | Verifier `$DISPLAY` ou `$WAYLAND_DISPLAY` est set |
