# JARVIS Turbo v10.3 — Project Instructions

## Langue
Toujours repondre en francais. Code en anglais, commentaires en francais si pertinent.

## Architecture
- **SDK**: Claude Agent SDK Python v0.1.35 | **Runtime**: uv + Python 3.13
- **Cluster**: 6 noeuds IA (M1/M2/M3/OL1/GEMINI/CLAUDE) | 10 GPU, 78 GB VRAM
- **Modules**: 28 dans `src/` | **Outils MCP**: 75 SDK + 88 standalone
- **Canvas**: `canvas/` — UI standalone port 18800 avec autolearn engine

## Conventions Code
- Python: type hints, async/await, f-strings, dataclasses
- Imports: `from __future__ import annotations` en premier
- Node.js (canvas): CommonJS require, pas d'ESM
- Nommage: snake_case Python, camelCase JS
- Tests: `uv run pytest` — fichiers `test_*.py`

## Fichiers critiques (ne pas casser)
- `src/config.py` — Noeuds cluster, routage, chemins projets
- `src/tools.py` — 75 outils MCP (pool httpx partagee)
- `src/commands.py` — 1719 commandes vocales
- `src/commander.py` — Classification/decomposition taches
- `canvas/direct-proxy.js` — Proxy HTTP cluster + autolearn

## Cluster — Acces rapide
| Noeud | URL | Modele | Role |
|-------|-----|--------|------|
| OL1 | 127.0.0.1:11434 | qwen3:1.7b | Rapide (0.5s) |
| M2 | 192.168.1.26:1234 | deepseek-coder | Champion code (1.3s) |
| M3 | 192.168.1.113:1234 | mistral-7b | Solide general (2.5s) |
| M1 | 10.5.0.2:1234 | qwen3-8b | Fast primary (0.6-2.5s) |

## Regles
- JAMAIS `localhost` → toujours `127.0.0.1` (IPv6 lag Windows)
- Ollama cloud: `think:false` OBLIGATOIRE
- M1: qwen3-8b fast (0.6-2.5s), qwen3-30b dual pour deep tasks
- LM Studio API: `/v1/chat/completions` (messages) avec fallback `/api/v1/chat` (responses)
- GPU: warning 75C, critical 85C → re-routage cascade
- Ne pas committer: `data/*.db`, `.env`, credentials, `node_modules/`

## Scripts utiles
```bash
uv run python scripts/system_audit.py --quick    # Audit rapide
uv run python scripts/trading_v2/gpu_pipeline.py --quick --json  # Trading scan
node canvas/direct-proxy.js                       # Canvas proxy
```

## Slash commands disponibles (plugin jarvis-turbo, 19 commandes)
`/cluster-check` `/mao-check` `/gpu-status` `/thermal` `/heal-cluster` `/m2-optimize`
`/consensus` `/quick-ask` `/web-search` `/test-cluster`
`/trading-scan` `/trading-feedback` `/canvas-status` `/canvas-restart`
`/audit` `/model-swap` `/deploy` `/n8n-trigger` `/backup-db`

## Troubleshooting rapide

| Symptome | Diagnostic | Fix |
|----------|-----------|-----|
| M2 TIMEOUT | GPT-OSS 20B charge en plus → VRAM saturee | `/m2-optimize` decharge les modeles secondaires |
| OL1 OFFLINE | `curl 127.0.0.1:11434/api/tags` → refuse | `ollama serve` restart |
| Canvas crash | port 18800 refuse | `node canvas/direct-proxy.js` restart |
| GPU >75C | `nvidia-smi` | `/thermal` pour diagnostic, decharger modeles |
| M3 echoue math | mistral-7b mauvais en calcul | Router math vers OL1 ou M2 |

## Autotest cluster
```bash
python3 C:/Users/franc/jarvis_autotest.py 10 8  # 10 cycles x 8 taches
```
Resultats: `C:/Users/franc/jarvis_autotest_results.json`
Benchmark 2026-02-25: OL1 83%, M3 75%, M2 33% (VRAM saturee par GPT-OSS)
