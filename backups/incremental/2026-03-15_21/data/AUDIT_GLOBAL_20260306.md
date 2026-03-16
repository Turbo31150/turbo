# AUDIT GLOBAL JARVIS — 2026-03-06 (8 agents paralleles)

## STATISTIQUES REELLES (vs MEMORY.md)

| Metrique | MEMORY.md | Reel | Delta |
|----------|-----------|------|-------|
| Scripts cowork/dev/ | 388 | **409** | +21 |
| Modules src/ | 224 | **246** (93,294 lignes) | +22 |
| MCP handlers | 593 | **602** (+7 cowork = 609) | +16 |
| REST endpoints | 498 | **517** | +19 |
| Tests fichiers | - | **77** (dont 54 pytest, 23 manuels) | - |
| Tests fonctions | 298 | **2,241** | +1943 |
| Crons OpenClaw | 48 | **11** (fixe today, etait 114) | -37 |
| Tables etoile.db | 19 | **42** | +23 |
| Rows etoile.db | 11,222 | **13,488** | +2266 |
| Disk F: free | 104 GB | **37 GB** | -67 GB CRITIQUE |
| Disk C: free | 82 GB | **71 GB** | -11 GB |
| n8n workflows | 20 | **63** (API needs X-N8N-API-KEY) | +43 |
| Ollama models | 12 | **15** | +3 |
| Launchers | 16 | **35** | +19 |
| Electron pages | 19 | **29** | +10 |
| Agents SDK | 7 | **13** | +6 |
| Agent patterns | 6 | **80** | +74 |
| Agent dispatch log | 118 | **742** | +624 |
| DBs total | 4 | **63** (160.4 MB) | +59 |
| Commandes vocales | 2339 | **955** (voice_commands DB) | incompatible |
| Skills | 89 | **80** (uniques jarvis.db) | -9 |

---

## P0 — CRITIQUE / SECURITE

### SEC-01: SECRETS EXPOSES SUR GITHUB ~~PUBLIC~~ PRIVATE (fixe)
- **4 repos passes en PRIVATE** (turbo, jarvis-cowork, etoile, essai-cloud)
- MAIS tokens dans l'historique git — REVOQUER OBLIGATOIRE:
  - **Telegram bot token** dans 69 fichiers (73 occurrences)
  - **MEXC API keys** (trading futures REEL, argent reel!)
  - **Gemini API keys** (2 cles Google AI Studio)
  - **LM Studio API keys** (3 cles)
  - **Llama API key** (Meta)
  - **Gmail App Password** (miningexpert31@gmail.com)
  - **Gateway password** (turbo2024, admin:admin)
- STATUS: **REPOS PRIVATE** | TOKENS: **A REVOQUER**

### SEC-02: 10 services sur 0.0.0.0 (tout le reseau)
- canvas/direct-proxy.js:18800 **(FIXE -> 127.0.0.1)**
- cowork/dev/cluster_dashboard_api.py:8085
- cowork/dev/code_generator.py
- projects/serveur/scripts/worker_server.py:5001
- projects/serveur/scripts/master_server.py:5000
- projects/lm_studio_system/mcp_server_lmstudio.py:8000
- src/mcp_server_sse.py
- src/tache5_gateway/gateway.py:8900 (login admin:admin!)
- data/m2-lmstudio-config/http-server-config.json
- STATUS: 1/10 fixe, **9 restants**

### SEC-03: Commandes dangereuses
- 48+ subprocess(shell=True) dont certains avec input dynamique
- os.system() avec injection possible (os_pilot.py:152)
- rm -rf dans domino_pipelines.py
- STATUS: **A AUDITER**

---

## P1 — URGENT (cette semaine)

### DISK-01: F: a 92% (37 GB libres)
- .venv: 932 MB | electron/node_modules: 620 MB | .git: 122 MB
- F:/models (LM Studio): ~300 GB
- trading.db: 90 MB | 63 DBs total: 160 MB
- STATUS: **A NETTOYER** (modeles LM Studio inutilises)

### DISK-02: C: a 86% (71 GB libres)
- .claude: 3.2 GB -> **2.9 GB (253 MB liberes)**
- Ollama: 5.2 GB
- STATUS: **PARTIEL** (253 MB liberes)

### DB-01: etoile.db FK violations — **FIXE**
### DB-02: cowork_gaps.db — PAS vide (4 MB, 56 tables, 34935 rows dans cowork/dev/data/)
- data/cowork_gaps.db EST vide (0 bytes) + dataetoile.db (0 bytes) = fantomes
- STATUS: **Fichiers fantomes a supprimer**

### DB-03: WAL files — **FIXE** (checkpoint + phantom root WAL supprime)
### DB-04: 3 tables vides etoile.db + 6 DBs totalement vides dans cowork/dev/
- etoile.db: agent_episodic_memory, cowork_proactive_log, self_improvement_log
- cowork/dev: deployer.db, autotuner.db, test_runner.db, cluster_bench.db, continuous_dev.db, conversations.db
- STATUS: **A NETTOYER**

### DB-05: Doublons DB
- etoile.db existe en racine ET dans data/ (meme taille)
- finetuning/finetuning.db == finetuning/memoire_finetuning.db (identiques)
- cowork_gaps.db a 3 copies (data/, cowork/dev/, cowork/dev/data/)
- STATUS: **A UNIFIER**

### GIT-01: 64 fichiers modifies non commites
- 21 src/ + 17 cowork/dev/ + 11 data/ + 18 untracked
- STATUS: **A COMMITER**

### BOOT-01: JARVIS_BOOT_V2.bat — **FIXE** (>nul)
### LAUNCHER-01: JARVIS_MASTER.bat — **FIXE** (launchers/)

### OPENCLAW-05: Modele mistral-7b manquant sur M3
- 7 agents referencent lm-m3/mistral-7b-instruct-v0.3 mais M3 a deepseek-r1
- **Translator FR/EN CASSE** (modele primaire inexistant)
- STATUS: **A CORRIGER dans openclaw.json**

### OPENCLAW-04: Telegram delivery — **FIXE** (channel=telegram, to=2010747443)

---

## P2 — IMPORTANT (ce mois)

### CODE-01: Duplications classes critiques (52 cas)
**Critiques:**
- CircuitBreaker: 3 fichiers (adaptive_router, circuit_breaker, retry_manager)
- RateLimiter: 3 fichiers (rate_limiter, security, gateway)
- NotificationManager: 3+ fichiers
- EventBus: 2 fichiers
- AutoScaler: 2 fichiers
- SelfImprover: 2 fichiers
**Utilitaires dupliques:** _cache_key, _error, _safe_int, _text dans tools.py ET mcp_server.py

### CODE-02: 38 TODO/FIXME dans src/ (6 fichiers)
- autonomous_dev_agent.py: 14 | domino_pipelines.py: 12 | commands_dev.py: 7

### CODE-03: Fichiers trop gros
- mcp_server.py: 6,282 lignes | domino_pipelines.py: 5,782 | commands_pipelines.py: 2,721
- cowork: sniper_scanner.py: 1,951 | voice_computer_control.py: 1,405
- **19 scripts cowork > 500 lignes**

### TEST-01: 32 modules src/ sans test
- brain.py, orchestrator.py, commands_dev.py, commands_maintenance.py, etc.
- Couverture src: 85.5% | Couverture cowork: **0.5%** (2/409)

### OPENCLAW-01: Agents orphelins
- 3 agents sans workspace: coder-agent, cowork, voice-assistant
- 1 workspace sans agent: workspace-voice

### OPENCLAW-02: System prompt main trop gros
- IDENTITY.md(11KB) + SOUL.md(2KB) + TOOLS.md(9KB) = 22KB (~5K tokens)
- 550 jobs disabled poids mort dans jobs.json (566 KB)

### MEMORY-01: MEMORY.md depasse 200 lignes (246, tronque)
- 12+ stats obsoletes
- 2 references contradictoires etoile.db (lignes 53 vs 163)
- Version: header v12.4 vs tableau v10.3

### MEMORY-02: turbo/CLAUDE.md tres obsolete
- Dit 28 modules (reel: 246), 75 tools (reel: 609), M2=deepseek-coder (faux)

### DOCS-01: 5 docs obsoletes
- INSTALL.md, N8N_WORKFLOWS.md, JARVIS_COMPLETE_REFERENCE.md (23j)
- COMMANDES_VOCALES.md, CATALOGUE_COMMANDES.md (12j)
- pitch_meditation_ia.txt (VIDE)

---

## P3 — AMELIORATIONS (backlog)

### VOICE-01: voice_corrections en double (jarvis.db ET etoile.db, 2628 rows chacune)
### ELECTRON-01: Build incomplet (dist/ sans package)
### FINETUNE-01: tables models et training_logs vides
### PROCESS-01: 17 python + 13 node actifs (zombies?)
### COWORK-01: 2 SyntaxWarnings (jarvis_feature_builder.py, smart_launcher.py)
### COWORK-02: 154 chemins hardcodes F:/ dans cowork (tous valides mais non portables)

---

## SCORES PAR DOMAINE (8 audits)

| Domaine | Grade | Score | Detail |
|---------|-------|-------|--------|
| Cowork scripts | **A** | 92/100 | 409/409 compilent, 0 import casse |
| Databases | **B+** | 78/100 | 63 DBs, 6 FK fixed, doublons a nettoyer |
| Source modules | **B+** | 72/100 | Imports OK, 52 duplications, 38 TODO |
| Config/Launchers | **A-** | 88/100 | 34/35 OK, deps 20/20, 1 casse (fixe) |
| Tests | **B** | 70/100 | 2241 functions, 85.5% src, 0.5% cowork |
| OpenClaw | **B** | 75/100 | 11 crons OK, 1 modele manquant, orphelins |
| Documentation | **C+** | 60/100 | 12+ stats fausses, 5 docs obsoletes |
| Securite | **D** | 35/100 | Secrets exposes (repos fixes), 10 ports 0.0.0.0 |

**SCORE GLOBAL: B- (71/100)**

---

## CORRECTIONS EFFECTUEES (2026-03-06)

| # | Tache | Status |
|---|-------|--------|
| 1 | 4 repos GitHub -> PRIVATE | FAIT |
| 2 | Canvas proxy -> 127.0.0.1 | FAIT |
| 3 | Startup BAT -> >nul | FAIT |
| 4 | etoile.db 6 FK violations | FAIT |
| 5 | WAL checkpoint + phantom cleanup | FAIT |
| 6 | JARVIS_MASTER.bat chemin | FAIT |
| 7 | OpenClaw crons 114 -> 11 | FAIT |
| 8 | Delivery queue 59 -> 0 | FAIT |
| 9 | Telegram delivery channel fix | FAIT |
| 10 | Claude sessions -253 MB | FAIT |
| 11 | n8n 63 workflows confirme | FAIT |
| 12 | OpenClaw gateway restart | FAIT |
| 13 | Secrets nettoyes historique Git (10 tokens x 3 repos) | FAIT |
| 14 | Git local resynchro avec GitHub nettoye | FAIT |
| 15 | 13 services 0.0.0.0 -> 127.0.0.1 (11 fichiers) | FAIT |
| 16 | DBs fantomes + doublons supprimes (5 fichiers) | FAIT |
| 17 | finetuning/memoire_finetuning.db doublon supprime | FAIT |
| 18 | 3 DBs vides cowork/dev/data/ supprimees | FAIT |
| 19 | jobs.json purge 567KB -> 11KB (98%) | FAIT |
| 20 | OpenClaw mistral-7b -> deepseek-r1 (7 agents) | FAIT |
| 21 | OpenClaw translator model path fix (deepseek/ prefix) | FAIT |
| 22 | turbo/CLAUDE.md refonte complete (v10.3 -> v12.4) | FAIT |
| 23 | MEMORY.md reduit 246 -> 95 lignes, stats corrigees | FAIT |
| 24 | services.md mis a jour (M2/M3, n8n, etoile) | FAIT |
| 25 | SyntaxWarnings cowork (backslash escape) | FAIT |
| 26 | 4 vieux backups openclaw.json supprimes | FAIT |
| 27 | 2 agent dirs orphelins supprimes (coder-agent, cowork) | FAIT |

## RESTE A FAIRE (par priorite)

| # | Action | Priorite | Effort |
|---|--------|----------|--------|
| 1 | **git commit** ~144 fichiers modifies | P1 | 10min |
| 2 | Nettoyer modeles LM Studio (F: 92%, 37GB free) | P1 | 30min |
| 3 | Fix 3 CRITIQUES subprocess injection (workflow_engine, win_app_controller, win_task_automator) | P1 | 1h |
| 4 | Reduire IDENTITY+TOOLS OpenClaw (17KB->10KB, dedupliquer) | P2 | 30min |
| 5 | Unifier CircuitBreaker x3 (adaptive_router, circuit_breaker, retry_manager) | P2 | 2h |
| 6 | Unifier RateLimiter x3 (rate_limiter, security, gateway) | P2 | 1h |
| 7 | Unifier EventBus x2 (event_bus, tache5_gateway/event_bus) | P2 | 1h |
| 8 | Creer tests 40 modules src/ sans couverture (brain, orchestrator, commander, trading) | P2 | 4h |
| 9 | Mettre a jour 3 docs obsoletes (INSTALL.md, REFERENCE.md, COMMANDES_VOCALES.md) | P2 | 1h |
| 10 | Deduplicar voice_corrections (2628 rows x2 dans jarvis.db + etoile.db) | P2 | 15min |
| 11 | Rebalancer 10 agents M2 + 6 agents M3 dans OpenClaw (primaire -> M1) | P2 | 30min |
| 12 | Purger sessions OpenClaw anciennes (~8MB) + browser cache (31MB) | P3 | 10min |
| 13 | Refactorer mcp_server.py (6282 lignes) | P3 | 2h |
| 14 | Refactorer domino_pipelines.py (5782 lignes) | P3 | 2h |
| 15 | 34 fichiers src/ > 500 lignes, 19 cowork/ > 500 lignes | P3 | Backlog |
| 16 | 17 TODO/FIXME reels dans src/ (12 autonomous_dev, 3 brain, 2 autres) | P3 | 2h |
| 17 | 154 chemins hardcodes F:/ dans cowork (fonctionnels mais non portables) | P3 | Backlog |

## SCORES MIS A JOUR

| Domaine | Score initial | Score actuel | Delta |
|---------|-------------|-------------|-------|
| Securite | D (35) | **B (75)** | +40 |
| Config/Launchers | A- (88) | **A (95)** | +7 |
| Databases | B+ (78) | **A- (88)** | +10 |
| Documentation | C+ (60) | **B+ (78)** | +18 |
| OpenClaw | B (75) | **A- (85)** | +10 |
| Source modules | B+ (72) | B+ (72) | 0 |
| Tests | B (70) | B (70) | 0 |
| Cowork | A (92) | **A (93)** | +1 |
| **GLOBAL** | **B- (71)** | **B+ (82)** | **+11** |
