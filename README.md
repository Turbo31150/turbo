# JARVIS Etoile v10.2 — Orchestrateur IA Distribue

**Repo prive — Turbo31150**

**Claude = Commandant Pur. Il ne fait JAMAIS le travail lui-meme. Il ORDONNE, VERIFIE et ORCHESTRE.**

```
                    ╔═══════════════════════════════════════╗
                    ║       JARVIS ETOILE v10.2             ║
                    ║   Orchestrateur IA Multi-GPU Distribue║
                    ║   9 GPU | 70 GB VRAM | 4 Noeuds IA   ║
                    ║   5 Agents | 83 Outils MCP | Voice    ║
                    ╚═══════════════════════════════════════╝
```

---

## Table des Matieres

1. [Architecture Globale](#architecture-globale)
2. [Cluster IA — Noeuds & Cles](#cluster-ia--noeuds--cles)
3. [Pipeline Commander](#pipeline-commander--workflow-complet)
4. [5 Agents Claude SDK](#5-agents-claude-sdk)
5. [Routage Commander](#routage-commander)
6. [Seuil Thermique GPU](#seuil-thermique-gpu)
7. [83 Outils MCP](#83-outils-mcp)
8. [n8n Workflow Etoile](#n8n-workflow-etoile)
9. [Architecture Vocale](#architecture-vocale)
10. [Trading MEXC](#trading-mexc-futures)
11. [Modes de Lancement](#modes-de-lancement)
12. [Structure du Projet](#structure-du-projet)
13. [Bases de Donnees](#bases-de-donnees)
14. [Installation & Configuration](#installation--configuration)
15. [Benchmark](#benchmark)
16. [Appels API — Exemples Complets](#appels-api--exemples-complets)

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
 |  1. classify_task()  --> M1 qwen3-30b (5ms)  |
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

## Cluster IA — Noeuds & Cles

### M1 — Analyse Profonde (6 GPU, 46 GB VRAM)

| Parametre | Valeur |
|-----------|--------|
| **IP** | `http://10.5.0.2:1234` |
| **API Key** | `LMSTUDIO_KEY_M1_REDACTED` |
| **GPU** | RTX 2060 + 4x GTX 1660 Super + RTX 3080 |
| **VRAM** | 46 GB total |
| **CUDA_VISIBLE_DEVICES** | `5,0,1,2,3,4` |
| **Modele permanent** | `qwen/qwen3-30b-a3b-2507` |
| **Role** | Classification, analyse profonde, raisonnement |

**Modeles on-demand M1 :**
| Modele | VRAM | Usage |
|--------|------|-------|
| `qwen3-coder-30b` | 18.63 GB | Code specialise |
| `devstral-small-2` | 15.21 GB | Dev tasks |
| `gpt-oss-20b` | 12.11 GB | General purpose |

**Blacklist M1** (gaspillent VRAM) : `nemotron-3-nano`, `glm-4.7-flash`

**Appel M1 (API native v1) :**
```bash
curl -s http://10.5.0.2:1234/api/v1/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer LMSTUDIO_KEY_M1_REDACTED" \
  -d '{
    "model": "qwen/qwen3-30b-a3b-2507",
    "input": "VOTRE PROMPT",
    "temperature": 0.4,
    "max_output_tokens": 8192,
    "stream": false,
    "store": false
  }'
# Reponse: {"output":[{"content":"..."}], "stats":{"total_output_tokens":...}}
```

### M2 — Code Rapide (3 GPU, 24 GB VRAM)

| Parametre | Valeur |
|-----------|--------|
| **IP** | `http://192.168.1.26:1234` |
| **API Key** | `LMSTUDIO_KEY_M2_REDACTED` |
| **GPU** | 3 GPU |
| **VRAM** | 24 GB total |
| **Modele** | `deepseek-coder-v2-lite-instruct` |
| **Role** | Generation code rapide |

**Appel M2 (API native v1) :**
```bash
curl -s http://192.168.1.26:1234/api/v1/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer LMSTUDIO_KEY_M2_REDACTED" \
  -d '{
    "model": "deepseek-coder-v2-lite-instruct",
    "input": "VOTRE PROMPT",
    "temperature": 0.3,
    "max_output_tokens": 8192,
    "stream": false,
    "store": false
  }'
# Reponse: {"output":[{"content":"..."}], "stats":{"total_output_tokens":...}}
```

### M3 — Backup (ONLINE)

| Parametre | Valeur |
|-----------|--------|
| **IP** | `http://192.168.1.113:1234` |
| **Modeles** | mistral-7b, phi-3.1-mini |
| **Role** | Backup, reasoning leger |

### OL1 — Ollama Local + Cloud

| Parametre | Valeur |
|-----------|--------|
| **IP** | `http://127.0.0.1:11434` |
| **Version** | Ollama v0.16.1 |
| **Local** | `qwen3:1.7b` (1.36 GB) |
| **Cloud** | minimax-m2.5, glm-5, kimi-k2.5 |
| **Role** | Correction vocale, recherche web, taches legeres |

**IMPORTANT** : `"think": false` OBLIGATOIRE pour les modeles cloud.

**Appel OL1 local :**
```bash
curl -s http://127.0.0.1:11434/api/chat -d '{
  "model": "qwen3:1.7b",
  "messages": [{"role": "user", "content": "VOTRE PROMPT"}],
  "stream": false
}'
```

**Appel OL1 cloud (minimax) :**
```bash
curl -s http://127.0.0.1:11434/api/chat -d '{
  "model": "minimax-m2.5:cloud",
  "messages": [{"role": "user", "content": "VOTRE PROMPT"}],
  "stream": false,
  "think": false
}'
```

### GEMINI — Architecture & Vision (Cloud)

| Parametre | Valeur |
|-----------|--------|
| **Proxy** | `node F:/BUREAU/turbo/gemini-proxy.js` |
| **Modeles** | Gemini 2.5 Pro / Flash |
| **Timeout** | 2 minutes |
| **Fallback** | Pro -> Flash auto |

**Appel Gemini :**
```bash
node F:/BUREAU/turbo/gemini-proxy.js "VOTRE PROMPT"
node F:/BUREAU/turbo/gemini-proxy.js --json "VOTRE PROMPT"
```

### LM Studio CLI

```
C:\Users\franc\.lmstudio\bin\lms.exe
```

**Commandes utiles :**
```bash
lms status          # Status serveur
lms ls              # Modeles charges
lms load qwen/qwen3-30b-a3b-2507 --gpu max
lms unload --all
```

### Health Check Cluster

```bash
# M1 (API native v1)
curl -s --max-time 3 http://10.5.0.2:1234/api/v1/models \
  -H "Authorization: Bearer LMSTUDIO_KEY_M1_REDACTED" \
  | python -c "import sys,json;d=json.load(sys.stdin);print('M1 OK:',len([m for m in d.get('models',[]) if m.get('loaded_instances')]),'modeles charges')"

# M2 (API native v1)
curl -s --max-time 3 http://192.168.1.26:1234/api/v1/models \
  -H "Authorization: Bearer LMSTUDIO_KEY_M2_REDACTED" \
  | python -c "import sys,json;d=json.load(sys.stdin);print('M2 OK:',len([m for m in d.get('models',[]) if m.get('loaded_instances')]),'modeles charges')"

# OL1 (Ollama)
curl -s --max-time 3 http://127.0.0.1:11434/api/tags \
  | python -c "import sys,json;print('OL1 OK:',len(json.load(sys.stdin).get('models',[])),'modeles')"
```

---

## Pipeline Commander — Workflow Complet

Le mode Commandant est **PERMANENT** sur tous les modes (interactif, vocal, hybride, one-shot).

```
ENTREE UTILISATEUR (voix / clavier / one-shot)
       |
       v
+------------------+
| classify_task()  |  M1 qwen3-30b (5ms avg)
| 6 categories:    |  Fallback: heuristique (0ms)
| code / analyse / |
| trading / systeme|
| web / simple     |
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

### Classification Heuristique (24/24 correct)

Priorite: `code-override > web-override > trading > systeme > analyse > code > web > simple`

- **code-override** : debug, segfault, bug, fix, patch, refactor
- **web-override** : actualite, news, dernieres nouvelles
- **trading** : trading, signal, mexc, breakout, btc, eth, sol (word-boundary)
- **systeme** : ouvre, ferme, fichier, powershell, windows, service (word-boundary)
- **analyse** : analyse, architecture, strategie, benchmark, audit
- **code** : code, fonction, python, script, api, react, flask
- **web** : cherche, recherche, google, documentation
- **simple** : tout le reste

### TaskUnit (Data Structure)

```python
@dataclass
class TaskUnit:
    id: str               # t1, t2, t3...
    prompt: str           # Prompt adapte au role
    task_type: str        # code/analyse/trading/systeme/web/simple
    target: str           # ia-deep/ia-fast/ia-check/ia-trading/ia-system/M1/M2/OL1/GEMINI
    priority: int = 1     # 1=haute, 3=basse
    depends_on: list[str] # IDs des taches prealables
    result: str | None    # Resultat de l'agent/IA
    status: str           # pending/running/done/failed
    quality_score: float  # 0.0 - 1.0
```

---

## 5 Agents Claude SDK

Definis dans `src/agents.py`, utilisant le Claude Agent SDK Python v0.1.35.

### ia-deep (Opus) — Architecte

| Parametre | Valeur |
|-----------|--------|
| **Modele** | Claude Opus |
| **Role** | Analyse profonde, architecture, strategie, logs |
| **Outils** | Read, Glob, Grep, WebSearch, WebFetch, lm_query, consensus |
| **Prompt** | "Analyser les problemes en profondeur... Utilise M1 pour enrichir..." |

### ia-fast (Haiku) — Ingenieur Code

| Parametre | Valeur |
|-----------|--------|
| **Modele** | Claude Haiku |
| **Role** | Code rapide, edits, execution |
| **Outils** | Read, Write, Edit, Bash, Glob, Grep, lm_query |
| **Prompt** | "Ecrire du code rapidement... Utilise M2 via lm_query..." |

### ia-check (Sonnet) — Validateur

| Parametre | Valeur |
|-----------|--------|
| **Modele** | Claude Sonnet |
| **Role** | Review, validation, score qualite 0-1 |
| **Outils** | Read, Bash, Glob, Grep, lm_query, consensus |
| **Prompt** | "Reviewer et valider... TOUJOURS produire un score 0.0-1.0..." |

### ia-trading (Sonnet) — Trading MEXC

| Parametre | Valeur |
|-----------|--------|
| **Modele** | Claude Sonnet |
| **Role** | Scanner marche, breakout, signaux, positions |
| **Outils** | Read, Bash, Glob, Grep, run_script, lm_query, consensus, ollama_web_search |
| **Prompt** | "Scanner MEXC Futures... Paires: BTC ETH SOL SUI PEPE DOGE XRP ADA AVAX LINK..." |

### ia-system (Haiku) — Systeme Windows

| Parametre | Valeur |
|-----------|--------|
| **Modele** | Claude Haiku |
| **Role** | Fichiers, registre, processus, PowerShell |
| **Outils** | Read, Write, Edit, Bash, Glob, Grep, powershell_run, system_info |
| **Prompt** | "Acces complet au systeme Windows... C:\\Users\\franc, F:\\BUREAU..." |

---

## Routage Commander

Matrice definie dans `config.py` → `commander_routing` :

| Type | Agent | IA Cible | Role | Priorite |
|------|-------|----------|------|----------|
| **code** | ia-fast | M2 (deepseek) | coder | 1 (haute) |
| **code** | ia-check | M1 (qwen3) | reviewer | 2 (depends) |
| **analyse** | ia-deep | M1 (qwen3) | analyzer | 1 |
| **trading** | ia-trading | M1 (qwen3) | scanner | 1 |
| **trading** | - | OL1 | web_data | 1 |
| **trading** | ia-check | M1 (qwen3) | validator | 2 (depends) |
| **systeme** | ia-system | - | executor | 1 |
| **web** | - | OL1 | searcher | 1 |
| **web** | ia-deep | M1 (qwen3) | synthesizer | 2 (depends) |
| **simple** | - | M1 (qwen3) | responder | 1 |

**Regle** : Les reviewers/validators/synthesizers **dependent** des taches principales (priority 2).

---

## Seuil Thermique GPU

Verifie a chaque `decompose_task()` via `nvidia-smi --query-gpu=temperature.gpu`.

| Niveau | Temperature | Action |
|--------|------------|--------|
| **Normal** | < 75C | Routage standard |
| **Warning** | 75-84C | Preferer M2 pour code, reduire charge M1 |
| **Critical** | >= 85C | Deporter M1 -> M2/OL1/GEMINI, alerte dans prompt |

```python
# Fonction: check_thermal_status() -> dict
# Retourne: {ok, max_temp, status, hot_gpus, recommendation}
# Exemple: {"ok": True, "max_temp": 34, "status": "normal", "hot_gpus": []}
```

---

## 83 Outils MCP

Prefixe: `mcp__jarvis__`

### IA & Cluster (4)
| Outil | Description |
|-------|-------------|
| `lm_query` | Interroger M1/M2/M3/OL1 directement |
| `lm_models` | Lister les modeles charges |
| `lm_cluster_status` | Status complet du cluster |
| `consensus` | Consensus multi-noeuds (M1+OL1) |

### Model Management (7)
| Outil | Description |
|-------|-------------|
| `lm_load_model` | Charger un modele sur M1/M2 |
| `lm_unload_model` | Decharger un modele |
| `lm_switch_coder` | Charger qwen3-coder-30b sur M1 |
| `lm_switch_dev` | Charger devstral sur M1 |
| `lm_gpu_stats` | Stats GPU (VRAM, temp, utilisation) |
| `lm_benchmark` | Benchmark modele (tokens/s) |
| `lm_perf_metrics` | Metriques performance cluster |

### Ollama (7)
| Outil | Description |
|-------|-------------|
| `ollama_query` | Query Ollama local |
| `ollama_models` | Lister modeles Ollama |
| `ollama_pull` | Telecharger un modele |
| `ollama_status` | Status Ollama |
| `ollama_web_search` | Recherche web via cloud (minimax/glm/kimi) |
| `ollama_subagents` | 3 sous-agents paralleles |
| `ollama_trading_analysis` | Analyse trading via Ollama |

### Scripts (3)
| Outil | Description |
|-------|-------------|
| `run_script` | Executer un script indexe (33 scripts) |
| `list_scripts` | Lister les scripts disponibles |
| `list_project_paths` | Lister les chemins projets |

### Windows (47)
| Categorie | Nombre | Exemples |
|-----------|--------|----------|
| Applications | 3 | open_app, close_app, list_apps |
| Processus | 2 | kill_process, list_processes |
| Fenetres | 4 | focus_window, minimize, maximize, list_windows |
| Clavier/Souris | 4 | send_keys, click, type_text, hotkey |
| Clipboard | 2 | get_clipboard, set_clipboard |
| Fichiers | 9 | read_file, write_file, copy_file, move_file, delete_file, list_dir, create_dir, file_info, search_files |
| Audio | 3 | set_volume, get_volume, mute_toggle |
| Ecran | 2 | screenshot, screen_info |
| Systeme | 8 | system_info, disk_space, memory_usage, cpu_usage, uptime, env_var, hostname, os_version |
| Services | 3 | list_services, start_service, stop_service |
| Reseau | 3 | network_info, ping, dns_lookup |
| Registre | 2 | reg_read, reg_write |
| Notifications | 3 | toast_notification, balloon_tip, message_box |
| Power | 3 | shutdown, restart, sleep |

### Trading (5)
| Outil | Description |
|-------|-------------|
| `trading_pending_signals` | Signaux en attente |
| `trading_execute_signal` | Executer un signal |
| `trading_positions` | Positions ouvertes |
| `trading_status` | Status trading global |
| `trading_close_position` | Fermer une position |

### Brain (4)
| Outil | Description |
|-------|-------------|
| `brain_status` | Etat du cerveau auto-apprenant |
| `brain_analyze` | Analyser un pattern |
| `brain_suggest` | Suggestions basees sur l'historique |
| `brain_learn` | Apprendre un nouveau pattern |

### Skills (5)
| Outil | Description |
|-------|-------------|
| `list_skills` | 86+ skills dynamiques (16 vagues) |
| `create_skill` | Creer une nouvelle skill |
| `remove_skill` | Supprimer une skill |
| `suggest_actions` | Suggestions d'actions contextuelles |
| `action_history` | Historique des actions executees |

---

## n8n Workflow Etoile

### Configuration n8n

| Parametre | Valeur |
|-----------|--------|
| **Version** | v2.4.8 |
| **Port** | 5678 |
| **URL** | `http://127.0.0.1:5678` |
| **API Key** | Via X-N8N-API-KEY header (JWT) |
| **MCP Endpoint** | `http://127.0.0.1:5678/mcp-server/http` |
| **Auto-start** | Hook `startup.ps1` dans `.claude/hooks/` |

### Workflow "Etoile - JARVIS Commander Pipeline v10.2"

**ID** : `4Y2SrFR256HIFT42`
**Status** : ACTIF
**Trigger** : Webhook (`/webhook/etoile-commander`)

```
                    ┌──────────────────┐
                    │  Webhook Etoile  │  POST /webhook/etoile-commander
                    │  (Trigger)       │  Body: {"input": "votre prompt"}
                    └────────┬─────────┘
                             │
                             v
                    ┌──────────────────┐
                    │ 1. M1 Classify   │  qwen3-30b → code/analyse/trading/
                    │ (qwen3-30b)      │  systeme/web/simple
                    └────────┬─────────┘
                             │
                             v
                    ┌──────────────────┐
                    │ 2. Route by Type │  Switch 6 branches
                    │ (Switch Node)    │
                    └──┬───┬───┬───┬───┘
                       │   │   │   │
          ┌────────────┘   │   │   └───────────────┐
          v                v   v                    v
  ┌───────────────┐ ┌──────────────┐ ┌──────────────┐ ┌────────────────┐
  │3a. M2 Code    │ │3b. M1 Analyse│ │3c. M1 Trading│ │3d. OL1 Web     │
  │(deepseek)     │ │(qwen3-30b)   │ │(qwen3-30b)   │ │(qwen3:1.7b)    │
  └───────┬───────┘ └──────┬───────┘ └──────┬───────┘ └────────┬───────┘
          │                │                │                   │
          └────────┬───────┘────────┬───────┘───────────────────┘
                   v                v
          ┌──────────────────┐
          │4. M1 Verify      │  Score qualite 0.0-1.0
          │Quality           │  JSON: {score, issues, recommendation}
          └────────┬─────────┘
                   │
                   v
          ┌──────────────────┐
          │5. Synthesize     │  Combine tous les resultats
          │(Code Node)       │  Retourne: {synthesis, timestamp, pipeline}
          └──────────────────┘
```

### Appeler le Workflow Etoile

```bash
# Via webhook (quand actif)
curl -s -X POST http://127.0.0.1:5678/webhook/etoile-commander \
  -H "Content-Type: application/json" \
  -d '{"input": "analyse le code de config.py"}'

# Via API n8n (execution manuelle)
curl -s -X POST "http://127.0.0.1:5678/api/v1/workflows/4Y2SrFR256HIFT42/execute" \
  -H "X-N8N-API-KEY: VOTRE_CLE" \
  -H "Content-Type: application/json"
```

### Autres Workflows n8n

| Workflow | ID | Description |
|----------|-----|-------------|
| Trading Ultimate | `4ovJaOxtAzITyJEd` | Pipeline trading complet |
| Multi IA Consensus | `lJEz0hbG66DceXYA` | Consensus M1+M2+Gemini |
| Ancrage Manager | `jGlSm9FWTYb7OKZF` | Gestion ancrages trading |
| Scanner Pro | `PruXHoV67xhxwRZC` | Scanner breakout avance |
| Telegram Signals | `HtIDKlxK6UWHJux8` | Alertes trading Telegram |
| CLAIRE Ultimate | `n7lQHhg1oWn9bs8c` | Scanner complet 5min |
| Cluster Monitor | `4vb15uEx3j4A9YPT` | Monitoring GPU/noeuds |
| Trading V2 Multi IA | `6ssOxO4AOlWiCKNY` | Trading multi-IA |

---

## Architecture Vocale

```
Micro (Sony WH-1000XM4 Bluetooth)
       |
       v
 Whisper (faster-whisper CUDA, GPU)
       |
       v
 Correction Pipeline
 ├── Dictionnaire local (438 commandes)
 └── OL1 qwen3:1.7b (correction IA, timeout 8s)
       |
       v
 Command Match (fuzzy matching, 438 cmds)
       |
  +----+----+
  |         |
  v         v
MATCH     NO MATCH
(execute)  (Commander Mode)
             |
             v
        M1 pre-analyse (qwen3-30b)
             |
             v
        Claude dispatche (COMMANDER_PROMPT)
             |
             v
        TTS (Windows SAPI)
```

| Parametre | Valeur |
|-----------|--------|
| Micro | Sony WH-1000XM4 Bluetooth |
| STT | faster-whisper CUDA |
| Wake word | "jarvis" → attend commande |
| Exit confidence | >= 0.85 |
| Commandes | 438 commandes vocales |
| TTS | Windows SAPI |
| Cache micro | check_microphone() 30s |

---

## Trading MEXC Futures

| Parametre | Valeur |
|-----------|--------|
| **Exchange** | MEXC Futures |
| **Levier** | 10x |
| **Paires** | BTC ETH SOL SUI PEPE DOGE XRP ADA AVAX LINK |
| **TP** | 0.4% |
| **SL** | 0.25% |
| **Taille** | 10 USDT par position |
| **Score min** | 70/100 |
| **DRY_RUN** | false (production) |

### Scripts Trading Indexes

| Script | Chemin | Description |
|--------|--------|-------------|
| mexc_scanner | carV1/python_scripts/scanners/ | Scanner MEXC |
| breakout_detector | carV1/python_scripts/scanners/ | Detection breakout |
| sniper_breakout | carV1/python_scripts/ | Sniper precis |
| hyper_scan_v2 | carV1/python_scripts/ | Scan hyperactif |
| pipeline_intensif_v2 | PROD_INTENSIVE_V1/scripts/ | Pipeline autonome |

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

### Launchers (.bat)

| Launcher | Description |
|----------|-------------|
| `JARVIS_VOICE.bat` | Mode vocal complet |
| `JARVIS_KEYBOARD.bat` | Mode clavier + TTS |
| `JARVIS_COMMANDER.bat` | Commander explicite |
| `JARVIS_STATUS.bat` | Status cluster |
| `JARVIS_OLLAMA.bat` | Mode Ollama cloud |
| `JARVIS_BOOT.bat` | Boot cluster M1+M2 |
| `JARVIS_FINETUNE.bat` | Pipeline fine-tuning |
| `JARVIS_DASHBOARD.bat` | Dashboard web |
| `PIPELINE_10.bat` | 10 paires trading |
| `SNIPER.bat` | Sniper breakout |
| `SNIPER_10.bat` | Sniper 10 paires |
| `TRIDENT.bat` | Triple strategie |
| `SCAN_HYPER.bat` | Scan hyperactif |
| `MONITOR_RIVER.bat` | Monitor flux |

---

## Structure du Projet

```
F:\BUREAU\turbo\
|-- main.py                      # Point d'entree (7 modes: -i -c -v -k -o -s "prompt")
|-- pyproject.toml               # Dependencies (uv, Python 3.13)
|-- gemini-proxy.js              # Proxy Gemini 2.5 Pro/Flash (timeout 2min, fallback)
|-- CLAUDE_MULTI_AGENT.md        # Protocole MAO complet
|-- .env                         # Variables d'env (API keys, DB paths)
|-- .gitignore                   # .env, .venv/, __pycache__/, *.db, logs/
|
|-- src/
|   |-- __init__.py              # Package init
|   |-- orchestrator.py          # Moteur principal + COMMANDER_PROMPT + run_*()
|   |-- commander.py             # Pipeline Commander (classify/decompose/verify/synthesize)
|   |-- config.py                # Config cluster + routage + thermal + 33 scripts indexes
|   |-- agents.py                # 5 agents Claude SDK (ia-deep/fast/check/trading/system)
|   |-- tools.py                 # 83 outils MCP (IA, Windows, Trading, Brain, Skills)
|   |-- mcp_server.py            # Serveur MCP stdio pour Claude Code
|   |-- commands.py              # 438 commandes vocales (18 vagues)
|   |-- skills.py                # 86+ skills dynamiques (16 vagues)
|   |-- voice.py                 # Whisper STT + SAPI TTS + push-to-talk
|   |-- voice_correction.py      # Pipeline correction vocale (dict + OL1)
|   |-- cluster_startup.py       # Boot cluster + thermal monitoring + GPU stats
|   |-- trading.py               # Trading MEXC Futures (CCXT)
|   |-- brain.py                 # Auto-apprentissage (patterns, suggestions)
|   |-- executor.py              # Execution commandes/skills
|   |-- windows.py               # API Windows (PowerShell, COM, WMI)
|   |-- database.py              # SQLite persistence (jarvis.db)
|   |-- scenarios.py             # 79+ scenarios validation (tests)
|   |-- output.py                # Schema sortie JSON
|   |-- whisper_worker.py        # Worker Whisper persistent (process separe)
|   |-- dashboard.py             # API dashboard REST
|   |-- systray.py               # System tray icon (Windows)
|
|-- dashboard/
|   |-- server.py                # Serveur HTTP dashboard (stdlib, zero dep)
|   |-- index.html               # UI dashboard (HTML/CSS/JS)
|
|-- data/
|   |-- jarvis.db                # Base SQLite principale (6 tables)
|   |-- skills.json              # Skills persistantes
|   |-- brain_state.json         # Etat cerveau auto-apprenant
|   |-- jarvis_m1_prompt.txt     # Prompt compact pour M1
|   |-- action_history.json      # Historique actions
|   |-- etoile_workflow.json     # Workflow n8n Etoile (backup)
|
|-- launchers/                   # 14 fichiers .bat
|-- finetuning/                  # Pipeline QLoRA (Qwen3-30B, 55k exemples)
|-- scripts/                     # Scripts startup M1/M2
```

---

## Bases de Donnees

| Base | Chemin | Tables | Usage |
|------|--------|--------|-------|
| **jarvis.db** | `F:\BUREAU\turbo\data\` | 6 (skills, actions, historique...) | Base principale JARVIS |
| **etoile.db** | `F:\BUREAU\` | 6 (agents, api_keys, skills_log, sessions, memories, metrics) | Orchestration distribuee |
| **trading_latest.db** | `F:\BUREAU\carV1\database\` | trades, signaux | Trading carV1 |
| **trading.db** | `F:\BUREAU\TRADING_V2_PRODUCTION\database\` | predictions | Trading v2 |

---

## Installation & Configuration

### Prerequis

- Windows 11 Pro
- Python 3.13
- uv v0.10.2 (`C:\Users\franc\.local\bin\uv.exe`)
- CUDA (pour Whisper + LM Studio)
- LM Studio (M1 + M2)
- Ollama v0.16.1
- Node.js (pour gemini-proxy.js)
- n8n v2.4.8

### Installation

```bash
cd F:\BUREAU\turbo
uv sync

# Configurer .env
cp .env.example .env
# Editer avec vos cles API
```

### Lancer

```bash
# Interactif (Commander par defaut)
uv run python main.py

# Mode vocal
uv run python main.py -v

# Commander explicite
uv run python main.py -c

# Hybride (clavier + TTS)
uv run python main.py -k

# Status cluster
uv run python main.py -s

# One-shot
uv run python main.py "scanne le marche crypto"
```

### Notes Techniques Windows

- **TOUJOURS** utiliser `127.0.0.1` au lieu de `localhost` (IPv6 = +10s latence)
- PowerShell: `$_` est mange par bash → ecrire des fichiers .ps1
- uv: `powershell -Command "& 'C:\Users\franc\.local\bin\uv.exe' ..."`

---

## Benchmark

Date: 2026-02-18

| Metrique | Valeur |
|----------|--------|
| Classification M1 | 24/24 correct, 5ms avg |
| Classification heuristique | 24/24 correct, 0ms |
| Pipeline complet (classify+decompose+enrich) | 150ms avg |
| M1 inference (qwen3-30b) | 1.3-17.6s selon complexite |
| M2 inference (deepseek-coder) | 1.1-7.2s |
| OL1 inference (qwen3:1.7b) | 0.3-1.2s |
| Parallele M1+M2+OL1 | 2.2s (vs 3.7s sequentiel, +40%) |
| GPU | 6 GPU, 57% VRAM utilisee, 34C max |
| Thermal | Normal (< 75C) |

---

## Appels API — Exemples Complets

### Classification via M1 (API native v1)

```bash
curl -s http://10.5.0.2:1234/api/v1/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer LMSTUDIO_KEY_M1_REDACTED" \
  -d '{
    "model": "qwen/qwen3-30b-a3b-2507",
    "input": "debug le segfault dans main.py",
    "system_prompt": "Classifie cette demande en UNE categorie: code, analyse, trading, systeme, web, simple. Reponds UNIQUEMENT avec le mot-cle.",
    "temperature": 0.1,
    "max_output_tokens": 32,
    "stream": false,
    "store": false
  }'
# Reponse: {"output":[{"content":"code"}], "stats":{"total_output_tokens":1}}
```

### Consensus Multi-Noeuds

```bash
# M1 + M2 + OL1 en parallele, puis synthese
# Voir src/tools.py → consensus()
```

### Trading Signal

```bash
# Via l'agent ia-trading + run_script(mexc_scanner)
uv run python main.py "scanne BTC ETH SOL pour breakout"
```

### Gemini Architecture Review

```bash
node F:/BUREAU/turbo/gemini-proxy.js --json \
  "Review l'architecture de ce pipeline Commander. Points forts et faiblesses?"
```

---

## Protocole MAO (Multi-Agent Orchestrator)

Documentation complete: `CLAUDE_MULTI_AGENT.md`

### Commandes MAO

| Commande | Action |
|----------|--------|
| `MAO check` | Health check M1+M2+OL1+Gemini |
| `MAO consensus [question]` | Question sur M1+M2+GEMINI, synthese |
| `MAO code [description]` | M2 code → M1 review → presentation |
| `MAO archi [sujet]` | GEMINI avis → M1 validation |

### Matrice MAO

| Tache | Principal | Secondaire | Verificateur |
|-------|-----------|------------|--------------|
| Code nouveau | M2 | M1 (review) | GEMINI (archi) |
| Bug fix | M1 | M2 (patch) | - |
| Architecture | GEMINI | M1 (faisabilite) | - |
| Refactoring | M2 | M1 (validation) | - |
| Trading | M1 | OL1-cloud (web) | - |
| Question simple | OL1 | - | - |
| Consensus critique | M1+M2+GEMINI | Vote majoritaire | - |

---

## Fine-Tuning

| Parametre | Valeur |
|-----------|--------|
| **Dossier** | `F:\BUREAU\turbo\finetuning\` |
| **Methode** | QLoRA 4-bit + PEFT LoRA |
| **Modele base** | Qwen3-30B-A3B |
| **Dataset** | 55,549 exemples |
| **Launcher** | `JARVIS_FINETUNE.bat` |

**IMPORTANT** : Arreter LM Studio AVANT de lancer le training (conflits GPU).

---

## Dashboard

| Parametre | Valeur |
|-----------|--------|
| **URL** | `http://127.0.0.1:8080` |
| **API** | `/api/cluster` |
| **Server** | `dashboard/server.py` (stdlib, zero dep) |
| **UI** | `dashboard/index.html` |
| **Launcher** | `JARVIS_DASHBOARD.bat` |

---

## Disques

| Disque | Capacite | Libre | Contenu |
|--------|----------|-------|---------|
| **C:\\** | 476 GB | ~20 GB | Systeme, Python, uv |
| **F:\\** | 446 GB | ~45 GB | Projets, modeles LM Studio (~300 GB) |

---

## Licence

Projet prive — **Turbo31150** — 2026
