# COWORK MEGA TASKS — 100 tâches distribuables
# Généré: 2026-03-21 | Session 45 | Par: CLAUDE + cluster
# Distribution: cowork_engine.py --cycle + Scheduled Tasks Windows

---

## A. MONITORING WINDOWS (12 tâches)
1. [WIN_MONITORING] Scanner températures GPU toutes les 5min, alerter si >85°C → `gpu_thermal_guard.py`
2. [WIN_MONITORING] Surveiller VRAM usage, alerter si >90% → `vram_monitor.py`
3. [WIN_MONITORING] Logger CPU/RAM/Disk I/O toutes les 30s dans etoile.db → `system_metrics_logger.py`
4. [WIN_MONITORING] Détecter processus zombies et les kill automatiquement → `zombie_killer.py`
5. [WIN_MONITORING] Surveiller espace disque C: et F:, alerter si <5GB → `disk_space_watcher.py`
6. [WIN_MONITORING] Tracker événements Windows (crashs, BSOD, services failed) → `event_log_tracker.py`
7. [WIN_MONITORING] Monitorer latence réseau vers M2/M3, basculer si timeout → `network_latency_monitor.py`
8. [WIN_MONITORING] Scanner ports ouverts, détecter intrusions → `port_scanner.py`
9. [WIN_MONITORING] Surveiller services Windows critiques (Docker, LM Studio, Ollama) → `service_watcher.py`
10. [WIN_MONITORING] Dashboard temps réel performances système → `perf_dashboard.py`
11. [WIN_MONITORING] Auto-nettoyage temp/cache quand C: <2GB → `auto_cleaner.py`
12. [WIN_MONITORING] Rapport quotidien santé système → `daily_health_report.py`

## B. CLUSTER MANAGEMENT (10 tâches)
13. [CLUSTER] Health check M1/M2/M3/OL1 toutes les 60s, failover auto → `cluster_heartbeat.py`
14. [CLUSTER] Auto-tuning poids consensus selon performances → `cluster_auto_tuner.py`
15. [CLUSTER] Load balancing requêtes entre nœuds → `cluster_load_balancer.py`
16. [CLUSTER] Prédiction charge GPU, pré-routing intelligent → `cluster_load_predictor.py`
17. [CLUSTER] Sync modèles entre M1/M2/M3 → `model_sync.py`
18. [CLUSTER] Benchmark quotidien automatique des nœuds → `cluster_daily_bench.py`
19. [CLUSTER] Failover cascade M1→OL1→M2→M3→GEMINI→CLAUDE → `failover_cascade.py`
20. [CLUSTER] Détection anomalies performances, auto-restart → `anomaly_auto_restart.py`
21. [CLUSTER] Gestion mémoire VRAM, unload modèles inactifs → `vram_manager.py`
22. [CLUSTER] Dashboard cluster temps réel web → `cluster_dashboard_api.py`

## C. TRADING PIPELINE (10 tâches)
23. [TRADING] Scan 10 paires MEXC toutes les 5min, scoring 0-100 → `trading_scanner.py`
24. [TRADING] Backtest stratégies sur données historiques → `signal_backtester.py`
25. [TRADING] Gestion portfolio positions ouvertes → `portfolio_tracker.py`
26. [TRADING] Calcul risk management (position sizing, drawdown) → `risk_manager.py`
27. [TRADING] Analyse orderbook depth + OB imbalances → `orderbook_analyzer.py`
28. [TRADING] Alertes Telegram signaux score >80 → `trading_telegram_alerts.py`
29. [TRADING] Corrélation inter-paires, détection divergences → `correlation_analyzer.py`
30. [TRADING] Analyse sentiment social (Twitter, Reddit) → `sentiment_scanner.py`
31. [TRADING] Journal trades auto dans sniper.db → `trade_journal.py`
32. [TRADING] Rapport P&L hebdomadaire → `weekly_pnl_report.py`

## D. VOICE & NLP (10 tâches)
33. [VOICE] Entraîner corrections phonétiques Whisper → `voice_correction_trainer.py`
34. [VOICE] Pipeline wake word → STT → intent → action → TTS → `voice_full_pipeline.py`
35. [VOICE] Profils vocaux multiples (Turbo, invités) → `voice_profiles.py`
36. [NLP] Classification intentions multi-langue → `intent_classifier.py`
37. [NLP] Analyse sentiment conversations → `sentiment_analyzer.py`
38. [NLP] Résumé automatique conversations longues → `conversation_summarizer.py`
39. [NLP] Extraction entités (noms, dates, montants) → `entity_extractor.py`
40. [NLP] Traduction auto FR↔EN dans le pipeline → `auto_translator.py`
41. [VOICE] Dictée vocale avec ponctuation auto → `dictation_engine.py`
42. [VOICE] Commandes vocales contextuelles (état app courante) → `context_voice_commands.py`

## E. DEVOPS & CI/CD (10 tâches)
43. [DEVOPS] Git auto-commit changes cowork/dev/ quotidien → `auto_git_commit.py`
44. [DEVOPS] Tests syntaxe + imports tous les scripts → `syntax_validator.py`
45. [DEVOPS] Backup auto bases SQL toutes les 6h → `auto_backup.py`
46. [DEVOPS] Changelog auto depuis git log → `auto_changelog.py`
47. [DEVOPS] Audit sécurité: secrets exposés, permissions → `security_auditor.py`
48. [DEVOPS] Migration schema DB (versions) → `db_migrator.py`
49. [DEVOPS] CI pipeline: test → lint → deploy → notify → `ci_pipeline.py`
50. [DEVOPS] Rotation logs (>50MB → archive → compress) → `log_rotator.py`
51. [DEVOPS] Audit dépendances Python, MAJ sécurité → `dependency_auditor.py`
52. [DEVOPS] Deploy scripts vers containers Docker → `docker_deployer.py`

## F. AUTOMATION & SELF-IMPROVE (10 tâches)
53. [AUTO] Auto-scheduler: planifier tâches selon priorité/charge → `auto_scheduler.py`
54. [AUTO] Auto-healer: détecter services crashés, restart → `auto_healer.py`
55. [AUTO] Auto-learner: mémoriser patterns succès/échec → `auto_learner.py`
56. [AUTO] Auto-deployer: déployer scripts validés en prod → `auto_deployer.py`
57. [AUTO] Self-improvement: analyser scores, proposer améliorations → `self_improve_engine.py`
58. [AUTO] Skill generator: créer nouveaux scripts depuis gaps → `skill_generator.py`
59. [AUTO] Night ops: tâches lourdes programmées 2h-6h → `night_operator.py`
60. [AUTO] A/B testing: comparer 2 versions de scripts → `ab_tester.py`
61. [AUTO] Feedback loop: collecter résultats → ajuster routing → `feedback_loop.py`
62. [AUTO] Autonomy score: mesurer niveau autonomie global → `autonomy_scorer.py`

## G. TELEGRAM & COMMS (8 tâches)
63. [TELEGRAM] Bot commands: /status /health /trade /voice → `telegram_commands.py`
64. [TELEGRAM] Alertes critiques (disk full, GPU hot, service down) → `telegram_alerts.py`
65. [TELEGRAM] Rapport quotidien auto 8h → `telegram_daily_report.py`
66. [TELEGRAM] Voice messages: STT→process→TTS→send → `telegram_voice_bridge.py`
67. [TELEGRAM] Commandes interactives (inline buttons) → `telegram_interactive.py`
68. [TELEGRAM] File sharing (screenshots, logs, reports) → `telegram_file_sender.py`
69. [COMMS] Email rapports hebdo → `email_weekly_report.py`
70. [COMMS] Notifications push desktop → `desktop_notifier.py`

## H. BROWSER & WEB (8 tâches)
71. [BROWSER] Automation LinkedIn: like, comment, post → `linkedin_automation.py`
72. [BROWSER] Web scraping prix crypto temps réel → `crypto_price_scraper.py`
73. [BROWSER] Surveillance GitHub repos (issues, PRs, stars) → `github_watcher.py`
74. [BROWSER] Auto-publish GitHub releases → `github_releaser.py`
75. [BROWSER] Portfolio web JARVIS (GitHub Pages) → `portfolio_generator.py`
76. [BROWSER] Codeur.com profil auto-update → `codeur_updater.py`
77. [BROWSER] Veille techno auto (HN, Reddit, ArXiv) → `tech_watch.py`
78. [BROWSER] Screenshot automatique dashboards → `dashboard_screenshotter.py`

## I. DATA & DATABASES (8 tâches)
79. [DATA] Optimisation requêtes SQL lentes → `query_optimizer.py`
80. [DATA] Export données en JSON/CSV pour analyse → `data_exporter.py`
81. [DATA] Knowledge graph: relations entre entités JARVIS → `knowledge_graph.py`
82. [DATA] Métriques agrégées: latence, succès, usage → `metrics_aggregator.py`
83. [DATA] Nettoyage données obsolètes (>30j) → `data_cleaner.py`
84. [DATA] Embedding vectoriel pour recherche sémantique → `embedding_service.py`
85. [DATA] Sync etoile.db ↔ jarvis.db (voice_corrections) → `db_syncer.py`
86. [DATA] Audit intégrité toutes les bases → `integrity_auditor.py`

## J. MCP & INTEGRATION (8 tâches)
87. [MCP] Bridge cowork → Claude Code (7 outils) → `cowork_mcp_bridge.py`
88. [MCP] Bridge cowork → OpenClaw Gateway → `openclaw_bridge.py`
89. [MCP] Bridge cowork → n8n workflows → `n8n_bridge.py`
90. [MCP] Bridge cowork → Telegram Bot → `telegram_mcp_bridge.py`
91. [MCP] Health endpoint /health pour tous les bridges → `mcp_health_monitor.py`
92. [MCP] Auto-discovery nouveaux outils MCP → `mcp_discovery.py`
93. [MCP] Logging toutes les interactions MCP → `mcp_logger.py`
94. [MCP] Rate limiting et quota management → `mcp_rate_limiter.py`

## K. DOCKER & INFRASTRUCTURE (6 tâches)
95. [DOCKER] Health monitoring 3 containers cowork → `docker_health_monitor.py`
96. [DOCKER] Auto-rebuild images si scripts changent → `docker_auto_rebuild.py`
97. [DOCKER] Log aggregation containers → `docker_log_aggregator.py`
98. [DOCKER] Resource limits (CPU/RAM) par container → `docker_resource_manager.py`
99. [DOCKER] Backup volumes Docker → `docker_volume_backup.py`
100. [DOCKER] Network monitoring inter-containers → `docker_network_monitor.py`

---

## SCHEDULED TASKS WINDOWS (à créer)

| Task Name | Schedule | Script | Priority |
|-----------|----------|--------|----------|
| JARVIS Cowork Docker | On Start | start_cowork_docker.ps1 | CRITICAL |
| JARVIS Cluster Health | Every 1min | cluster_heartbeat.py | HIGH |
| JARVIS Trading Scan | Every 5min | trading_scanner.py | HIGH |
| JARVIS GPU Monitor | Every 5min | gpu_thermal_guard.py | HIGH |
| JARVIS Disk Watcher | Every 10min | disk_space_watcher.py | HIGH |
| JARVIS Auto Backup | Every 6h | auto_backup.py | MEDIUM |
| JARVIS Daily Report | Daily 8:00 | daily_health_report.py | MEDIUM |
| JARVIS Night Ops | Daily 2:00 | night_operator.py | LOW |
| JARVIS Log Rotate | Weekly Sun | log_rotator.py | LOW |
| JARVIS Weekly P&L | Weekly Mon 9:00 | weekly_pnl_report.py | LOW |

---

## DISTRIBUTION MULTI-IA

| Tâche | Agent Principal | Secondaire |
|-------|----------------|------------|
| Code generation (53-62) | M1/qwen3-8b | CLAUDE |
| Trading analysis (23-32) | OL1/minimax (web) | M1 |
| NLP/Voice (33-42) | M1 | M2/deepseek-r1 |
| Architecture (87-94) | GEMINI | M1 |
| Review/Audit (43-52) | M2/deepseek-r1 | M1 |
| Browser/Web (71-78) | BrowserOS | CLAUDE |
| Monitoring (1-12) | OL1 (rapide) | M1 |
| Consensus critique | ALL (vote pondéré) | — |
