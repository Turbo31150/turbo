# Auto-Heal v2 — Multi-Pipeline Interactif

Date: 2026-03-07
Status: VALIDATED

## Contexte

Le daemon auto-heal v1 (`scripts/auto_heal_daemon.py`, 787 lignes) fonctionne mais est limité :
- Fixes basiques (restart service seulement)
- Telegram one-way (notifications sans interaction)
- Analyse AI simple (M1 seul, séquentiel)
- Détection limitée (5 détecteurs, pas de logs)

## Objectifs

1. **Intelligence des fixes** : catalogue de fixes avec niveaux de risque
2. **Boucle Telegram interactive** : boutons InlineKeyboard (Approuver/Rejeter/Retry)
3. **Couverture détection** : log watcher temps réel + latence API
4. **Multi-pipeline distribué** : dispatch parallèle M1+OL1+M2, consensus voté

## Architecture

```
scripts/auto_heal_daemon.py     <- Orchestrateur (existant, simplifié)
   |-- src/heal_detectors.py    <- 7 détecteurs
   |-- src/heal_telegram.py     <- Bot interactif InlineKeyboard + callback polling
   |-- src/heal_pipeline.py     <- Dispatch parallèle, consensus voté
   +-- src/heal_fixes.py        <- Catalogue de fixes, niveaux de risque, exécution
```

## Flux principal

```
Detection -> Pipeline parallele (M1+OL1+M2 analysent) -> Consensus vote
  -> Telegram notification + boutons [Approuver] [Rejeter] [Retry] [Details]
    -> User clique Approuver -> Fix execute -> Verification -> Rapport Telegram
    -> User clique Rejeter -> Issue marquee "skipped", prochain cycle
    -> Timeout 5min sans reponse -> Issue remonte au cycle suivant
```

## Decisions clés

- **Autonomie** : TOUT avec validation Telegram avant action (aucun fix auto)
- **Pipeline** : Parallèle — tous les agents analysent chaque issue, consensus voté
- **Telegram** : InlineKeyboard (boutons), polling getUpdates toutes les 2s
- **Détection prioritaire** : Logs d'erreur temps réel (Traceback/Exception pattern matching)

## Module 1 : heal_detectors.py — 7 détecteurs

| Detecteur | Source | Seuils | Priorite |
|-----------|--------|--------|----------|
| detect_nodes | Port check + API /models | offline = critical | P0 |
| detect_services | Port check (7 services) | critical si jarvis_ws | P0 |
| detect_logs | Tail logs/*.log + python_ws/logs | Traceback, Exception, Error | P1 |
| detect_thermal | nvidia-smi | >85C = critical, >75C = warning | P1 |
| detect_doublons | PowerShell Get-CimInstance | >1 instance meme script | P2 |
| detect_db | PRAGMA integrity_check | corruption = critical | P2 |
| detect_latency | Ping M1/OL1/M2 avec timer | >2x baseline = warning | P3 |

### Log Watcher (nouveau)

- Fichiers scannés : logs/auto_heal.log, logs/jarvis.log, python_ws/logs/*.log, logs/trading.log
- Patterns : Traceback, Exception, Error, CRITICAL, ConnectionRefused
- Déduplication : même erreur vue dans les 5 dernières minutes = ignorée
- Contexte : 5 lignes avant/après pour analyse AI

### Latency Detector (nouveau)

- Ping HTTP chaque noeud avec timer
- Baseline calculée sur les 10 dernières mesures
- Alerte si >2x baseline

## Module 2 : heal_pipeline.py — Consensus multi-agent

Dispatch parallèle via asyncio/threading :
- M1 (poids 1.9) : qwen3-8b, rapide, principal
- OL1 (poids 1.4) : qwen3:1.7b, ultra-rapide
- M2 (poids 1.5) : deepseek-r1, reasoning profond

Chaque agent retourne :
1. Cause probable (1 phrase)
2. Fix recommandé (commande ou action)
3. Niveau de risque : safe / moderate / dangerous
4. Confiance : 0-100%

Consensus : vote pondéré, quorum >= 0.65 (poids MAO existants)

## Module 3 : heal_telegram.py — Bot interactif

- Polling getUpdates toutes les 2s (thread dédié)
- InlineKeyboard sous chaque alerte :
  - [Approuver] [Rejeter] [Retry] [Details]
- callback_data encodé : fix:<component>:<fix_type>:<cycle>
- Timeout 5min sans réponse -> issue remonte au cycle suivant
- File d'attente : fixes approuvés s'exécutent séquentiellement

## Module 4 : heal_fixes.py — Catalogue de fixes

| Fix | Risque | Action |
|-----|--------|--------|
| restart_service | safe | Singleton acquire + Popen |
| reload_model | safe | lms load |
| kill_doublon | moderate | taskkill le plus ancien PID |
| swap_node | moderate | Rediriger trafic M1->OL1 |
| clear_db_lock | moderate | PRAGMA wal_checkpoint |
| rollback_config | dangerous | Restaurer config depuis backup |
| restart_node | dangerous | Kill + restart LM Studio/Ollama |

Chaque fix a une méthode verify() qui confirme la réparation.

## Persistence

- SQLite : data/auto_heal.db (existant, tables heal_log + persistent_issues)
- Nouvelles tables : fix_queue (fixes en attente validation), consensus_log (votes agents)

## Contraintes

- Windows 11, Python 3.13, pas d'async natif dans le daemon -> threading pour Telegram polling
- M2 circuit-open (24% success) -> fallback M1+OL1 si M2 timeout
- OLLAMA_NUM_PARALLEL=3 -> ne pas saturer OL1
- cp1252 console -> ASCII dans print(), Unicode dans Telegram (HTTP/UTF-8)
