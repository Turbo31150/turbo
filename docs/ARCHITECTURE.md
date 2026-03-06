# JARVIS Etoile v12.1 — Architecture Complete

> Schema monstrueux detaillant TOUS les composants, noeuds, routage, outils, integrations et flux de JARVIS.

---

## Vue d'Ensemble — Le Monstre

```
                                          UTILISATEUR (Turbo)
                                     voix / clavier / telegram
                                               |
               +-------------------------------+-------------------------------+
               |                               |                               |
        TELEGRAM BOT                   WHISPER STT (CUDA)               ELECTRON DESKTOP
        @turboSSebot                   large-v3-turbo                    29 pages React 19
        OpenClaw :18789                OpenWakeWord (jarvis 0.7)         FastAPI WS :9742
               |                       VAD silero 16kHz                        |
               |                               |                               |
               +-------------------------------+-------------------------------+
                                               |
                                    +----------v-----------+
                                    |   VOICE CORRECTION    |
                                    |   3,895 entries       |
                                    |   2,628 corrections   |
                                    |   301 dominos         |
                                    |   1,078 triggers      |
                                    |   106 phonetics       |
                                    |   153 fillers         |
                                    |   678 implicits       |
                                    +----------+-----------+
                                               |
                                    +----------v-----------+
                                    |   DISPATCH ENGINE     |
                                    |   dispatch_engine.py  |
                                    |   622 lignes          |
                                    |   9-step pipeline     |
                                    +----------+-----------+
                                               |
               +-------------------------------+-------------------------------+
               |               |               |               |               |
        QUALITY GATE    PROMPT OPTIMIZER  EVENT STREAM    SELF IMPROVEMENT
        6 gates         agent_prompt_     SSE pub/sub     5 action types
        (length,         optimizer.py     10 topics       (route_shift,
         structure,                                        temp_adjust,
         relevance,                                        tokens_adjust,
         confidence,                                       gate_tune,
         latency,                                          prompt_enhance)
         hallucination)
```

---

## Couche 1 — Entrees (Input Layer)

### 1.1 Whisper STT (Speech-to-Text)

```
Microphone / Telegram vocal
    |
    v
OpenWakeWord (mot-cle "jarvis", seuil 0.7)
    |
    v
VAD silero (Voice Activity Detection, 16kHz, chunks 512)
    |
    v
faster-whisper large-v3-turbo (CUDA, RTX 3080)
    - Modele: large-v3-turbo (Q8, ~1.5GB VRAM)
    - Langue: fr
    - Beam size: 5
    - Latence: <2s (commandes connues <0.5s via cache LRU 200)
    |
    v
Texte brut transcrit
```

**Fichiers**: `src/whisper_worker.py`, `src/vad.py`, `src/wake_word.py`

### 1.2 Voice Correction Pipeline

```
Texte brut transcrit
    |
    v
voice_correction.py (3,895 entries)
    |
    +-- Phonetic corrections (106 regles, 19 vagues)
    |   Ex: "jarvisse" → "jarvis", "cluester" → "cluster"
    |
    +-- Filler removal (153 fillers, 8 vagues)
    |   Ex: "euh", "hein", "ben", "du coup"
    |
    +-- Implicit resolution (678 implicits, 67 vagues)
    |   Ex: "fais-le" → derniere commande, "encore" → repeter
    |
    +-- Alias expansion (2,628 corrections, 120 vagues)
    |   Ex: "scan" → "scan trading complet", "mails" → "lis mes mails"
    |
    +-- Param pattern extraction (28 patterns)
    |   Ex: "{n} pourcent", "volume a {level}", "ping {host}"
    |
    v
Texte corrige + intent + parametres
```

**Tables DB**: `voice_corrections` (etoile.db + jarvis.db)

### 1.3 Telegram Bot (@turboSSebot)

```
Telegram API (long polling getUpdates)
    |
    v
canvas/telegram-bot.js
    |
    +-- /status → health cluster
    +-- /health → diagnostic complet
    +-- /consensus → vote pondere
    +-- /model → info modeles charges
    +-- /stats → statistiques usage
    +-- /help → liste commandes
    +-- Texte libre → POST /chat → dispatch engine
    +-- Vocal OGG → ffmpeg decode → faster-whisper STT → dispatch engine
    |
    v
Reponse texte + vocal (OGG Opus via win_tts.py)
```

**Securite**: chat_id whitelist (2010747443), split 4096 chars

### 1.4 Electron Desktop (29 pages)

```
Electron 33 + React 19 + Vite 6
    |
    v
FastAPI WebSocket :9742 (python_ws/server.py, 5,221 lignes, 513 endpoints)
    |
    Pages:
    ├── DashboardPage      — Vue d'ensemble systeme
    ├── ChatPage           — Interface chat IA
    ├── TradingPage        — Trading MEXC
    ├── VoicePage          — Controle vocal
    ├── LMStudioPage       — Gestion modeles
    ├── SettingsPage        — Configuration
    ├── DictionaryPage     — Dictionnaire vocal
    ├── PipelinePage       — Gestion pipelines
    ├── ToolboxPage        — Outils MCP
    ├── LogsPage           — Logs systeme
    ├── OrchestratorPage   — Orchestration agents
    ├── MemoryPage         — Memoire episodique
    ├── MetricsPage        — Metriques cluster
    ├── AlertsPage         — Alertes et notifications
    ├── WorkflowPage       — Workflows visuels
    ├── HealthPage         — Sante systeme
    ├── ResourcePage       — Ressources CPU/RAM/GPU
    ├── SchedulerPage      — Planificateur taches
    ├── GatewayPage        — OpenClaw Gateway
    ├── InfraPage          — Infrastructure cluster
    ├── MeshPage           — Mesh multi-noeuds
    ├── ProcessesPage      — Processus Windows
    ├── QueuePage          — File d'attente taches
    ├── ServicesPage       — Services Windows
    ├── SnapshotsPage      — Snapshots systeme
    ├── SystemPage         — Info systeme
    ├── TerminalPage       — Terminal integre
    ├── AutomationPage     — Automatisation
    └── NotificationsPage  — Centre notifications
```

**Build**: Portable 72.5 MB | NSIS 80 MB | Launcher: `launchers/JARVIS.bat`

---

## Couche 2 — Dispatch Engine (Cerveau)

### 2.1 Pipeline 9 Etapes

```
Step 1: HEALTH CHECK
    └── Verifie les noeuds disponibles (M1/M2/M3/OL1)
    └── Thermal check GPU (75C warning / 85C critical)

Step 2: CLASSIFY
    └── commander.py: M1 qwen3-8b (3-45ms) + fallback heuristique
    └── Types: code, analyse, trading, systeme, web, simple, reasoning

Step 3: MEMORY ENRICHMENT
    └── agent_episodic_memory.py: contexte des interactions precedentes
    └── Injecte historique pertinent dans le prompt

Step 3b: PROMPT OPTIMIZATION
    └── agent_prompt_optimizer.py: ameliore le prompt automatiquement
    └── Techniques: precision, structure, contexte, contraintes

Step 4: ROUTE SELECTION
    └── Matrice de routage dynamique (22 scenarios, 58 regles)
    └── Poids auto-ajustes par self_improvement.py
    └── pattern_agents.py: 20 patterns hardcodes + 78 dynamiques

Step 5: DISPATCH
    └── Appel REST vers le noeud selectionne
    └── Fallback cascade si echec: OL1→M1→M3 (circuit breaker 3 fails/60s)
    └── dynamic_agents.py: 78 patterns supplementaires depuis DB

Step 6: QUALITY GATE
    └── quality_gate.py: 6 gates (length, structure, relevance, confidence, latency, hallucination)
    └── Score 0.0-1.0, retry_recommended si < seuil

Step 7: FEEDBACK LOOP
    └── agent_feedback_loop.py: enregistre qualite + latence
    └── self_improvement.py: analyse tendances, suggere ameliorations

Step 8: EPISODIC STORE
    └── Sauvegarde dans agent_episodic_memory
    └── Pattern, prompt, reponse, qualite, noeud, timestamp

Step 9: EVENT EMISSION
    └── event_stream.py: SSE pub/sub (topics: dispatch, pipeline, alert)
    └── Dashboard + alertes temps reel
```

### 2.2 Pattern Agents (98 total)

```
HARDCODED (20 patterns — pattern_agents.py):
    ├── simple          — Questions simples (OL1 qwen3:1.7b)
    ├── analysis        — Analyses complexes (M1 qwen3-8b)
    ├── code            — Generation code (M1)
    ├── code_review     — Revue code (M1/OL1)
    ├── debug           — Debug (M1/M2)
    ├── architecture    — Architecture (M1/OL1)
    ├── trading         — Trading (OL1/M1)
    ├── system          — Windows system (M1)
    ├── security        — Securite (M1/OL1)
    ├── math            — Math/calcul (M1)
    ├── reasoning       — Raisonnement (M1/M2)
    ├── web_search      — Recherche web (OL1)
    ├── consensus       — Consensus multi-IA
    ├── embedding       — Embedding (M1)
    ├── documentation   — Documentation (M1)
    ├── refactoring     — Refactoring (M1/OL1)
    ├── testing         — Tests (M1/OL1)
    ├── database        — Base de donnees (M1)
    ├── networking      — API/HTTP (M1)
    └── creative        — Creatif (M1/OL1)

DYNAMIC (78 patterns — dynamic_agents.py + etoile.db):
    ├── task-router         — Classificateur central (M1, prio 1)
    ├── quick-dispatch      — Ultra-rapide <1s (OL1, prio 2)
    ├── code-champion       — Expert code (M1, prio 3)
    ├── deep-reasoning      — Raisonnement profond (M2 deepseek-r1, prio 4)
    ├── analysis-engine     — Comparaisons, rapports (M1, prio 3)
    ├── system-ops          — GPU, services, monitoring (M1, prio 3)
    ├── win_*               — 17 patterns Windows
    ├── jarvis_*            — 17 patterns JARVIS
    ├── ia_*                — 12 patterns IA autonome
    ├── cw-win/*jarvis/*ia  — Patterns COWORK
    └── discovered-*        — Auto-crees par pattern_evolution.py
```

### 2.3 Nodes Configuration (4 noeuds)

```
NODES = {
    "M1":       { host: "127.0.0.1:1234",       model: "qwen3-8b",                   weight: 1.8, api: "lm_studio" },
    "M2":       { host: "192.168.1.26:1234",     model: "deepseek-r1-0528-qwen3-8b",  weight: 1.5, api: "lm_studio" },
    "M3":       { host: "192.168.1.113:1234",    model: "deepseek-r1-0528-qwen3-8b",  weight: 1.2, api: "lm_studio" },
    "OL1":      { host: "127.0.0.1:11434",       model: "qwen3:1.7b",                 weight: 1.3, api: "ollama"    },
}

LM Studio API:  POST /api/v1/chat  { model, input: "/nothink\nPROMPT", temperature, max_output_tokens }
Ollama API:     POST /api/chat      { model, messages: [{role,content}], stream: false, think: false }
```

---

## Couche 3 — Cluster IA (Hardware)

### 3.1 Machine M1 — PC Principal (MASTER)

```
+---------------------------------------------------------------+
|  M1 — PC PRINCIPAL (127.0.0.1 / 127.0.0.1)                    |
|                                                                |
|  GPU 0: RTX 3080 10GB    — LM Studio primary compute          |
|  GPU 1: RTX 2060 12GB    — LM Studio secondary + Whisper CUDA |
|  GPU 2: GTX 1660S 6GB    — LM Studio compute pool             |
|  GPU 3: GTX 1660S 6GB    — LM Studio compute pool             |
|  GPU 4: GTX 1660S 6GB    — LM Studio compute pool             |
|  GPU 5: GTX 1660S 6GB    — LM Studio compute pool             |
|  VRAM Total: 46 GB                                             |
|                                                                |
|  SERVICES:                                                     |
|  ├── LM Studio :1234                                           |
|  │   └── qwen3-8b (65 tok/s, Q4_K_M, /nothink obligatoire)   |
|  ├── Ollama :11434 (OLLAMA_NUM_PARALLEL=3)                    |
|  │   ├── qwen3:14b (23 tok/s, local)                          |
|  │   └── qwen3:1.7b (84 tok/s, local)                         |
|  ├── FastAPI WS :9742 (backend Electron)                       |
|  ├── Dashboard :8080 (web standalone)                          |
|  ├── OpenClaw Gateway :18789 (Telegram + agents)               |
|  ├── Gemini Proxy :18791 (gemini-proxy.js)                     |
|  ├── n8n :5678 (20 workflows)                                  |
|  └── CDP :9222 (Comet/Chrome/Edge browser pilot)               |
+---------------------------------------------------------------+
```

### 3.2 Machine M2 — PC Secondaire (CODE)

```
+---------------------------------------------------------------+
|  M2 — PC SECONDAIRE (192.168.1.26)                            |
|                                                                |
|  GPU: 3x GPU — 24 GB VRAM total                               |
|  VRAM Total: 24 GB                                             |
|                                                                |
|  SERVICES:                                                     |
|  └── LM Studio :1234                                           |
|      └── deepseek-r1-0528-qwen3-8b (reasoning, 44 tok/s)     |
|          ctx 27k, max_output_tokens >= 2048                    |
|          Output: reasoning + message blocks                    |
+---------------------------------------------------------------+
```

### 3.3 Machine M3 — PC Tertiaire (GENERAL)

```
+---------------------------------------------------------------+
|  M3 — PC TERTIAIRE (192.168.1.113)                            |
|                                                                |
|  GPU: 1x GPU — 8 GB VRAM                                      |
|  VRAM Total: 8 GB                                              |
|                                                                |
|  SERVICES:                                                     |
|  └── LM Studio :1234                                           |
|      └── deepseek-r1-0528-qwen3-8b (reasoning fallback)      |
|          ctx 25k, 33 tok/s, sequentiel                        |
+---------------------------------------------------------------+
```

### 3.4 Cloud Services (optionnels)

```
OLLAMA CLOUD (via 127.0.0.1:11434, think:false obligatoire):
    ├── minimax-m2.5:cloud      — Web search
    ├── glm-5:cloud             — General 7 tok/s
    └── kimi-k2.5:cloud         — Reasoning
    (Note: gpt-oss, devstral, glm-4.7, qwen3-coder etc. supprimés 2026-03)

GEMINI (via gemini-proxy.js):
    ├── gemini-3-pro             — Architecture, vision, longs docs
    └── gemini-3-flash           — Fallback rapide
    Timeout: 2min, fallback auto pro→flash

CLAUDE (via claude-proxy.js):
    ├── opus                     — Raisonnement profond
    ├── sonnet                   — Equilibre
    └── haiku                    — Rapide
    Timeout: 2min, sanitisation env CLAUDE*
```

---

## Couche 4 — Outils et Integrations

### 4.1 MCP Server (mcp_server.py — 6,217 lignes, 597 handlers)

```
CATEGORIES DE HANDLERS:
    ├── Cluster Management      (60+)  — health_check, model_load/unload, node_status, dispatch, routing
    ├── Trading Pipeline        (80+)  — turbo_scan, sniper, orderbook, consensus_5ia, positions, PnL
    ├── Voice & TTS             (40+)  — tts_speak, whisper_transcribe, correction, pipeline, cache
    ├── SQL Database            (50+)  — query, insert, export, backup, vacuum, reindex, schema
    ├── Telegram Bot            (30+)  — send_message, send_voice, get_updates, commands
    ├── Consensus & Mesh        (40+)  — vote_pondere, aggregate, multi_model, scenario_weights
    ├── Dashboard & Metrics     (60+)  — pages REST API, websocket, alerts, workflows, health
    ├── n8n & Automation        (30+)  — trigger_workflow, webhook, cron, pipeline execution
    ├── Skills & Brain          (40+)  — learn, execute, index, search, pattern, memory
    ├── Self Improvement        (15+)  — analyze, suggest, apply, history, stats
    ├── Dynamic Agents          (15+)  — list, dispatch, load, patterns, registry
    ├── Cowork Proactive        (15+)  — detect_needs, plan, execute, anticipate
    ├── Reflection Engine       (12+)  — reflect, timeline, summary, insights
    ├── Pattern Evolution       (12+)  — analyze_gaps, auto_create, evolve, history
    ├── Browser Pilot           (20+)  — navigate, click, screenshot, evaluate, CDP
    └── Windows System          (40+)  — powershell, services, registry, processes, GPU, network
```

### 4.2 SDK Tools (tools.py — 2,582 lignes, 181 fonctions)

```
CATEGORIES D'OUTILS SDK:
    ├── Cluster IA        (15)  — lm_query, consensus, bridge_mesh, bridge_query, gemini_query, ollama_query
    ├── Windows System    (15)  — powershell_run, system_info, open_app, close_app, gpu_info
    ├── Brain/Skills      (10)  — learn_skill, execute_skill, brain_index, brain_search
    ├── Trading Bridge     (8)  — run_script, trading_signal, sniper_execute
    ├── Filesystem         (7)  — read_file, write_file, list_dir, search_files
    ├── Bridge Multi-Nds  (12)  — mesh_parallel, route_smart, fallback_chain
    ├── Consensus/Mesh    (10)  — consensus_vote, mesh_query, aggregate_results
    ├── SQL Tools          (3)  — sql_query, sql_insert, sql_export
    ├── Browser/Comet      (8)  — navigate, screenshot, click, comet_pilot, cdp_connect
    ├── Self Improvement   (4)  — analyze, suggest, apply, history
    ├── Dynamic Agents     (3)  — list, dispatch, load
    ├── Cowork Proactive   (3)  — detect_needs, plan, execute
    └── Utilities         (83)  — tts_speak, screenshot, clipboard, hotkey, scheduler, notifications
```

### 4.3 REST API (server.py — 5,221 lignes, 513 endpoints)

```
GROUPES D'ENDPOINTS:
    ├── /api/health             — Health check systeme
    ├── /api/cluster/*          — Noeuds, modeles, dispatch, routing
    ├── /api/trading/*          — Scan, signaux, portfolio, backtest
    ├── /api/voice/*            — TTS, STT, corrections, pipelines
    ├── /api/commands/*         — Commandes vocales, skills, dominos
    ├── /api/database/*         — Queries, exports, backups, vacuum
    ├── /api/pipelines/*        — Dictionary, tests, execution
    ├── /api/consensus/*        — Vote, scenarios, weights
    ├── /api/telegram/*         — Messages, status, history
    ├── /api/dashboard/*        — Widgets, metriques, alertes
    ├── /api/browser/*          — Navigation, CDP, screenshots
    ├── /api/self_improvement/* — Analyse, suggestions, application
    ├── /api/dynamic_agents/*   — Listing, dispatch, patterns
    ├── /api/cowork_proactive/* — Besoins, plans, execution
    ├── /api/reflection/*       — Insights, timeline, summary
    ├── /api/evolution/*        — Gaps, creation, evolution
    ├── /api/tts                — TTS HTTP endpoint (MP3 bytes)
    └── /ws                     — WebSocket Electron
```

### 4.4 TTS Pipeline (Text-to-Speech)

```
Texte reponse
    |
    v
clean_text_for_speech()
    — Supprime ponctuation, symboles, emojis
    — Normalise nombres et abbreviations
    |
    v
Edge TTS (edge-tts Python package)
    — Voix: fr-FR-DeniseNeural (femme, Neural)
    — Format: MP3 24kHz
    — Streaming: chunks async
    |
    v
ffmpeg post-processing
    — Conversion: MP3 → OGG Opus (96kbps, 48kHz)
    — Volume boost: +1.3
    — Compresseur audio
    |
    v
Sortie:
    ├── Telegram sendVoice (OGG Opus)
    ├── Telegram sendAudio (MP3 192k)
    ├── Local playback (ffplay)
    └── HTTP /api/tts (MP3 bytes pour Canvas UI)

Scripts: dev/win_tts.py, src/tts_streaming.py
Voix: fr-FR-DeniseNeural (permanent, voix femme)
Reference audio: F:\BUREAU\voix valider.ogg
```

### 4.5 Trading Pipeline

```
MEXC Futures 10x
    |
    +-- Paires (10): BTC ETH SOL SUI PEPE DOGE XRP ADA AVAX LINK
    +-- Params: TP 0.4% | SL 0.25% | Size 10 USDT | Score min 70/100
    |
    v
Pipeline v2.3 GPU:
    1. Data Collection (OL1 minimax web search + MEXC API)
    2. Technical Analysis (100 strategies)
    3. IA Consensus (4 modeles: M1 + M2 + OL1 + M3)
    4. Risk Management (drawdown, correlation, position sizing)
    5. Signal Generation (score 0-100, seuil 70)
    6. Execution (DRY_RUN=false, MEXC API)
    7. Monitoring (PnL, positions, alertes)

DBs: sniper.db (coins, signaux, categories, strategies)
Scripts: src/trading.py, src/trading_engine.py, src/trading_sentinel.py
```

### 4.6 OpenClaw Gateway

```
Port 18789 — HTTP Gateway
    |
    +-- 78 agents (DB agent_patterns)
    +-- 7 providers:
    │   ├── lm-m1 (qwen3-8b, local)
    │   ├── lm-m2 (deepseek-r1, local)
    │   ├── lm-m3 (deepseek-r1, local)
    │   ├── ollama (12 modeles: 2 local + 10 cloud)
    │   ├── gemini (pro/flash)
    │   ├── claude (opus/sonnet/haiku)
    │   └── qwen-portal
    +-- Telegram polling (getUpdates → POST /chat → sendMessage)
    +-- Crons: 316+ taches planifiees (5min → 24h)
    +-- Scripts: 438 cowork (dev/*.py)
    +-- Cluster race: 5 noeuds parallele, premier repond gagne
```

### 4.7 n8n Workflows

```
Port 5678 — n8n v2.4.8
    |
    +-- 20 workflows automation
    +-- 3 MCP tools integres
    +-- Triggers: webhook, cron, manual
    +-- Actions: HTTP, Script, Email, Telegram
```

### 4.8 Browser Pilot (CDP)

```
Chrome DevTools Protocol :9222
    |
    +-- Auto-detection:
    │   1. Comet (Perplexity) %LOCALAPPDATA%\Perplexity\Comet\Application\comet.exe
    │   2. Chrome: Program Files\Google\Chrome\chrome.exe
    │   3. Edge: Program Files (x86)\Microsoft\Edge\msedge.exe
    |
    +-- browser_pilot.py: pilotage autonome (navigate, click, fill, screenshot)
    +-- voice_browser_nav.py: navigation vocale ("ouvre github", "cherche X")
    +-- browser_navigator.py: Playwright persistent, 17 commandes
```

### 4.9 Perplexity MCP Connector

```
Connecteur MCP "4" via OpenClaw Gateway
    |
    +-- 23 outils directs:
    │   ├── lm_query (M1 qwen3-8b)
    │   ├── ollama_query (cloud modeles)
    │   ├── gemini_query
    │   ├── consensus (vote pondere)
    │   ├── trading_scan
    │   ├── system_info
    │   └── ... (17 autres)
    |
    +-- Deep Research: peut generer du code deploye directement dans src/
    +-- Voit: OL1 (qwen3:1.7b)
    +-- Ne voit PAS: M1/M2/M3 (IPs locales non exposees)
```

---

## Couche 5 — Intelligence Autonome

### 5.1 Self-Improvement Loop

```
self_improvement.py (430 lignes)
    |
    1. ANALYZE
    │   └── Query quality_gate_log + dispatch_pipeline_log
    │   └── Detecte tendances: baisses qualite, latence, echecs
    |
    2. SUGGEST
    │   └── 5 types d'actions:
    │       ├── route_shift: changer le noeud pour un pattern
    │       ├── temp_adjust: modifier temperature du modele
    │       ├── tokens_adjust: ajuster max_output_tokens
    │       ├── gate_tune: recalibrer seuils quality gate
    │       └── prompt_enhance: ameliorer prompts systeme
    |
    3. APPLY (auto si critical/high priority)
    │   └── Modifie routing, parametres, seuils en DB
    |
    4. LOG
    │   └── self_improvement_log (etoile.db)
```

### 5.2 Pattern Evolution

```
pattern_evolution.py (349 lignes)
    |
    1. ANALYZE GAPS
    │   ├── _find_misclassified(): prompts generiques matchant des clusters specifiques
    │   ├── _find_underperforming(): patterns avec qualite < 0.5
    │   └── _find_redundant(): patterns similaires fusionnables
    |
    2. 10 KEYWORD CLUSTERS
    │   deployment, testing, documentation, database, networking,
    │   frontend, infrastructure, nlp, visualization, automation
    |
    3. AUTO-CREATE PATTERNS
    │   └── Si >= 3 prompts matchent un cluster non-couvert → cree pattern en DB
    |
    4. EVOLVE PATTERNS
    │   └── Si qualite < 0.5 → suggere changement modele/noeud
    |
    5. LOG
    │   └── pattern_evolution_log (etoile.db)
```

### 5.3 Reflection Engine

```
reflection_engine.py (445 lignes)
    |
    5 AXES D'ANALYSE:
    ├── Quality    — Tendances qualite, pires patterns
    ├── Performance — Latence pipeline, noeuds les plus lents
    ├── Reliability — Taux succes, frequence fallbacks
    ├── Efficiency  — Utilisation noeuds, usage enrichissement
    └── Growth      — Nombre patterns, taux utilisation
    |
    Health Score: 0-100 (weighted average des 5 axes)
    Timeline Analysis: fenetre glissante configurable
    |
    └── reflection_log (etoile.db)
```

### 5.4 Cowork Proactive Engine

```
cowork_proactive.py (349 lignes)
    |
    1. DETECT NEEDS (4 sources)
    │   ├── quality_gate: qualite basse detectee
    │   ├── health: noeuds offline ou lents
    │   ├── dispatch: patterns non-couverts
    │   └── self_improvement: suggestions auto-amelioration
    |
    2. PLAN EXECUTION
    │   └── 10 categories → scripts cowork:
    │       quality→performance_tracker, health→health_checker,
    │       dispatch→dispatch_optimizer, etc.
    |
    3. EXECUTE
    │   └── Lance scripts via CoworkBridge (subprocess)
    |
    4. ANTICIPATE
    │   └── Predictions basees sur tendances
    |
    └── cowork_proactive_log (etoile.db)
```

### 5.5 Dynamic Agents

```
dynamic_agents.py (311 lignes)
    |
    Charge 78 patterns depuis agent_patterns (etoile.db)
    |
    17 CATEGORY PROMPTS:
    ├── win_*         — Expert Windows system
    ├── jarvis_*      — Expert JARVIS core
    ├── ia_*          — Expert IA autonome
    ├── cw-win/*      — Cowork Windows
    ├── cw-jarvis/*   — Cowork JARVIS
    ├── cw-ia/*       — Cowork IA
    ├── discovered-*  — Auto-decouverts
    ├── fix_*         — Corrections
    └── cross_*       — Cross-domain
    |
    MODEL_TO_NODE mapping:
    ├── qwen3-8b              → M1
    ├── deepseek-r1-0528      → M2
    ├── deepseek-r1-0528      → M3
    └── qwen3:1.7b            → OL1
    |
    register_to_registry(): inject dans PatternAgentRegistry live
```

---

## Couche 6 — Donnees (Persistance)

### 6.1 Bases de Donnees

```
etoile.db (19 tables, principal)
    ├── map                    — Cartographie systeme (2,600+ entries)
    ├── agent_patterns         — 78 patterns agents
    ├── agent_dispatch_log     — Historique dispatch (classified_type, node, quality_score, latency_ms)
    ├── agent_episodic_memory  — Memoire episodique
    ├── agent_feedback         — Feedback qualite
    ├── agent_semantic_facts   — Faits semantiques
    ├── agent_improvement_reports — Rapports amelioration
    ├── auto_scale_log         — Logs autoscaling
    ├── cowork_execution_log   — Execution scripts cowork
    ├── cowork_proactive_log   — Logs proactivite
    ├── cowork_script_mapping  — Mapping scripts ↔ patterns
    ├── dispatch_pipeline_log  — Logs pipeline dispatch
    ├── ensemble_log           — Logs ensemble voting
    ├── pattern_evolution_log  — Evolution patterns
    ├── pattern_lifecycle_log  — Cycle de vie patterns
    ├── prompt_optimization_log — Optimisation prompts
    ├── quality_gate_log       — Logs quality gate
    ├── reflection_log         — Logs reflection engine
    └── self_improvement_log   — Logs auto-amelioration

jarvis.db (tables vocales + validation)
    ├── commands         — 443 commandes vocales
    ├── skills           — 108 skills persistants
    ├── scenarios        — 475 scenarios test
    ├── validation_cycles — 500 resultats validation
    ├── voice_corrections — 2,628 corrections
    ├── node_metrics     — Metriques par noeud
    ├── benchmark_runs   — Benchmarks
    └── benchmark_results — Resultats benchmarks

sniper.db (trading)
    ├── coins            — Paires crypto
    ├── signals          — Signaux trading
    ├── categories       — Categories strategies
    └── strategies       — 100+ strategies

finetuning.db (ML)
    ├── examples         — 17,152 examples training
    ├── evaluations      — Resultats evaluation
    └── (6 autres tables)
```

---

## Couche 7 — Fichiers Source (226 modules)

### 7.1 Repartition par Domaine

```
src/ — 226 modules Python, 84,582 lignes
    |
    CORE (15 modules):
    ├── dispatch_engine.py      — Cerveau: pipeline 9 etapes (622 lignes)
    ├── pattern_agents.py       — 20 patterns hardcodes + registry (~600 lignes)
    ├── commander.py            — Classification taches + thermal
    ├── brain.py                — Cerveau central JARVIS
    ├── agents.py               — 7 agents Claude SDK
    ├── config.py               — Configuration globale
    ├── executor.py             — Execution commandes
    ├── commands.py             — Registry commandes
    ├── skills.py               — Skills engine
    ├── voice.py                — Pipeline vocale
    ├── voice_correction.py     — Corrections vocales
    ├── whisper_worker.py       — Whisper STT CUDA
    ├── vad.py                  — Voice Activity Detection
    ├── wake_word.py            — OpenWakeWord
    └── output.py               — Output formatting

    CLUSTER & ROUTING (25 modules):
    ├── adaptive_router.py, routing_optimizer.py, smart_dispatcher.py
    ├── load_balancer.py, rate_limiter.py, circuit_breaker.py
    ├── service_registry.py, service_mesh.py, health_probe.py
    ├── cluster_intelligence.py, cluster_diagnostics.py, cluster_self_healer.py
    ├── agent_auto_scaler.py, auto_scaler.py, auto_tune.py
    └── ...

    INTELLIGENCE AUTONOME (20 modules):
    ├── self_improvement.py, pattern_evolution.py, reflection_engine.py
    ├── dynamic_agents.py, cowork_proactive.py, cowork_bridge.py
    ├── agent_episodic_memory.py, agent_feedback_loop.py
    ├── agent_prompt_optimizer.py, agent_self_improve.py
    ├── prediction_engine.py, auto_developer.py
    ├── autonomous_loop.py, autonomous_dev_agent.py
    └── ...

    WINDOWS (40+ modules):
    ├── windows.py, process_manager.py, power_manager.py
    ├── registry_manager.py, firewall_controller.py, service_controller.py
    ├── disk_health.py, disk_monitor.py, gpu_monitor.py, gpu_guardian.py
    ├── network_monitor.py, network_scanner.py, wifi_manager.py
    ├── bluetooth_manager.py, usb_monitor.py, usb_device_manager.py
    ├── display_manager.py, screen_capture.py, screen_resolution_manager.py
    ├── audio_controller.py, audio_device_manager.py, volume_manager.py
    ├── clipboard_manager.py, font_manager.py, shortcut_manager.py
    ├── startup_manager.py, scheduled_task_manager.py, printer_manager.py
    ├── defender_status.py, installed_apps_manager.py
    └── ... (20+ autres)

    TRADING (5 modules):
    ├── trading.py, trading_engine.py, trading_sentinel.py
    ├── exchanges.py, signal_formatter.py
    └── sniper.db handlers

    COMMUNICATION (8 modules):
    ├── email_sender.py, notification_hub.py, notification_manager.py
    ├── notifier.py, message_broker.py, webhook_manager.py
    ├── tts_streaming.py, daily_report.py
    └── telegram handlers dans mcp_server.py

    OBSERVABILITY (12 modules):
    ├── metrics.py, metrics_aggregator.py, telemetry_collector.py
    ├── log_aggregator.py, logging_config.py, observability.py
    ├── health_dashboard.py, health_probe.py, health_probe_registry.py
    ├── event_bus.py, event_store.py, event_stream.py
    └── perfcounter.py, performance_counter.py

    DATA & STORAGE (10 modules):
    ├── database.py, data_pipeline.py, data_validator.py
    ├── cache.py, cache_manager.py, queue_manager.py
    ├── secret_vault.py, credential_vault.py, config_vault.py
    └── backup_manager.py

    BROWSER & DESKTOP (6 modules):
    ├── browser_navigator.py, desktop_actions.py
    ├── commands_browser.py, virtual_desktop.py
    ├── window_manager.py, app_launcher.py
    └── theme_controller.py

    MCP & API (5 modules):
    ├── mcp_server.py      — 6,217 lignes, 597 handlers
    ├── mcp_server_sse.py  — SSE transport
    ├── tools.py           — 2,582 lignes, 181 fonctions SDK
    ├── api_gateway.py     — API gateway
    └── perplexity_bridge.py — Connecteur Perplexity

    WORKFLOW & ORCHESTRATION (15 modules):
    ├── workflow_engine.py, state_machine.py, rule_engine.py
    ├── orchestrator.py, orchestrator_v2.py, agent_orchestrator_v3.py
    ├── pipeline_composer.py, chain_resolver.py
    ├── task_queue.py, task_scheduler.py, scheduler_manager.py
    ├── domino_executor.py, domino_pipelines.py
    └── scenarios.py, feature_flags.py

    COWORK (6 modules):
    ├── cowork_bridge.py         — Index 438 scripts, execution
    ├── cowork_proactive.py      — Detection besoins proactive
    ├── cowork_orchestrator.py   — Orchestration scripts
    ├── cowork_agent_config.py   — Config agents cowork
    ├── cowork_master_config.py  — Config master
    └── cowork_perplexity_executor.py — Execution via Perplexity
```

---

## Couche 8 — Tests (2,144 tests, 49 fichiers)

```
tests/ — 49 fichiers Python
    |
    ├── test_pattern_agents.py  — 217 tests (dispatch, patterns, quality, dynamic agents)
    ├── test_phase3.py          —  64 tests
    ├── test_phase4.py          — 100 tests
    ├── test_phase5.py          —  35 tests
    ├── test_phase6-9.py        — 159 tests (40+43+38+38)
    ├── test_phase10-15.py      — 293 tests
    ├── test_phase16-20.py      — 271 tests
    ├── test_phase21-25.py      — 268 tests
    ├── test_phase26-30.py      — 179 tests
    ├── test_phase31-35.py      — 183 tests
    ├── test_phase36-40.py      — 162 tests
    ├── test_phase41-43.py      —  89 tests
    ├── test_agents.py          —  11 tests
    ├── test_cache.py           —  13 tests
    ├── test_config.py          —  22 tests
    ├── test_mcp_tools.py       —  18 tests
    ├── test_security.py        —  27 tests
    ├── test_telegram_bot.py    —  23 tests
    └── test_vad.py             —   7 tests
```

---

## Couche 9 — Services Externes

### 9.1 Ports et Services

```
PORT MAP:
    ├── 1234    — LM Studio (M1 local, M2 192.168.1.26, M3 192.168.1.113)
    ├── 5678    — n8n (workflows automation)
    ├── 8080    — Dashboard web standalone
    ├── 9222    — CDP (Chrome DevTools Protocol — Comet/Chrome/Edge)
    ├── 9742    — FastAPI WebSocket (backend Electron)
    ├── 11434   — Ollama (local + cloud relay)
    ├── 18789   — OpenClaw Gateway (Telegram + agents)
    └── 18791   — Gemini Proxy
```

### 9.2 External APIs

```
    ├── Telegram Bot API  — @turboSSebot (token 8369376863, chat 2010747443)
    ├── MEXC Futures API  — Trading 10x (10 paires crypto)
    ├── Gmail IMAP        — 2 comptes (miningexpert31 + franckdelmas00)
    ├── Gemini API        — Architecture & vision (via gemini-proxy.js)
    ├── Claude API        — Raisonnement profond (via claude-proxy.js)
    ├── Ollama            — 2 modeles locaux (qwen3:14b, qwen3:1.7b)
    ├── Edge TTS          — Synthese vocale DeniseNeural
    └── OpenWakeWord      — Detection mot-cle "jarvis"
```

---

## Couche 10 — Flux de Donnees Complet

```
                                   UTILISATEUR
                                  voix / texte / telegram
                                        |
                        +---------------+---------------+
                        |               |               |
                   MICROPHONE     TELEGRAM BOT      ELECTRON
                        |           :18789           :9742
                        v               |               |
                   WAKE WORD            |               |
                   (jarvis 0.7)         |               |
                        |               |               |
                        v               v               v
                   WHISPER STT    ← ffmpeg decode ←
                   (CUDA, <2s)
                        |
                        v
                VOICE CORRECTION
                (3,895 entries)
                        |
                        v
              +-------- DISPATCH ENGINE --------+
              |   1. Health Check               |
              |   2. Classify (M1 3-45ms)       |
              |   3. Memory Enrichment          |
              |   3b. Prompt Optimization       |
              |   4. Route Selection            |
              |   5. Dispatch to Node           |
              |   6. Quality Gate (6 gates)     |
              |   7. Feedback Loop              |
              |   8. Episodic Store             |
              |   9. Event Emission (SSE)       |
              +---------------------------------+
                        |
            +-----------+-----------+
            |           |           |
         LOCAL       LOCAL       PROXY
      M1/M2/M3    OL1         Gemini
      LM Studio   Ollama      Claude
      :1234       :11434
            |           |           |
            +-----------+-----------+
                        |
                        v
              QUALITY GATE (score 0-1)
                        |
               PASS ----+---- FAIL
                |              |
                v              v
           TTS RESPONSE    RETRY (autre noeud)
           DeniseNeural
           OGG Opus
                |
       +--------+--------+
       |        |        |
    TELEGRAM  ELECTRON  LOCAL
    sendVoice   WS     ffplay
       |        |        |
       v        v        v
              PERSISTANCE
    etoile.db + jarvis.db + sniper.db
    (19+tables) (8+tables) (4 tables)
                |
                v
        SELF-IMPROVEMENT LOOP
        ├── Analyze trends
        ├── Suggest improvements
        ├── Auto-apply critical
        └── Pattern evolution
                |
                v
        COWORK PROACTIVE
        ├── Detect needs
        ├── Plan scripts
        ├── Execute 438 scripts
        └── Anticipate
                |
                v
        REFLECTION ENGINE
        └── 5 axes → Health Score → Insights
```

---

## Chiffres Recapitulatifs

| Composant | Quantite | Detail |
|-----------|----------|--------|
| **GPU** | 10 NVIDIA / 78 GB VRAM | 6 GPU M1 (46GB) + 3 GPU M2 (24GB) + 1 GPU M3 (8GB) |
| **Modeles IA** | 4 local | M1 qwen3-8b + M2 deepseek-r1 + M3 deepseek-r1 + OL1 qwen3:1.7b |
| **Modules src/** | 226 fichiers | 84,582 lignes Python |
| **Tests** | 2,144 fonctions | 49 fichiers test |
| **MCP Handlers** | 597 | mcp_server.py (6,217 lignes) |
| **SDK Tools** | 181 fonctions | tools.py (2,582 lignes) |
| **REST Endpoints** | 513 | server.py (5,221 lignes) |
| **Agent Patterns** | 98 (20 hard + 78 DB) | dispatch vers noeuds optimal |
| **COWORK Scripts** | 438 | dev/ (102 win + 103 jarvis + 66 ia + 167 autres) |
| **Commandes Vocales** | 443 + 1,706 map | jarvis.db + etoile.db |
| **Pipelines** | 656 dictionary + 461 vocal | Multi-etapes executables |
| **Domino Cascades** | 835 / 121 triggers | 11 categories |
| **Corrections Vocales** | 3,895 entries | 120 vagues |
| **Skills** | 108 persistants | etoile.db |
| **Electron Pages** | 29 | React 19 + Vite 6 |
| **Launchers** | 22 | .bat/.ps1 |
| **Scripts utilitaires** | 60 | scripts/ |
| **Databases** | 4 (51+ tables) | etoile.db + jarvis.db + sniper.db + finetuning.db |
| **Crons** | 316+ | 5min → 24h |
| **Plugin Slash Commands** | 43 | jarvis-turbo v3.1 |
| **n8n Workflows** | 20 | Port 5678 |
| **Ports Services** | 8 | 1234, 5678, 8080, 9222, 9742, 11434, 18789, 18791 |

---

*JARVIS Etoile v12.1 — Systeme d'IA distribue autonome multi-GPU — 2026-03-05*
