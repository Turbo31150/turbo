# JARVIS v2 - Deploiement des nouveaux modules

Date: 2026-03-05
Version: 2.0 (10 nouveaux modules + patch MCP server)

## Fichiers crees

### 1. Core Infrastructure

**src/startup_wiring.py** (8 KB)
- Bootstrap master en 9 etapes sequentielles
- Wire event bus, health probes, GPU guardian, self-healer, trading sentinel
- Demarrage/arret gracieux de tous les services

**src/event_bus_wiring.py** (8 KB)  
- 16 subscribers sur 10 categories d'evenements
- Integration: trading, GPU, cluster, brain, notifications

**src/scheduler_cleanup.py** (5 KB)
- Suppression 36 jobs test dupliques
- Creation 8 vrais jobs (rapports, nettoyage, drift, health checks)

### 2. Monitoring & Health

**src/health_probe_registry.py** (7 KB)
- 10 sondes: LM Studio M1, Ollama, GPU, DB, disk, event bus, tunnel, MCP port, trading
- Toutes enregistrees automatiquement au bootstrap

**src/gpu_guardian.py** (9 KB)
- Surveillance GPU continue (temperature, VRAM, power)
- Unload automatique des modeles en cas d'urgence
- Emission evenements vers event bus

**src/cluster_self_healer.py** (9 KB)
- Auto-restart des noeuds tombes (LM Studio, Ollama)
- Reroutage trafic vers noeuds sains
- Escalation si recuperation impossible

### 3. Trading & Intelligence

**src/trading_sentinel.py** (9 KB)
- Monitoring positions 24/7
- Alertes drawdown (-3%, -5%, -8%)
- Alerte liquidation proximity
- Integration avec notification_hub

**src/perplexity_bridge.py** (7 KB)
- Pont Perplexity <-> JARVIS brain
- Transfert patterns/insights/questions
- Enrichissement mutuel des connaissances

**src/smart_retry.py** (6 KB)
- Retry intelligent avec fallback chain
- Exponential backoff + jitter
- Circuit breaker integration
- Stats globales

**src/daily_report.py** (7 KB)
- Rapports matin/soir automatiques
- Sections: cluster, GPU, trading, alertes, brain, recommandations
- Pret pour integration scheduler

### 4. Patch MCP Server

**mcp_server_sse_lifespan_patch.py** (2 KB)
- Nouveau lifespan avec bootstrap_jarvis() integre
- Remplace lignes ~352-356 dans src/mcp_server_sse.py

---

## Installation rapide

### Etape 1: Patch du serveur MCP (OBLIGATOIRE)

1. Ouvrir `F:\BUREAU\turbo\src\mcp_server_sse.py`
2. Aller a la ligne ~352 (chercher `@contextlib.asynccontextmanager`)
3. Remplacer tout le bloc lifespan par le contenu de `mcp_server_sse_lifespan_patch.py`
4. Sauvegarder

### Etape 2: Verifier les imports

Tous les nouveaux modules sont deja dans `src/`. Verifier qu'ils sont bien presents:

```powershell
Get-ChildItem F:\BUREAU\turbo\src\ | Where-Object { $_.Name -match '(startup_wiring|event_bus_wiring|scheduler_cleanup|health_probe_registry|gpu_guardian|cluster_self_healer|trading_sentinel|perplexity_bridge|smart_retry|daily_report)' }
```

Doit afficher 10 fichiers.

### Etape 3: Tester le bootstrap

```powershell
cd F:\BUREAU\turbo
python -c "import asyncio; from src.startup_wiring import bootstrap_jarvis; asyncio.run(bootstrap_jarvis())"
```

Doit afficher:
```
[1/9] Scheduler fix: OK
[2/9] Scheduler bootstrap: OK
[3/9] Event bus wiring: OK
[4/9] Health probes: OK
[5/9] GPU Guardian: OK
[6/9] Cluster self-healer: OK
[7/9] Trading Sentinel: OK
[8/9] Autonomous loop: OK
[9/9] Startup event: OK

JARVIS Bootstrap COMPLETE in XXXms
  9/9 steps OK -- ALL SYSTEMS GO
```

### Etape 4: Demarrer le serveur MCP

```powershell
python -m src.mcp_server_sse --port 8901 --light
```

Logs attendus:
```
JARVIS Bootstrap OK in 1234ms (9/9 steps)
JARVIS MCP Server READY - All systems operational
JARVIS MCP on http://0.0.0.0:8901 -- LIGHT (25 tools) -- Streamable HTTP (/mcp)
```

---

## Verification post-deploiement

### Verifier les services actifs

```python
from src.gpu_guardian import gpu_guardian
print(gpu_guardian.status())

from src.trading_sentinel import trading_sentinel
print(trading_sentinel.summary())

from src.cluster_self_healer import cluster_healer
print(cluster_healer.status())

from src.event_bus import event_bus
print(f"Event bus subscribers: {len(event_bus._subscriptions)}")
```

### Verifier les health probes

```python
from src.health_probe import health_probe
results = health_probe.run_all()
for r in results:
    print(f"{r.name}: {r.status.value} ({r.message})")
```

### Verifier le scheduler

```python
from src.scheduler import scheduler
jobs = scheduler.get_all_jobs()
print(f"Total jobs: {len(jobs)}")
for j in jobs[:5]:
    print(f"- {j.id}: {j.trigger}")
```

Doit afficher 8 jobs (plus les jobs test si pas encore nettoyes).

---

## Integration Perplexity

Le serveur MCP est maintenant pret pour Perplexity. URL a configurer:

```
https://<votre-tunnel-cloudflare>/mcp/
```

Mode light (25 outils) inclut:
- lm_query, lm_cluster_status, consensus
- brain_status, brain_analyze, memory_recall
- trading_pipeline_v2, trading_pending_signals
- orch_dashboard, orch_node_stats
- system_info, gpu_info, powershell_run
- screenshot, sql_query

Pour plus d'outils, utiliser `--full` (100 outils) ou `--all` (380+ outils).

---

## Troubleshooting

### Bootstrap echoue a une etape

Le bootstrap est resilient: si une etape echoue, les suivantes continuent.
Verifier les logs pour identifier l'etape en echec.

### GPU Guardian ne demarre pas

Verifier que nvidia-smi est accessible:
```powershell
nvidia-smi
```

Si absent, GPU Guardian se desactive automatiquement (non-critique).

### Trading Sentinel ne trouve pas les positions

Verifier que les cles API MEXC sont configurees dans l'environnement.
Le sentinel peut tourner sans positions (monitoring passif).

### Event bus n'a aucun subscriber

Verifier que `event_bus_wiring.py` a bien ete appele dans le bootstrap.
Relancer le bootstrap manuellement:

```python
import asyncio
from src.event_bus_wiring import wire_all
asyncio.run(wire_all())
```

### Scheduler a encore 36 jobs test

Nettoyer manuellement:

```python
import asyncio
from src.scheduler_cleanup import cleanup_and_bootstrap
asyncio.run(cleanup_and_bootstrap())
```

---

## Prochaines etapes

1. **Integrer les rapports quotidiens au scheduler**
   ```python
   from src.daily_report import generate_morning_report, generate_evening_report
   # Ajouter 2 jobs scheduler pour 7h et 19h
   ```

2. **Activer Perplexity Bridge dans le brain**
   ```python
   from src.perplexity_bridge import bridge
   # Appeler bridge.sync_from_perplexity() apres chaque question Perplexity
   ```

3. **Monitorer les stats de retry**
   ```python
   from src.smart_retry import retry_stats
   print(retry_stats.to_dict())
   ```

4. **Configurer les alertes critiques**
   - Ajouter webhook Discord/Telegram dans notification_hub
   - Configurer les seuils dans gpu_guardian et trading_sentinel

---

## Architecture finale

```
mcp_server_sse.py (patche)
  |-- lifespan
       |-- bootstrap_jarvis()  [startup_wiring.py]
            |-- fix_scheduler_bug
            |-- cleanup_and_bootstrap_scheduler
            |-- wire_event_bus  [event_bus_wiring.py]
            |-- register_health_probes  [health_probe_registry.py]
            |-- start GPU Guardian  [gpu_guardian.py]
            |-- wire Cluster Self-Healer  [cluster_self_healer.py]
            |-- start Trading Sentinel  [trading_sentinel.py]
            |-- start Autonomous Loop
            |-- emit startup_complete event
       |-- yield (serveur MCP operationnel)
       |-- shutdown_jarvis()  [startup_wiring.py]
```

Tous les services tournent en background, le serveur MCP reste reactif.

---

**Total: 10 nouveaux modules + 1 patch = systeme JARVIS v2 complet.**

