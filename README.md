---

## Language Switcher
[Français](README.md) | [English](README.en.md)

---

```
       ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗
       ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝
       ██║███████║██████╔╝██║   ██║██║███████╗
  ██   ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║
  ╚█████╔╝██║  ██║██║  ██║ ╚████╔╝ ██║███████║
   ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝
   T U R M O N T   —   O R C H E S T R A T E U R   V 3 . 0
```

<p align="center">
  <img src="https://img.shields.io/badge/plateforme-Windows%2011-0078D4?style=for-the-badge&logo=windows11&logoColor=white" />
  <img src="https://img.shields.io/badge/Python-278%20modules-3776AB?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/lignes-108%2C666-informational?style=for-the-badge" />
  <img src="https://img.shields.io/badge/MCP-613%20handlers-blueviolet?style=for-the-badge" />
  <img src="https://img.shields.io/badge/tests-8%2C716-success?style=for-the-badge&logo=pytest&logoColor=white" />
  <img src="https://img.shields.io/badge/licence-Priv%C3%A9e-red?style=for-the-badge" />
</p>

<p align="center">
  <img src="https://img.shields.io/badge/GPU-6x%20NVIDIA-76B900?style=flat-square&logo=nvidia&logoColor=white" />
  <img src="https://img.shields.io/badge/CPU-Ryzen%205700X3D-ED1C24?style=flat-square&logo=amd&logoColor=white" />
  <img src="https://img.shields.io/badge/RAM-46%20GB-orange?style=flat-square" />
  <img src="https://img.shields.io/badge/ZRAM-12%20GB-yellow?style=flat-square" />
  <img src="https://img.shields.io/badge/cluster-3%20machines-cyan?style=flat-square" />
  <img src="https://img.shields.io/badge/coworks-477%20scripts-ff69b4?style=flat-square" />
</p>

---

## Qu'est-ce que JARVIS Turmont ?

**JARVIS** est un ecosysteme d'intelligence artificielle distribuee, entierement orchestre sous **Windows 11**, pilotant un cluster de 3 machines et 6 GPUs NVIDIA. Il integre voix, trading, pipelines autonomes et un serveur MCP massif de **613 handlers** -- le tout coordonne par un orchestrateur Zero-Stop qui ne demande jamais la permission.

> *"Agis avec puissance, rapidite et precision technique."*

---

## Architecture du Cluster

```
 +-----------------------------------------------------------------+
 |                     RESEAU JARVIS TURMONT                       |
 +-----------------------------------------------------------------+
 |                                                                 |
 |   +-------------------+     +----------------+     +---------+  |
 |   |   M1 - MASTER     |     |  M2 - WORKER   |     |   M3    |  |
 |   |   La Creatrice    |     |     LMT2       |     |  SERVER |  |
 |   +-------------------+     +----------------+     +---------+  |
 |   | Ryzen 5700X3D     |     | LM Studio API  |     | n8n     |  |
 |   | 46 GB RAM         |     | Port 1234      |     | SQL     |  |
 |   | 6x GPU NVIDIA     |     | Backend IA     |     | Git     |  |
 |   | 12 GB ZRAM        |     | Intelligence   |     | Valid.  |  |
 |   +-------------------+     +----------------+     +---------+  |
 |   | MCP Flask   :8080 |           |                     |       |
 |   | WhisperFlow :9000 |           |                     |       |
 |   | Electron    :5173 |     +-----+-----+---------------+       |
 |   | Telegram    :18800|     |  BRIDGE RESEAU INTERNE            |
 |   | OpenClaw    :auto |     +-----------------------------------+
 |   +-------------------+                                         |
 +-----------------------------------------------------------------+

 +----------------------------+
 |      7 AGENTS SDK          |
 +----------------------------+
 | ia-deep      Analyse prof. |
 | ia-fast      Reponse eclair|
 | ia-check     Validation    |
 | ia-trading   Marches       |
 | ia-system    Monitoring    |
 | ia-bridge    Inter-cluster |
 | ia-consensus Multi-avis    |
 +----------------------------+
```

---

## Fonctionnalites Principales

### Orchestrateur V3.0 Zero-Stop
Coeur du systeme. Execution asynchrone, boucle de debug interne recursive, resolution autonome des erreurs de permissions, code et dependances. Aucune confirmation humaine requise pour les operations techniques.

### MCP Server — 613 Handlers
Serveur Model Context Protocol massif exposant 613 outils via Flask sur le port 8080. Integration native avec **Claude Desktop** et **Claude Code** pour piloter JARVIS directement depuis l'interface Anthropic.

### OpenClaw — 96 Patterns d'Autonomie
Moteur d'autonomie avancee avec 96 patterns de decision qui permettent a JARVIS d'agir, apprendre et s'adapter sans intervention humaine.

### WhisperFlow — Pipeline Vocal CUDA
Pipeline vocal complet : detection du mot-cle "Jarvis" via Porcupine, transcription temps reel Whisper acceleree CUDA sur port 9000, synthese vocale EasySpeak.

### Domino Pipelines
Systeme de cascades d'actions chainables. Chaque domino declenche le suivant, permettant des workflows autonomes complexes a travers tout le cluster.

### DERNI ULTIMATE — Trading Automatise
Systeme de trading multi-exchange :
- **Exchanges** : CoinEx + MEXC Futures
- **Workflow n8n** : 32 noeuds, 6 fichiers JSON de workflows
- **Consensus** : Multi-agents ia-trading + ia-consensus
- **Execution** : Signaux automatises via pipelines domino

### Dashboard Electron
Interface graphique cyberpunk construite avec **React 19**, **Vite 6**, theme sombre neon. Monitoring temps reel du cluster, des GPUs, du trading et des pipelines.

### Bot Telegram via Canvas Bridge
Bot Telegram accessible sur le port 18800 via le bridge canvas, incluant proxy direct et boucle d'auto-amelioration (`autolearn.js`, `improve_loop.py`).

### Docker
Conteneurisation complete avec `docker-compose.yml` et scripts PowerShell d'installation, demarrage et arret.

---

## Arborescence du Projet

```
F:\BUREAU\turbo\
|
|-- src\                    278 modules Python (108,666 lignes)
|   |-- core\               Orchestrateur, scheduler, config
|   |-- domino_pipelines.py Cascades d'actions
|   +-- mcp_server.py       613 handlers MCP
|
|-- tests\                  305 fichiers, 8,716 fonctions de test
|-- coworks\                477 scripts de cooperation inter-agents
|-- canvas\                 14 fichiers (Telegram bot, proxy, Electron bridge)
|-- electron\               Dashboard React 19 + Vite 6
|-- docker\                 Conteneurisation (compose + PowerShell)
|-- finetuning\             Fine-tuning de modeles
|-- memory\                 long_term.db (contexte persistant SQLite)
|-- backups\                Git bundles & snapshots SQL
|-- n8n\                    6 workflows JSON (trading DERNI, etc.)
|
|-- install.bat             Installation automatisee
|-- JARVIS_CONSOLE.bat      Console interactive JARVIS
|-- JARVIS_GEMINI_PROXY.bat Proxy Gemini
|-- JARVIS_STATUS.bat       Statut du cluster
|-- JARVIS_UNIFIED_BOOT.bat Boot unifie de tous les services
|-- jarvis.ps1              Lanceur principal PowerShell
|-- check_jarvis.ps1        Verification sante du systeme
|-- system_info.ps1         Informations systeme
|-- test_m2.ps1             Tests machine M2
|-- test_perf.ps1           Benchmark performances
|-- claude_desktop_dispatch.ps1   Dispatch Claude Desktop
|-- find_windows.ps1        Detection des fenetres actives
|
+-- CLAUDE.md               Instructions orchestrateur pour Claude
```

---

## Installation

### Prerequis
- **Windows 11** avec PowerShell 7+
- **Python 3.11+**
- **Node.js 20+** (pour Electron et canvas)
- **NVIDIA Drivers** + **CUDA Toolkit** (pour WhisperFlow et GPU routing)
- **Docker Desktop** (optionnel, pour conteneurisation)

### Procedure

```powershell
# 1. Cloner le depot
git clone https://github.com/Turbo31150/turbo.git F:\BUREAU\turbo
cd F:\BUREAU\turbo

# 2. Installation automatisee
.\install.bat

# 3. Configurer l'environnement
# Editer le fichier .env avec vos cles API :
#   - ANTHROPIC_API_KEY
#   - GEMINI_API_KEY
#   - TELEGRAM_BOT_TOKEN
#   - COINEX_API_KEY / MEXC_API_KEY
#   - etc.

# 4. Boot unifie de tous les services
.\JARVIS_UNIFIED_BOOT.bat
```

### Verification

```powershell
# Sante du systeme
.\check_jarvis.ps1

# Statut complet du cluster
.\JARVIS_STATUS.bat

# Informations hardware
.\system_info.ps1
```

---

## Utilisation

### Console Interactive

```powershell
.\JARVIS_CONSOLE.bat
```

### Lanceur Principal PowerShell

```powershell
.\jarvis.ps1
```

### Dashboard Electron

```powershell
cd electron
npm install
.\start-dev.ps1
# -> http://localhost:5173
```

### Bot Telegram

```powershell
cd canvas
npm install
node telegram-bot.js
# -> Ecoute sur le port 18800
```

### Docker

```powershell
cd docker
.\install_docker.ps1
.\start.ps1
# Pour arreter :
.\stop.ps1
```

### Integration Claude Desktop

Le fichier `claude_desktop_dispatch.ps1` configure automatiquement le dispatch MCP pour que Claude Desktop puisse piloter JARVIS via les 613 handlers du serveur MCP.

---

## Tests

```powershell
# Suite complete (305 fichiers, 8,716 tests)
pytest tests\ -v

# Benchmark performances
.\test_perf.ps1

# Tests machine M2
.\test_m2.ps1
```

---

## Chiffres Cles

| Metrique | Valeur |
|---|---|
| Modules Python | **278** |
| Lignes de code | **108,666** |
| Handlers MCP | **613** |
| Fichiers de test | **305** |
| Fonctions de test | **8,716** |
| Scripts cowork | **477** |
| Launchers (.bat/.ps1) | **12** |
| Agents SDK | **7** |
| Patterns OpenClaw | **96** |
| Workflows n8n | **6** |
| GPUs NVIDIA | **6** |
| Machines cluster | **3** |

---

## Stack Technique

| Couche | Technologies |
|---|---|
| Langage principal | Python 3.11+ |
| Serveur MCP | Flask (port 8080) |
| Frontend | Electron, React 19, Vite 6, TypeScript |
| Voice | Whisper CUDA, Porcupine, EasySpeak |
| Trading | CoinEx API, MEXC Futures, n8n |
| Messagerie | Telegram Bot API, Canvas Bridge |
| Base de donnees | SQLite (long_term.db) |
| Conteneurs | Docker, docker-compose |
| Scripting | PowerShell 7, Batch |
| IA Backend | LM Studio (M2), Claude, Gemini |
| Hardware | Ryzen 5700X3D, 46GB RAM, 6x NVIDIA, 12GB ZRAM |

---

## Licence

**Depot prive.** Tous droits reserves. Aucune redistribution autorisee sans accord explicite.

---

<p align="center">
<br>

```
  ╔══════════════════════════════════════════════════════════════╗
  ║  JARVIS TURMONT v3.0 — Orchestrateur Autonome Windows 11   ║
  ║  278 modules | 613 MCP | 8,716 tests | 6 GPUs | 3 machines ║
  ║  "Zero-Stop. Zero-Permission. Maximum Precision."           ║
  ╚══════════════════════════════════════════════════════════════╝
```

</p>
