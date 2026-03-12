# Workflows n8n JARVIS

## Vue d'ensemble

6 workflows automatises pour JARVIS Turbo, integrant le cluster IA, le trading, et la maintenance systeme.

## 1. Cluster Monitor (`jarvis_cluster_monitor.json`)

**Frequence:** Toutes les 5 minutes
**Action:** Verifie M1/M2/M3 via `/v1/models`, agregue le statut, alerte Windows si un noeud est offline.

```
Schedule(5min) → [Check M1, Check M2, Check M3] → Aggregate → Alert?
```

## 2. Trading Pipeline (`jarvis_trading_pipeline.json`)

**Frequence:** Toutes les 15 minutes
**Action:** M1 analyse profonde + M2 signal rapide → merge → M3 valide le consensus.

```
Schedule(15min) → [M1 Deep, M2 Fast] → Merge → M3 Validate → Consensus
```

Paires: BTC, ETH, SOL, SUI | Config: MEXC Futures, 10x, TP 0.4%, SL 0.25%

## 3. Daily Report (`jarvis_daily_report.json`)

**Frequence:** Tous les jours a 8h00
**Action:** Check cluster + systeme → rapport compile → synthese vocale TTS.

```
Schedule(8h) → [Check M1, M2, M3, System] → Build Report → TTS Speak
```

## 4. System Health (`jarvis_system_health.json`)

**Frequence:** Toutes les 10 minutes
**Action:** CPU/RAM/disque → parse → alerte vocale si critique (>90%).

```
Schedule(10min) → Metrics → Parse → Alert? → Voice Alert
```

## 5. Brain Learning (`jarvis_brain_learning.json`)

**Frequence:** Toutes les heures
**Action:** Charge l'historique d'actions → detecte patterns → auto-cree des skills.

```
Schedule(1h) → Check History → Analyze → Enough Data? → Brain Learn → Parse
```

## 6. Git Auto Backup (`jarvis_git_auto_backup.json`)

**Frequence:** Toutes les 6 heures
**Action:** Git status → si changements → commit + push automatique.

```
Schedule(6h) → Git Status → Changes? → Commit & Push
```

## Import dans n8n

```bash
# Via CLI n8n
n8n import:workflow --input=n8n_workflows/jarvis_cluster_monitor.json
n8n import:workflow --input=n8n_workflows/jarvis_trading_pipeline.json
n8n import:workflow --input=n8n_workflows/jarvis_daily_report.json
n8n import:workflow --input=n8n_workflows/jarvis_system_health.json
n8n import:workflow --input=n8n_workflows/jarvis_brain_learning.json
n8n import:workflow --input=n8n_workflows/jarvis_git_auto_backup.json
```

Ou manuellement: n8n UI > Settings > Import from file
