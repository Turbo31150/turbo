# COWORK CONDENSÉ — Session 45+ Complète
# Date: 2026-03-21 | Scripts: 529 | Mappings: 909 | Patterns: 40
# Copier ce document dans OpenClaw, Gemini, ou tout agent autonome

---

## ÉTAT DU SYSTÈME

| Composant | Valeur |
|-----------|--------|
| Scripts cowork/dev/ | 529 |
| Mappings etoile.db | 909 |
| Patterns PAT_CW_* | 40 |
| Page elements pré-enregistrés | 66 (7 sites) |
| Boucles workflow | 140 (16 catégories) |
| Scheduled Tasks Windows | 27+ |
| Hooks settings.json | 8 (SessionStart, PostToolUse, PreCompact, Stop) |
| Docker containers cowork | 3 (engine, dispatcher, MCP) |
| OpenClaw agents | 40 (prompts générés) |
| Navigateurs CDP | Chrome:9222, Comet:9223, BrowserOS:9000 |

## SCRIPTS CRÉÉS CETTE SESSION (48 nouveaux)

### Infrastructure (8)
- `mcp_health_monitor.py` — Check 8 ports services
- `disk_space_watcher.py` — Alerte si C:/F: < 5GB
- `auto_cleaner.py` — Nettoyage auto temp/cache
- `service_watcher.py` — Check+restart Docker/LM Studio/Ollama/Proxy
- `daily_health_report.py` — Rapport complet JSON → data/reports/
- `docker_health_monitor.py` — Monitor containers cowork
- `query_optimizer.py` — Index + VACUUM etoile.db
- `page_element_extractor.py` — Extract 66 selectors → etoile.db

### Contenu Social (6)
- `linkedin_content_generator.py` — Posts LinkedIn via M1 + BrowserOS
- `codeur_profile_manager.py` — Profil Codeur.com + projets
- `email_orchestrator.py` — Triage inbox IMAP
- `calendar_sync.py` — Briefing Google Calendar
- `drive_organizer.py` — Index C:/F:/H: + clean
- `social_pipeline.py` — Orchestrateur 6 triggers parallèles

### Automatisation Intensive (5)
- `social_automation_engine.py` — Moteur MONITOR→DETECT→GENERATE→PUBLISH
- `news_reactor.py` — Veille tech → commentaires LinkedIn
- `interaction_bot.py` — Like/comment/propose LinkedIn+GitHub+Codeur
- `notification_dispatcher.py` — Hub central notifs, triage urgent/normal/low
- `auto_publisher.py` — Queue contenu → publish multi-plateforme

### Multi-IA Distribution (5)
- `multi_ia_task_distributor.py` — 7 IAs routing + consensus pondéré
- `chatgpt_dispatcher.py` — CDP dispatch vers ChatGPT via Comet
- `perplexity_dispatcher.py` — CDP dispatch vers Perplexity
- `browseros_workflow_runner.py` — 4 workflows MCP chaînés
- `multi_browser_dispatcher.py` — 3 navigateurs, 4 templates

### Workflow Chains (4)
- `workflow_chain_engine.py` — 5 chaînes (social, research, morning, codeur, audit)
- `workflow_trigger.py` — Trigger workflows par nom (health, full_cycle, etc.)
- `cowork_cycle_runner.py` — Boucle deploy→test→gaps→docker→disk
- `cluster_consensus.py` — Vote pondéré M1+OL1

### Bridges & Sync (3)
- `openclaw_bridge.py` — Bridge cowork↔OpenClaw Gateway
- `openclaw_prompt_generator.py` — 40 prompts agents OpenClaw
- `cowork_openclaw_sync.py` — Sync bidirectionnel push/pull

### Learning & Patterns (5)
- `feedback_loop.py` — Ajuste scenario_weights selon succès/échec
- `autonomy_scorer.py` — Score autonomie 0-100 (actuel: 65/B)
- `pattern_detector.py` — Détecte anomalies, scripts lents, nœuds instables
- `pipeline_domino_hook.py` — Auto-génère workflows si pattern 3+ fois
- `cowork_loop_generator.py` — 140 boucles auto depuis MEGA_TASKS

### Data & Audit (6)
- `data_exporter.py` — Export toutes tables en JSON
- `knowledge_graph.py` — 3612 nodes, 2631 edges
- `integrity_auditor.py` — 77 DBs, 481 tables, 236K rows
- `db_syncer.py` — Sync voice_corrections etoile↔jarvis
- `auto_changelog.py` — Git log → changelog JSON
- `security_auditor.py` — 169 hits/27 fichiers, api_keys obfusquées

### Communication (3)
- `telegram_mcp_bridge.py` — Alertes/rapports via Bot API
- `n8n_bridge.py` — Bridge cowork↔n8n workflows
- `scheduled_task_improver.py` — Audit+fix+optimize 27 tasks

## ÉLÉMENTS PAGE PRÉ-ENREGISTRÉS (66)

| Site | Éléments | Selectors clés |
|------|----------|---------------|
| LinkedIn | 14 | share, like, comment, connect, follow, search, notifs, feed_posts |
| ChatGPT | 12 | prompt, submit, response, copy, regenerate, model_selector |
| BrowserOS Apps | 10 | gmail_compose, slack_message, notion_page, drive_upload |
| Codeur.com | 10 | projects, apply, search, skills, pagination |
| GitHub | 8 | repos, stars, notifs, search, new_repo |
| Perplexity | 8 | search, submit, response, follow_up, collections |
| AI Studio | 4 | new_prompt, prompt_input, run, model_selector |

## WORKFLOW CHAINS (5 pré-définies)

| Chaîne | Étapes | Timers |
|--------|--------|--------|
| social_publish_chain | news→publish→linkedin→engage→notifs | 5s→3s→10s→5s |
| multi_ia_research_chain | M1→OL1 web→Perplexity→consensus→telegram | 3s→3s→10s→2s |
| morning_routine_chain | calendar→email→notifs→news→social→report | 2s→3s→2s→5s→3s |
| codeur_prospect_chain | scan→propose→publish→track | 5s→10s→3s |
| full_audit_chain | health→integrity→security→patterns→score→report | 2s→5s→5s→2s→2s |

## ROUTING MULTI-IA

| Mot-clé | IA cible | Poids |
|---------|----------|-------|
| code/script/debug | M1/qwen3-8b | 1.9 |
| web search/news/actualité | OL1 minimax cloud | 1.3 |
| quick question | OL1 local | 1.4 |
| research/deep | Perplexity CDP | 1.5 |
| browser action | BrowserOS MCP | — |
| notify/alert | Telegram Bot API | — |
| consensus | ALL → vote pondéré | — |

## SCHEDULED TASKS WINDOWS (27 actives)

| Catégorie | Tasks |
|-----------|-------|
| Contenu | LinkedIn 8h+18h, Codeur 9h, Calendar 7h30, Drive 12h, Social Pipeline 8h |
| Monitoring | Cluster Health, GPU Monitor, Disk Watcher, Service Watcher (toutes 5min) |
| Automation | Auto Backup 6h, Auto Git Commit 8h, Night Ops 2h, Log Rotate dim |
| Boucles | Workflow Tick 1min, Trading Scan 5min, Weekly PnL lun |
| MCP | BrowserOS, CometDevMCP, OpenClaw |
| Docker | Cowork Docker (onstart) |

## HOOKS CLAUDE CODE (8)

| Hook | Event | Fonction |
|------|-------|----------|
| Services check | SessionStart | Chrome+BrowserOS+OpenClaw status (async) |
| Disk check | SessionStart | Alerte si C: < 5GB (async) |
| Browser log | PostToolUse (browseros/chrome-devtools) | Log action → etoile.db |
| Route learning | PostToolUse (Write/Edit) | Enregistre fichier → memories (async) |
| Trading domino | PostToolUse (trading) | Log pipeline |
| Comet domino | PostToolUse (playwright-comet) | Log pipeline |
| Pre-compact save | PreCompact | Sauvegarde contexte avant compaction |
| Session end | Stop | Log fin de session |

## COMMANDES RAPIDES

```bash
# Health check complet
python cowork/dev/mcp_health_monitor.py --once

# Morning routine (6 étapes chaînées)
python cowork/dev/workflow_chain_engine.py --once --chain morning_routine_chain

# Multi-IA parallèle
python cowork/dev/multi_ia_task_distributor.py --parallel --task "votre question"

# Social pipeline (6 triggers)
python cowork/dev/social_pipeline.py --once

# Browser dispatch 3 navigateurs
python cowork/dev/multi_browser_dispatcher.py --audit

# Score autonomie
python cowork/dev/autonomy_scorer.py --once

# Workflow health
python cowork/dev/workflow_trigger.py --workflow health

# Extract page elements
python cowork/dev/page_element_extractor.py --extract-all

# Recall selectors LinkedIn
python cowork/dev/page_element_extractor.py --recall linkedin

# OpenClaw prompts
python cowork/dev/openclaw_prompt_generator.py --once

# Cowork loops
python cowork/dev/cowork_loop_generator.py --once

# Sync OpenClaw
python cowork/dev/cowork_openclaw_sync.py --once
```

## RÈGLES ABSOLUES

1. DISTRIBUER — jamais traiter seul, toujours dispatcher
2. PARALLÈLE — lancer plusieurs tâches simultanément
3. ROUTES GPS — ne jamais re-explorer, utiliser les chemins connus
4. JSON OUTPUT — toujours retourner du JSON structuré
5. ETOILE.DB — logger chaque action dans memories table
6. CODE COULEUR — RED=monitoring, ORANGE=trading, YELLOW=AI, GREEN=GitHub, BLUE=docs
7. ZÉRO RELOAD — evaluate_script > get_content > click
8. BOUTONS MÉMORISÉS — 66 selectors en DB, action directe sans scan
9. PUBLISH ON — gated par validation IA (consensus ≥2, score ≥0.7, caps, quiet hours)
10. AUCUNE SUPPRESSION — Jarvis Linux intouché, roll-forward only
