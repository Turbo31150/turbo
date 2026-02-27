<p align="center">
  <img src="https://img.shields.io/badge/version-v10.3.5-blueviolet?style=for-the-badge" alt="version"/>
  <img src="https://img.shields.io/badge/GPU-10x_NVIDIA-76B900?style=for-the-badge&logo=nvidia" alt="gpu"/>
  <img src="https://img.shields.io/badge/Claude_SDK-Opus_4-orange?style=for-the-badge&logo=anthropic" alt="claude"/>
  <img src="https://img.shields.io/badge/Python-3.13-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="python"/>
  <img src="https://img.shields.io/badge/Electron-33-47848F?style=for-the-badge&logo=electron&logoColor=white" alt="electron"/>
  <img src="https://img.shields.io/badge/License-Private-red?style=for-the-badge" alt="license"/>
</p>

<h1 align="center">JARVIS Etoile v10.3.5</h1>
<h3 align="center">Orchestrateur IA Distribue Multi-GPU — HEXA_CORE</h3>

<p align="center">
  <strong>Systeme d'intelligence artificielle distribue sur 3 machines physiques, 10 GPU NVIDIA (~78 GB VRAM), 6 noeuds IA (HEXA_CORE) et 108 skills autonomes. Controle vocal en francais avec 1,706 commandes + 425 pipelines, trading algorithmique MEXC multi-consensus, et interface desktop Electron.</strong>
</p>

<p align="center">
  <em>"Claude = Commandant Pur. Il ne fait JAMAIS le travail lui-meme. Il ORDONNE, VERIFIE et ORCHESTRE."</em>
</p>

---

## Chiffres Cles

| Metrique | Valeur | Detail |
|----------|--------|--------|
| **GPU** | 10 NVIDIA / ~78 GB VRAM | RTX 3080 10GB, RTX 2060 12GB, 4x GTX 1660S 6GB, 3x GPU M2 24GB, 1x GPU M3 8GB |
| **Noeuds IA** | 6 actifs (HEXA_CORE) | M1 (qwen3-8b), M2 (deepseek-coder), M3 (mistral), OL1 (ollama), GEMINI, CLAUDE |
| **Agents** | 7 Claude SDK + 11 Plugin | deep, fast, check, trading, system, bridge, consensus + 11 plugin agents |
| **Outils MCP** | 92 SDK + 89 handlers | IA, Windows, Trading, Bridge, Brain, SQL, Consensus |
| **Commandes vocales** | 1,706 + 425 pipelines | 437 vocal_pipeline, 906 total vocal |
| **Skills** | 108 dynamiques | 16 vagues + 6 nouvelles categories IA, persistants en etoile.db |
| **Source Python** | 28 modules / 24,000+ lignes | src/ (42,000+ total projet) |
| **Databases** | 3 bases SQL + pipeline_tests | 35 tables, 2,477 map entries, 159 tests PASS |
| **Pipeline Tests** | 135/135 PASS (100%) | 42 categories testees sur cluster live |
| **Plugin** | 24 slash commands | + 24 skills + 11 agents + 4 hooks |
| **Desktop** | Electron 33 + React 19 | Portable 72.5 MB |
| **Trading** | v2.3 Multi-GPU | MEXC Futures 10x, 6 IA consensus |
| **Corrections vocales** | 2,627 regles | Phonetiques + alias + auto-training |

---

## Nouveautes v10.3.5 — Audit Pipeline Complet (135/135 PASS)

> **+135 pipelines** deployees en 6 batches, couvrant **42 categories** a travers 4 niveaux de priorite. Audit systematique du README vs code reel — zero gap restant. Toutes les pipelines testees live sur le cluster IA (M1/M2/M3/OL1).

### Couverture par priorite

| Priorite | Categories | Pipelines | Score |
|----------|-----------|-----------|-------|
| **CRITIQUE** | Canvas Autolearn, Voice System, Plugin Management, Embedding/Vector, Fine-Tuning Orchestration, Brain Learning | 28 | 28/28 PASS |
| **HAUTE** | RAG System, Consensus/Vote, Security Hardening, Model Management, Cluster Predictive, N8N Advanced, DB Optimization, Dashboard Widgets, Hotfix/Emergency | 27 | 27/27 PASS |
| **MEDIUM** | Learning Cycles, Scenarios/Testing, API Management, Performance Profiling, Workspace/Session, Trading Enhanced, Notification/Alerting, Documentation Auto, Logging/Observability | 32 | 32/32 PASS |
| **LOW** | User Preferences, Accessibility, Streaming/Broadcasting, Collaboration | 12 | 12/12 PASS |
| *v10.3.1* | Cluster, Diagnostic IA, Cognitif, Securite, Debug Reseau, Routines, Electron, Database | 36 | 36/36 PASS |

### Nouvelles categories v10.3.2 — v10.3.5

<details>
<summary><b>28 categories ajoutees</b> (cliquer pour details)</summary>

| Categorie | Pipelines | Exemples |
|-----------|-----------|----------|
| Canvas Autolearn | 5 | `canvas_autolearn_status`, `canvas_autolearn_trigger`, `canvas_memory_review` |
| Voice System | 5 | `voice_wake_word_test`, `voice_latency_check`, `voice_fallback_chain` |
| Plugin Management | 5 | `plugin_list_enabled`, `plugin_jarvis_status`, `plugin_health_check` |
| Embedding/Vector | 4 | `embedding_model_status`, `embedding_search_test`, `embedding_generate_batch` |
| Fine-Tuning | 4 | `finetune_monitor_progress`, `finetune_validate_quality`, `finetune_export_lora` |
| Brain Learning | 5 | `brain_memory_status`, `brain_pattern_learn`, `brain_memory_export` |
| RAG System | 3 | `rag_status`, `rag_index_status`, `rag_search_test` |
| Consensus/Vote | 3 | `consensus_weights_show`, `consensus_test_scenario`, `consensus_routing_rules` |
| Security Hardening | 4 | `security_vuln_scan`, `security_firewall_check`, `security_patch_status` |
| Model Management | 4 | `model_inventory_full`, `model_vram_usage`, `model_benchmark_compare` |
| Cluster Predictive | 3 | `cluster_health_predict`, `cluster_load_forecast`, `cluster_thermal_trend` |
| N8N Advanced | 3 | `n8n_workflow_export`, `n8n_trigger_manual`, `n8n_execution_history` |
| DB Optimization | 3 | `db_reindex_all`, `db_schema_info`, `db_export_snapshot` |
| Dashboard Widgets | 2 | `dashboard_widget_list`, `dashboard_config_show` |
| Hotfix/Emergency | 2 | `hotfix_deploy_express`, `hotfix_verify_integrity` |
| Learning Cycles | 4 | `learning_cycle_status`, `learning_cycle_benchmark`, `learning_cycle_feedback` |
| Scenario/Testing | 4 | `scenario_count_all`, `scenario_report_generate`, `scenario_regression_check` |
| API Management | 3 | `api_health_all`, `api_latency_test`, `api_keys_status` |
| Profiling | 4 | `profile_cluster_bottleneck`, `profile_memory_usage`, `profile_optimize_auto` |
| Workspace/Session | 3 | `workspace_snapshot`, `workspace_switch_context`, `workspace_session_info` |
| Trading Enhanced | 4 | `trading_backtest_strategy`, `trading_correlation_pairs`, `trading_drawdown_analysis` |
| Notification | 3 | `notification_channels_test`, `notification_config_show`, `notification_alert_history` |
| Documentation Auto | 3 | `doc_auto_generate`, `doc_sync_check`, `doc_usage_examples` |
| Logging | 4 | `logs_search_errors`, `logs_daily_report`, `logs_anomaly_detect`, `logs_rotate_archive` |
| User Preferences | 3 | `preference_work_hours`, `preference_app_usage`, `preference_auto_suggest` |
| Accessibility | 3 | `accessibility_profile_show`, `accessibility_voice_speed`, `accessibility_contrast_check` |
| Streaming | 3 | `stream_obs_status`, `stream_quality_check`, `stream_chat_monitor` |
| Collaboration | 3 | `collab_sync_status`, `collab_commands_export`, `collab_db_merge_check` |

</details>

### Architecture Pipeline v2/v3

```
Commande vocale / texte
    |
    v
commands_pipelines.py (425 pipelines)
    |
    +-- powershell: [commandes systeme directes]
    +-- curl/REST API: [M1 qwen3-8b, M2 deepseek, OL1 ollama]
    +-- uv run python: [SQLite queries, imports, exports]
    +-- Invoke-WebRequest: [Canvas 18800, n8n 5678, Dashboard 8080]
    |
    v
Resultat → TTS vocal ou console
    |
    v
etoile.db (pipeline_tests: 159, vocal_pipeline: 437)
```

### Resultats des tests live (cumul)

```
135/135 PASS — 0 FAIL — 6 batches — ~213 secondes total
  Batch 1: 24 pipelines (cluster, diagnostic, cognitif, securite, debug, routines)
  Batch 2: 36 pipelines (electron, cluster avance, database, n8n, SDK, finetuning, trading, skills)
  Batch 3: 28 pipelines CRITIQUES (canvas, voice, plugin, embedding, finetuning orch, brain)
  Batch 4: 27 pipelines HAUTES (RAG, consensus, security, model, predictive, n8n adv, db optim, dashboard, hotfix)
  Batch 5: 32 pipelines MEDIUM (learning, scenarios, API, profiling, workspace, trading enh, notif, doc, logs)
  Batch 6: 12 pipelines LOW (preferences, accessibility, streaming, collaboration)
```

---

## Nouveautes v10.3.1 — Pipelines IA Cognitives

> **+24 pipelines intelligentes** dans 6 nouvelles categories. Premiere integration du raisonnement IA dans les pipelines vocales — le systeme collecte les metriques systeme et les envoie au cluster pour analyse en temps reel.

### Nouvelles categories de pipelines

| Categorie | Pipelines | Description |
|-----------|-----------|-------------|
| **Cluster Management** | `cluster_health_live`, `cluster_model_status`, `cluster_reload_m1`, `cluster_restart_ollama` | Pilotage du cluster IA : health check, modeles charges, reload, restart |
| **Diagnostic Intelligent** | `diag_intelligent_pc`, `diag_pourquoi_lent`, `diag_gpu_thermal`, `diag_processus_suspect` | Analyse systeme via M1/qwen3 : metriques collectees puis interpretees par IA |
| **Cognitif** | `cognitif_resume_activite`, `cognitif_consensus_rapide`, `cognitif_analyse_erreurs`, `cognitif_suggestion_tache` | Raisonnement multi-etapes : resume, consensus M1+M2, analyse logs, suggestions |
| **Securite Avancee** | `securite_ports_ouverts`, `securite_check_defender`, `securite_audit_services`, `securite_permissions_sensibles` | Audit securite : scan ports, Defender, services tiers, fichiers sensibles |
| **Debug Reseau** | `debug_reseau_complet`, `debug_latence_cluster`, `debug_wifi_diagnostic`, `debug_dns_avance` | Diagnostic reseau : ping, latence cluster, WiFi, DNS multi-serveurs |
| **Routines Conversationnelles** | `routine_bonjour_jarvis`, `routine_bilan_journee`, `routine_tout_va_bien`, `routine_jarvis_selfcheck` | Interactions naturelles : "Bonjour Jarvis", "Tout va bien?", bilan IA |

### Architecture Diagnostic IA

```
Commande vocale → Collecte PowerShell (CPU/RAM/GPU/Disques)
                → Envoi au cluster M1/qwen3-8b via REST API
                → Analyse IA en temps reel (<2s)
                → Reponse synthetisee avec recommandations
```

### Resultats des tests live

```
27/27 PASS — 65.2 secondes
  Cluster:  M1 21ms | M2 7ms | M3 21ms | OL1 6ms (4/4 online)
  GPU:      5 cartes 30-54C [OK]
  IA:       Diagnostic, consensus, resume, suggestion fonctionnels
  Securite: Defender ACTIF, 47 connexions, 13 .env detectes
  Reseau:   DNS google 664ms, github 471ms, anthropic 447ms
```

### Learning Cycles (1,000 requetes cluster)

| Script | Requetes | Duree | Champion | Score |
|--------|----------|-------|----------|-------|
| v3 (PowerShell) | 500 | 618s | M2-coder 79.5/100 | M1 83.2 avg |
| v4 (Conversationnel) | 500 | 1,724s | M2-coder 71.2/100 | OL1 62.0 avg |

---

## Table des Matieres

- [Nouveautes v10.3.5 — Audit Pipeline Complet](#nouveautes-v1035--audit-pipeline-complet-135135-pass)
- [Nouveautes v10.3.1](#nouveautes-v1031--pipelines-ia-cognitives)
- [Architecture Globale](#architecture-globale)
- [Cluster IA — HEXA_CORE](#cluster-ia--hexacore)
- [Pipeline Commander](#pipeline-commander)
- [7 Agents Claude SDK](#7-agents-claude-sdk)
- [Consensus Multi-Source](#consensus-multi-source)
- [84 Skills Autonomes](#84-skills-autonomes)
- [92 Outils MCP + 89 Handlers](#92-outils-mcp--89-handlers)
- [Bases de Donnees](#bases-de-donnees)
- [Catalogue Vocal & Pipelines](#catalogue-vocal--pipelines)
- [Architecture Vocale](#architecture-vocale)
- [Trading MEXC Futures](#trading-mexc-futures)
- [Desktop Electron](#desktop-electron)
- [Arborescence du Projet](#arborescence-du-projet)
- [Installation](#installation)
- [Benchmark Cluster](#benchmark-cluster)
- [n8n Workflows](#n8n-workflows)
- [Stack Technique](#stack-technique)

---

## Architecture Globale

```
                              +-----------------------+
                              |     UTILISATEUR        |
                              |   (Voix / Clavier)     |
                              +-----------+-----------+
                                          |
                              +-----------v-----------+
                              |    CLAUDE OPUS 4.6     |
                              |     (Commandant)       |
                              | Ordonne, Verifie,      |
                              | Orchestre — JAMAIS seul |
                              +-----------+-----------+
                                          |
                  +-----------------------+-----------------------+
                  |                       |                       |
         +--------v--------+    +--------v--------+    +--------v--------+
         |  M1 — MASTER    |    |  M2 — CHAMPION  |    |  M3 — VALIDATEUR|
         | 10.5.0.2:1234   |    | 192.168.1.26    |    | 192.168.1.113   |
         | 6 GPU / 46 GB   |    | 3 GPU / 24 GB   |    | 1 GPU / 8 GB    |
         | qwen3-8b        |    | deepseek-coder  |    | mistral-7b      |
         | Score: 100%     |    | Score: 92%      |    | Score: 89%      |
         | PRIORITAIRE     |    | Code review     |    | Cross-check     |
         +--------+--------+    +--------+--------+    +--------+--------+
                  |                       |                       |
                  +-----------+-----------+-----------+-----------+
                              |                       |
                   +----------v----------+  +---------v----------+
                   |  OL1 — OLLAMA       |  |  GEMINI — CLOUD    |
                   |  127.0.0.1:11434    |  |  gemini-proxy.js   |
                   |  qwen3:1.7b + cloud |  |  gemini-2.5-pro    |
                   |  Score: 88%, 0.5s   |  |  Score: 74%        |
                   +---------------------+  +--------------------+
                              |
                   +----------v----------+
                   |  CLAUDE — CLOUD     |
                   |  claude-proxy.js    |
                   |  opus/sonnet/haiku  |
                   |  Reasoning profond  |
                   +---------------------+
```

### Flux de Donnees

```
Voix/Texte ──> STT (Whisper large-v3-turbo, CUDA) ──> Correction IA (2,627 regles)
    ──> Classification Intent (M1 qwen3-8b, 3-45ms)
    ──> Decomposition en micro-taches
    ──> Dispatch Multi-GPU (matrice de routage dynamique)
    ──> Execution Parallele sur cluster
    ──> Consensus Pondere (6 noeuds, vote pondere)
    ──> Reponse Vocale (TTS Edge fr-FR-HenriNeural)
    ──> Persistance (etoile.db + jarvis.db)
```

---

## Cluster IA — HEXA_CORE

### M1 — Machine Master (10.5.0.2) — PRIORITAIRE

| Composant | Specification |
|-----------|---------------|
| GPU Principal | RTX 3080 (10 GB) — PCIe Gen 4 x16 |
| GPU Secondaire | RTX 2060 (12 GB) — PCIe Gen 3 x4 |
| GPU Compute | 4x GTX 1660 SUPER (6 GB chacun) |
| VRAM Totale | **46 GB** |
| Role | **PRIORITAIRE** — Code, Math, Raisonnement, Embedding |
| LM Studio | Port 1234 — **qwen3-8b** (65 tok/s, Q4_K_M, dual-instance) |
| Modele secondaire | qwen3-30b (9 tok/s, disponible en TTL) |
| Score Benchmark | **100%** |
| Latence | 0.6–2.5s |
| Poids Consensus | **1.8** |
| Note | `/nothink` obligatoire — evite le thinking cache Qwen3 |

### M2 — Code Champion (192.168.1.26)

| Composant | Specification |
|-----------|---------------|
| GPU | 3 GPU — 24 GB VRAM total |
| Role | Code review, debug, analyse profonde |
| LM Studio | Port 1234 — **deepseek-coder-v2-lite** (16B, Q4_K_M) |
| Score Benchmark | **92%** |
| Latence | 1.3s |
| Poids Consensus | 1.4 |

### M3 — Validateur (192.168.1.113)

| Composant | Specification |
|-----------|---------------|
| GPU | 1 GPU — 8 GB VRAM |
| Role | General, validation croisee (PAS raisonnement) |
| LM Studio | Port 1234 — **mistral-7b-instruct-v0.3** (Q4_K_M) |
| Score Benchmark | **89%** |
| Latence | 2.5s |
| Poids Consensus | 1.0 |

### OL1 — Ollama (127.0.0.1:11434)

| Composant | Specification |
|-----------|---------------|
| Backend | Ollama v0.16.1 |
| Modele Local | **qwen3:1.7b** (0.5s, le plus rapide du cluster) |
| Modeles Cloud | minimax-m2.5, glm-5, kimi-k2.5 (`think:false` obligatoire) |
| Role | Vitesse, web search, correction vocale |
| Score Benchmark | **88%** |
| Poids Consensus | 1.3 |

### GEMINI — Cloud (gemini-proxy.js)

| Composant | Specification |
|-----------|---------------|
| Modeles | gemini-2.5-pro / gemini-3-flash (fallback) |
| Proxy | `node gemini-proxy.js "prompt"` — timeout 2min, fallback auto |
| Role | Architecture, vision, review de plans |
| Score Benchmark | **74%** (variable, instable sur longs prompts) |
| Poids Consensus | 1.2 |

### CLAUDE — Cloud (claude-proxy.js)

| Composant | Specification |
|-----------|---------------|
| Modeles | opus / sonnet / haiku (fallback auto) |
| Proxy | `node claude-proxy.js "prompt"` — sanitisation env CLAUDE* |
| Role | Raisonnement profond cloud, review code avance |
| Latence | 12–18s |
| Poids Consensus | 1.2 |

---

## Pipeline Commander

Le coeur de JARVIS suit un pipeline strict ou Claude ne fait **jamais** le travail lui-meme :

```
 1. CLASSIFY    ──> Identifier le type de tache (M1 qwen3-8b, 3-45ms)
 2. DECOMPOSE   ──> Decouper en micro-taches executables
 3. THERMAL     ──> Verifier temperature GPU (75C warning / 85C critical)
 4. ENRICH      ──> Ajouter contexte systeme au prompt
 5. DISPATCH    ──> Router vers le bon noeud selon matrice de routage
 6. EXECUTE     ──> Le noeud execute la tache
 7. VALIDATE    ──> Cross-check par un second noeud
 8. AGGREGATE   ──> Consensus pondere si multi-source
 9. RESPOND     ──> Reponse vocale ou texte
10. PERSIST     ──> Sauvegarder en DB (etoile.db + jarvis.db)
```

Module: `src/commander.py` — Classification: M1 qwen3-8b + fallback heuristique.
Cascade thermique: M1 → M2 → M3 si temperature critique.

### Routage Intelligent (benchmark-tuned 2026-02-26, M1 PRIORITAIRE)

| Type de tache | Principal | Secondaire | Verificateur |
|---------------|-----------|------------|--------------|
| Code nouveau | **M1** (100%, 0.6s) | M2 (review) | GEMINI (archi) |
| Bug fix | **M1** | M2 (patch) | — |
| Architecture | GEMINI | **M1** (validation) | M2 (faisabilite) |
| Refactoring | **M1** | M2 (validation) | — |
| Raisonnement | **M1** (100%) | M2 (analyse) | JAMAIS M3 |
| Math/Calcul | **M1** (100%) | OL1 (rapide) | — |
| Trading | OL1 (web) | **M1** (analyse) | — |
| Securite/audit | **M1** | GEMINI | M3 (scan) |
| Question simple | OL1 (0.5s) | M3 (2.5s) | — |
| Recherche web | OL1-cloud | GEMINI | — |
| Revue code finale | CLAUDE | GEMINI | **M1** |
| Consensus critique | M1+M2+OL1+GEMINI+CLAUDE | Vote pondere | — |
| Embedding | **M1** | — | — |

Fallback automatique: M1 → M2 → M3 → OL1 → GEMINI → CLAUDE.

---

## 7 Agents Claude SDK

Definis dans `src/agents.py`, chaque agent a un role, un modele Claude et des outils MCP specifiques.

| Agent | Modele | Role | Outils cles |
|-------|--------|------|-------------|
| **ia-deep** | Opus | Architecte — analyse approfondie, raisonnement long | Read, Glob, Grep, WebSearch, bridges, lm_query, consensus |
| **ia-fast** | Haiku | Ingenieur — code rapide, edits, commandes | Read, Write, Edit, Bash, Glob, Grep, lm_query |
| **ia-check** | Sonnet | Validateur — review, tests, score qualite 0-1 | Read, Bash, Glob, Grep, bridges, consensus |
| **ia-trading** | Sonnet | Trading MEXC 10x — scan, breakout, consensus IA | Read, Bash, run_script, consensus, ollama_web_search |
| **ia-system** | Haiku | Systeme Windows — fichiers, PowerShell, registre | Read, Write, Edit, Bash, powershell_run, system_info |
| **ia-bridge** | Sonnet | Orchestrateur multi-noeuds — mesh, routage | bridges, consensus, gemini_query, lm_query, lm_mcp_query |
| **ia-consensus** | Sonnet | Vote pondere multi-source avec verdicts structures | consensus, bridges, gemini_query, lm_query, ollama_web_search |

### 11 Agents Plugin (jarvis-turbo)

| Agent | Couleur | Specialite |
|-------|---------|------------|
| cluster-ops | Cyan | Operations cluster, health checks |
| trading-analyst | Vert | Analyse marche, signaux trading |
| code-architect | Bleu | Architecture code, design patterns |
| debug-specialist | Rouge | Debug, root cause analysis |
| performance-monitor | Jaune | Metriques, bottlenecks, latence |
| smart-dispatcher | Magenta | Routage intelligent multi-noeuds |
| auto-healer | Rouge | Diagnostic + reparation automatique |
| raisonnement-specialist | Violet | Raisonnement profond (M1 prioritaire) |
| benchmark-runner | Jaune | Tests de performance cluster |
| routing-optimizer | Orange | Optimisation des poids de routage |
| canvas-operator | — | Proxy Canvas + autolearn |

---

## Consensus Multi-Source

Chaque decision importante passe par un pipeline de consensus pondere. Tous les noeuds sont interroges en parallele, puis leurs reponses sont agregees avec un vote pondere :

```
  M1     (poids 1.8)  ──┐
  M2     (poids 1.4)  ──┤
  OL1    (poids 1.3)  ──┼──> Agregation ──> Score Consensus ──> Decision
  GEMINI (poids 1.2)  ──┤        │
  CLAUDE (poids 1.2)  ──┤        │
  M3     (poids 1.0)  ──┘        v
                            >= 0.66  ──> FORT : Decision nette
                           0.4–0.66  ──> MOYEN : Decision + alternatives
                            < 0.4    ──> FAIBLE : Pas de decision, divergences exposees
```

**Formule :** `score(option) = SUM(weight_i * confidence_i) / SUM(weight_i)`
**Quorum :** score >= 0.65 pour valider une decision.

### Scenario Weights (58 regles, 22 scenarios)

Les poids de routage sont dynamiques et stockes dans `etoile.db` (`scenario_weights`). Chaque scenario definit une chaine de fallback avec priorites :

| Scenario | Chaine de routage |
|----------|-------------------|
| **architecture** | GEMINI (w=1.5) → CLAUDE (w=1.2) → M2 (w=1.0) |
| **code_generation** | M2 (w=1.6) → M3 (w=1.0) / M1 (w=1.0) → OL1 (w=0.5) |
| **consensus** | M2 → OL1 → M3 → M1 → GEMINI → CLAUDE (6 sources) |
| **critical** | M2 (w=1.5) → OL1 (w=1.3) → GEMINI (w=1.2) / M1 |
| **reasoning** | CLAUDE (w=1.4) → M2 (w=1.2) / M1 (w=1.2) |
| **short_answer** | OL1 (w=1.5) → M3 (w=1.0) / M1 |
| **trading_signal** | OL1 (w=1.5) → M2 (w=1.2) → M1 (w=0.8) |
| **web_research** | OL1 (w=1.5) → GEMINI (w=1.0) → M1 (w=0.6) |

### Domino Chains (12 enchainements automatiques)

Les domino chains sont des reactions automatiques declenchees par un evenement + condition :

| Trigger | Condition | Action suivante | Description |
|---------|-----------|-----------------|-------------|
| `arena` | new_champion | `export` | Export config si nouveau champion |
| `ask` | timeout | `ask_fallback` | Fallback auto sur timeout |
| `heal` | node_repaired | `status` (5s) | Re-check status apres reparation |
| `mode_code` | start | `cluster_check` (1s) | Check cluster en mode code |
| `mode_trading` | start | `trading_scan` (2s) | Scan auto en mode trading |
| `routine_matin` | start | `status` → `scores` | Routine matinale complete |
| `status` | node_fail | `heal --status` | Auto-diagnostic quand noeud en panne |
| `status` | all_ok | `log_health` | Log sante quand tout va bien |

---

## 84 Skills Autonomes

Les skills sont des pipelines multi-etapes persistants dans `etoile.db`. Ils survivent aux redemarrages et accumulent des statistiques d'utilisation. Declenchables par commande vocale ou par les agents.

| Categorie | Nombre | Exemples |
|-----------|--------|----------|
| **Diagnostics systeme** | 29 | Diagnostic complet, reseau, GPU, demarrage, sante PC, audit securite |
| **Dev workflows** | 18 | Frontend, backend, Docker, Git, Turbo, benchmark, data science |
| **Modes** | 22 | Trading, Dev, Gaming, Focus, Cinema, Nuit, Stream, Presentation |
| **Routines** | 9 | Rapport matin, rapport soir, pause cafe, fin de journee |
| **Productivite** | 9 | Focus travail, session creative, mode recherche web |
| **Maintenance** | 8 | Nettoyage RAM/fichiers/reseau, optimisation DNS/performances |
| **Entertainment** | 5 | Cinema, musique, gaming, detente |
| **Fichiers** | 4 | Backup, nettoyage, sync, archive |
| **Communication** | 3 | Telegram, email, notifications |
| **Trading** | 3 | Consensus multi-IA, check complet, mode MEXC |
| **Navigation** | 1 | Split screen, multi-bureau |

### 24 Skills Plugin (jarvis-turbo)

mao-workflow, cluster-management, trading-pipeline, failover-recovery, security-audit, performance-tuning, autotest-analysis, continuous-improvement, smart-routing, weighted-orchestration, prompt-engineering, agent-benchmarking, chain-optimization, quality-scoring + 10 domaines etoile.db (dev-workflows, system-diagnostics, trading-operations, daily-routines, productivity-modes, entertainment-modes, communication-modes, file-management, accessibility-modes, navigation-tools).

---

## 92 Outils MCP + 89 Handlers

Repartis en 2 serveurs MCP principaux + 1 serveur filesystem :

```
JARVIS-TURBO (92 tools)               TRADING-AI-ULTIMATE (89 handlers)
├── Cluster IA (15)                    ├── Scanner MEXC (15)
│   lm_query, consensus,              │   turbo_scan, scan_sniper,
│   bridge_mesh, bridge_query,         │   pump_detector, breakout_scan
│   gemini_query, ollama_query         │
├── Windows System (15)                ├── Orderbook Analysis (8)
│   powershell_run, system_info,       │   deep_orderbook, whale_walls,
│   open_app, close_app, gpu_info      │   buy_pressure, liquidity_map
├── Brain/Skills (10)                  ├── Multi-IA Consensus (12)
│   learn_skill, execute_skill,        │   consensus_5ia, vote_pondere,
│   brain_index, brain_search          │   multi_model_analysis
├── Trading Bridge (8)                 ├── Positions/Margins (10)
│   run_script, trading_signal,        │   open_positions, margin_status,
│   sniper_execute                     │   pnl_tracker, risk_calc
├── Filesystem (7)                     ├── Alerts/Telegram (14)
│   read_file, write_file,             │   send_signal, alert_config,
│   list_dir, search_files             │   telegram_notify, webhook
├── Bridge Multi-Noeuds (12)           ├── SQL Database (12)
│   mesh_parallel, route_smart,        │   query_sql, insert_signal,
│   fallback_chain                     │   export_data, backup_db
├── Consensus/Mesh (10)               ├── LM Studio Dispatch (12)
│   consensus_vote, mesh_query,        │   dispatch_m1, dispatch_m2,
│   aggregate_results                  │   load_model, health_check
├── SQL Tools (3)                      └── n8n/GitHub/System (6)
│   sql_query, sql_insert,                 trigger_workflow, github_api
│   sql_export
└── Utilities (12)
    tts_speak, screenshot,
    clipboard, hotkey
```

### 3 Serveurs MCP Configures

| Serveur | Commande | Description |
|---------|----------|-------------|
| **jarvis-turbo** | `jarvis_mcp_stdio.bat` | 92 outils SDK + 89 handlers MCP |
| **trading-ai-ultimate** | `trading_mcp_ultimate_v3.py` | Scanner MEXC, consensus, execution |
| **filesystem** | `npx @modelcontextprotocol/server-filesystem` | Acces complet C:\, D:\, F:\ |

---

## Bases de Donnees

### Vue d'ensemble

| Base | Chemin | Tables | Rows | Usage |
|------|--------|--------|------|-------|
| **etoile.db** | `data/etoile.db` | 18 | 6,045 | Carte HEXA_CORE, cles API, agents, metrics, pipelines, corrections |
| **jarvis.db** | `data/jarvis.db` | 11 | 4,193 | 443 commandes, 80 skills, 475 scenarios, 2,627 corrections, benchmarks |
| **sniper.db** | `data/sniper.db` | 5 | 657 | 67 coins, 521 signaux trading, 11 categories |

### etoile.db — Carte du Systeme

La table `map` centralise la cartographie complete du systeme :

| Type d'entite | Nombre | Description |
|---------------|--------|-------------|
| vocal_command | 1,706 | Commandes vocales avec triggers et actions |
| vocal_pipeline | 437 | Pipelines multi-etapes (enchainements automatises) |
| skill | 108 | Skills persistants avec statistiques |
| tool | 75 | Outils MCP SDK enregistres |
| script | 39 | Scripts Python/PowerShell disponibles |
| routing_rule | 22 | Regles de routage cluster |
| launcher | 15 | Launchers .bat/.ps1 |
| model | 15 | Modeles IA charges/disponibles |
| mcp_tool | 12 | Outils MCP standalone |
| route | 10 | Routes de dispatch |
| tool_category | 8 | Categories d'outils |
| workflow | 8 | Workflows n8n |
| agent | 7 | Agents Claude SDK |
| node | 6 | Noeuds cluster |
| voice_command | 5 | Commandes vocales speciales |
| database | 4 | Bases de donnees |

Autres tables: `pipeline_dictionary` (656 pipelines), `pipeline_tests` (159 tests, 135/135 PASS), `scenario_weights` (58 regles), `domino_chains` (12 chaines), `voice_corrections` (2,627 regles), `benchmark_runs/results`, `consensus_log`, `jarvis_queries`, `cluster_health`, `agent_keywords`, `memories` (44 entries), `api_keys`, `skills_log`, `sessions`, `metrics`.

### jarvis.db — Commandes & Validation

| Table | Rows | Description |
|-------|------|-------------|
| commands | 443 | Commandes vocales avec triggers JSON, action_type, usage stats |
| skills | 80 | Skills avec steps, taux de succes, compteurs |
| scenarios | 475 | Scenarios de test (validation vocale) |
| validation_cycles | 500 | Resultats de cycles de validation |
| voice_corrections | 2,627 | Corrections phonetiques + alias + auto-training |
| node_metrics | 5 | Metriques par noeud (score, latence, weight) |
| benchmark_runs | 1 | Dernier benchmark complet |
| benchmark_results | 50 | Resultats detailles par noeud/level |
| consensus_log | 3 | Logs de consensus multi-source |

---

## Catalogue Vocal & Pipelines

### Commandes Vocales (443 commandes)

> Source: `jarvis.db` table `commands` — Chaque commande a un nom, une description, des triggers vocaux (JSON array), un type d'action et la commande executee.

| Categorie | Nombre | Types d'action |
|-----------|--------|----------------|
| **systeme** | 260 | powershell, hotkey, ms_settings, jarvis_tool, script, app_open |
| **fichiers** | 31 | powershell, hotkey, jarvis_tool |
| **navigation** | 26 | app_open, browser, hotkey, powershell |
| **app** | 23 | app_open, jarvis_tool, hotkey, powershell |
| **trading** | 17 | script, jarvis_tool |
| **dev** | 15 | powershell, browser |
| **clipboard** | 13 | hotkey, jarvis_tool |
| **fenetre** | 13 | hotkey, jarvis_tool, powershell |
| **jarvis** | 12 | exit, list_commands, jarvis_repeat, jarvis_tool |
| **launcher** | 12 | script |
| **accessibilite** | 10 | ms_settings, powershell |
| **media** | 7 | hotkey, powershell |
| **saisie** | 4 | powershell, hotkey |

<details>
<summary><b>systeme</b> (260 commandes) — Exemples</summary>

| Commande | Description | Triggers vocaux | Type |
|----------|-------------|----------------|------|
| `a_propos_pc` | Informations systeme | "a propos du pc", "infos systeme" | ms_settings |
| `activation_windows` | Statut activation Windows | "activation windows", "licence windows" | powershell |
| `adresse_mac` | Afficher adresse MAC | "adresse mac", "mac address" | powershell |
| `batterie_niveau` | Niveau de batterie | "niveau de batterie", "battery level" | powershell |
| `bluetooth_on` | Activer bluetooth | "active le bluetooth", "bluetooth on" | powershell |
| `capture_ecran` | Capture d'ecran | "capture ecran", "screenshot" | hotkey |
| `connexions_actives` | Connexions TCP actives | "connexions actives", "netstat" | powershell |
| `cpu_info` | Informations processeur | "quel processeur", "cpu info" | powershell |
| `date_actuelle` | Date du jour | "quelle date", "quel jour" | powershell |
| `defrag_disque` | Defragmenter un disque | "defragmente", "defrag" | powershell |
| `dns_changer_google` | DNS Google | "mets le dns google", "dns 8.8.8.8" | powershell |
| `eteindre_pc` | Eteindre l'ordinateur | "eteins le pc", "shutdown" | powershell |
| `gpu_info` | Infos carte graphique | "quelle carte graphique", "gpu info" | powershell |
| `ip_publique` | Adresse IP publique | "ip publique", "mon ip" | powershell |
| `luminosite` | Regler luminosite | "luminosite a {n}", "brightness" | powershell |
| `memoire_ram` | Utilisation RAM | "combien de ram", "memoire vive" | powershell |
| `mode_avion` | Mode avion | "mode avion", "airplane mode" | ms_settings |
| `moniteur_performances` | Ouvrir perfmon | "performances", "task manager" | powershell |
| `ping_serveur` | Ping un serveur | "ping {host}", "teste la connexion" | powershell |
| `processus_actifs` | Liste des processus | "processus actifs", "task list" | powershell |
| `redemarrer_pc` | Redemarrer | "redemarre le pc", "reboot" | powershell |
| `reseau_wifi` | Reseaux WiFi | "reseaux wifi", "wifi networks" | powershell |
| `taille_ecran` | Resolution ecran | "resolution ecran", "display settings" | ms_settings |
| `temperature_gpu` | Temperature GPU | "temperature gpu", "gpu temp" | powershell |
| `verrouiller_pc` | Verrouiller la session | "verrouille le pc", "lock" | powershell |
| `volume_augmenter` | Augmenter volume | "monte le son", "volume up" | hotkey |
| `volume_baisser` | Baisser volume | "baisse le son", "volume down" | hotkey |

*...et 233 autres commandes systeme (DNS, services, registre, pilotes, ecrans, pare-feu, taches planifiees, etc.)*

</details>

<details>
<summary><b>fichiers</b> (31 commandes)</summary>

| Commande | Description | Triggers | Type |
|----------|-------------|----------|------|
| `bureau` | Ouvrir le bureau | "ouvre le bureau", "desktop" | hotkey |
| `corbeille_ouvrir` | Ouvrir la corbeille | "ouvre la corbeille", "recycle bin" | powershell |
| `corbeille_vider` | Vider la corbeille | "vide la corbeille", "empty trash" | powershell |
| `creer_dossier` | Creer un dossier | "cree un dossier {nom}", "new folder" | powershell |
| `downloads` | Ouvrir telechargements | "ouvre les telechargements", "downloads" | powershell |
| `espace_disque` | Espace disque restant | "espace disque", "disk space" | powershell |
| `fichiers_recents` | Fichiers recents | "fichiers recents", "recent files" | powershell |
| `nouveau_fichier` | Creer un fichier | "cree un fichier", "new file" | powershell |
| `rechercher_fichier` | Rechercher un fichier | "cherche {fichier}", "find file" | powershell |
| `renommer` | Renommer un fichier | "renomme {ancien} en {nouveau}" | powershell |
| `supprimer_fichier` | Supprimer un fichier | "supprime {fichier}", "delete" | powershell |

*...et 20 autres (compresser, decompresser, copier, deplacer, trier, etc.)*

</details>

<details>
<summary><b>navigation</b> (26 commandes)</summary>

| Commande | Description | Triggers | Type |
|----------|-------------|----------|------|
| `github` | Ouvrir GitHub | "ouvre github" | browser |
| `google` | Recherche Google | "cherche {query} sur google" | browser |
| `gmail` | Ouvrir Gmail | "ouvre gmail", "mes mails" | browser |
| `youtube` | Ouvrir YouTube | "ouvre youtube" | browser |
| `maps` | Ouvrir Google Maps | "ouvre maps", "google maps" | browser |
| `twitter` | Ouvrir Twitter/X | "ouvre twitter", "ouvre x" | browser |
| `reddit` | Ouvrir Reddit | "ouvre reddit" | browser |
| `stack_overflow` | Ouvrir Stack Overflow | "ouvre stack overflow" | browser |

*...et 18 autres (chatgpt, notion, discord, spotify, netflix, etc.)*

</details>

<details>
<summary><b>app</b> (23), <b>trading</b> (17), <b>dev</b> (15), <b>clipboard</b> (13), <b>fenetre</b> (13), <b>jarvis</b> (12), <b>launcher</b> (12), <b>accessibilite</b> (10), <b>media</b> (7), <b>saisie</b> (4)</summary>

| Categorie | Exemples de commandes |
|-----------|-----------------------|
| **app** | Ouvrir/fermer apps (Chrome, VS Code, Discord, Steam, Spotify, etc.) |
| **trading** | Scan MEXC, consensus IA, analyse breakout, portfolio, signaux |
| **dev** | Git status/push/pull, Docker, Ollama, benchmark, mode dev |
| **clipboard** | Copier/coller/couper, compter caracteres, vider presse-papier |
| **fenetre** | Minimiser/maximiser, split screen, snap gauche/droite, fermer |
| **jarvis** | Aide, liste commandes, repete, mode silence, quitter |
| **launcher** | Lancer JARVIS (voice, dashboard, commander, hybrid, mcp) |
| **accessibilite** | Clavier virtuel, contraste, narrateur, filtres couleur, sous-titres |
| **media** | Play/pause, mute, volume, chanson suivante/precedente |
| **saisie** | Dictee, emoji picker, clavier tactile, mode frappe |

</details>

### Pipeline Dictionary (656 pipelines)

> Source: `etoile.db` table `pipeline_dictionary` — Workflows multi-etapes executant plusieurs actions en sequence.

| Categorie | Nombre | Types d'actions |
|-----------|--------|-----------------|
| **systeme** | 262 | powershell, hotkey, jarvis_tool, ms_settings, script, app_open |
| **pipeline** | 205 | pipeline (enchainements multi-etapes complexes) |
| **fichiers** | 31 | powershell, hotkey, jarvis_tool |
| **navigation** | 26 | app_open, browser, hotkey, powershell |
| **app** | 23 | app_open, jarvis_tool, hotkey, powershell |
| **trading** | 23 | script, jarvis_tool |
| **dev** | 15 | powershell, browser |
| **clipboard** | 13 | hotkey, jarvis_tool |
| **fenetre** | 13 | hotkey, jarvis_tool, powershell |
| **jarvis** | 12 | powershell, list_commands, exit, jarvis_repeat |
| **launcher** | 12 | script |
| **accessibilite** | 10 | ms_settings, powershell |
| **media** | 7 | hotkey, powershell |
| **saisie** | 4 | powershell, hotkey |

<details>
<summary><b>pipeline</b> (205 pipelines multi-etapes) — Exemples</summary>

| Pipeline | Trigger vocal | Description |
|----------|--------------|-------------|
| `mode_cinema` | "mode cinema" | Luminosite basse + plein ecran + volume optimal + desactive notifications |
| `mode_dev` | "mode developpement" | VS Code + terminal + navigateur dev tools + cluster check |
| `mode_focus` | "mode focus" | Ferme apps distraction + DND + minuterie Pomodoro |
| `mode_gaming` | "mode gaming" | Performances max + ferme apps fond + GPU priority |
| `mode_nuit` | "mode nuit" | Filtre lumiere bleue + luminosite basse + mode sombre |
| `mode_trading` | "mode trading" | MEXC + terminal + scan auto + consensus IA |
| `mode_streaming` | "mode streaming" | OBS + micro + scene principale + chat overlay |
| `routine_matin` | "routine du matin" | Status cluster → scores → rapport meteo → planning |
| `routine_soir` | "rapport du soir" | Sauvegarde → metriques → rapport journalier |
| `pause_cafe` | "pause cafe" | Lock ecran + minuterie 15min + musique chill |
| `diagnostic_complet` | "diagnostic systeme" | CPU + RAM + GPU + disques + reseau + services + cluster |
| `nettoyage_complet` | "nettoyage complet" | Temp + cache + corbeille + RAM + logs anciens |
| `workspace_frontend` | "workspace frontend" | VS Code + Chrome DevTools + Figma + terminal npm |
| `workspace_backend` | "workspace backend" | VS Code + terminal Python + Postman + DB viewer |
| `backup_rapide` | "backup rapide" | Git add + commit + push + confirmation vocale |
| `deploiement` | "deploie le projet" | Tests → build → git push → notification Telegram |
| `consensus_trading` | "consensus trading" | Scan 5 IA → vote pondere → signal si score > 70 |

*...et 188 autres pipelines (arena, heal, benchmark, optimisation, audit, etc.)*

</details>

<details>
<summary><b>systeme</b> (262 pipelines) — Exemples</summary>

Memes commandes que la section Commandes Vocales systeme, stockees aussi dans pipeline_dictionary avec les steps PowerShell detailles. Inclut : gestion DNS, bluetooth, WiFi, services, processus, certificats SSL, registre, ecrans, pilotes, pare-feu, BitLocker, taches planifiees, restauration systeme, defragmentation, BIOS info, etc.

</details>

### Corrections Vocales (2,627 regles)

Systeme de correction automatique de la reconnaissance vocale, stocke dans `voice_corrections` :

| Categorie | Nombre | Exemples |
|-----------|--------|----------|
| **phonetic** | 2,559 | "met en plein ecrant" → "plein ecran", "ouvre crome" → "ouvre chrome" |
| **alias** | 34 | "arrete l'ordinateur" → "eteins le pc", "ouvre steam" → "ouvre steam" |
| **auto_training** | 33 | Corrections apprises automatiquement par le systeme |
| **training** | 1 | Corrections manuelles d'entrainement |

---

## Architecture Vocale

### Pipeline v2 (2026-02-22)

```
                    CTRL (Push-to-Talk)
                          │
                          v
                  ┌───────────────┐
                  │  Sony WH-1000 │  ◄── Auto-detection micro
                  │  XM4 / Defaut │
                  └───────┬───────┘
                          │
                  ┌───────v───────┐
                  │ Whisper        │  ◄── large-v3-turbo, CUDA GPU
                  │ STT < 200ms   │      Persistent Worker (charge 1x)
                  └───────┬───────┘
                          │
                  ┌───────v───────┐
                  │ Correction IA │  ◄── 2,627 regles phonetiques
                  │ + LM Studio   │      + correction contextuelle M1
                  └───────┬───────┘
                          │
                  ┌───────v───────┐
                  │ Intent Match  │  ◄── 1,706 commandes + 656 pipelines
                  │ + Fuzzy Match │      Matching semantique + phonetique
                  └───────┬───────┘
                          │
                  ┌───────v───────┐
                  │ Orchestrator  │  ◄── Dispatch vers cluster HEXA_CORE
                  │ Commander     │      Classification M1 (3-45ms)
                  └───────┬───────┘
                          │
                  ┌───────v───────┐
                  │ TTS Edge      │  ◄── fr-FR-HenriNeural
                  │ Streaming     │      Latence < 2s (cache LRU 200)
                  └───────────────┘
```

**Latence totale** : < 2s pour commandes connues, < 0.5s via cache LRU.
**Wake word** : OpenWakeWord "jarvis" (seuil 0.7).
**Fallback** : OL1 down → GEMINI → local-only.

---

## Trading MEXC Futures

### Configuration

| Parametre | Valeur |
|-----------|--------|
| Exchange | MEXC Futures |
| Levier | 10x |
| TP | 0.4% |
| SL | 0.25% |
| Taille position | 10 USDT |
| Score minimum | 70/100 |
| DRY_RUN | false |
| Paires suivies | BTC, ETH, SOL, SUI, PEPE, DOGE, XRP, ADA, AVAX, LINK |

### Pipeline v2.3 Multi-GPU

```
Scan 850+ tickers MEXC Futures
    │
    v
Filtre : Volume > 3M USDT, Change > 2%
    │
    v
Analyse technique : RSI, MACD, Bollinger Bands, ATR, Stochastic, OBV
    │
    v
Orderbook : 50 niveaux bid/ask, buy pressure, whale walls
    │
    v
Scoring composite (breakout + reversal + momentum + liquidity)
    │
    v
Consensus 6 IA (M1 + M2 + M3 + OL1 + GEMINI + CLAUDE)
    │
    v
Entry / TP1 / TP2 / TP3 / TP4 / SL calcules (ATR-based, Fibonacci)
    │
    v
Signal Telegram (@turboSSebot) + Sauvegarde SQL (sniper.db)
```

### Outils de Scan

| Scanner | Description | Duree |
|---------|-------------|-------|
| `turbo_scan` | Scan complet + consensus 4 modeles IA | 2-3 min |
| `scan_sniper` | Scanner premium 5 IA, 400+ contrats | 5-7 min |
| `pump_detector` | Detection breakout imminents (momentum + volume) | 1-2 min |
| `scan_breakout_imminent` | Orderbook + liquidity clusters + whale walls | 2-3 min |
| `perplexity_scan` | BB squeeze + Supertrend + RSI/MACD crossover | 2-3 min |
| `smart_scan` | Full scan + Multi-IA + signal Telegram automatique | 3-5 min |

---

## Desktop Electron

Application desktop construite avec Electron 33 + React 19 + TypeScript + Vite 6 + Tailwind CSS.
Portable 72.5 MB, installeur NSIS 80 MB. Raccourci: `Ctrl+Shift+J`.

### Pages

| Page | Fonction |
|------|----------|
| **Dashboard** | Vue d'ensemble systeme, cluster status, metriques temps reel |
| **Chat** | Interface conversationnelle avec JARVIS (agent badges, markdown) |
| **Voice** | Visualisation audio, log transcriptions, waveform |
| **Trading** | Positions ouvertes, signaux actifs, historique PnL |
| **LM Studio** | Gestion modeles, charge GPU, benchmarks, load/unload |
| **Settings** | Configuration systeme, preferences, cles API |

### Architecture

```
electron/
├── src/main/              # Process principal Electron
│   ├── index.ts           # Entry point + window creation
│   ├── ipc-handlers.ts    # Communication main ↔ renderer
│   ├── python-bridge.ts   # Pont vers backend FastAPI (port 9742)
│   ├── tray.ts            # System tray icon + menu
│   └── window-manager.ts  # Gestion fenetres + widgets
├── src/renderer/          # Interface React
│   ├── components/
│   │   ├── chat/          # AgentBadge, MessageBubble
│   │   ├── cluster/       # NodeCard, ClusterGrid
│   │   ├── layout/        # Sidebar, TopBar
│   │   ├── trading/       # PositionsTable, SignalsTable
│   │   └── voice/         # AudioVisualizer, TranscriptionLog
│   ├── hooks/             # useChat, useCluster, useLMStudio,
│   │                        useTrading, useVoice, useWebSocket
│   └── pages/             # 6 pages principales
└── widget-windows/        # Widgets overlay detachables
```

Backend WebSocket: `python_ws/` (FastAPI, port 9742) — 6 routes: cluster, trading, voice, chat, files, sql.

---

## Arborescence du Projet

```
turbo/
├── src/                       # 28 modules Python (22,994 lignes)
│   ├── orchestrator.py        # Cerveau central — dispatch + aggregation
│   ├── commander.py           # Pipeline Commander (classify/decompose/enrich)
│   ├── agents.py              # 7 agents Claude SDK (deep/fast/check/trading/system/bridge/consensus)
│   ├── tools.py               # 92 outils MCP SDK (v3.4.0+)
│   ├── mcp_server.py          # 89 handlers MCP standalone
│   ├── commands.py            # Commandes vocales principales
│   ├── commands_dev.py        # Commandes developpement (git, ollama, docker)
│   ├── commands_maintenance.py# Commandes maintenance
│   ├── commands_navigation.py # Commandes navigation
│   ├── commands_pipelines.py  # 278 pipelines multi-etapes
│   ├── config.py              # Configuration cluster + routage + 14 regles
│   ├── skills.py              # 84 skills dynamiques
│   ├── brain.py               # Auto-apprentissage (patterns)
│   ├── voice.py               # Pipeline vocale (Whisper + TTS)
│   ├── voice_correction.py    # Correction vocale (2,627 regles + OL1)
│   ├── wake_word.py           # OpenWakeWord "jarvis" (seuil 0.7)
│   ├── tts_streaming.py       # TTS streaming Edge fr-FR-HenriNeural
│   ├── whisper_worker.py      # Whisper large-v3-turbo CUDA (process persistent)
│   ├── cluster_startup.py     # Boot cluster + thermal + GPU stats
│   ├── trading.py             # Trading MEXC Futures (CCXT)
│   ├── prompt_engineering.py  # Expert system prompts + query enhancer
│   ├── database.py            # SQLite persistence (etoile.db + jarvis.db)
│   ├── executor.py            # Execution commandes/skills
│   ├── windows.py             # API Windows (PowerShell, COM, WMI)
│   ├── scenarios.py           # Scenarios de validation
│   ├── output.py              # Schema sortie JSON
│   ├── dashboard.py           # API dashboard REST
│   └── systray.py             # System tray icon
├── electron/                  # App desktop (Electron 33 + React 19 + Vite 6)
├── python_ws/                 # Backend WebSocket (FastAPI port 9742)
│   └── routes/                # 6 routes (cluster/trading/voice/chat/files/sql)
├── plugins/jarvis-turbo/      # Plugin Claude Code
│   ├── agents/ (11)           # cluster-ops, trading-analyst, code-architect...
│   ├── commands/ (24)         # /deploy, /cluster-check, /consensus, /trading-scan...
│   ├── skills/ (24)           # mao-workflow, smart-routing, failover-recovery...
│   └── hooks/                 # SessionStart, PreToolUse, Stop, SubagentStop
├── scripts/                   # 13 scripts utilitaires + cockpit/ + trading_v2/
├── launchers/                 # 17 launchers (.bat + .ps1)
├── finetuning/                # Pipeline QLoRA (Qwen3-30B-A3B, 55,549 exemples)
├── canvas/                    # Canvas Autolearn Engine (port 18800)
├── n8n_workflows/             # 6 workflows n8n
├── data/                      # 3 bases SQL (etoile.db, jarvis.db, sniper.db)
├── docs/                      # 6 fichiers documentation
├── dashboard/                 # Dashboard web (stdlib, port 8080)
└── docker/                    # Docker Compose stack
```

---

## Installation

### Prerequis

- Windows 10/11 avec PowerShell 7+
- Python 3.13 (gere via `uv` v0.10.2)
- Node.js 20+ (pour Electron et MCP)
- NVIDIA GPU avec drivers recents (CUDA support)
- LM Studio installe sur chaque noeud (M1, M2, M3)

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
.\jarvis.bat                    # Mode standard
.\jarvis_voice.bat              # Mode vocal (Push-to-Talk CTRL)
.\jarvis_interactive.bat        # Mode interactif terminal
.\JARVIS_COMMANDER.bat          # Mode Commander (recommande)
```

### Modes de Lancement

| Launcher | Description |
|----------|-------------|
| `jarvis.bat` | Mode standard |
| `jarvis_voice.bat` | Mode vocal (Push-to-Talk CTRL, Whisper CUDA) |
| `jarvis_interactive.bat` | Mode interactif terminal |
| `JARVIS_COMMANDER.bat` | **Mode Commander** (Claude orchestre, recommande) |
| `jarvis_hybrid.bat` | Mode hybride voix + texte |
| `jarvis_dashboard.bat` | Dashboard web (port 8080) |
| `jarvis_systray.bat` | System tray (icone barre des taches) |
| `jarvis_mcp_stdio.bat` | Serveur MCP (pour Claude Desktop / LM Studio) |

### Slash Commands (plugin jarvis-turbo)

| Commande | Description |
|----------|-------------|
| `/cluster-check` | Health check tous noeuds |
| `/mao-check` | Health + GPU + services complet |
| `/gpu-status` | Temperatures + VRAM par GPU |
| `/thermal` | Monitoring thermique detaille |
| `/consensus [question]` | Vote pondere M2+OL1+M3+GEMINI |
| `/quick-ask [question]` | Question rapide OL1 (< 1s) |
| `/web-search [query]` | Recherche web minimax cloud |
| `/trading-scan [mode]` | Pipeline GPU trading |
| `/trading-feedback` | Retro-analyse signaux |
| `/heal-cluster` | Diagnostic + auto-reparation |
| `/canvas-status` | Statut proxy + autolearn |
| `/canvas-restart` | Kill + restart proxy 18800 |
| `/audit [mode]` | Audit systeme complet (10 sections, score A-F) |
| `/model-swap [args]` | Load/unload modeles LM Studio |
| `/deploy` | Git commit + push |

---

## Benchmark Cluster

Resultats du benchmark reel (2026-02-26) :

| Noeud | Modele | Latence | Score | Status | Poids |
|-------|--------|---------|-------|--------|-------|
| **M1** | qwen3-8b (65 tok/s) | 0.6–2.5s | **100%** | ONLINE | **1.8** |
| **M2** | deepseek-coder-v2-lite | 1.3s | **92%** | ONLINE | 1.4 |
| **OL1** | qwen3:1.7b | 0.5s | **88%** | ONLINE | 1.3 |
| **M3** | mistral-7b-instruct | 2.5s | **89%** | ONLINE | 1.0 |
| **GEMINI** | gemini-2.5-pro | variable | **74%** | CLOUD | 1.2 |
| **CLAUDE** | opus/sonnet/haiku | 12-18s | — | CLOUD | 1.2 |

```
Benchmark score global : 97% (7/7 phases)
Improve loop : 81.8/100 avg (377 OK / 403 tests)
M1 dual-instance : 2x qwen3-8b charges (65 tok/s chacun)
Audit systeme : Grade A, 82/100
```

---

## n8n Workflows

| Workflow | Fonction |
|----------|----------|
| `jarvis_brain_learning` | Auto-apprentissage et memorisation de patterns |
| `jarvis_cluster_monitor` | Surveillance sante cluster (toutes les 5min) |
| `jarvis_daily_report` | Rapport quotidien automatique (matin + soir) |
| `jarvis_git_auto_backup` | Backup Git automatique (commit + push) |
| `jarvis_system_health` | Health check systeme complet |
| `jarvis_trading_pipeline` | Pipeline trading automatise (scan + signal) |

---

## Stack Technique

| Couche | Technologies |
|--------|-------------|
| **Orchestration** | Claude Opus 4.6 (Agent SDK v0.1.35), MCP Protocol, uv v0.10.2 |
| **IA Locale** | LM Studio (qwen3-8b, deepseek-coder-v2, mistral-7b), Ollama v0.16.1 (qwen3:1.7b) |
| **IA Cloud** | Gemini 2.5 Pro, Claude Opus 4.6, Perplexity, minimax-m2.5 |
| **Backend** | Python 3.13, FastAPI, asyncio, httpx |
| **Desktop** | Electron 33, React 19, TypeScript, Vite 6, Tailwind CSS |
| **Voice** | Whisper large-v3-turbo (CUDA), Edge TTS fr-FR-HenriNeural, OpenWakeWord |
| **Trading** | CCXT (MEXC Futures), scoring multi-IA, sniper.db |
| **Database** | SQLite3 (etoile.db 18 tables, jarvis.db 11 tables, sniper.db 5 tables) |
| **Automation** | n8n v2.4.8, Playwright, Telegram Bot API |
| **DevOps** | Docker Compose, GitHub, uv (Python packaging) |

---

<p align="center">
  <strong>JARVIS Etoile v10.3</strong> — Built with passion by <a href="https://github.com/Turbo31150">Turbo31150</a>
</p>
<p align="center">
  <em>Repo prive — Derniere mise a jour : 2026-02-26</em>
</p>
