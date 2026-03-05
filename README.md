<p align="center">
  <img src="https://img.shields.io/badge/version-v11.0.0-blueviolet?style=for-the-badge" alt="version"/>
  <img src="https://img.shields.io/badge/GPU-10x_NVIDIA-76B900?style=for-the-badge&logo=nvidia" alt="gpu"/>
  <img src="https://img.shields.io/badge/Claude_SDK-Opus_4.6-orange?style=for-the-badge&logo=anthropic" alt="claude"/>
  <img src="https://img.shields.io/badge/Python-3.13-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="python"/>
  <img src="https://img.shields.io/badge/Electron-33-47848F?style=for-the-badge&logo=electron&logoColor=white" alt="electron"/>
  <img src="https://img.shields.io/badge/Telegram-Bot-26A5E4?style=for-the-badge&logo=telegram" alt="telegram"/>
  <img src="https://img.shields.io/badge/License-Private-red?style=for-the-badge" alt="license"/>
</p>

<h1 align="center">JARVIS Etoile v11.0.0</h1>
<h3 align="center">Orchestrateur IA Distribue Multi-GPU — HEXA_CORE + Telegram Autonome + OpenClaw Gateway + Perplexity MCP</h3>

<p align="center">
  <strong>Systeme d'intelligence artificielle distribue sur 3 machines physiques, 10 GPU NVIDIA (~78 GB VRAM), 12 modeles IA (2 local + 10 cloud) et 108 skills autonomes. Controle vocal en francais avec 1,706 commandes + 476 pipelines + 835 domino cascades + 2,628 corrections vocales. Bot Telegram autonome (@turboSSebot) via OpenClaw Gateway (port 18789, 35 agents). Perplexity connecte via MCP (23 outils). Messages vocaux TTS DeniseNeural + Whisper STT entrant. Trading algorithmique MEXC multi-consensus. Interface desktop Electron 19 pages. Navigateur Comet (Perplexity) par defaut. 212 modules source (80,000+ lignes), 528+ tests, 249 scripts COWORK continu (80 batches), 244+ crons autonomes.</strong>
</p>

<p align="center">
  <em>"Claude = Commandant Pur. Il ne fait JAMAIS le travail lui-meme. Il ORDONNE, VERIFIE et ORCHESTRE."</em>
</p>

---

## Chiffres Cles

| Metrique | Valeur | Detail |
|----------|--------|--------|
| **GPU** | 10 NVIDIA / ~78 GB VRAM | RTX 3080 10GB, RTX 2060 12GB, 4x GTX 1660S 6GB, 3x GPU M2 24GB, 1x GPU M3 8GB |
| **Modeles IA** | 12 (2 local + 10 cloud) | M1 qwen3-8b, OL1 qwen3:14b/1.7b, gpt-oss:120b, devstral-2:123b, deepseek-coder, mistral-7b, GEMINI, CLAUDE + 6 cloud |
| **Agents** | 7 Claude SDK + 11 Plugin + 35 OpenClaw | 53 agents total — deep, fast, check, trading, system, bridge, consensus + 11 plugin + 35 OpenClaw Gateway |
| **Outils MCP** | 117 tools + 531 handlers | tools.py (117 fonctions) + mcp_server.py (531 handlers) = 7,322 lignes |
| **Commandes vocales** | 1,706 commandes + 476 pipelines | 443 commands jarvis.db + 1,706 map entries + 121 domino triggers |
| **Domino Cascades** | 835 cascades / 121 triggers | 11 categories, 84 actions Python, 28 param patterns, 40 pipelines domino |
| **Corrections vocales** | 2,628 regles (120 vagues) | Phonetiques + alias + implicits + fillers + auto-training |
| **Skills** | 108 dynamiques | 16 vagues + domaines etoile.db, persistants en DB |
| **Source Python** | 212 modules / 80,000+ lignes | src/ uniquement (135,000+ total avec COWORK dev/) |
| **Databases** | 4 bases SQL (40 tables) | etoile.db (22t, 11,282r) + jarvis.db (12t, 5,908r) + sniper.db (6t, 768r) + finetuning.db |
| **Tests** | 528+ tests (11 suites) | test_phase1 a test_phase11 + test_telegram_bot |
| **Plugin** | 40 slash commands | + 24 skills + 11 agents + 4 hooks (plugin v3.0) |
| **Desktop** | Electron 33 + React 19 | 19 pages, Portable 72.5 MB |
| **Navigateur** | Comet (Perplexity) | Defaut CDP port 9222, fallback Chrome/Edge |
| **Trading** | v2.3 Multi-GPU | MEXC Futures 10x, 6 IA consensus |
| **Telegram Bot** | @turboSSebot autonome | OpenClaw Gateway (port 18789) + 35 agents + Whisper STT + DeniseNeural TTS |
| **OpenClaw** | Gateway + 35 agents | 7 providers (M1, M2, M3, OL1, Gemini, Claude, Qwen), fallback cascade |
| **COWORK** | 249 scripts + 244 crons | 80 batches (28-108), dev continu 24/7, Perplexity MCP integre |
| **Voix TTS** | DeniseNeural (femme) | Edge TTS Neural + ffmpeg OGG Opus + Telegram sendVoice |
| **Voix STT** | Whisper large-v3-turbo | Transcription vocaux Telegram entrants, CUDA accelere |

---

## Nouveautes v11.0.0 — 249 Scripts COWORK + 244 Crons + 80 Batches + Perplexity MCP (2026-03-05)

> **249 scripts COWORK** en developpement continu autonome (80 batches, 244 crons). **Perplexity connecte via MCP** avec 23 outils directs sur le cluster. **35 agents OpenClaw** avec 7 providers IA. **212 modules Python** (80,000+ lignes src/). Batches 28-108 couvrant Windows Automation, JARVIS Intelligence, IA Autonome, Trading, Security, Voice, Neural Core, Swarm Intelligence, Meta-Learning, et bien plus. Crons planifies pour dev autonome non-stop 24/7.

### Changements v10.7.0 → v11.0.0

| Categorie | Avant | Apres | Detail |
|-----------|-------|-------|--------|
| **COWORK Scripts** | 131 scripts | **249 scripts** | +118 scripts (batches 49-108) |
| **COWORK Crons** | 76 crons | **244 crons** | Dev continu 24/7, crons recurrents + one-shot |
| **COWORK Batches** | 18 batches (28-48) | **80 batches (28-108)** | +62 batches Windows/JARVIS/IA Autonome |
| **Perplexity MCP** | Non connecte | **23 outils MCP** | lm_query, ollama_query, gemini_query, consensus, trading, etc. |
| **Modules src/** | 177 modules | **212 modules** | 80,000+ lignes (phase 4-11 + expansions) |
| **COWORK Deploy** | 83 deployed | **167 deployed** | 80 PENDING, deploiement autonome continu |

### Batches COWORK (28-108) — 80 Batches

| Range | Themes | Scripts |
|-------|--------|---------|
| 28-48 | Foundation (Windows, JARVIS, IA, Cluster, Productivite) | 63 scripts |
| 49-60 | JARVIS Performance, Windows Security, IA Predictive | 36 scripts |
| 61-68 | Registry, Performance, Automation Pro, Intelligence Hub | 24 scripts |
| 69-76 | System Hardening, Voice Evolution, Autonomous Decision | 24 scripts |
| 77-84 | AI Integration, Workflow Automation, Creative Engine | 24 scripts |
| 85-92 | AI Desktop, Neural Core, Swarm Intelligence, Cognitive | 24 scripts |
| 93-100 | Deep Automation, Smart Routing, Meta-Learning, Ultimate | 24 scripts |
| 101-108 | Advanced Control, Conversational AI, Generative, Final | 24 scripts |

### Changements v10.6.0 → v10.6.1 (historique)

| Categorie | Avant | Apres | Detail |
|-----------|-------|-------|--------|
| **Telegram Backend** | canvas proxy (18800) | **OpenClaw Gateway (18789)** | 35 agents, 7 providers, polling natif |
| **Voix TTS** | HenriNeural (homme) | **DeniseNeural (femme, Neural)** | Edge TTS → MP3 → ffmpeg OGG Opus → Telegram |
| **Voix STT** | Aucun | **Whisper large-v3-turbo** | Transcription vocaux entrants Telegram, CUDA |
| **TTS Script** | Aucun | **win_tts.py** | Pipeline complete : clean text + edge-tts + OGG + Telegram |
| **Modele primaire** | gpt-oss:120b-cloud | **M1 qwen3-8b (local)** | 0 quota cloud, contexte max, 45 tok/s |
| **OpenClaw Config** | Basique | **Full autonome** | exec-approvals off, reasoning false, sandbox off |
| **IDENTITY.md** | Generique | **3 regles absolues** | Execution immediate, reponse complete, vocal obligatoire |

### Architecture Telegram via OpenClaw Gateway

```
Utilisateur ecrit/parle dans Telegram
    |
    v
OpenClaw Gateway (port 18789, long polling)
    |
    +-- Texte → agent main (M1 qwen3-8b, fallback cascade)
    +-- Vocal → Whisper transcription → agent main
    |
    v
Agent embedded → lit IDENTITY.md/SOUL.md → execute scripts dev/
    |
    +-- python dev/telegram_commander.py --cmd [status|emails|trading|...]
    +-- python dev/win_tts.py --speak "RESUME" --telegram
    +-- curl cluster IA (M1/M2/M3/OL1/gpt-oss/devstral/GEMINI/CLAUDE)
    |
    v
Reponse texte + vocal OGG Opus → Telegram
```

**Providers OpenClaw (7) :** lm-m1 (qwen3-8b), lm-m2 (deepseek-coder), lm-m3 (mistral-7b), ollama (10 cloud), gemini (pro/flash), claude (opus/sonnet/haiku), qwen-portal.

**Fallback cascade :** M1 → OL1 (1.7b/14b) → M2 → gpt-oss → devstral → Gemini → Claude.

### Navigateur Comet (Perplexity) — Defaut CDP

```
Comet (Perplexity) → Chrome DevTools Protocol (port 9222)
    |
    +-- browser_pilot.py : pilotage navigateur autonome
    +-- voice_browser_nav.py : navigation vocale
    |
    v
Auto-detection : Comet > Chrome > Edge (priorite)
    Comet : %LOCALAPPDATA%\Perplexity\Comet\Application\comet.exe
    Chrome : Program Files\Google\Chrome\Application\chrome.exe
    Edge : Program Files (x86)\Microsoft\Edge\Application\msedge.exe
```

### COWORK — Developpement Continu Autonome (131 scripts, 76 crons)

| Batch | Theme | Scripts | Status |
|-------|-------|---------|--------|
| 28 | Monitoring | log_analyzer, api_monitor, resource_forecaster | DEPLOYED |
| 29 | Alerting | alert_manager, dashboard_generator, metrics_collector | DEPLOYED |
| 30 | AI Pipeline | prompt_router, response_evaluator, model_benchmark | DEPLOYED |
| 31 | Conversation | conversation_manager, knowledge_updater, pipeline_orchestrator | DEPLOYED |
| 32 | Windows Auto | service_watchdog, startup_manager, power_manager | DEPLOYED |
| 33 | IA Autonome | auto_dispatcher, self_improver, task_learner | DEPLOYED |
| 34 | Cluster Intel | node_balancer, model_manager, cluster_sync | DEPLOYED |
| 35 | Telegram+ | telegram_scheduler, telegram_stats, voice_enhancer | DEPLOYED |
| 36 | Windows Deep | win_event_watcher, win_firewall_manager, win_task_automator | DEPLOYED |
| 37 | IA Avancee | agent_orchestrator, code_generator, decision_engine | DEPLOYED |
| 38 | Perf Optimize | gpu_optimizer, memory_optimizer, network_optimizer | DEPLOYED |
| 39 | Intelligence | continuous_learner, proactive_agent, workspace_analyzer | DEPLOYED |
| 43 | Brain Evolution | context_engine, skill_builder, reflection_engine | Cron programme |
| 44 | Windows Deep Mastery | clipboard_manager, hotkey_manager, multi_desktop | Cron programme |
| 45 | IA Autonome Nv2 | goal_tracker, experiment_runner, auto_fixer | Cron programme |
| 46 | Communication | notification_center, report_generator, voice_command_evolve | Cron programme |
| 47 | Cluster Intel Avancee | model_selector, cluster_autoscaler, consensus_voter | Cron programme |
| 48 | Productivite | workflow_builder, time_tracker, focus_mode | Cron programme |

**49 crons recurrents 24/7 + 27 one-shot (batches 43-48).**

Principaux crons recurrents :
- **5 min** : dev_proactive_check, dev_electron_monitor
- **10 min** : dev_decision_engine, dev_trading_intel, dev_perf_tuner
- **30 min** : dev_proactive_agent
- **1-2h** : dev_feature_builder, dev_improve_scripts, dev_jarvis_brain, dev_cluster_autotuner, dev_conversation_memory, dev_registry_guardian, dev_self_feed
- **3-4h** : dev_ia_autonome, dev_learning_cycle, dev_continuous_code, dev_voice_optimizer, dev_auto_deployer, dev_self_evolve, dev_windows_services, dev_test_all_scripts, dev_auto_codegen
- **6-8h** : dev_mcp_tools, dev_workspace_health, dev_new_features, dev_mcp_tester, dev_skill_generator, dev_cluster_optimize
- **12h+** : dev_telegram_features, dev_testing_infra (daily), dev_continuous_tests (daily), dev_night_ops (23h)

### Pipeline TTS Vocal (win_tts.py)

```
Texte reponse
    |
    v
clean_text_for_speech() — supprime ponctuation, symboles, emojis
    |
    v
edge-tts --voice "fr-FR-DeniseNeural" → MP3 (24kHz Neural)
    |
    v
ffmpeg → OGG Opus (96kbps, 48kHz, volume boost +1.3, compresseur)
    |
    v
Telegram sendVoice → vocal ecoutable
```

**Commandes Telegram :** texte libre → routing auto, vocaux → Whisper → execution.

**Scripts disponibles (71+ existants) :** emails, status, trading, gpu, disk, cluster, bluetooth, wifi, backup, securite, processus, reseau, screenshot, audio, registre, drivers, et 50+ autres dans dev/.

### Nouveaux Modules Systeme (Phases 19-43)

| Phase | Modules | Description |
|-------|---------|-------------|
| 4 | orchestrator_v2, autonomous_loop, task_queue, notifier, agent_memory, pipeline_composer, proactive_agent, conversation_store, load_balancer | Orchestration avancee + memoire |
| 5 | auto_optimizer, event_bus, metrics_aggregator | Optimisation automatique |
| 6 | workflow_engine, session_manager, alert_manager | Workflows + alertes |
| 7 | config_manager, audit_trail, cluster_diagnostics | Configuration + audit |
| 8 | rate_limiter, task_scheduler, health_dashboard | Limites + planification |
| 9 | plugin_manager, command_router, resource_monitor | Plugins + NL routing |
| 10 | retry_manager, data_pipeline, service_registry | Resilience + ETL |
| 11 | cache_manager, secret_vault, dependency_graph | Cache L1/L2 + secrets |

### gpt-oss:120b — CHAMPION Cloud (100/100, 4 runs stables)

Nouveau champion code cloud via Ollama : **gpt-oss:120b** score parfait 100/100 (Q100% V100% R100%, 51 tok/s). Poids consensus 1.9. Routing prioritaire pour code/review/securite.

---

## Utilisation — Comment parler a JARVIS

JARVIS est un assistant IA personnel autonome controlable depuis **Telegram** (@turboSSebot). Il suffit d'ecrire ou de parler, JARVIS execute et repond en vocal.

### Communication

```
Tu parles ou ecris dans Telegram
    |
    +-- Message texte → JARVIS lit et execute immediatement
    +-- Message vocal → Whisper transcrit ta voix → JARVIS execute
    |
    v
JARVIS repond en TEXTE + MESSAGE VOCAL (voix Denise, femme francaise)
```

**Pas besoin de commandes speciales.** Tu parles naturellement en francais et JARVIS comprend ce que tu veux. Il ne demande jamais de confirmation — il execute directement et te dit quand c'est fini.

### Ce que tu peux demander

#### Emails
| Tu dis... | JARVIS fait... |
|-----------|----------------|
| "lis mes mails" | Lit les derniers emails des 2 comptes Gmail (perso + mining) |
| "j'ai des mails ?" | Verifie les boites de reception et resume les nouveaux messages |
| "envoie un mail a X" | Redige et envoie un email via le compte configure |

#### Marche & Trading
| Tu dis... | JARVIS fait... |
|-----------|----------------|
| "scan le marche" | Analyse les 10 paires crypto (BTC, ETH, SOL, SUI, PEPE, DOGE, XRP, ADA, AVAX, LINK) |
| "signal trading" | Genere des signaux d'achat/vente avec score de confiance (seuil 70/100) |
| "comment va le bitcoin" | Donne le prix, tendance et analyse technique |
| "backtest la strategie" | Retro-analyse les performances des signaux passes |
| "portfolio" | Affiche le portefeuille, gains/pertes, positions ouvertes |

#### Controle Windows
| Tu dis... | JARVIS fait... |
|-----------|----------------|
| "range le bureau" | Organise les fichiers du bureau dans des dossiers par type |
| "optimise le PC" | Lance l'optimisation Windows (cache, temp files, services) |
| "espace disque" | Affiche l'espace libre sur C: et F: |
| "temperature GPU" | Affiche les temperatures et VRAM des 10 GPU |
| "processus" | Liste les processus les plus gourmands en CPU/RAM |
| "screenshot" | Prend une capture d'ecran et l'envoie sur Telegram |
| "wifi" | Affiche l'etat de la connexion WiFi |
| "bluetooth" | Status des peripheriques Bluetooth |
| "volume" | Controle le volume audio du PC |
| "pilotes" | Verifie les drivers Windows et detecte les problemes |
| "registre" | Gere le registre Windows (lecture, nettoyage) |
| "sauvegarde" | Lance un backup complet du systeme |
| "securite" | Scan de securite complet (ports, services, vulnerabilites) |
| "reseau" | Monitore le reseau local et la bande passante |
| "USB" | Detecte les peripheriques USB connectes |

#### Cluster IA
| Tu dis... | JARVIS fait... |
|-----------|----------------|
| "status cluster" | Verifie les 4 noeuds (M1, M2, M3, OL1) et leurs modeles |
| "health check" | Diagnostic complet du cluster avec scores |
| "benchmark" | Teste les performances de chaque noeud IA |
| "charge un modele" | Charge/decharge des modeles sur LM Studio ou Ollama |

#### Taches & Rapports
| Tu dis... | JARVIS fait... |
|-----------|----------------|
| "rapport" | Genere un bilan complet : systeme, cluster, trading, emails |
| "status" | Resume rapide de l'etat du systeme |
| "aide" | Liste toutes les commandes disponibles |
| Toute question complexe | Dispatch au cluster IA pour une reponse intelligente |

### Taches Automatisees (sans rien demander)

JARVIS execute ces taches tout seul, 24h/24, et te previent sur Telegram si quelque chose d'important se passe :

#### Monitoring continu
| Tache | Frequence | Action |
|-------|-----------|--------|
| **Health check cluster** | Toutes les heures | Verifie M1/M2/M3/OL1, alerte si un noeud tombe |
| **Status systeme** | Toutes les 15 min | CPU, RAM, GPU, disques — alerte si seuils depasses |
| **Trading scan** | Toutes les 30 min | Scanne les 10 paires crypto, envoie signaux si score > 70 |
| **Surveillance GPU** | Continue | Alerte si temperature > 80C, decharge le modele si > 85C |

#### Maintenance automatique
| Tache | Frequence | Action |
|-------|-----------|--------|
| **Backup** | Chaque nuit 2h | Sauvegarde les configs, scripts et bases de donnees |
| **Optimisation DB** | Chaque nuit 4h | VACUUM et reindex des 4 bases SQLite |
| **Scan securite** | Chaque nuit 3h | Audit ports, services, permissions Windows |
| **Mise a jour check** | Chaque matin 7h | Verifie les mises a jour disponibles |
| **Rapport quotidien** | Chaque matin 8h | Resume de la nuit envoye sur Telegram |
| **Rotation logs** | Quotidien | Nettoie les logs > 7 jours |

#### Developpement continu (COWORK)
| Tache | Frequence | Action |
|-------|-----------|--------|
| **Amelioration scripts** | Toutes les 2h | Analyse et corrige les scripts existants dans dev/ |
| **Creation scripts** | Toutes les 6h | Cree le prochain script PENDING de la queue COWORK |
| **Tests automatiques** | Toutes les 4h | Teste tous les scripts avec --help, corrige les fails |
| **Optimisation cluster** | Toutes les 8h | Analyse les performances et optimise le routing |
| **Services Windows** | Toutes les 4h | Verifie et developpe les integrations Windows |
| **IA autonome** | Toutes les 3h | Developpe les fonctionnalites d'IA autonome |
| **Outils MCP** | Toutes les 6h | Ameliore les outils MCP du cluster |
| **Features Telegram** | Toutes les 12h | Ameliore le bot Telegram et ses commandes |
| **Infra de tests** | Quotidien | Ameliore la couverture de tests |

### Les 131 scripts operationnels

<details>
<summary><b>Liste complete des 131 scripts dev/ (cliquer pour voir)</b></summary>

| Script | Fonction |
|--------|----------|
| **telegram_commander.py** | Hub central — emails, status, trading, health, services, benchmark |
| **win_tts.py** | Synthese vocale DeniseNeural → OGG Opus → Telegram |
| **email_reader.py** | Lecture Gmail 2 comptes (perso + mining) |
| **auto_trader.py** | Trading algorithmique MEXC Futures 10x |
| **signal_backtester.py** | Backtest strategies trading |
| **portfolio_tracker.py** | Suivi portefeuille crypto |
| **risk_manager.py** | Gestion du risque trading |
| **trading_intelligence.py** | Analyse marche multi-IA |
| **gpu_thermal_guard.py** | Surveillance thermique GPU avec alertes |
| **process_manager.py** | Gestion processus Windows (top, kill) |
| **file_organizer.py** | Range les fichiers par type/date |
| **win_optimizer.py** | Optimisation Windows (cache, services, startup) |
| **win_backup.py** | Backup systeme automatise |
| **security_scanner.py** | Audit securite complet |
| **network_monitor.py** | Monitoring reseau et bande passante |
| **audio_controller.py** | Controle volume audio |
| **screenshot_tool.py** | Capture ecran → Telegram |
| **bluetooth_manager.py** | Gestion peripheriques Bluetooth |
| **wifi_manager.py** | Status et gestion WiFi |
| **usb_monitor.py** | Detection peripheriques USB |
| **driver_checker.py** | Verification pilotes Windows |
| **registry_manager.py** | Gestion registre Windows |
| **system_restore.py** | Points de restauration Windows |
| **scheduled_task_creator.py** | Taches planifiees Windows |
| **display_manager.py** | Gestion ecrans et resolution |
| **power_manager.py** | Plans d'alimentation Windows |
| **startup_manager.py** | Programmes au demarrage |
| **health_checker.py** | Diagnostic sante systeme |
| **system_benchmark.py** | Benchmark performances |
| **db_optimizer.py** | Optimisation bases SQLite |
| **log_analyzer.py** | Analyse fichiers log |
| **log_rotator.py** | Rotation et nettoyage logs |
| **api_monitor.py** | Monitoring APIs du cluster |
| **resource_forecaster.py** | Prediction utilisation ressources |
| **alert_manager.py** | Gestionnaire alertes configurables |
| **dashboard_generator.py** | Dashboard HTML metriques |
| **metrics_collector.py** | Collecte metriques periodique |
| **auto_monitor.py** | Monitoring automatique continu |
| **auto_reporter.py** | Rapports automatiques |
| **auto_scheduler.py** | Planification taches automatique |
| **auto_healer.py** | Auto-reparation services |
| **auto_updater.py** | Mise a jour automatique |
| **auto_learner.py** | Apprentissage automatique patterns |
| **auto_documenter.py** | Documentation auto du code |
| **service_watcher.py** | Surveillance services Windows |
| **load_balancer.py** | Equilibrage charge cluster |
| **model_rotator.py** | Rotation modeles IA |
| **intent_classifier.py** | Classification intentions texte |
| **code_reviewer.py** | Revue automatique code |
| **config_validator.py** | Validation configurations |
| **test_generator.py** | Generation tests automatique |
| **notification_hub.py** | Hub notifications multi-canal |
| **event_logger.py** | Journal evenements systeme |
| **performance_profiler.py** | Profilage performances |
| **data_exporter.py** | Export donnees CSV/JSON |
| **knowledge_graph.py** | Graphe de connaissances |
| **context_engine.py** | Moteur de contexte conversationnel |
| **prompt_optimizer.py** | Optimisation prompts IA |
| **usage_analytics.py** | Analytiques utilisation |
| **workspace_sync.py** | Synchronisation workspace |
| **deployment_manager.py** | Gestion deploiements |
| **smart_launcher.py** | Lanceur intelligent applications |
| **report_mailer.py** | Envoi rapports par email |
| **tts_cache_manager.py** | Cache synthese vocale |
| **clipboard_history.py** | Historique presse-papier |
| **task_queue.py** | File d'attente taches |
| **task_automator.py** | Automatisation taches complexes |
| **anomaly_detector.py** | Detection anomalies systeme |
| **telegram_bot_monitor.py** | Monitoring bot Telegram |
| **voice_trainer.py** | Entrainement reconnaissance vocale |
| **ai_conversation.py** | Conversations multi-tours IA |
| **ia_self_improver.py** | Auto-amelioration IA |
| **ia_proactive_agent.py** | Agent proactif anticipation |
| **jarvis_autonomy_engine.py** | Moteur d'autonomie JARVIS |
| **jarvis_brain.py** | Cerveau central JARVIS |
| **jarvis_conversation_memory.py** | Memoire conversationnelle |
| **jarvis_feature_builder.py** | Constructeur de features |
| **jarvis_night_ops.py** | Operations nocturnes automatiques |
| **jarvis_self_evolve.py** | Auto-evolution du systeme |
| **jarvis_skill_generator.py** | Generateur de skills |
| **multi_agent_coordinator.py** | Coordination multi-agents |
| **cluster_dashboard_api.py** | API dashboard cluster |
| **cluster_autotuner.py** | Auto-tuning cluster |
| **continuous_test_runner.py** | Tests continus automatiques |
| **mcp_tool_tester.py** | Testeur outils MCP |
| **voice_pipeline_optimizer.py** | Optimisation pipeline vocale |
| **win_performance_tuner.py** | Tuning performances Windows |
| **win_registry_guardian.py** | Gardien registre Windows |
| **windows_service_hardener.py** | Durcissement services Windows |
| **windows_integration_agent.py** | Agent integration Windows |
| **electron_app_monitor.py** | Monitoring app Electron |
| **auto_deployer.py** | Deploiement automatique |
| **win_notify.py** | Notifications Windows natives |
| **agent_orchestrator.py** | Orchestration multi-agents (Coder/Reviewer/Tester/Monitor) |
| **code_generator.py** | Generation code IA via M1 (qwen3-8b) + templates |
| **continuous_learner.py** | Apprentissage continu Q&A avec auto-categorisation |
| **decision_engine.py** | Moteur de decisions avec 7 regles built-in |
| **gpu_optimizer.py** | Optimisation GPU (4 profils, benchmark, thermal) |
| **memory_optimizer.py** | Analyse RAM/VRAM, cleanup cache, monitoring continu |
| **network_optimizer.py** | Optimisation reseau cluster (latence, bandwidth, MTU) |
| **proactive_agent.py** | Agent proactif avec triggers (time, gpu_temp, disk, port) |
| **telegram_stats.py** | Statistiques usage Telegram (daily/weekly/commands) |
| **win_event_watcher.py** | Monitoring Windows Event Viewer (wevtutil) |
| **win_firewall_manager.py** | Gestion pare-feu Windows (netsh advfirewall) |
| **win_task_automator.py** | Gestion Task Scheduler (schtasks + templates) |
| **workspace_analyzer.py** | Analyse sante workspace (AST, health score, deps) |
| **browser_pilot.py** | Pilotage navigateur CDP (Comet/Chrome/Edge) |
| **voice_browser_nav.py** | Navigation navigateur par commandes vocales |

</details>

### Exemple d'une journee type avec JARVIS

```
08:00 — JARVIS t'envoie un vocal : "Bonjour Franck voici ton rapport matinal
         3 nouveaux mails 2 signaux trading cluster 100 pourcent en ligne"

08:15 — Tu dis : "lis mes mails"
         JARVIS lit les 2 boites Gmail et resume chaque email en vocal

09:00 — Tu ecris : "scan le marche"
         JARVIS analyse les 10 paires crypto, donne les signaux forts

12:00 — [AUTOMATIQUE] JARVIS detecte GPU a 82C, decharge le modele lourd,
         te previent en vocal : "GPU chaud j'ai decharge qwen3 30b"

14:00 — Tu dis : "range le bureau"
         JARVIS organise les fichiers par type (images, docs, code, videos)
         et te confirme en vocal : "Bureau range 23 fichiers deplaces"

15:30 — Tu ecris : "optimise le PC c'est lent"
         JARVIS vide les caches, arrete les services inutiles, nettoie les temp files
         et repond en vocal : "PC optimise 2.3 Go liberes"

18:00 — [AUTOMATIQUE] Trading scan detecte un signal BTC fort (score 85/100)
         JARVIS t'envoie : "Signal achat BTC score 85 tendance haussiere"

22:00 — Tu dis : "bonne nuit"
         JARVIS lance la routine du soir : backup, nettoyage logs, rapport fin de journee

02:00 — [AUTOMATIQUE] Backup nocturne, optimisation DB, scan securite
04:00 — [AUTOMATIQUE] COWORK : cree de nouveaux scripts, teste et ameliore les existants
```

---

## Nouveautes v10.3.10 — TTS Live + Domino Pipelines (174/174 PASS, 63 TTS)

> **Synthese vocale TTS live** sur les 40 cascades domino : Edge TTS `fr-FR-DeniseNeural` annonce chaque categorie, chaque resultat, et produit un rapport vocal final. **63 messages TTS** joues en temps reel, **174/174 PASS en 336s** avec audio. **40 cascades** across **11 categories**, executees via `DominoExecutor` distribue sur le cluster M1/M2/M3/OL1.

### Domino Pipelines (v10.3.7 — v10.3.10)

| Metrique | Valeur |
|----------|--------|
| **Cascades** | 40 domino pipelines |
| **Triggers vocaux** | 121 phrases FR (fuzzy matching) |
| **Steps executables** | 175 (powershell, curl, python, pipeline, condition) |
| **Categories** | 11 (routine_matin, trading, debug, deploy, securite, GPU, backup, monitoring, collaboration, streaming, routine_soir) |
| **DominoExecutor** | Routing auto M1/M2/M3/OL1/LOCAL + fallback chain + SQLite logging |
| **TTS Live** | Edge TTS `fr-FR-DeniseNeural` — 63 messages vocaux, 336s avec audio |
| **Dataset apprentissage** | 97 examples JSONL pour fine-tuning |
| **Score parallele** | 174/174 PASS (100%) — 40 cascades en 19.6s (sans TTS) |
| **Score TTS live** | 174/174 PASS (100%) — 40 cascades + 63 TTS en 336s |

<details>
<summary><b>11 categories domino</b> (cliquer pour details)</summary>

| Categorie | Cascades | Exemples de triggers |
|-----------|----------|---------------------|
| routine_matin | 5 | "bonjour jarvis", "mode cafe code", "reveil rapide", "matin trading" |
| trading_cascade | 5 | "scan trading complet", "execute signal", "ferme tout trading", "backtest" |
| debug_cascade | 5 | "debug cluster", "gpu surchauffe", "debug reseau", "debug api" |
| deploy_flow | 4 | "deploie le code", "hotfix urgent", "rollback deploy", "deploy safe" |
| security_sweep | 4 | "scan securite complet", "check api keys", "intrusion check" |
| gpu_thermal | 3 | "monitore les gpu", "optimise les gpu", "urgence gpu" |
| backup_chain | 3 | "backup complet", "backup rapide", "restaure le backup" |
| monitoring_alert | 3 | "monitoring systeme", "verifie les alertes", "benchmark rapide" |
| collaboration | 3 | "synchronise le cluster", "partage le modele", "consensus cluster" |
| routine_soir | 3 | "bonne nuit jarvis", "pause dejeuner", "mode weekend" |
| streaming | 2 | "lance le stream", "arrete le stream" |

</details>

### Architecture DominoExecutor

```
Commande vocale
    |
    v
find_domino() — fuzzy matching (121 triggers)
    |
    v
DominoExecutor.run(domino)
    |
    +-- route_step() → M1/M2/M3/OL1/LOCAL (par type)
    |       powershell → LOCAL
    |       curl /api/v1/chat → M1 (POST + auth)
    |       curl /api/chat → OL1 (POST)
    |       python → LOCAL (ou M1 si GPU)
    |
    +-- execute_step() → PASS/FAIL/SKIP
    |       on_fail: stop | skip | fallback
    |       condition: gpu_temp > 80, db_size > 50MB
    |
    +-- DominoLogger → etoile.db (domino_logs table)
    |
    v
Rapport TTS vocal + SQLite persistence
```

### Resultats Domino Live TTS (40 cascades + 63 messages vocaux)

```
174/174 PASS — 0 FAIL — 1 SKIP (n8n offline) — 336.2s avec TTS live
  backup_chain:      3 runs | 12 PASS |  14.4s | TTS: backup termine, restaure, verifie
  collaboration:     3 runs | 14 PASS |  10.9s | TTS: cluster synchronise, consensus
  debug_cascade:     5 runs | 24 PASS |  26.1s | TTS: diagnostic cluster/GPU/reseau/DB/API
  deploy_flow:       4 runs | 19 PASS |  29.3s | TTS: deploiement, hotfix, rollback
  gpu_thermal:       3 runs | 12 PASS |  18.4s | TTS: monitoring, optimisation, urgence
  monitoring_alert:  3 runs | 14 PASS |  22.9s | TTS: systeme, alertes, benchmark
  routine_matin:     5 runs | 21 PASS |  26.3s | TTS: bonjour, briefing, cafe code
  routine_soir:      3 runs | 13 PASS |  14.5s | TTS: bonne nuit, pause, weekend
  security_sweep:    4 runs | 15 PASS |  27.8s | TTS: scan securite, cles, reseau
  streaming:         2 runs |  7 PASS |  12.7s | TTS: stream pret, VOD sauvegardee
  trading_cascade:   5 runs | 23 PASS |  20.7s | TTS: scan, execute, backtest, drawdown
```

### Pipeline TTS Live

```
Commande vocale → find_domino() → DominoExecutor.run()
    |                                      |
    v                                      v
Edge TTS fr-FR-DeniseNeural          execute_step() → M1/M2/M3/OL1
    |                                      |
    v                                      v
ffplay (audio MP3)                  PASS/FAIL/SKIP → rapport vocal TTS
```

---

## Audit Pipeline Complet (v10.3.2 — v10.3.6, 171/171 PASS)

> **+171 pipelines** deployees en 7 batches, couvrant **42+ categories** a travers 4 niveaux de priorite + completions. Audit systematique du README vs code reel — zero gap restant. **461 pipelines totales**.

### Couverture par priorite

| Priorite | Categories | Pipelines | Score |
|----------|-----------|-----------|-------|
| **CRITIQUE** | Canvas Autolearn, Voice System, Plugin Management, Embedding/Vector, Fine-Tuning Orchestration, Brain Learning | 28 | 28/28 PASS |
| **HAUTE** | RAG System, Consensus/Vote, Security Hardening, Model Management, Cluster Predictive, N8N Advanced, DB Optimization, Dashboard Widgets, Hotfix/Emergency | 27 | 27/27 PASS |
| **MEDIUM** | Learning Cycles, Scenarios/Testing, API Management, Performance Profiling, Workspace/Session, Trading Enhanced, Notification/Alerting, Documentation Auto, Logging/Observability | 32 | 32/32 PASS |
| **LOW** | User Preferences, Accessibility, Streaming/Broadcasting, Collaboration | 12 | 12/12 PASS |
| **COMPLETION** | 19 categories — gaps restants dans Fine-Tuning, Plugin, Voice, Embedding, Brain, Dashboard, RAG, DB, Consensus, Security, Model, Hotfix, Cluster, N8N, API, Workspace, Trading, Notification, Documentation | 36 | 36/36 PASS |
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
commands_pipelines.py (461 pipelines)
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
etoile.db (pipeline_tests: 235, vocal_pipeline: 473, domino_logs)
```

### Resultats des tests live (cumul)

```
171/171 PASS — 0 FAIL — 7 batches — ~250 secondes total
  Batch 1: 24 pipelines (cluster, diagnostic, cognitif, securite, debug, routines)
  Batch 2: 36 pipelines (electron, cluster avance, database, n8n, SDK, finetuning, trading, skills)
  Batch 3: 28 pipelines CRITIQUES (canvas, voice, plugin, embedding, finetuning orch, brain)
  Batch 4: 27 pipelines HAUTES (RAG, consensus, security, model, predictive, n8n adv, db optim, dashboard, hotfix)
  Batch 5: 32 pipelines MEDIUM (learning, scenarios, API, profiling, workspace, trading enh, notif, doc, logs)
  Batch 6: 12 pipelines LOW (preferences, accessibility, streaming, collaboration)
  Batch 7: 36 pipelines COMPLETION (19 categories — gaps audit fermes)
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

- [Nouveautes v10.7.0 — 131 Scripts + 76 Crons + Comet](#nouveautes-v1070--131-scripts-cowork--76-crons--comet-browser--18-batches-2026-03-05)
- [Nouveautes v10.3.10 — TTS Live + Domino](#nouveautes-v10310--tts-live--domino-pipelines-174174-pass-63-tts)
- [Audit Pipeline Complet](#audit-pipeline-complet-v1032--v1036-171171-pass)
- [Connexions & Branchements](#connexions--branchements)
- [Architecture Globale](#architecture-globale)
- [Cluster IA — HEXA_CORE + Cloud](#cluster-ia--hexacore)
- [Pipeline Commander](#pipeline-commander)
- [53 Agents Total (7 SDK + 11 Plugin + 35 OpenClaw)](#53-agents-total-7-sdk--11-plugin--35-openclaw)
- [Consensus Multi-Source](#consensus-multi-source)
- [108 Skills Autonomes](#108-skills-autonomes)
- [117 Outils MCP + 531 Handlers](#117-outils-mcp--531-handlers-7322-lignes)
- [Bases de Donnees](#bases-de-donnees)
- [Catalogue Vocal & Pipelines](#catalogue-vocal--pipelines)
- [Architecture Vocale](#architecture-vocale)
- [Trading MEXC Futures](#trading-mexc-futures)
- [Telegram Bot Autonome](#telegram-bot-autonome-turbossebot)
- [Desktop Electron (19 pages)](#desktop-electron)
- [COWORK Autonome (131 scripts)](#cowork-autonome-131-scripts-76-crons-30515-lignes)
- [Arborescence du Projet](#arborescence-du-projet)
- [Installation](#installation)
- [Benchmark Cluster](#benchmark-cluster)
- [n8n Workflows](#n8n-workflows)
- [Stack Technique](#stack-technique)

---

## Connexions & Branchements

### Endpoints du Cluster

| Noeud | IP | Port | Protocole | Auth | Modele |
|-------|----|------|-----------|------|--------|
| **M1** | 10.5.0.2 / 127.0.0.1 | 1234 | HTTP REST (LM Studio Responses API) | `LMSTUDIO_KEY_M1_REDACTED` | qwen3-8b (65 tok/s) + qwen3-30b (9 tok/s) |
| **M2** | 192.168.1.26 | 1234 | HTTP REST (LM Studio Responses API) | `LMSTUDIO_KEY_M2_REDACTED` | deepseek-coder-v2-lite-instruct |
| **M3** | 192.168.1.113 | 1234 | HTTP REST (LM Studio Responses API) | `LMSTUDIO_KEY_M3_REDACTED` | mistral-7b-instruct-v0.3 |
| **OL1** | 127.0.0.1 | 11434 | HTTP REST (Ollama API) | Aucune | qwen3:14b, qwen3:1.7b + 10 cloud |
| **GEMINI** | — | — | Node.js proxy | API Key | gemini-3-pro / gemini-3-flash |
| **CLAUDE** | — | — | Node.js proxy | API Key | opus / sonnet / haiku |

### Services Internes

| Service | IP | Port | Protocole | Description |
|---------|----|------|-----------|-------------|
| **OpenClaw Gateway** | 127.0.0.1 | 18789 | HTTP | Gateway Telegram + 35 agents + 76 crons |
| **Gemini Proxy** | 127.0.0.1 | 18791 | HTTP | Proxy Gemini avec timeout + fallback |
| **FastAPI Backend** | 127.0.0.1 | 9742 | WebSocket | Backend Electron (6 routes) |
| **Dashboard** | 127.0.0.1 | 8080 | HTTP | Dashboard web standalone |
| **n8n** | 127.0.0.1 | 5678 | HTTP | 20 workflows automation |
| **CDP Browser** | 127.0.0.1 | 9222 | WebSocket | Chrome DevTools Protocol (Comet/Chrome/Edge) |
| **Ollama** | 127.0.0.1 | 11434 | HTTP | `OLLAMA_NUM_PARALLEL=3` (3 requetes simultanées) |

### Schema de Connexions

```
                    INTERNET
                       |
        +--------------+---------------+
        |              |               |
   Telegram Bot   Ollama Cloud    Gemini/Claude
   (@turboSSebot)  (10 modeles)    (proxies)
        |              |               |
        v              v               v
   +----+----+    +----+----+    +----+----+
   | OpenClaw |    |  OL1     |    | Proxies  |
   | :18789   |    | :11434   |    | .js      |
   +----+----+    +----+----+    +----+----+
        |              |               |
        +--------------+------+--------+
                              |
                    +---------v---------+
                    |   M1 (MASTER)     |
                    |  127.0.0.1:1234   |
                    |  qwen3-8b (65t/s) |
                    +---------+---------+
                              |
              +---------------+---------------+
              |                               |
    +---------v---------+           +---------v---------+
    |   M2 (CODE)       |           |   M3 (GENERAL)    |
    | 192.168.1.26:1234 |           | 192.168.1.113:1234|
    | deepseek-coder    |           | mistral-7b        |
    +-------------------+           +-------------------+

Branchements supplementaires :
    M1 ──> FastAPI :9742 ──> Electron Desktop (19 pages)
    M1 ──> Dashboard :8080 ──> Browser web
    M1 ──> n8n :5678 ──> 20 workflows
    M1 ──> CDP :9222 ──> Comet/Chrome/Edge (browser_pilot.py)
    OpenClaw ──> dev/*.py (131 scripts) ──> SQLite (dev/data/*.db)
```

### Fallback Cascade (code)

```
gpt-oss:120b (cloud, 100/100)
    |-- FAIL --> M1 qwen3-8b (local, 98.4/100)
        |-- FAIL --> devstral-2:123b (cloud, 94/100)
            |-- FAIL --> M2 deepseek-coder (local, 85.1)
                |-- FAIL --> OL1 qwen3:14b (local, 88%)
                    |-- FAIL --> GEMINI gemini-3-pro (cloud, 74%)
                        |-- FAIL --> CLAUDE opus (cloud)
```

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
Voix/Texte/Telegram ──> STT (Whisper large-v3-turbo, CUDA) ──> Correction IA (3,466 regles)
    ──> Classification Intent (M1 qwen3-8b, 3-45ms)
    ──> Decomposition en micro-taches
    ──> Dispatch Multi-GPU (matrice de routage dynamique, autolearn scoring)
    ──> Execution Parallele sur cluster (M1/M2/M3/OL1/gpt-oss/devstral/GEMINI/CLAUDE)
    ──> Consensus Pondere (12 modeles, vote pondere)
    ──> Reponse Vocale (TTS Edge fr-FR-DeniseNeural) ou Telegram
    ──> Persistance (etoile.db + jarvis.db + autolearn)
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
| Backend | Ollama v0.17.4, `OLLAMA_NUM_PARALLEL=3` |
| Modeles Locaux | **qwen3:14b** (23 tok/s) + **qwen3:1.7b** (84 tok/s, le plus rapide) |
| Cloud CODE | **gpt-oss:120b** (CHAMPION 100/100, 51 tok/s) + **devstral-2:123b** (94/100, 36 tok/s) |
| Cloud Utility | glm-4.7, qwen3-coder:480b, minimax-m2.5, glm-5, kimi-k2.5, qwen3.5, cogito-2.1:671b, deepseek-v3.2 |
| Total | **12 modeles** (2 local + 10 cloud), `think:false` obligatoire pour cloud |
| Role | Vitesse, web search, code cloud champion |
| Score Benchmark | **88%** (local) / **100%** (gpt-oss cloud) |
| Poids Consensus | 1.3 (local) / **1.9** (gpt-oss) / **1.5** (devstral) |

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

### Routage Intelligent (benchmark-tuned 2026-02-28, gpt-oss CHAMPION 100/100)

| Type de tache | Principal | Secondaire | Verificateur |
|---------------|-----------|------------|--------------|
| Code nouveau | **gpt-oss:120b** (100/100, 51 tok/s) | **M1** (98.3, 45 tok/s) | devstral-2 (96.5) |
| Bug fix | **gpt-oss:120b** | **M1** (patch) | devstral-2 (audit) |
| Architecture | GEMINI | **M1** (validation) | gpt-oss:120b |
| Refactoring | **gpt-oss:120b** | **M1** | devstral-2 |
| Raisonnement | **M1** (100%) | OL1-14b (local) | — JAMAIS M3 |
| Math/Calcul | **M1** (100%) | OL1 (rapide) | — |
| Trading | OL1 (web) | **M1** (analyse) | — |
| Securite/audit | **gpt-oss:120b** | GEMINI | M3 (scan) |
| Question simple | OL1 (0.5s) | glm-4.7 (4.6s) | — |
| Recherche web | OL1-cloud (minimax) | GEMINI | — |
| Revue code finale | **gpt-oss:120b** (100/100) | devstral-2 (96.5) | **M1** |
| Consensus critique | **gpt-oss**+**M1**+devstral+M2+GEMINI+CLAUDE | Vote pondere | — |
| Embedding | **M1** | — | — |

Fallback code: gpt-oss:120b → M1 → devstral-2:123b → M2 → OL1 → GEMINI → CLAUDE.

---

## 53 Agents Total (7 SDK + 11 Plugin + 35 OpenClaw)

### 7 Agents Claude SDK

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

### 35 Agents OpenClaw Gateway

<details>
<summary><b>Liste des 35 agents OpenClaw (cliquer pour voir)</b></summary>

| Agent | Modele Principal | Fallback | Role |
|-------|-----------------|----------|------|
| **main** | ollama/gpt-oss:120b-cloud | lm-m1/qwen3-8b | Agent principal — routing automatique |
| **coding** | ollama/gpt-oss:120b-cloud | lm-m1/qwen3-8b | Developpement code |
| **cowork** | lm-m1/qwen3-8b | ollama/gpt-oss:120b-cloud | Dev continu COWORK (76 crons) |
| **trading** | ollama/gpt-oss:120b-cloud | lm-m1/qwen3-8b | Trading MEXC |
| **trading-scanner** | ollama/gpt-oss:120b-cloud | — | Scan marche crypto |
| **voice-assistant** | lm-m1/qwen3-8b | — | Assistant vocal TTS/STT |
| **windows** | lm-m1/qwen3-8b | — | Gestion Windows |
| **consensus-master** | ollama/gpt-oss:120b-cloud | — | Vote pondere multi-agents |
| **debug-detective** | ollama/gpt-oss:120b-cloud | — | Debug & root cause |
| **fast-chat** | lm-m1/qwen3-8b | — | Reponses rapides |
| **deep-work** | ollama/gpt-oss:120b-cloud | — | Analyse profonde |
| **creative-brainstorm** | gemini/gemini-3-pro | — | Brainstorming creatif |
| **data-analyst** | ollama/gpt-oss:120b-cloud | — | Analyse donnees |
| **doc-writer** | lm-m1/qwen3-8b | — | Redaction documentation |
| **devops-ci** | ollama/gpt-oss:120b-cloud | — | CI/CD & DevOps |
| **securite-audit** | ollama/gpt-oss:120b-cloud | — | Audit securite |
| **recherche-synthese** | ollama/gpt-oss:120b-cloud | — | Recherche & synthese |
| **translator** | lm-m1/qwen3-8b | — | Traduction |
| **m1-deep** | lm-m1/qwen3-8b | — | M1 analyse profonde |
| **m1-reason** | lm-m1/qwen3-8b | — | M1 raisonnement |
| **m2-code** | lm-m2/deepseek-coder | — | M2 code generation |
| **m2-review** | lm-m2/deepseek-coder | — | M2 code review |
| **m3-general** | lm-m3/mistral-7b | — | M3 taches generales |
| **ol1-fast** | ollama/qwen3:1.7b | — | OL1 reponses rapides |
| **ol1-reasoning** | ollama/qwen3:14b | — | OL1 raisonnement |
| **ol1-web** | ollama/minimax-m2.5:cloud | — | OL1 recherche web |
| **gemini-pro** | gemini/gemini-3-pro | — | Gemini Pro |
| **gemini-flash** | gemini/gemini-3-flash | — | Gemini Flash (rapide) |
| **claude-reasoning** | claude/opus | — | Claude raisonnement profond |
| **pipeline-comet** | lm-m1/qwen3-8b | — | Pilotage navigateur Comet |
| **pipeline-maintenance** | lm-m1/qwen3-8b | — | Maintenance systeme |
| **pipeline-modes** | lm-m1/qwen3-8b | — | Gestion modes (dev/trading/gaming) |
| **pipeline-monitor** | lm-m1/qwen3-8b | — | Monitoring pipelines |
| **pipeline-routines** | lm-m1/qwen3-8b | — | Routines automatiques |
| **pipeline-trading** | lm-m1/qwen3-8b | — | Pipeline trading |

</details>

---

## Consensus Multi-Source

Chaque decision importante passe par un pipeline de consensus pondere. Tous les noeuds sont interroges en parallele, puis leurs reponses sont agregees avec un vote pondere :

```
  gpt-oss (poids 1.9) ──┐
  M1     (poids 1.8)  ──┤
  devstral(poids 1.5)  ──┤
  M2     (poids 1.4)  ──┼──> Agregation ──> Score Consensus ──> Decision
  OL1    (poids 1.3)  ──┤        │
  GEMINI (poids 1.2)  ──┤        │
  CLAUDE (poids 1.2)  ──┤        │
  M3     (poids 0.8)  ──┘        v
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

## 108 Skills Autonomes

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

## 117 Outils MCP + 531 Handlers (7,322 lignes)

Chiffres reels verifies (2026-03-05) : `tools.py` (1,979 lignes, 117 fonctions) + `mcp_server.py` (5,343 lignes, 531 handlers).

```
JARVIS-TURBO tools.py (117 outils)     JARVIS-TURBO mcp_server.py (531 handlers)
├── Cluster IA (15)                     ├── Cluster Management (60+)
│   lm_query, consensus,               │   health_check, model_load/unload,
│   bridge_mesh, bridge_query,          │   node_status, dispatch, routing
│   gemini_query, ollama_query          │
├── Windows System (15)                 ├── Trading Pipeline (80+)
│   powershell_run, system_info,        │   turbo_scan, sniper, orderbook,
│   open_app, close_app, gpu_info       │   consensus_5ia, positions, PnL
│                                       │
├── Brain/Skills (10)                   ├── Voice & TTS (40+)
│   learn_skill, execute_skill,         │   tts_speak, whisper_transcribe,
│   brain_index, brain_search           │   correction, pipeline, cache
│                                       │
├── Trading Bridge (8)                  ├── SQL Database (50+)
│   run_script, trading_signal,         │   query, insert, export, backup,
│   sniper_execute                      │   vacuum, reindex, schema
│                                       │
├── Filesystem (7)                      ├── Telegram Bot (30+)
│   read_file, write_file,             │   send_message, send_voice,
│   list_dir, search_files              │   get_updates, commands
│                                       │
├── Bridge Multi-Noeuds (12)            ├── Consensus & Mesh (40+)
│   mesh_parallel, route_smart,         │   vote_pondere, aggregate,
│   fallback_chain                      │   multi_model, scenario_weights
│                                       │
├── Consensus/Mesh (10)                 ├── Dashboard & Metrics (60+)
│   consensus_vote, mesh_query,         │   pages REST API, websocket,
│   aggregate_results                   │   alerts, workflows, health
│                                       │
├── SQL Tools (3)                       ├── n8n & Automation (30+)
│   sql_query, sql_insert,             │   trigger_workflow, webhook,
│   sql_export                          │   cron, pipeline execution
│                                       │
├── Browser / Comet (8)                 └── Skills & Brain (40+)
│   navigate, screenshot, click,            learn, execute, index,
│   comet_pilot, cdp_connect                search, pattern, memory
│
└── Utilities (29)
    tts_speak, screenshot, clipboard,
    hotkey, scheduler, notifications
```

### 3 Serveurs MCP Configures

| Serveur | Commande | Outils | Lignes |
|---------|----------|--------|--------|
| **jarvis-turbo** | `jarvis_mcp_stdio.bat` | 117 tools + 531 handlers | 7,322 lignes |
| **trading-ai-ultimate** | `trading_mcp_ultimate_v3.py` | Scanner MEXC, consensus, execution | — |
| **filesystem** | `npx @modelcontextprotocol/server-filesystem` | Acces complet C:\, D:\, F:\ | — |

---

## Bases de Donnees

### Vue d'ensemble

| Base | Chemin | Tables | Rows | Usage |
|------|--------|--------|------|-------|
| **etoile.db** | `data/etoile.db` | 22 | 11,282 | Carte HEXA_CORE, cles API, agents, metrics, pipelines, 2,628 corrections, 835 dominos |
| **jarvis.db** | `data/jarvis.db` | 12 | 5,908 | 443 commandes, 108 skills, scenarios, benchmarks |
| **sniper.db** | `data/sniper.db` | 6 | 768 | Coins, signaux trading, categories |
| **finetuning.db** | `data/finetuning.db` | — | — | Pipeline QLoRA, examples, evaluations |

### etoile.db — Carte du Systeme

La table `map` centralise la cartographie complete du systeme :

| Type d'entite | Nombre | Description |
|---------------|--------|-------------|
| vocal_command | 1,706 | Commandes vocales avec triggers et actions |
| vocal_pipeline | 476 | Pipelines multi-etapes (enchainements automatises) |
| domino_trigger | 121 | Declencheurs domino (fuzzy matching) |
| skill | 108 | Skills persistants avec statistiques |
| tool | 75 | Outils MCP SDK enregistres |
| domino_pipeline | 40 | Pipelines domino executables |
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

Autres tables: `pipeline_dictionary` (656 pipelines), `pipeline_tests` (528+ tests), `scenario_weights` (58 regles), `domino_chains` (835 cascades), `voice_corrections` (2,628 regles), `domino_logs`, `user_patterns`, `benchmark_runs/results`, `consensus_log`, `jarvis_queries`, `cluster_health`, `agent_keywords`, `memories`, `api_keys`, `skills_log`, `sessions`, `metrics`.

### jarvis.db — Commandes & Validation

| Table | Rows | Description |
|-------|------|-------------|
| commands | 443 | Commandes vocales avec triggers JSON, action_type, usage stats |
| skills | 108 | Skills avec steps, taux de succes, compteurs |
| scenarios | 475 | Scenarios de test (validation vocale) |
| validation_cycles | 500 | Resultats de cycles de validation |
| voice_corrections | 2,628 | Corrections phonetiques + alias + implicits + fillers (120 vagues) |
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

### Corrections Vocales (2,628 regles — 120 vagues)

Systeme de correction automatique de la reconnaissance vocale :

| Categorie | Nombre | Description |
|-----------|--------|-------------|
| **Corrections** | 2,628 | Phonetiques + alias + auto-training (120 vagues) |
| **Domino Chains** | 835 | Cascades domino auto-generees |
| **Triggers** | 1,078 | Declencheurs de commandes vocales |
| **Implicits** | 678 | Commandes implicites (67 vagues) |
| **Fillers** | 153 | Mots de remplissage (8 vagues) |
| **Phonetics** | 106 | Regles phonetiques (19 vagues) |
| **Actions** | 84 | Actions Python executables |
| **Param Patterns** | 28 | Patterns parametriques |

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
                  │ Correction IA │  ◄── 3,466 regles phonetiques
                  │ + LM Studio   │      + correction contextuelle M1
                  └───────┬───────┘
                          │
                  ┌───────v───────┐
                  │ Intent Match  │  ◄── 2,332 commandes + 656 pipelines
                  │ + Fuzzy Match │      Matching semantique + phonetique
                  └───────┬───────┘
                          │
                  ┌───────v───────┐
                  │ Orchestrator  │  ◄── Dispatch vers cluster HEXA_CORE
                  │ Commander     │      Classification M1 (3-45ms)
                  └───────┬───────┘
                          │
                  ┌───────v───────┐
                  │ TTS Edge      │  ◄── fr-FR-DeniseNeural
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

### Pages (19 total)

| Page | Fonction |
|------|----------|
| **Dashboard** | Vue d'ensemble systeme, cluster status, metriques temps reel |
| **Chat** | Interface conversationnelle avec JARVIS (agent badges, markdown) |
| **Voice** | Visualisation audio, log transcriptions, waveform |
| **Trading** | Positions ouvertes, signaux actifs, historique PnL |
| **LM Studio** | Gestion modeles, charge GPU, benchmarks, load/unload |
| **Settings** | Configuration systeme, preferences, cles API |
| **Dictionary** | Dictionnaire de commandes vocales |
| **Pipelines** | Gestion des pipelines multi-etapes |
| **Toolbox** | Outils MCP disponibles |
| **Logs** | Logs systeme en temps reel |
| **Orchestrator** | Vue orchestration multi-agents |
| **Memory** | Memoire conversationnelle et profil utilisateur |
| **Metrics** | Metriques agregees et historiques |
| **Alerts** | Systeme d'alertes et notifications |
| **Workflows** | Moteur de workflows visuels |
| **Health** | Dashboard sante unifie (8 sous-systemes) |
| **Resources** | Moniteur CPU/RAM/GPU/Disk |
| **Scheduler** | Planificateur de taches (cron-like) |
| **Canvas** | Canvas Autolearn Engine |

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

## Telegram Bot Autonome (@turboSSebot)

Le bot Telegram est gere par **OpenClaw Gateway** (port 18789) avec 35 agents, 7 providers IA et fallback cascade automatique. Messages vocaux bidirectionnels (TTS DeniseNeural + Whisper STT).

| Composant | Detail |
|-----------|--------|
| **Bot ID** | 8369376863 |
| **Chat ID** | 2010747443 |
| **Backend** | **OpenClaw Gateway** (port 18789) — remplace canvas proxy |
| **Agents** | **35 agents** (main, coding, trading, voice-assistant, windows, cowork, etc.) |
| **Providers** | 7 (lm-m1, lm-m2, lm-m3, ollama, gemini, claude, qwen-portal) |
| **Polling** | Long polling natif OpenClaw |
| **Routing** | Autolearn scoring → fallback cascade (M1 → OL1 → M2 → gpt-oss → devstral → Gemini → Claude) |
| **Modeles** | M1 qwen3-8b (primaire, local), gpt-oss:120b (cloud), devstral-2:123b + 9 autres |
| **Voix TTS** | Edge TTS fr-FR-DeniseNeural → MP3 → ffmpeg OGG Opus → Telegram sendVoice |
| **Voix STT** | Whisper large-v3-turbo CUDA → transcription vocaux entrants |
| **Commandes** | `/status`, `/consensus`, `/health`, `/help`, `/model` + texte libre |
| **COWORK** | 76 crons autonomes (dev continu, monitoring, trading, maintenance) |

### Commandes Telegram

| Commande | Action |
|----------|--------|
| `/status` | Health check cluster (GET /health) |
| `/consensus <question>` | Query multiple noeuds + vote pondere |
| `/health` | Etat detaille de chaque noeud |
| `/help` | Liste des commandes disponibles |
| `/model <id>` | Forcer un noeud specifique (M1/M2/OL1/etc.) |
| Texte libre | Dispatch automatique via routing autolearn |

### 8 Commandes Pipeline Telegram

status, trading, health, services, benchmark, emails, workspace, report — automatisees via Telegram Bot API.

---

## COWORK Autonome (131 scripts, 76 crons, 30,515 lignes)

Systeme de developpement continu autonome via OpenClaw. 131 scripts Python standalone + 76 crons (49 recurrents + 27 one-shot). Chaque script a un argparse CLI (`--help`) et une base SQLite locale dans `dev/data/`.

### Domaines couverts

| Domaine | Scripts | Exemples |
|---------|---------|----------|
| **JARVIS Core** | 30+ | brain, memory, skill_generator, feature_builder, self_evolve, night_ops, context_engine, reflection_engine |
| **Windows** | 20+ | service_hardener, registry_guardian, performance_tuner, event_watcher, firewall_manager, task_automator, clipboard_manager, hotkey_manager |
| **IA Autonome** | 25+ | proactive_agent, multi_agent_coordinator, cluster_autotuner, goal_tracker, experiment_runner, auto_fixer, decision_engine, agent_orchestrator |
| **Trading** | 10+ | trading_intelligence, signal generation, market analysis |
| **Infrastructure** | 20+ | auto_deployer, continuous_test_runner, mcp_tool_tester, gpu_optimizer, memory_optimizer, network_optimizer |
| **Voice** | 5+ | voice_pipeline_optimizer, voice_command_evolve, command coverage |
| **Communication** | 5+ | notification_center, report_generator, telegram_stats |
| **Cluster Intelligence** | 10+ | model_selector, cluster_autoscaler, consensus_voter, code_generator |
| **Productivite** | 5+ | workflow_builder, time_tracker, focus_mode, workspace_analyzer |

### Crons actifs (76 total)

| Frequence | Nombre | Exemples |
|-----------|--------|----------|
| **5 min** | 2 | dev_proactive_check, dev_electron_monitor |
| **10-15 min** | 3 | dev_decision_engine, dev_trading_intel, dev_perf_tuner |
| **30 min** | 2 | dev_proactive_agent, telegram_status |
| **1-2h** | 10 | dev_feature_builder, dev_improve_scripts, dev_jarvis_brain, dev_cluster_autotuner, dev_conversation_memory |
| **3-4h** | 12 | dev_ia_autonome, dev_learning_cycle, dev_continuous_code, dev_self_evolve, dev_auto_codegen |
| **6-8h** | 7 | dev_mcp_tools, dev_workspace_health, dev_cluster_optimize, dev_skill_generator |
| **12h+** | 3 | dev_telegram_features, dev_testing_infra, dev_continuous_tests |
| **Cron specifique** | 10 | daily_backup (2h), security_scan (3h), db_optimize (4h), daily_report (8h), dev_night_ops (23h) |
| **One-shot** | 27 | Batches 43-48 (planifies toutes les 10 min, deleteAfterRun) |

---

## Arborescence du Projet

```
turbo/
├── src/                       # 177 modules Python (74,393 lignes)
│   ├── orchestrator.py        # Cerveau central — dispatch + aggregation
│   ├── commander.py           # Pipeline Commander (classify/decompose/enrich)
│   ├── agents.py              # 7 agents Claude SDK (deep/fast/check/trading/system/bridge/consensus)
│   ├── tools.py               # 117 outils MCP SDK (1,979 lignes)
│   ├── mcp_server.py          # 531 handlers MCP (5,343 lignes)
│   ├── commands.py            # Commandes vocales principales
│   ├── commands_dev.py        # Commandes developpement (git, ollama, docker)
│   ├── commands_maintenance.py# Commandes maintenance
│   ├── commands_navigation.py # Commandes navigation
│   ├── commands_pipelines.py  # 476 pipelines multi-etapes
│   ├── config.py              # Configuration cluster + routage + 22 regles
│   ├── skills.py              # 108 skills dynamiques
│   ├── brain.py               # Auto-apprentissage (patterns)
│   ├── voice.py               # Pipeline vocale (Whisper + TTS)
│   ├── voice_correction.py    # Correction vocale (2,628 regles + OL1)
│   ├── wake_word.py           # OpenWakeWord "jarvis" (seuil 0.7)
│   ├── tts_streaming.py       # TTS streaming Edge fr-FR-DeniseNeural
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
│   ├── systray.py             # System tray icon
│   ├── orchestrator_v2.py     # Orchestrateur v2 (phase 4)
│   ├── autonomous_loop.py     # Boucle autonome
│   ├── task_queue.py          # File de taches
│   ├── cache_manager.py       # Cache L1 mem + L2 disk (LRU, TTL)
│   ├── secret_vault.py        # Coffre-fort chiffre (Fernet)
│   ├── dependency_graph.py    # DAG + topo sort + impact analysis
│   ├── rate_limiter.py        # Token bucket rate limiting
│   ├── retry_manager.py       # Exponential backoff + circuit breaker
│   ├── service_registry.py    # Heartbeat + TTL service discovery
│   └── ... (+100 modules phases 4-11)
├── canvas/                    # Canvas Autolearn Engine (port 18800)
│   ├── direct-proxy.js        # Proxy intelligent avec autolearn scoring
│   ├── telegram-bot.js        # Bot Telegram autonome (long polling)
│   ├── autolearn.js           # Moteur autolearn (speed*0.3 + quality*0.5 + reliability*0.2)
│   └── data/                  # Scores, memoire, historique autolearn
├── electron/                  # App desktop (Electron 33 + React 19 + Vite 6) — 19 pages
├── python_ws/                 # Backend WebSocket (FastAPI port 9742)
│   └── routes/                # 6 routes (cluster/trading/voice/chat/files/sql)
├── plugins/jarvis-turbo/      # Plugin Claude Code v3.0
│   ├── agents/ (11)           # cluster-ops, trading-analyst, code-architect...
│   ├── commands/ (40)         # /deploy, /cluster-check, /consensus, /trading-scan...
│   ├── skills/ (24)           # mao-workflow, smart-routing, failover-recovery...
│   └── hooks/                 # SessionStart, PreToolUse, Stop, SubagentStop
├── scripts/                   # 13 scripts utilitaires + cockpit/ + trading_v2/
├── launchers/                 # 15 launchers (.bat + .ps1)
├── finetuning/                # Pipeline QLoRA (Qwen3-30B-A3B, 55,549 exemples)
├── canvas/                    # Canvas Autolearn Engine (port 18800)
├── n8n_workflows/             # 6 workflows n8n
├── data/                      # 4 bases SQL (etoile.db, jarvis.db, sniper.db, finetuning.db)
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

### Slash Commands (plugin jarvis-turbo v3.0 — 40 commandes)

| Commande | Description |
|----------|-------------|
| `/cluster-check` | Health check tous noeuds |
| `/mao-check` | Health + GPU + services complet |
| `/gpu-status` | Temperatures + VRAM par GPU |
| `/thermal` | Monitoring thermique detaille |
| `/consensus [question]` | Vote pondere multi-noeuds |
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
| `/n8n-trigger` | Declenchement workflow n8n |
| `/backup-db` | Backup databases SQLite |
| `/test-cluster` | Test complet du cluster |
| `/improve-loop` | Boucle d'amelioration continue |
| `/cluster-benchmark` | Benchmark performance cluster |

*...et 20 autres commandes (m2-optimize, routing, etc.)*

---

## Benchmark Cluster

Resultats du benchmark reel (2026-02-28, 4 runs, ~250 checks) :

| Noeud | Modele | Latence | Score | Status | Poids |
|-------|--------|---------|-------|--------|-------|
| **gpt-oss** | gpt-oss:120b (51 tok/s) | cloud | **100/100** | CLOUD | **1.9** |
| **M1** | qwen3-8b (65 tok/s) | 0.6–2.5s | **98.4/100** | ONLINE | **1.8** |
| **devstral** | devstral-2:123b (36 tok/s) | cloud | **~94/100** | CLOUD | **1.5** |
| **M2** | deepseek-coder-v2-lite | 1.3s | **85.1** | ONLINE | 1.4 |
| **OL1** | qwen3:14b + qwen3:1.7b | 0.5s | **88%** | ONLINE | 1.3 |
| **glm-4.7** | glm-4.7:cloud (48 tok/s) | cloud | **88/100** | CLOUD | 1.2 |
| **GEMINI** | gemini-3-pro | variable | **74%** | CLOUD | 1.2 |
| **CLAUDE** | opus/sonnet/haiku | 12-18s | — | CLOUD | 1.2 |
| **M3** | mistral-7b-instruct | 2.5s | **89%** | ONLINE | 0.8 |

```
gpt-oss:120b — CHAMPION CLOUD : Q100% V100% R100%, 51 tok/s, score parfait 100/100
M1 — CHAMPION LOCAL : Q100% 45 tok/s, ZERO FAIL sur 40 requetes
Benchmark score global : 97% (7/7 phases)
Stress test : 28/28 OK (100%) — M1 34tok/s (3x) / M2 15tok/s / M3 10tok/s
Audit systeme : Grade A, 82/100
OLLAMA_NUM_PARALLEL=3 (env User persistant)
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
| **IA Locale** | LM Studio (qwen3-8b, deepseek-coder-v2, mistral-7b), Ollama v0.17.4 (qwen3:14b + qwen3:1.7b) |
| **IA Cloud** | gpt-oss:120b (CHAMPION 100/100), devstral-2:123b, Gemini 3 Pro, Claude Opus 4.6, minimax-m2.5, glm-4.7, kimi-k2.5 |
| **Backend** | Python 3.13, FastAPI, asyncio, httpx, ~96 REST endpoints, 177 modules (74,393 lignes) |
| **Desktop** | Electron 33, React 19, TypeScript, Vite 6, Tailwind CSS — 19 pages |
| **Navigateur** | Comet (Perplexity) par defaut, Chrome/Edge fallback, CDP port 9222 |
| **Voice** | Whisper large-v3-turbo (CUDA), Edge TTS fr-FR-DeniseNeural (femme), OpenWakeWord |
| **Trading** | CCXT (MEXC Futures), scoring multi-IA, sniper.db (6 tables, 768 rows) |
| **MCP** | 117 outils + 531 handlers (7,322 lignes), 3 serveurs MCP |
| **Database** | SQLite3 — 4 bases, 40 tables, 17,958 rows |
| **Telegram** | Bot @turboSSebot autonome via OpenClaw Gateway (port 18789), 35 agents, 7 providers |
| **Automation** | n8n v2.4.8, Playwright, Telegram Bot API, 131 scripts COWORK |
| **DevOps** | Docker Compose, GitHub, uv (Python packaging), OpenClaw (76 crons) |
| **Agents** | 53 total (7 Claude SDK + 11 Plugin + 35 OpenClaw Gateway) |

---

<p align="center">
  <strong>JARVIS Etoile v10.7.0</strong> — Built with passion by <a href="https://github.com/Turbo31150">Turbo31150</a>
</p>
<p align="center">
  <em>Repo prive — Derniere mise a jour : 2026-03-05</em>
</p>
