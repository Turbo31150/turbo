# JARVIS COWORK — 438 Scripts Autonomes de Developpement Continu

Workspace OpenClaw pour le developpement continu et autonome de JARVIS. Chaque script est independant, stdlib-only, et pilotable via argparse. Le systeme s'auto-alimente 24/7 via crons planifies sur le cluster IA distribue (4 noeuds locaux + 10 modeles cloud).

---

## Chiffres

| Metrique | Valeur |
|----------|--------|
| **Scripts Python** | 438 |
| **Prefixes uniques** | 101 |
| **Categories principales** | 10+ (win, jarvis, ia, auto, cluster, voice, dispatch, model, telegram, general) |
| **Batches** | 132 (1-132) |
| **Conventions** | stdlib-only, argparse CLI, JSON output, SQLite storage |

---

## Categories

### Windows (win_*) — 102 scripts
Monitoring systeme, thermique GPU, memoire, I/O disque, registre, firewall, WiFi, DNS, VPN, processus, services, taches planifiees, certificats, accessibilite, workspace profiles, focus timer, smart launcher, audio, fenetres, ecran, clipboard, app usage, crash analyzer, battery, peripheriques, defrag, imprimantes, corbeille, display, sound mixer, gestes, game mode, media, screen recorder, backup, file watcher, restore points, event watcher, task automator, power manager, optimizer, startup, security, network, drivers, USB, Bluetooth.

### JARVIS (jarvis_*) — 103 scripts
Performance, plugins, templates, macros, cron optimizer, embedding engine, NLP, sentiment, commandes predictives, backup, secrets scanner, permissions, changelog, config validator, ecosysteme map, pipeline monitor, API gateway, pattern learner, conversation memory, rule engine, notification hub, state machine, webhook server, event stream, config center, intent router, response cache, A/B tester, orchestrator v3, self-test suite, evolution engine, dialog manager, personality engine, multi-language, wake word tuner, voice profiles, dictation, health aggregator, release manager, meta dashboard, FAQ builder, wiki engine, skill recommender, self-improve, performance tracker.

### IA Autonome (ia_*) — 66 scripts
Cost tracker, routing optimizer, weight calibrator, ensemble voter, model benchmarker, context compressor, code generator, doc writer, test writer, workload balancer, model cache, inference profiler, swarm coordinator, memory consolidator, skill synthesizer, feedback loop, prompt optimizer, anomaly detector, goal decomposer, task prioritizer, chain-of-thought, self-critic, knowledge distiller, agent spawner, goal tracker, experiment runner, curriculum planner, transfer learner, meta-optimizer, debate engine, peer reviewer, teacher-student, story generator, image prompt crafter, data synthesizer, fact checker, hypothesis tester.

### Automation (auto_*) — 13 scripts
auto_deployer, auto_dispatcher, auto_documentation_updater, auto_documenter, auto_fixer, auto_healer, auto_learner, auto_monitor, auto_reporter, auto_scheduler, auto_skill_tester, auto_trader, auto_updater. Scripts d'automatisation transversale : deploiement continu, monitoring proactif, reparation autonome, documentation auto-generee.

### Cluster (cluster_*) — 9 scripts
cluster_autoscaler, cluster_autotuner, cluster_benchmark_auto, cluster_dashboard_api, cluster_health_monitor, cluster_load_predictor, cluster_model_lifecycle, cluster_resource_optimizer, cluster_sync. Gestion avancee du cluster IA : autoscaling, autotuning, benchmark, dashboard, prediction de charge, lifecycle modeles.

### Voice (voice_*) — 7 scripts
voice_browser_nav, voice_command_evolve, voice_enhancer, voice_profiles, voice_recognition_tuner, voice_wake_word, voice_dictation. Pipeline vocale complete : navigation navigateur, evolution commandes, profils voix, wake word, dictee, tuning reconnaissance.

### Dispatch (dispatch_*) — 6 scripts
dispatch_logger, dispatch_optimizer, dispatch_quality_tracker, dispatch_router, dispatch_strategy, dispatch_analytics. Moteur de routage intelligent : logging, optimisation, qualite, strategie adaptative, analytics.

### Model (model_*) — 5 scripts
model_benchmark, model_cache, model_rotator, model_selector, model_manager. Gestion des modeles IA : benchmark, cache, rotation, selection dynamique.

### Telegram (telegram_*) — 4 scripts
telegram_commander, telegram_scheduler, telegram_stats, telegram_features. Hub Telegram : commandes, planification, statistiques, fonctionnalites avancees.

### Autres prefixes (167 scripts)
`smart_*` (3), `log_*` (3), `continuous_*` (3), `workspace_*` (2), `windows_*` (2), `system_*` (2), `service_*` (2), `self_*` (2), `resource_*` (2), `report_*` (2), `notification_*` (2), `performance_*` (2), et 60+ prefixes uniques couvrant : agent_orchestrator, ai_conversation, anomaly_detector, api_monitor, audio_controller, browser_automation, clipboard, context_engine, dashboard, data_exporter, decision_engine, deployment_manager, energy_manager, event_logger, file_organizer, gpu_*, health_checker, intent_classifier, knowledge_graph, load_balancer, metrics_collector, network_monitor, node_balancer, pipeline_*, power_manager, prompt_optimizer, proactive_agent, screenshot_tool, security_scanner, signal_backtester, task_queue, test_generator, trading_intelligence, usage_analytics, workflow_builder, etc.

---

## Conventions

- **stdlib-only** — Aucune dependance pip, uniquement la bibliotheque standard Python 3.13
- **argparse CLI** — Chaque script a `--help` et `--once`
- **JSON output** — `json.dumps(result, ensure_ascii=False, indent=2)`
- **SQLite storage** — `dev/data/*.db` pour persistance locale
- **Windows 11** — ctypes user32, powershell, wmic, netsh
- **Idempotent** — Chaque script peut tourner en boucle sans effet de bord

---

## Cluster IA (4 noeuds locaux + cloud)

### Noeuds Locaux (24/7 sans internet)

| Noeud | Machine | GPU / VRAM | Modele | Score | Poids |
|-------|---------|------------|--------|-------|-------|
| **M1** | PC principal | 6 GPU / 46 GB | **qwen3-8b** | **98.4/100** | **1.8** |
| **M1B** | PC principal | 6 GPU / 46 GB | **gpt-oss-20b** (deep) | — | 1.7 |
| **M2** | PC secondaire | 3 GPU / 24 GB | **deepseek-r1-0528-qwen3-8b** | — | 1.5 |
| **M3** | PC tertiaire | 1 GPU / 8 GB | **deepseek-r1-0528-qwen3-8b** | — | 1.2 |

### Cloud (optionnel, etend les capacites)

| Service | Modele | Score | Poids |
|---------|--------|-------|-------|
| **gpt-oss:120b** | GPT-OSS 120B | **100/100** | **1.9** |
| **devstral-2:123b** | Devstral 2 123B | ~94/100 | 1.5 |
| **GEMINI** | Gemini 3 Pro/Flash | 74/100 | 1.2 |
| **CLAUDE** | Opus/Sonnet/Haiku | variable | 1.2 |

**Fallback cascade** : M1 → M1B → M2 → M3 → gpt-oss → devstral → Gemini → Claude

---

## Integration JARVIS

Ces scripts sont pilotes par le moteur dispatch (`src/dispatch_engine.py`) et le bridge cowork (`src/cowork_bridge.py`) de JARVIS Turbo. Le systeme proactif (`src/cowork_proactive.py`) detecte automatiquement les besoins et lance les scripts pertinents.

### Pipeline d'execution

```
Besoin detecte (quality_gate / health / dispatch / self_improvement)
    |
    v
cowork_proactive.detect_needs() → categorise le besoin
    |
    v
cowork_bridge.search(category) → trouve les scripts pertinents
    |
    v
ExecutionPlan → priorise et ordonne les scripts
    |
    v
execute_plan() → lance chaque script via subprocess
    |
    v
Resultat → log dans cowork_proactive_log (etoile.db)
```

### Modules JARVIS connectes

| Module | Role | Interaction |
|--------|------|-------------|
| `dispatch_engine.py` | Routage unifie | Route les requetes vers agents + scripts cowork |
| `cowork_bridge.py` | Index 438 scripts | Recherche par categorie/nom, execution CLI |
| `cowork_proactive.py` | Proactivite | Detection besoins → plan → execution automatique |
| `dynamic_agents.py` | Agents dynamiques | 78 patterns DB, fallback vers scripts cowork |
| `self_improvement.py` | Auto-amelioration | Analyse perf → suggestions → scripts correctifs |
| `pattern_evolution.py` | Evolution patterns | Cree/evolue patterns depuis historique dispatch |
| `reflection_engine.py` | Meta-cognition | Analyse tendances sur 5 axes |

---

## Usage

```bash
# Executer un script en mode one-shot
python dev/win_thermal_monitor.py --once

# Aide sur un script
python dev/jarvis_backup_manager.py --help

# Equilibrage charge cluster
python dev/ia_workload_balancer.py --balance

# Trading scan
python dev/auto_trader.py --once

# Audit securite
python dev/security_scanner.py --once
```

---

## Structure

```
jarvis-cowork/
├── dev/                        # 438 scripts Python autonomes
│   ├── win_*.py               # 102 — Windows monitoring & automation
│   ├── jarvis_*.py            # 103 — JARVIS intelligence & core
│   ├── ia_*.py                #  66 — IA autonome & machine learning
│   ├── auto_*.py              #  13 — Automation transversale
│   ├── cluster_*.py           #   9 — Cluster IA management
│   ├── voice_*.py             #   7 — Pipeline vocale
│   ├── dispatch_*.py          #   6 — Moteur de routage
│   ├── model_*.py             #   5 — Gestion modeles IA
│   ├── telegram_*.py          #   4 — Bot Telegram
│   ├── (60+ autres prefixes)  # 167 — Scripts specialises
│   └── data/                  # SQLite databases + exports + backups
├── COWORK_QUEUE.md            # Queue de taches (batches 1-132)
├── IDENTITY.md                # Identite JARVIS
├── INSTRUCTIONS.md            # Instructions systeme
├── TOOLS.md                   # Outils disponibles
└── README.md                  # Ce fichier
```

---

## Developpement Continu

Le systeme fonctionne en boucle fermee auto-alimentee :

1. **Detection** — `cowork_proactive.py` detecte gaps, baisses qualite, noeuds lents
2. **Planification** — Selectionne les scripts cowork pertinents
3. **Execution** — Lance les scripts en mode `--once`
4. **Feedback** — Resultats injectes dans `dispatch_engine` + `self_improvement`
5. **Evolution** — `pattern_evolution.py` cree de nouveaux patterns si necessaire
6. **Boucle** — Le cycle recommence toutes les 5min-12h selon la criticite

**Crons actifs** : 316+ taches planifiees (5min a 24h) couvrant monitoring, dev, tests, deploiement, trading, securite, voice, cluster.

---

*JARVIS Etoile v12.1 — Systeme d'IA distribue autonome multi-GPU*
