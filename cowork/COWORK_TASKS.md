# COWORK TASKS — Developpement continu JARVIS

## Regles COWORK
- Chaque tache est autonome et doit produire un fichier Python fonctionnel
- Fichiers dans `C:/Users/franc/.openclaw/workspace/dev/`
- Teste chaque fichier apres creation
- Confirme le resultat sur Telegram

## Etat actuel: 64 scripts | 12 cron jobs | MaJ 2026-03-05 01:00

---

### BATCH 1 — Agents IA Autonomes (DONE)
| Script | Status | CLI |
|--------|--------|-----|
| auto_scheduler.py | DONE | `--start / --list / --run-once` |
| auto_monitor.py | DONE | `--once / --loop` |
| auto_trader.py | DONE | `--once / --loop` |

### BATCH 2 — Windows Automation (DONE)
| Script | Status | CLI |
|--------|--------|-----|
| win_optimizer.py | DONE | `--once [--notify] / --loop` |
| win_backup.py | DONE | `--once [--notify] / --loop` |
| win_notify.py | DONE | `--test / --alert` |

### BATCH 3 — Intelligence (DONE)
| Script | Status | CLI |
|--------|--------|-----|
| auto_learner.py | DONE | `--once [--notify] / --detail` |
| auto_reporter.py | DONE | `--once [--notify] / --loop` |
| context_engine.py | DONE | `--stats / --context / --facts` |
| task_queue.py | DONE | `--add / --list / --run / --loop` |

### BATCH 4-6 — AI Avance (DONE)
| Script | Status | CLI |
|--------|--------|-----|
| auto_healer.py | DONE | `--once / --loop` |
| load_balancer.py | DONE | `--once / --query / --stats` |
| model_rotator.py | DONE | `--once / --status` |
| signal_backtester.py | DONE | `--once / --stats` |
| portfolio_tracker.py | DONE | `--once / --positions` |
| anomaly_detector.py | DONE | `--once / --loop` |
| prompt_optimizer.py | DONE | `--once / --stats` |
| knowledge_graph.py | DONE | `--stats / --search` |
| risk_manager.py | DONE | `--once / --status` |

### BATCH 7-9 — System & Voice (DONE)
| Script | Status | CLI |
|--------|--------|-----|
| security_scanner.py | DONE | `--once` |
| log_rotator.py | DONE | `--once` |
| voice_trainer.py | DONE | `--once / --stats` |
| tts_cache_manager.py | DONE | `--once / --warm` |
| db_optimizer.py | DONE | `--once` |
| usage_analytics.py | DONE | `--once / --report` |
| report_mailer.py | DONE | `--daily / --weekly` |

### BATCH 10-12 — Infrastructure (DONE)
| Script | Status | CLI |
|--------|--------|-----|
| gpu_thermal_guard.py | DONE | `--once / --loop` |
| process_manager.py | DONE | `--list / --kill / --top` |
| cluster_dashboard_api.py | DONE | `--start` |
| notification_hub.py | DONE | `--send / --list` |
| network_monitor.py | DONE | `--once / --loop` |
| auto_updater.py | DONE | `--once` |

### BATCH 13-15 — Tools & Utils (DONE)
| Script | Status | CLI |
|--------|--------|-----|
| clipboard_history.py | DONE | `--once / --search / --loop` |
| smart_launcher.py | DONE | `--launch APP / --list / --running` |
| performance_profiler.py | DONE | `--profile / --all / --report` |
| event_logger.py | DONE | `--server / --send / --tail` |
| workspace_sync.py | DONE | `--check / --report / --list` |
| ai_conversation.py | DONE | `--chat / --ask / --history` |

### BATCH 16-18 — Windows Advanced (DONE)
| Script | Status | CLI |
|--------|--------|-----|
| wifi_manager.py | DONE | `--once / --scan / --profiles` |
| audio_controller.py | DONE | `--status / --set LEVEL / --mute` |
| screenshot_tool.py | DONE | `--capture / --window / --list` |
| file_organizer.py | DONE | `--scan / --organize / --undo` |
| system_benchmark.py | DONE | `--once / --quick / --history` |
| startup_manager.py | DONE | `--list / --disable / --enable` |

### BATCH 19-21 — System Management (DONE)
| Script | Status | CLI |
|--------|--------|-----|
| power_manager.py | DONE | `--status / --performance / --balanced` |
| display_manager.py | DONE | `--status / --brightness / --night-mode` |
| service_watcher.py | DONE | `--once / --loop / --restart` |
| task_automator.py | DONE | `--run NAME / --list / --once` |
| data_exporter.py | DONE | `list / schema / export` |
| health_checker.py | DONE | `--once / --loop / --json` |

### NEW — Telegram & Email (DONE)
| Script | Status | CLI |
|--------|--------|-----|
| telegram_commander.py | DONE | `--cmd COMMAND / --list / --all` |
| email_reader.py | DONE | `--read / --telegram / --setup` |

### BATCH 22-24 — Windows Deep (DONE)
| Script | Status | CLI |
|--------|--------|-----|
| registry_manager.py | DONE | `read / write / backup / search / list` |
| bluetooth_manager.py | DONE | `--scan / --list / --status / --connect` |
| usb_monitor.py | DONE | `--once / --loop / --history` |
| scheduled_task_creator.py | DONE | `create / list / delete / run / status` |
| driver_checker.py | DONE | `--list / --outdated / --problems / --gpu` |
| system_restore.py | DONE | `--create / --list / --info` |

### BATCH 25-27 — AI Autonome Advanced (DONE)
| Script | Status | CLI |
|--------|--------|-----|
| intent_classifier.py | DONE | `--classify TEXT / --batch / --stats [--ai]` |
| auto_documenter.py | DONE | `--once [DIR] / --file FILE [--output text/json/md]` |
| code_reviewer.py | DONE | `--review FILE / --all [DIR] / --report` |
| test_generator.py | DONE | `--generate FILE / --all [DIR] / --run FILE` |
| config_validator.py | DONE | `--once / --fix / --report` |
| deployment_manager.py | DONE | `--deploy [MSG] / --status / --rollback / --history` |

### BATCH 28-30 — Monitoring & Analytics (PENDING)
| Script | Status | CLI |
|--------|--------|-----|
| log_analyzer.py | PENDING | `--analyze / --errors / --trends / --report` |
| api_monitor.py | PENDING | `--once / --loop / --endpoints / --latency` |
| resource_forecaster.py | PENDING | `--predict / --trends / --report` |
| alert_manager.py | PENDING | `--rules / --add / --trigger / --history` |
| dashboard_generator.py | PENDING | `--html / --json / --serve` |
| metrics_collector.py | PENDING | `--collect / --export / --history` |

### BATCH 31-33 — AI Pipeline & Orchestration (PENDING)
| Script | Status | CLI |
|--------|--------|-----|
| prompt_router.py | PENDING | `--route TEXT / --benchmark / --stats` |
| response_evaluator.py | PENDING | `--eval FILE / --compare / --score` |
| model_benchmark.py | PENDING | `--run / --compare / --leaderboard` |
| conversation_manager.py | PENDING | `--new / --resume / --list / --export` |
| knowledge_updater.py | PENDING | `--update / --sources / --verify` |
| pipeline_orchestrator.py | PENDING | `--create / --run / --list / --monitor` |

---

## Cron Jobs (12 actifs)

| Nom | Intervalle | Description |
|-----|-----------|-------------|
| telegram_status | 15min | Status formate Telegram |
| telegram_trading | 30min | Trading formate Telegram |
| telegram_health | 1h | Health check Telegram |
| daily_backup | 2h cron | Backup DB + configs |
| security_scan | 3h cron | Scan securite |
| db_optimize | 4h cron | VACUUM + ANALYZE |
| voice_training | 6h | Entrainement vocal |
| update_check | 7h cron | Check mises a jour |
| daily_report | 8h cron | Rapport quotidien |
| telegram_report | 8h cron | Rapport Telegram complet |
| usage_report | 9h cron | Analytics usage |
| weekly_email | Lundi 10h | Email hebdomadaire |

## Telegram Commands (via telegram_commander.py)

| Commande | Pipeline |
|----------|----------|
| `status` | Status systeme complet |
| `trading` | Analyse trading MEXC |
| `health` | Health check + grade |
| `services` | Services Windows |
| `benchmark` | Benchmark CPU/RAM/GPU |
| `emails` | Lire les emails (IMAP Gmail) |
| `workspace` | Etat workspace COWORK |
| `report` | Rapport complet |

## Corrections appliquees
- Session lock OpenClaw supprime (boucle fixee)
- load_balancer.py: API endpoints corrige (Ollama vs LMStudio)
- signal_backtester.py: colonne entry_price -> entry
- voice_trainer.py: colonne type -> hit_count
- email_reader.py: nouveau script IMAP cree
- telegram_commander.py: reponses formatees avec emojis
- telegram_commander.py: pipeline emails corrige (jarvis_mail.py IMAP)
- 5 crons frequents desactives (lock contention)
- Sessions corrompues supprimees (boucle retry)
- email_config.json: multi-compte (mining + perso)
- Batch 22-27: 12 scripts crees et testes OK
