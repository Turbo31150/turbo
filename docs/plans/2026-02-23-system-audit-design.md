# Design: System Audit — Diagnostic Distribué JARVIS

**Date**: 2026-02-23
**Approche**: Script Python autonome (asyncio parallèle)
**Fichier cible**: `scripts/system_audit.py`

## Objectif

Remplacer le health check basique (`MAO check`) par un audit complet du cluster
qui produit un rapport structuré en 10 sections avec scores de readiness.

Utilisable en CLI, commande vocale, et outil MCP.

## Architecture

```
scripts/system_audit.py
├── async main()              → orchestrateur, lance tous les checks en parallèle
│
├── Phase 1: Node Health
│   ├── check_lm_node(node)   → ping + modèles chargés + VRAM (M1/M2/M3)
│   ├── check_ollama()        → ping + modèles locaux/cloud (OL1)
│   └── check_gemini()        → test proxy gemini-proxy.js
│
├── Phase 2: System Info
│   ├── check_gpu_local()     → nvidia-smi (temp, VRAM, utilisation)
│   ├── check_system()        → OS version, RAM, CPU, disques
│   └── check_ports()         → scan ports connus (async socket)
│
├── Phase 3: Consistency
│   ├── check_mcp_status()    → endpoints MCP actifs
│   └── detect_drift()        → versions LM Studio, modèles manquants
│
├── Phase 4: Analysis
│   ├── analyze_spof()        → Single Points of Failure
│   ├── analyze_security()    → ports exposés, API keys, auth
│   ├── analyze_persistence() → backups, logs, recovery
│   └── compute_scores()      → 6 scores readiness (0-100)
│
└── Phase 5: Output
    ├── generate_report()     → assemblage 10 sections
    └── save_report()         → data/audit_YYYY-MM-DD_HHmm.json + console
```

## Collecte parallèle

```python
results = await asyncio.gather(
    check_lm_node(config.lm_nodes[0]),  # M1
    check_lm_node(config.lm_nodes[1]),  # M2
    check_lm_node(config.lm_nodes[2]),  # M3
    check_ollama(),                      # OL1
    check_gemini(),                      # GEMINI
    check_gpu_local(),                   # GPU nvidia-smi
    check_system(),                      # OS/RAM/disques
    check_ports(),                       # Ports actifs
    return_exceptions=True,
)
```

Timeout par noeud : **5s** (audit rapide, pas d'attente sur M1 qui timeout).

## APIs utilisées

| Noeud | Endpoint | Données récupérées |
|-------|----------|-------------------|
| M1/M2/M3 | `GET /api/v1/models` + auth | Modèles chargés, VRAM, context_length, loaded_instances |
| M1/M2/M3 | `POST /api/v1/chat` "ping" | Latence réelle (prompt test minimal) |
| OL1 | `GET /api/tags` | Modèles locaux installés |
| OL1 | `POST /api/chat` "ping" | Latence réelle qwen3:1.7b |
| GEMINI | `node gemini-proxy.js "test"` | Disponibilité + latence proxy |
| Local | `nvidia-smi --query-gpu=...` | Temp, VRAM free/total, utilisation % |
| Local | PowerShell: `Get-CimInstance` | OS, RAM, CPU, disques |

## Les 10 sections du rapport

1. **Executive Summary** — Status global (OK/WARNING/CRITICAL), nb noeuds up, version
2. **Architecture Map** — Arbre ASCII : machines, IPs, rôles, modèles chargés
3. **Node Health Table** — Par noeud : status, latence, modèles, VRAM, GPU temp
4. **Topology & Dependencies** — Flux, dépendances, failover paths
5. **Multimodal Capability Matrix** — Text/embedding/vision/audio par noeud
6. **Critical Risks** — SPOF, noeuds down, saturations (severity HIGH/MED/LOW)
7. **Security Assessment** — Ports, auth, API keys, trust boundaries
8. **Performance & Scaling** — Latences, throughput, bottlenecks, GPU headroom
9. **Persistence & Recovery** — Backups, logs, RTO/RPO estimés
10. **Readiness Scores** — 6 scores 0-100 :
    - Stability (noeuds up, latence, GPU temp)
    - Resilience (failover paths, redondance modèles)
    - Security (auth, ports, isolation)
    - Horizontal Scalability (GPU headroom, routing diversity)
    - Multimodal Maturity (text, embedding, vision, audio)
    - Operational Observability (monitoring, logs, alertes)

## Calcul des scores

```
Stability       = (nodes_up/total * 40) + (latency_ok * 30) + (gpu_temp_ok * 30)
Resilience      = (failover_paths * 40) + (model_redundancy * 30) + (no_spof * 30)
Security        = (auth_present * 40) + (ports_safe * 30) + (no_exposed_keys * 30)
Scalability     = (gpu_headroom * 40) + (routing_diversity * 30) + (node_count * 30)
Multimodal      = (text_ok * 40) + (embedding_ok * 20) + (vision * 20) + (audio * 20)
Observability   = (logs_exist * 40) + (monitoring * 30) + (backup_exist * 30)
```

## SPOF Detection

Checks automatiques :
- GEMINI proxy = seul point d'entrée Gemini → SPOF si proxy crash
- M1 = seul noeud embedding → SPOF pour RAG
- OL1 = seul noeud web research → SPOF pour données temps réel
- Machine maître = orchestrateur unique → SPOF critique
- Réseau LAN = pas de WAN failover

## Intégration

### CLI
```bash
uv run python scripts/system_audit.py
uv run python scripts/system_audit.py --json  # sortie JSON seule
uv run python scripts/system_audit.py --quick  # santé cluster seulement (phases 1-2)
```

### Commande vocale
Ajout dans `src/commands.py` :
```python
"audit_systeme": {"action": "run_script", "script": "system_audit", "args": []},
"etat_du_cluster": {"action": "run_script", "script": "system_audit", "args": ["--quick"]},
```

### Outil MCP
Ajout dans `src/tools.py` :
```python
@tool
async def system_audit(mode: str = "full") -> str:
    """Run complete cluster audit. mode: 'full' or 'quick'."""
```

## Dépendances

Aucune nouvelle :
- `httpx` (déjà installé) — requêtes async
- `asyncio` (stdlib) — parallélisme
- `subprocess` (stdlib) — nvidia-smi, PowerShell, gemini-proxy
- `json` (stdlib) — sérialisation rapport
- `src/config.py` — configuration cluster existante

## Sortie

### Console (colorée si terminal)
```
╔══════════════════════════════════════════╗
║     JARVIS CLUSTER AUDIT — 2026-02-23   ║
╠══════════════════════════════════════════╣
║ Status: ✓ OPERATIONAL (4/5 nodes up)    ║
╚══════════════════════════════════════════╝

§1 EXECUTIVE SUMMARY
  Cluster: JARVIS v10.2 | 5 nodes | 10 GPU | ~78 GB VRAM
  Status: 4/5 UP — M1 timeout (expected)
  ...
```

### JSON (`data/audit_2026-02-23_1430.json`)
```json
{
  "timestamp": "2026-02-23T14:30:00",
  "version": "10.2",
  "nodes": {...},
  "scores": {"stability": 82, ...},
  "risks": [...],
  "report_sections": [...]
}
```

## Contraintes

- JAMAIS `localhost` → toujours `127.0.0.1`
- Timeout 5s par noeud (pas 120s)
- Ne pas saturer M1 avec un prompt test (juste GET /api/v1/models)
- Import config depuis `src/config.py` pour les IPs/keys
- Compatible Python 3.13 + uv
