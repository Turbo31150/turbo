# JARVIS Etoile v10.2 — Orchestrateur IA Distribue

**Claude = Commandant Pur. Il ne fait JAMAIS le travail lui-meme. Il ORDONNE, VERIFIE et ORCHESTRE.**

```
                         JARVIS ETOILE v10.2
                    Orchestrateur IA Distribue
                  9 GPU | 70 GB VRAM | 4 Noeuds
                 5 Agents | 83 Outils MCP | Voice-First
```

---

## Architecture Globale

```
 UTILISATEUR (voix / clavier / one-shot)
       |
       v
 +---------------------------------------------+
 |            JARVIS COMMANDER                  |
 |       (Claude Agent SDK - Opus/Sonnet)       |
 |                                              |
 |  1. classify_task()  --> M1 qwen3-30b (3ms)  |
 |  2. decompose_task() --> TaskUnit[]           |
 |  3. thermal_check()  --> GPU temp < 85C ?     |
 |  4. enrich_prompt()  --> COMMANDER_PROMPT     |
 +-----+-------+-------+-------+-------+-------+
       |       |       |       |       |
       v       v       v       v       v
  +--------+------+-------+--------+--------+
  |ia-deep |ia-fast|ia-check|ia-trade|ia-sys |  <-- 5 Agents Claude SDK
  | Opus   |Haiku  |Sonnet  |Sonnet  |Haiku  |
  +---+----+--+---+---+----+---+----+---+----+
      |       |       |       |       |
      v       v       v       v       v
  +------+ +------+ +------+ +------+ +----------+
  |  M1  | |  M2  | |  OL1 | |GEMINI| |PowerShell|
  |qwen3 | |deep- | |qwen3 | |proxy | | Windows  |
  | 30b  | |seek  | |1.7b  | | .js  | |  SAPI    |
  |6 GPU | |3 GPU | |local | |cloud | |  83 MCP  |
  |46 GB | |24 GB | |+cloud| |      | |  tools   |
  +------+ +------+ +------+ +------+ +----------+
      |       |       |       |
      +-------+-------+-------+
              |
              v
      SYNTHESE COMMANDANT
      [AGENT/modele] attribution
      Score qualite 0-1
      Re-dispatch si < 0.7
```

---

## Cluster IA — 4 Noeuds

| Noeud | IP | GPU | VRAM | Modele | Role |
|-------|-----|-----|------|--------|------|
| **M1** | 10.5.0.2:1234 | 6 (RTX2060+4xGTX1660S+RTX3080) | 46 GB | qwen3-30b permanent | Analyse, Classification, Deep |
| **M2** | 192.168.1.26:1234 | 3 | 24 GB | deepseek-coder-v2-lite | Code rapide |
| **M3** | 192.168.1.113:1234 | ? | ? | mistral-7b, phi-3.1-mini | Backup, Reasoning |
| **OL1** | 127.0.0.1:11434 | - | 1.4 GB | qwen3:1.7b local | Correction vocale, Cloud |

### Modeles On-Demand M1
- `qwen3-coder-30b` — Code specialise (18.63 GB)
- `devstral-small-2` — Dev tasks (15.21 GB)
- `gpt-oss-20b` — General purpose (12.11 GB)

---

## 5 Agents Claude SDK

| Agent | Modele | Outils | Role |
|-------|--------|--------|------|
| **ia-deep** | Opus | Read, Glob, Grep, WebSearch, WebFetch, lm_query, consensus | Architecte, analyse profonde |
| **ia-fast** | Haiku | Read, Write, Edit, Bash, Glob, Grep, lm_query | Code, execution rapide |
| **ia-check** | Sonnet | Read, Bash, Glob, Grep, lm_query, consensus | Validation, score qualite 0-1 |
| **ia-trading** | Sonnet | Read, Bash, Glob, Grep, run_script, lm_query, consensus, ollama_web_search | Trading MEXC Futures |
| **ia-system** | Haiku | Read, Write, Edit, Bash, Glob, Grep, powershell_run, system_info | Operations Windows |

---

## Mode Commandant — Pipeline

```
ENTREE UTILISATEUR
       |
       v
+------------------+
| classify_task()  |  M1 qwen3-30b (3-45ms)
| 6 types:         |  Fallback: heuristique (0ms)
| code/analyse/    |
| trading/systeme/ |
| web/simple       |
+--------+---------+
         |
         v
+------------------+
| decompose_task() |  Matrice commander_routing (config.py)
| TaskUnit[]       |  + check thermique GPU (nvidia-smi)
| Dependances      |  + re-routage si GPU > 85C
+--------+---------+
         |
         v
+------------------+
| build_enrichment |  Prompt enrichi pour Claude:
| MODE COMMANDANT  |  - Classification
| PLAN DE DISPATCH |  - Sous-taches avec cibles
| ORDRES           |  - Pre-analyse M1 (optionnel)
+--------+---------+
         |
         v
+------------------+
| Claude dispatche |  Via Task (agents) + lm_query (IAs directes)
| EN PARALLELE     |  Max 4 outils MCP simultanes
+--------+---------+
         |
         v
+------------------+
| ia-check valide  |  Score qualite 0.0 - 1.0
| Si < 0.7 :       |  Re-dispatch (max 2 cycles)
+--------+---------+
         |
         v
+------------------+
| SYNTHESE FINALE  |  Attribution [AGENT/modele]
| Vocal ou texte   |  Score global + agents utilises
+------------------+
```

---

## Routage Commander

| Type | Agent | IA | Role |
|------|-------|----|------|
| **code** | ia-fast | M2 | coder |
| **code** | ia-check | M1 | reviewer |
| **analyse** | ia-deep | M1 | analyzer |
| **trading** | ia-trading | M1 | scanner |
| **trading** | - | OL1 | web_data |
| **trading** | ia-check | M1 | validator |
| **systeme** | ia-system | - | executor |
| **web** | - | OL1 | searcher |
| **web** | ia-deep | M1 | synthesizer |
| **simple** | - | M1 | responder |

---

## Seuil Thermique GPU

| Niveau | Temperature | Action |
|--------|------------|--------|
| **Normal** | < 75C | Routage standard |
| **Warning** | 75-84C | Preferer M2 pour code |
| **Critical** | >= 85C | Deporter M1 -> M2/OL1/GEMINI |

Le check thermique est effectue a chaque `decompose_task()` via `nvidia-smi --query-gpu=temperature.gpu`.

---

## 83 Outils MCP (prefixe `mcp__jarvis__`)

### IA & Cluster (4)
`lm_query` `lm_models` `lm_cluster_status` `consensus`

### Model Management (7)
`lm_load_model` `lm_unload_model` `lm_switch_coder` `lm_switch_dev` `lm_gpu_stats` `lm_benchmark` `lm_perf_metrics`

### Ollama (7)
`ollama_query` `ollama_models` `ollama_pull` `ollama_status` `ollama_web_search` `ollama_subagents` `ollama_trading_analysis`

### Scripts (3)
`run_script` `list_scripts` `list_project_paths`

### Windows (47)
Applications (3) | Processus (2) | Fenetres (4) | Clavier/Souris (4) | Clipboard (2) | Fichiers (9) | Audio (3) | Ecran (2) | Systeme (8) | Services (3) | Reseau (3) | Registre (2) | Notifications (3) | Power (3)

### Trading (5)
`trading_pending_signals` `trading_execute_signal` `trading_positions` `trading_status` `trading_close_position`

### Brain (4)
`brain_status` `brain_analyze` `brain_suggest` `brain_learn`

### Skills (5)
`list_skills` `create_skill` `remove_skill` `suggest_actions` `action_history`

---

## Architecture Vocale

```
Micro (WH-1000XM4 BT)
       |
       v
 Whisper (faster-whisper CUDA)
       |
       v
 Correction Pipeline
 (dict local + OL1 qwen3:1.7b)
       |
       v
 Command Match (fuzzy, 438 cmds)
       |
  +----+----+
  |         |
  v         v
MATCH     NO MATCH
(execute)  (Commander Mode)
             |
             v
        M1 pre-analyse
             |
             v
        Claude dispatche
             |
             v
        TTS (Windows SAPI)
```

---

## Modes de Lancement

| Mode | Flag | Launcher | Description |
|------|------|----------|-------------|
| Interactif | `-i` (defaut) | `JARVIS_VOICE.bat` | REPL Commander |
| Commandant | `-c` | `JARVIS_COMMANDER.bat` | Commander explicite |
| Vocal | `-v` | `JARVIS_VOICE.bat` | Push-to-talk CTRL |
| Hybride | `-k` | `JARVIS_KEYBOARD.bat` | Clavier + TTS |
| Ollama | `-o` | `JARVIS_OLLAMA.bat` | Cloud gratuit |
| One-shot | `"prompt"` | - | Requete unique |
| Status | `-s` | `JARVIS_STATUS.bat` | Cluster check |

**TOUS les modes utilisent le COMMANDER_PROMPT par defaut.**

---

## Trading

- **Exchange**: MEXC Futures
- **Levier**: 10x
- **Paires**: BTC ETH SOL SUI PEPE DOGE XRP ADA AVAX LINK
- **TP**: 0.4% | **SL**: 0.25%
- **Taille**: 10 USDT | **Score min**: 70/100

---

## Structure du Projet

```
F:\BUREAU\turbo\
|-- main.py                    # Point d'entree (5 modes)
|-- pyproject.toml             # Dependencies (uv)
|-- gemini-proxy.js            # Proxy Gemini 2.5 Pro/Flash
|-- CLAUDE_MULTI_AGENT.md      # Protocole MAO
|-- src/
|   |-- orchestrator.py        # Moteur principal + COMMANDER_PROMPT
|   |-- commander.py           # Pipeline Commander (classify/decompose/enrich)
|   |-- config.py              # Config cluster + routage + thermal
|   |-- agents.py              # 5 agents Claude SDK
|   |-- tools.py               # 83 outils MCP
|   |-- mcp_server.py          # Serveur MCP stdio
|   |-- commands.py            # 438 commandes vocales
|   |-- skills.py              # 86+ skills dynamiques
|   |-- voice.py               # Whisper STT + SAPI TTS
|   |-- voice_correction.py    # Pipeline correction vocale
|   |-- cluster_startup.py     # Boot cluster + thermal monitoring
|   |-- trading.py             # Trading MEXC
|   |-- brain.py               # Auto-apprentissage
|   |-- executor.py            # Execution commandes/skills
|   |-- windows.py             # API Windows (PowerShell, COM)
|   |-- database.py            # SQLite persistence
|   |-- scenarios.py           # 79+ scenarios validation
|   |-- output.py              # Schema sortie
|   |-- whisper_worker.py      # Worker Whisper persistent
|   |-- dashboard.py           # API dashboard
|   |-- systray.py             # System tray icon
|-- dashboard/
|   |-- server.py              # Serveur HTTP dashboard (stdlib)
|   |-- index.html             # UI dashboard
|-- data/
|   |-- jarvis.db              # Base SQLite principale
|   |-- skills.json            # Skills persistantes
|   |-- brain_state.json       # Etat brain
|   |-- jarvis_m1_prompt.txt   # Prompt compact M1
|-- launchers/                 # 14 fichiers .bat
|-- finetuning/                # Pipeline QLoRA (Qwen3-30B)
|-- scripts/                   # Scripts startup M1/M2
```

---

## Benchmark (2026-02-18)

| Metrique | Valeur |
|----------|--------|
| Classification | 24/24 correct, 5ms avg |
| Pipeline complet | 150ms avg |
| M1 inference | 1.3-17.6s |
| M2 inference | 1.1-7.2s |
| Parallele M1+M2+OL1 | 2.2s (vs 3.7s seq, +40%) |
| GPU | 6 GPU, 57% VRAM, 39C max |
| Thermal | Normal |

---

## Installation

```bash
# Prerequis: uv, Python 3.13, CUDA, LM Studio
cd F:\BUREAU\turbo
uv sync

# Lancer
uv run python main.py        # Interactif (Commander par defaut)
uv run python main.py -v     # Mode vocal
uv run python main.py -c     # Commander explicite
```

---

## Licence

Projet prive — Turbo31150
