# JARVIS Turbo v12.4 — Project Instructions

## Langue
Toujours repondre en francais. Code en anglais, commentaires en francais si pertinent.

## Architecture
- **SDK**: Claude Agent SDK Python v0.1.35 | **Runtime**: uv v0.10.2 + Python 3.13
- **Cluster**: 4 noeuds IA (M1/M1B/M2/M3) + cloud (gpt-oss/devstral/glm/minimax) | 10 GPU, 78 GB VRAM
- **Modules**: 246 dans `src/` (93K lignes) | **Outils MCP**: 609 handlers | **REST**: 517 endpoints
- **Canvas**: `canvas/` — UI standalone port 18800 avec autolearn engine
- **COWORK**: 409 scripts dans `cowork/dev/` | Pipeline autonome
- **OpenClaw**: 40 agents + 56 dynamic | 11 crons | Gateway port 18789
- **Tests**: 2,241 fonctions (77 fichiers) | Couverture src: 85.5%
- **Electron**: 29 pages | **Launchers**: 35 | **n8n**: 63 workflows
- **DBs**: 63 bases (160 MB total) | etoile.db (42 tables, 13.5K rows)

## Conventions Code
- Python: type hints, async/await, f-strings, dataclasses
- Imports: `from __future__ import annotations` en premier
- Node.js (canvas): CommonJS require, pas d'ESM
- Nommage: snake_case Python, camelCase JS
- Tests: `uv run pytest` — fichiers `test_*.py`

## Fichiers critiques (ne pas casser)
- `src/config.py` — Noeuds cluster, routage, chemins projets
- `src/tools.py` — Outils MCP (pool httpx partagee)
- `src/mcp_server.py` — 602 handlers (6282 lignes)
- `src/commands.py` — Commandes vocales
- `src/commander.py` — Classification/decomposition taches
- `canvas/direct-proxy.js` — Proxy HTTP cluster + autolearn

## Cluster — Acces rapide
| Noeud | URL | Modele | Role | Score |
|-------|-----|--------|------|-------|
| M1 | 127.0.0.1:1234 / 10.5.0.2:1234 | qwen3-8b | CHAMPION LOCAL (46tok/s) | 98.4/100 |
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

## Scripts utiles
```bash
uv run python scripts/system_audit.py --quick          # Audit rapide
uv run python scripts/trading_v2/gpu_pipeline.py --quick --json  # Trading scan
node canvas/direct-proxy.js                             # Canvas proxy
python cowork/dev/autonomous_cluster_pipeline.py        # Pipeline autonome
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
