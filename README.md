<p align="center">
  <img src="https://img.shields.io/badge/version-v10.3-blueviolet?style=for-the-badge" alt="version"/>
  <img src="https://img.shields.io/badge/GPU-6x_NVIDIA-76B900?style=for-the-badge&logo=nvidia" alt="gpu"/>
  <img src="https://img.shields.io/badge/Claude_SDK-Opus_4-orange?style=for-the-badge&logo=anthropic" alt="claude"/>
  <img src="https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="python"/>
  <img src="https://img.shields.io/badge/Electron-33-47848F?style=for-the-badge&logo=electron&logoColor=white" alt="electron"/>
  <img src="https://img.shields.io/badge/License-Private-red?style=for-the-badge" alt="license"/>
</p>

<h1 align="center">JARVIS Etoile v10.3</h1>
<h3 align="center">Orchestrateur IA Distribue Multi-GPU</h3>

<p align="center">
  <strong>Systeme d'intelligence artificielle distribue sur 3 machines physiques, 6 GPU NVIDIA (46 GB VRAM local), 5 noeuds IA et 82 skills autonomes. Controle vocal en francais, trading algorithmique multi-consensus, et interface desktop Electron.</strong>
</p>

<p align="center">
  <em>"Claude = Commandant Pur. Il ne fait JAMAIS le travail lui-meme. Il ORDONNE, VERIFIE et ORCHESTRE."</em>
</p>

---

## Chiffres Cles

```
+------------------+---------------------------+--------------------------------------+
| Metrique         | Valeur                    | Detail                               |
+------------------+---------------------------+--------------------------------------+
| GPU              | 6 NVIDIA / 46 GB VRAM     | RTX 3080 10GB, RTX 2060 6GB,        |
|                  |                           | 4x GTX 1660S 6GB                    |
| Noeuds IA        | 5 actifs (PENTA_CORE)     | M1 (deep), M2 (fast), M3 (validate) |
|                  |                           | OL1 (Ollama), GEMINI (cloud)         |
| Agents           | 7 Claude SDK + 11 Plugin  | deep, fast, check, trading, system,  |
|                  |                           | bridge, consensus + 11 plugin agents |
| Outils MCP       | 75 SDK + 88 handlers      | IA, Windows, Trading, Bridge, Brain  |
| Commandes        | 1,697 vocales             | 278 pipelines multi-etapes           |
| Skills           | 82 dynamiques             | 16 vagues d'apprentissage            |
| Source Python    | 29 modules / 20,717 lignes| dans src/ uniquement                 |
| Launchers        | 34 .bat + 32 .ps1         | 66 scripts de lancement              |
| Plugin Commands  | 24 commandes              | + 10 skills plugin specialises       |
| n8n Workflows    | 6 workflows               | monitoring, trading, backup, reports |
| Desktop          | Electron 33 + React 19    | Portable 72.5 MB                     |
| Trading          | v2.3 Multi-GPU            | MEXC Futures + 5 IA consensus        |
+------------------+---------------------------+--------------------------------------+
```

---

## Table des Matieres

- [Architecture Globale](#architecture-globale)
- [Cluster IA - 3 Machines](#cluster-ia---3-machines)
- [Pipeline Commander](#pipeline-commander)
- [7 Agents Claude SDK](#7-agents-claude-sdk)
- [Consensus Multi-Source](#consensus-multi-source)
- [82 Skills Autonomes](#82-skills-autonomes)
- [88 Outils MCP](#88-outils-mcp)
- [Architecture Vocale](#architecture-vocale)
- [Trading MEXC Futures](#trading-mexc-futures)
- [Desktop Electron](#desktop-electron)
- [Arborescence du Projet](#arborescence-du-projet)
- [Installation](#installation)
- [Benchmark Cluster](#benchmark-cluster)

---

## Architecture Globale

```
                          +---------------------+
                          |    UTILISATEUR       |
                          |  (Voix / Clavier)    |
                          +----------+----------+
                                     |
                          +----------v----------+
                          |   CLAUDE OPUS 4     |
                          |   (Commandant)      |
                          |  Ordonne & Orchestre |
                          +----------+----------+
                                     |
                    +----------------+----------------+
                    |                |                |
           +--------v------+  +-----v-------+  +----v--------+
           |  M1 - MASTER  |  | M2 - WORKER |  | M3 - VALID  |
           | RTX 3080 10GB |  | 3 GPU 24GB  |  | 1 GPU 8GB   |
           | + RTX 2060    |  | LM Studio   |  | LM Studio   |
           | + 4x 1660S    |  | Fast Infer  |  | Cross-check |
           | LM Studio     |  | 192.168.1.26|  | 192.168.1.113|
           | Port 1234     |  |             |  |             |
           +-------+-------+  +------+------+  +------+------+
                   |                 |                 |
                   +--------+--------+---------+-------+
                            |                  |
                    +-------v------+   +-------v------+
                    | OL1 - OLLAMA |   |   GEMINI     |
                    | Cloud Infer  |   |   Cloud API  |
                    | Web Search   |   |  Architecture|
                    +--------------+   +--------------+
```

### Flux de Donnees

```
Voix/Texte --> STT (faster-whisper CUDA) --> Correction IA
    --> Classification Intent --> Decomposition Taches
    --> Dispatch Multi-GPU --> Execution Parallele
    --> Consensus Pondere --> Reponse Vocale (TTS SAPI)
```

---

## Cluster IA - 3 Machines

### M1 - Machine Master (localhost)

| Composant | Specification |
|-----------|---------------|
| GPU Principal | RTX 3080 (10 GB) - PCIe Gen 4 x16 |
| GPU Secondaire | RTX 2060 (6 GB) - PCIe Gen 3 x4 |
| GPU Compute | 4x GTX 1660 SUPER (6 GB chacun) |
| VRAM Totale | 46 GB |
| Role | Deep Analysis, Orchestration, DB Centrale |
| LM Studio | Port 1234, Modele: Qwen3-30B-A3B |
| Latence Moyenne | 4.7s (apres optimisation GPU priority) |

### M2 - Worker Rapide (192.168.1.26)

| Composant | Specification |
|-----------|---------------|
| GPU | 3 GPU - 24 GB VRAM total |
| Role | Fast Inference, Reponse rapide |
| LM Studio | Port 1234 |
| Score Benchmark | 92% |

### M3 - Validateur (192.168.1.113)

| Composant | Specification |
|-----------|---------------|
| GPU | 1 GPU - 8 GB VRAM |
| Role | Validation croisee, Cross-check |
| LM Studio | Port 1234 |
| Score Benchmark | 89% |

---

## Pipeline Commander

Le coeur de JARVIS suit un pipeline strict ou Claude ne fait **jamais** le travail lui-meme :

```
1. CLASSIFY    --> Identifier le type de tache (voice/system/trading/code/query)
2. DECOMPOSE   --> Decouper en micro-taches executables
3. THERMAL     --> Verifier temperature GPU avant dispatch
4. ENRICH      --> Ajouter contexte systeme au prompt
5. DISPATCH    --> Router vers le bon noeud (M1/M2/M3/OL1/GEMINI)
6. EXECUTE     --> Le noeud execute la tache
7. VALIDATE    --> Cross-check par un second noeud
8. AGGREGATE   --> Consensus pondere si multi-source
9. RESPOND     --> Reponse vocale ou texte
10. PERSIST    --> Sauvegarder en DB (etoile.db)
```

### Routage Intelligent (Benchmark-Tuned)

```
+------------------+------------------+--------+
| Type de Tache    | Noeud Principal  | Poids  |
+------------------+------------------+--------+
| Deep Analysis    | M1 (RTX 3080)   | 1.3    |
| Quick Signal     | M2 (Fast)       | 1.0    |
| Code Generation  | M1              | 1.3    |
| Validation       | M3              | 0.8    |
| Web Search       | OL1 (Ollama)    | 0.6    |
| Architecture     | GEMINI          | 0.5    |
+------------------+------------------+--------+
```

---

## 7 Agents Claude SDK

| Agent | Role | Trigger |
|-------|------|---------|
| **Deep** | Analyse approfondie, raisonnement long | Questions complexes, debug |
| **Fast** | Reponse rapide, commandes simples | Commandes directes, status |
| **Check** | Validation, cross-check, QA | Apres chaque decision critique |
| **Trading** | Analyse marche, signaux, consensus | Commandes trading, scan |
| **System** | Operations Windows, GPU, services | Commandes systeme |
| **Bridge** | Routage intelligent inter-noeuds | Taches multi-machines |
| **Consensus** | Agregation multi-IA, vote pondere | Decisions importantes |

### 11 Agents Plugin

Auto-healer, Benchmark Runner, Canvas Operator, Cluster Ops, Code Architect, Debug Specialist, Performance Monitor, Raisonnement Specialist, Routing Optimizer, Smart Dispatcher, Trading Analyst.

---

## Consensus Multi-Source

Chaque decision importante passe par un pipeline de consensus pondere :

```
  M1 (poids 1.3)  ----+
  M2 (poids 1.0)  ----+--> Agregation --> Score Consensus --> Decision
  M3 (poids 0.8)  ----+        |
  OL1 (poids 0.6) ----+        |
  GEMINI (poids 0.5) -+        v
                          FORT  (>= 0.66)  --> Decision nette
                          MOYEN (0.4-0.66) --> Decision + alternatives
                          FAIBLE (< 0.4)   --> Pas de decision, expose divergences
```

**Formule :** `score(option) = SUM(weight_i * confidence_i) / SUM(weight_i)`

---

## 82 Skills Autonomes

Les skills sont des pipelines multi-etapes declenches par commande vocale. Exemples :

| Categorie | Skills | Exemples |
|-----------|--------|----------|
| **Modes** | 22 | Trading, Dev, Gaming, Focus, Cinema, Nuit, Stream |
| **Workspace** | 7 | Frontend, Backend, Data Science, ML, Docker, Turbo |
| **Diagnostic** | 10 | Complet, Reseau, GPU, Demarrage, Sante PC, Connexion |
| **Trading** | 5 | Consensus, Check Complet, Scalping, Risk Alert, Feedback |
| **Maintenance** | 8 | Nettoyage, Optimisation, DNS, Fichiers, Backup |
| **Routine** | 6 | Rapport Matin, Rapport Soir, Pause Cafe, Retour, Fin Journee |
| **Systeme** | 12 | Inventaire HW, Performances, Audit Securite, Sync Machines |
| **Cluster** | 6 | Benchmark, Load Balancer, Recovery, Heal, GPU Pipeline |
| **Navigation** | 6 | Split Screen, 4 Fenetres, Double Ecran, Accessibilite |

---

## 88 Outils MCP

Repartis en 6 categories :

```
JARVIS-TURBO (52 tools)        TRADING-AI-ULTIMATE (88 handlers)
+-- Cluster IA (12)            +-- Scanner MEXC (15)
+-- Windows System (15)        +-- Orderbook Analysis (8)
+-- Brain/Skills (8)           +-- Multi-IA Consensus (12)
+-- Trading Bridge (6)         +-- Positions/Margins (10)
+-- Filesystem (5)             +-- Alerts/Telegram (14)
+-- Utilities (6)              +-- SQL Database (9)
                               +-- LM Studio Dispatch (12)
                               +-- n8n/GitHub/System (8)
```

---

## Architecture Vocale

### Pipeline v2 (2026-02-22)

```
                    CTRL (Push-to-Talk)
                          |
                          v
                  +---------------+
                  |  Sony WH-1000 |  <-- Auto-detection micro
                  |  XM4 / Defaut |
                  +-------+-------+
                          |
                  +-------v-------+
                  | faster-whisper |  <-- CUDA GPU accelere
                  |  STT < 200ms  |      Persistent Worker
                  +-------+-------+      (charge 1x, pipe stdin/stdout)
                          |
                  +-------v-------+
                  | Correction IA |  <-- LM Studio corrige
                  | "ouvre moa"   |      "ouvre moi"
                  | -> "ouvre moi"|
                  +-------+-------+
                          |
                  +-------v-------+
                  | Intent Match  |  <-- 1,697 commandes
                  | + Fuzzy Match |      278 pipelines
                  +-------+-------+
                          |
                  +-------v-------+
                  | Orchestrator  |  <-- Dispatch vers cluster
                  +-------+-------+
                          |
                  +-------v-------+
                  |  TTS (SAPI)   |  <-- Windows Speech API
                  |  PowerShell   |      Script .ps1 temporaire
                  +---------------+
```

---

## Trading MEXC Futures

### Pipeline v2.3

```
Scan 850+ tickers MEXC Futures
    |
    v
Filtre: Volume > 3M USDT, Change > 2%
    |
    v
Analyse technique: RSI, MACD, BB, ATR, Stochastic, OBV
    |
    v
Orderbook: 50 niveaux bid/ask, buy pressure, whale walls
    |
    v
Scoring composite (breakout + reversal + momentum + liquidity)
    |
    v
Consensus 5 IA (M1 + M2 + M3 + OL1 + GEMINI)
    |
    v
Entry/TP1/TP2/TP3/TP4/SL calcules (ATR-based)
    |
    v
Signal Telegram + Sauvegarde SQL (sniper.db)
```

### Outils de Scan

| Scanner | Description | Duree |
|---------|-------------|-------|
| `turbo_scan` | Scan complet + consensus 4 modeles | 2-3 min |
| `scan_sniper` | Scanner premium 5 IA, 400+ contrats | 5-7 min |
| `pump_detector` | Detection breakout imminents | 1-2 min |
| `scan_breakout_imminent` | Orderbook + liquidity clusters | 2-3 min |
| `perplexity_scan` | BB squeeze + Supertrend + RSI/MACD | 2-3 min |
| `smart_scan` | Full scan + Multi-IA + Telegram | 3-5 min |

---

## Desktop Electron

Application desktop construite avec Electron 33 + React 19 + TypeScript + Vite.

### Pages

| Page | Fonction |
|------|----------|
| Dashboard | Vue d'ensemble systeme, cluster status, metriques |
| Chat | Interface conversationnelle avec JARVIS |
| Voice | Visualisation audio, log transcriptions |
| Trading | Positions ouvertes, signaux, historique |
| LM Studio | Gestion modeles, charge GPU, benchmarks |
| Settings | Configuration systeme et preferences |

### Composants

```
electron/src/
+-- main/           # Process principal Electron
|   +-- index.ts
|   +-- ipc-handlers.ts
|   +-- python-bridge.ts
|   +-- tray.ts
|   +-- window-manager.ts
+-- renderer/        # Interface React
|   +-- components/
|   |   +-- chat/    # AgentBadge, MessageBubble
|   |   +-- cluster/ # NodeCard
|   |   +-- layout/  # Sidebar, TopBar
|   |   +-- trading/ # PositionsTable, SignalsTable
|   |   +-- voice/   # AudioVisualizer, TranscriptionLog
|   +-- hooks/       # useChat, useCluster, useLMStudio,
|   |                  useTrading, useVoice, useWebSocket
|   +-- pages/       # 6 pages principales
+-- widget-windows/  # Widgets overlay
```

---

## Arborescence du Projet

```
turbo/
+-- src/                    # 29 modules Python (20,717 lignes)
|   +-- orchestrator.py     # Cerveau central
|   +-- commander.py        # Pipeline Commander
|   +-- agents.py           # 7 agents Claude SDK
|   +-- commands.py         # Commandes vocales principales
|   +-- commands_dev.py     # Commandes developpement
|   +-- commands_maintenance.py  # Commandes maintenance
|   +-- commands_navigation.py   # Commandes navigation
|   +-- commands_pipelines.py    # 278 pipelines
|   +-- mcp_server.py       # Serveur MCP (75 outils)
|   +-- brain.py            # Cerveau auto-apprentissage
|   +-- skills.py           # 82 skills dynamiques
|   +-- config.py           # Configuration cluster
|   +-- voice.py            # Pipeline vocal
|   +-- trading.py          # Trading bridge
|   +-- ...
+-- electron/               # App desktop (React 19 + TS)
+-- plugins/jarvis-turbo/   # Plugin Claude Code
|   +-- agents/ (11)
|   +-- commands/ (24)
|   +-- skills/ (10)
+-- scripts/                # Scripts utilitaires
+-- launchers/              # 17 launchers principaux
+-- finetuning/             # Pipeline fine-tuning LLM
+-- n8n_workflows/          # 6 workflows n8n
+-- data/                   # DB, configs, exports
+-- docs/                   # 21 fichiers documentation
|   +-- plans/              # Plans d'implementation
+-- canvas/                 # Interface web legacy
+-- dashboard/              # Dashboard HTML
+-- docker/                 # Docker Compose stack
```

---

## Installation

### Prerequis

- Windows 10/11 avec PowerShell 7+
- Python 3.12 (gere via `uv`)
- Node.js 20+ (pour Electron et MCP)
- NVIDIA GPU avec drivers recents (CUDA support)
- LM Studio installe sur chaque noeud

### Demarrage Rapide

```powershell
# 1. Cloner le repo
git clone https://github.com/Turbo31150/turbo.git
cd turbo

# 2. Installer les dependances Python
uv sync

# 3. Configurer l'environnement
cp .env.example .env
# Editer .env avec vos cles API (MEXC, Telegram, Gemini)

# 4. Lancer JARVIS
.\jarvis.bat                # Mode standard
.\jarvis_voice.bat          # Mode vocal
.\jarvis_interactive.bat    # Mode interactif
.\JARVIS_COMMANDER.bat      # Mode Commander (recommande)
```

### Modes de Lancement

| Launcher | Description |
|----------|-------------|
| `jarvis.bat` | Mode standard |
| `jarvis_voice.bat` | Mode vocal (Push-to-Talk CTRL) |
| `jarvis_interactive.bat` | Mode interactif terminal |
| `JARVIS_COMMANDER.bat` | Mode Commander (Claude orchestre) |
| `jarvis_hybrid.bat` | Mode hybride voix + texte |
| `jarvis_dashboard.bat` | Dashboard web |
| `jarvis_systray.bat` | System tray |
| `jarvis_mcp_stdio.bat` | Serveur MCP (pour Claude Desktop) |

---

## Benchmark Cluster

Resultats du benchmark reel (2026-02-26) :

```
+--------+-----------+----------+--------+
| Noeud  | Latence   | Score    | Status |
+--------+-----------+----------+--------+
| M1     | 4.7s      | 100%     | ONLINE |
| M2     | ~5.2s     | 92%      | ONLINE |
| M3     | ~6.1s     | 89%      | ONLINE |
| OL1    | ~3.0s     | 88%      | ONLINE |
| GEMINI | variable  | 74%      | CLOUD  |
+--------+-----------+----------+--------+

M1 Optimisation GPU: 22.5s --> 4.7s (gain 79%)
Fix: GPU priority order dans LM Studio
```

---

## n8n Workflows

| Workflow | Fonction |
|----------|----------|
| `jarvis_brain_learning` | Auto-apprentissage et memorisation |
| `jarvis_cluster_monitor` | Surveillance sante cluster |
| `jarvis_daily_report` | Rapport quotidien automatique |
| `jarvis_git_auto_backup` | Backup Git automatique |
| `jarvis_system_health` | Health check systeme |
| `jarvis_trading_pipeline` | Pipeline trading automatise |

---

## Stack Technique

| Couche | Technologies |
|--------|-------------|
| **Orchestration** | Claude Opus 4 (Agent SDK), MCP Protocol |
| **IA Locale** | LM Studio (Qwen3-30B, Nemotron, Mistral), Ollama |
| **IA Cloud** | Gemini API, Perplexity |
| **Backend** | Python 3.12, FastAPI, Litestar, asyncio |
| **Desktop** | Electron 33, React 19, TypeScript, Vite, Tailwind |
| **Voice** | faster-whisper (CUDA), Windows SAPI (TTS) |
| **Trading** | CCXT (MEXC), PyTorch, Multi-GPU Pipeline |
| **Database** | SQLite3 (etoile.db, jarvis.db, sniper.db) |
| **Automation** | n8n, Playwright, Telegram Bot API |
| **DevOps** | Docker Compose, GitHub, uv (Python) |

---

<p align="center">
  <strong>JARVIS Etoile v10.3</strong> — Built with passion by <a href="https://github.com/Turbo31150">Turbo31150</a>
</p>
<p align="center">
  <em>Repo prive — Derniere mise a jour : 2026-02-26</em>
</p>
