# JARVIS COWORK — 331 Scripts Autonomes de Developpement Continu

Workspace OpenClaw pour le developpement continu et autonome de JARVIS.

## Chiffres

| Metrique | Valeur |
|----------|--------|
| **Scripts Python** | 331 |
| **DEPLOYED** | 251 |
| **PENDING** | 92 |
| **Batches** | 116 (1-116) |
| **Categories** | Windows, JARVIS, IA |

## Categories

### Windows (win_*)
Monitoring systeme, thermique GPU, memoire, I/O disque, registre, firewall, WiFi, DNS, VPN, processus, services, taches planifiees, certificats, accessibilite, workspace profiles, focus timer, smart launcher, audio, fenetres, ecran, clipboard, app usage, crash analyzer, battery, peripheriques, defrag, imprimantes, corbeille, display, sound mixer, gestes, game mode, media, screen recorder, backup, file watcher, restore points.

### JARVIS (jarvis_*)
Performance, plugins, templates, macros, cron optimizer, embedding engine, NLP, sentiment, commandes predictives, backup, secrets scanner, permissions, changelog, config validator, ecosysteme map, pipeline monitor, API gateway, pattern learner, conversation memory, rule engine, notification hub, state machine, webhook server, event stream, config center, intent router, response cache, A/B tester, orchestrator v3, self-test suite, evolution engine, dialog manager, personality engine, multi-language, wake word tuner, voice profiles, dictation, health aggregator, release manager, meta dashboard, FAQ builder, wiki engine, skill recommender.

### IA Autonome (ia_*)
Cost tracker, routing optimizer, weight calibrator, ensemble voter, model benchmarker, context compressor, code generator, doc writer, test writer, workload balancer, model cache, inference profiler, swarm coordinator, memory consolidator, skill synthesizer, feedback loop, prompt optimizer, anomaly detector, goal decomposer, task prioritizer, chain-of-thought, self-critic, knowledge distiller, agent spawner, goal tracker, experiment runner, curriculum planner, transfer learner, meta-optimizer, debate engine, peer reviewer, teacher-student, story generator, image prompt crafter, data synthesizer, fact checker, hypothesis tester.

## Conventions

- **stdlib-only** — Aucune dependance pip, uniquement la bibliotheque standard Python
- **argparse CLI** — Chaque script a `--help` et `--once`
- **JSON output** — `json.dumps(result, ensure_ascii=False, indent=2)`
- **SQLite storage** — `dev/data/*.db` pour persistance
- **Windows 11** — ctypes user32, powershell, wmic, netsh

## Cluster IA

| Noeud | Modele | Score | Poids |
|-------|--------|-------|-------|
| gpt-oss:120b | Cloud | 100/100 | 1.9 |
| M1 | qwen3-8b | 98.4/100 | 1.8 |
| devstral-2:123b | Cloud | ~94/100 | 1.5 |
| M2 | deepseek-coder | 85.1 | 1.4 |
| OL1 | qwen3:14b | 88% | 1.3 |
| GEMINI | gemini-3-pro | 74% | 1.2 |

## Usage

```bash
# Executer un script
python dev/win_thermal_monitor.py --once

# Aide
python dev/jarvis_backup_manager.py --help

# Stats
python dev/ia_workload_balancer.py --balance
```

## Structure

```
workspace/
├── dev/                  # 331 scripts Python
│   └── data/            # SQLite databases + exports + backups
├── COWORK_QUEUE.md      # Queue de taches (251 DEPLOYED / 92 PENDING)
├── IDENTITY.md          # Identite JARVIS
├── INSTRUCTIONS.md      # Instructions systeme
├── TOOLS.md             # Outils disponibles
└── README.md            # Ce fichier
```
