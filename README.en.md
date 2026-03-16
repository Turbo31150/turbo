# JARVIS Turmont - English Translation

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

## Language Switcher
[Français](README.md) | [English](README.en.md)

---

## What is JARVIS Turmont?

**JARVIS** is a distributed artificial intelligence ecosystem, entirely orchestrated under **Windows 11**, piloting a cluster of 3 machines and 6 NVIDIA GPUs. It integrates voice, trading, autonomous pipelines, and a massive MCP server with **613 handlers** — all coordinated by a Zero-Stop orchestrator that never asks for permission.

> *"Act with power, speed, and technical precision."*

---

## Cluster Architecture

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
 | ia-deep      Analysis      |
 | ia-fast      Quick Reply   |
 | ia-check     Validation    |
 | ia-trading   Markets       |
 | ia-system    Monitoring    |
 | ia-bridge    Inter-cluster |
 | ia-consensus Multi-opinion |
 +----------------------------+
```

---

## Key Features

### V3.0 Zero-Stop Orchestrator
Core of the system. Asynchronous execution, recursive internal debug loop, autonomous resolution of permissions, code, and dependencies. No human confirmation required for technical operations.

### MCP Server — 613 Handlers
Massive Model Context Protocol server exposing 613 tools via Flask on port 8080. Native integration with **Claude Desktop** and **Claude Code** to pilot JARVIS directly from the Anthropic interface.

### OpenClaw — 96 Autonomy Patterns
Advanced autonomy engine with 96 decision patterns that allow JARVIS to act, learn, and adapt without human intervention.

### WhisperFlow — CUDA Vocal Pipeline
Complete voice pipeline: "Jarvis" keyword detection via Porcupine, real-time Whisper transcription CUDA-accelerated on port 9000, EasySpeak voice synthesis.

### Domino Pipelines
Chainable action cascade system. Each domino triggers the next, enabling complex autonomous workflows across the entire cluster.

### DERNI ULTIMATE — Automated Trading
Multi-exchange automated trading system:
- **Exchanges**: CoinEx + MEXC Futures
- **n8n Workflow**: 32 nodes, 6 JSON workflow files
- **Consensus**: Multi-agents ia-trading + ia-consensus
- **Execution**: Automated signals via domino pipelines

### Electron Dashboard
Cyberpunk GUI built with **React 19**, **Vite 6**, neon dark theme. Real-time cluster, GPU, trading, and pipeline monitoring.

### Telegram Bot via Canvas Bridge
Telegram bot accessible on port 18800 via canvas bridge, including direct proxy and self-improvement loop (`autolearn.js`, `improve_loop.py`).

### Docker
Complete containerization with `docker-compose.yml` and PowerShell installation, start, and stop scripts.

---

## Project Structure

```
F:\BUREAU\turbo\
|
|-- src\                    278 Python modules (108,666 lines)
|   |-- core\               Orchestrator, scheduler, config
|   |-- domino_pipelines.py Action cascades
|   +-- mcp_server.py       613 MCP handlers
|
|-- tests\                  305 files, 8,716 test functions
|-- coworks\                477 inter-agent cooperation scripts
|-- canvas\                 14 files (Telegram bot, proxy, Electron bridge)
|-- electron\               React 19 + Vite 6 dashboard
|-- docker\                 Containerization (compose + PowerShell)
|-- finetuning\             Model fine-tuning
|-- memory\                 long_term.db (persistent SQLite context)
|-- backups\                Git bundles & SQL snapshots
|-- n8n\                    6 JSON workflows (DERNI trading, etc.)
|
|-- install.bat             Automated installation
|-- JARVIS_CONSOLE.bat      Interactive JARVIS console
|-- JARVIS_GEMINI_PROXY.bat Gemini proxy
|-- JARVIS_STATUS.bat       Cluster status
|-- JARVIS_UNIFIED_BOOT.bat Unified boot of all services
|-- jarvis.ps1              Main PowerShell launcher
|-- check_jarvis.ps1        System health check
|-- system_info.ps1         Hardware information
|-- test_m2.ps1             M2 machine tests
|-- test_perf.ps1           Performance benchmarks
|-- claude_desktop_dispatch.ps1   Claude Desktop dispatch
|-- find_windows.ps1        Active window detection
|
+-- CLAUDE.md               Orchestrator instructions for Claude
```

---

## Installation

### Prerequisites
- **Windows 11** with PowerShell 7+
- **Python 3.11+**
- **Node.js 20+** (for Electron and canvas)
- **NVIDIA Drivers** + **CUDA Toolkit** (for WhisperFlow and GPU routing)
- **Docker Desktop** (optional, for containerization)

### Procedure

```powershell
# 1. Clone the repository
git clone https://github.com/Turbo31150/turbo.git F:\BUREAU\turbo
cd F:\BUREAU\turbo

# 2. Automated installation
.\install.bat

# 3. Configure environment
# Edit the .env file with your API keys:
#   - ANTHROPIC_API_KEY
#   - GEMINI_API_KEY
#   - TELEGRAM_BOT_TOKEN
#   - COINEX_API_KEY / MEXC_API_KEY
#   - etc.

# 4. Unified boot of all services
.\JARVIS_UNIFIED_BOOT.bat
```

### Verification

```powershell
# System health
.\check_jarvis.ps1

# Full cluster status
.\JARVIS_STATUS.bat

# Hardware information
.\system_info.ps1
```

---

## Usage

### Interactive Console

```powershell
.\JARVIS_CONSOLE.bat
```

### Main PowerShell Launcher

```powershell
.\jarvis.ps1
```

### Electron Dashboard

```powershell
cd electron
npm install
.\start-dev.ps1
# -> http://localhost:5173
```

### Telegram Bot

```powershell
cd canvas
npm install
node telegram-bot.js
# -> Listening on port 18800
```

### Docker

```powershell
cd docker
.\install_docker.ps1
.\start.ps1
# To stop:
.\stop.ps1
```

### Claude Desktop Integration

The `claude_desktop_dispatch.ps1` file automatically configures MCP dispatch so Claude Desktop can pilot JARVIS via the 613 MCP server handlers.

---

## Tests

```powershell
# Full test suite (305 files, 8,716 tests)
pytest tests\ -v

# Performance benchmarks
.\test_perf.ps1

# M2 machine tests
.\test_m2.ps1
```

---

## Key Statistics

| Metric | Value |
|---|---|
| Python Modules | **278** |
| Lines of Code | **108,666** |
| MCP Handlers | **613** |
| Test Files | **305** |
| Test Functions | **8,716** |
| Cowork Scripts | **477** |
| Launchers (.bat/.ps1) | **12** |
| SDK Agents | **7** |
| OpenClaw Patterns | **96** |
| n8n Workflows | **6** |
| NVIDIA GPUs | **6** |
| Cluster Machines | **3** |

---

## Tech Stack

| Layer | Technologies |
|---|---|
| Main Language | Python 3.11+ |
| MCP Server | Flask (port 8080) |
| Frontend | Electron, React 19, Vite 6, TypeScript |
| Voice | Whisper CUDA, Porcupine, EasySpeak |
| Trading | CoinEx API, MEXC Futures, n8n |
| Messaging | Telegram Bot API, Canvas Bridge |
| Database | SQLite (long_term.db) |
| Containers | Docker, docker-compose |
| Scripting | PowerShell 7, Batch |
| AI Backend | LM Studio (M2), Claude, Gemini |
| Hardware | Ryzen 5700X3D, 46GB RAM, 6x NVIDIA, 12GB ZRAM |

---

## License

**Private repository.** All rights reserved. No redistribution allowed without explicit permission.

---

<p align="center">
<br>

```
  ╔══════════════════════════════════════════════════════════════╗
  ║  JARVIS TURMONT v3.0 — Windows 11 Autonomous Orchestrator ║
  ║  278 modules | 613 MCP | 8,716 tests | 6 GPUs | 3 machines ║
  ║  "Zero-Stop. Zero-Permission. Maximum Precision."           ║
  ╚══════════════════════════════════════════════════════════════╝
```

</p>

---

## Translation Notes

- **246 Python modules** (93K lines)
- **853 voice commands** (French)
- **613 MCP handlers** + **517 REST endpoints**
- **10 GPU cluster**, **78 GB VRAM**, **4 nodes**
- **2,281 automated tests** (85.5% coverage)
