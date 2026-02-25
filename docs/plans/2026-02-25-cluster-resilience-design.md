# Cluster Resilience & Model Arena — Design Document

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rendre le cluster JARVIS auto-reparant (H24 sans intervention), capable de tester de nouveaux modeles automatiquement, et de tracer l'evolution des performances dans le temps.

**Date:** 2026-02-25
**Auteur:** turbONE + Claude Opus 4.6

---

## 1. Auto-Healing Engine

### Principe

Un watchdog daemon qui tourne en continu (boucle 60s), ping chaque noeud du cluster, et reagit automatiquement aux pannes sans intervention humaine.

### Cycle de detection et reparation

```
ping noeud (curl /api/v1/models ou /api/tags, timeout 5s)
  → OK → rien, log "healthy"
  → FAIL → retry 1x (attendre 5s)
    → OK → log "recovered"
    → FAIL → action automatique :
        1. Unload/reload le modele via API LM Studio
        2. Si reload echoue → failover (bascule trafic vers noeud backup)
        3. Apres reload → mini-benchmark (3 questions rapides) → score OK (>= 66%) ?
           → OUI → retour en service, log "healed"
           → NON → rollback (recharger ancien modele ou marquer offline + alerte)
```

### Fichier

`C:/Users/franc/jarvis_cluster_healer.py` — script standalone Python, lancable en daemon.

### Endpoints de health check par noeud

| Noeud | Health URL | Timeout |
|-------|-----------|---------|
| M1 | `http://10.5.0.2:1234/api/v1/models` + auth header | 5s |
| M2 | `http://192.168.1.26:1234/api/v1/models` + auth header | 5s |
| M3 | `http://192.168.1.113:1234/api/v1/models` + auth header | 5s |
| OL1 | `http://127.0.0.1:11434/api/tags` | 3s |

### Rollback

Le healer maintient un `last_known_good` par noeud :
```python
last_known_good = {
    "M1": {"model": "qwen/qwen3-30b-a3b-2507", "config": {"context_length": 8192, ...}},
    "M2": {"model": "deepseek-coder-v2-lite-instruct", "config": {"context_length": 4096, ...}},
    ...
}
```

Si un modele reloade echoue le mini-benchmark 2 fois consecutives, le healer revert vers `last_known_good`.

### Notifications

- Console : print avec timestamp
- Log fichier : `C:/Users/franc/jarvis_healer.log`
- Optionnel : Telegram via webhook (si configure)

### Fallback order

M1 down → trafic vers M2. M2 down → M3. M3 down → OL1. Tous down → alerte critique, attente manuelle.

---

## 2. Model Arena (tournoi de modeles)

### Principe

Un systeme de tournoi qui charge un modele candidat sur un noeud (principalement M1), lui fait passer le benchmark autotest complet, et compare son score composite au champion actuel.

### Score composite

```
score = qualite * 0.6 + vitesse * 0.3 + fiabilite * 0.1
```

- **Qualite** = `pass_count / total_tests * 10` (normalise 0-10)
- **Vitesse** = `max(0, 10 - avg_latency_seconds)` (normalise 0-10, 0s=10, 10s+=0)
- **Fiabilite** = `(1 - error_rate) * 10` (normalise 0-10)

### Workflow du tournoi

```
1. Lire champion actuel depuis benchmark_history.json
2. Sauvegarder config actuelle (modele + settings) → "champion_backup"
3. Unload champion via API /api/v1/models/unload
4. Load candidat via API /api/v1/models/load avec settings optimaux
   (ctx=8192, flash_attention=true, eval_batch=512, kv_gpu=true)
5. Warmup : 3 requetes simples (jetees, pas comptees)
6. Benchmark : 5 cycles x 40 taches = 200 tests via jarvis_autotest.py
7. Calculer score composite du candidat
8. Comparer :
   - candidat.score > champion.score → NOUVEAU CHAMPION
     → sauvegarder config, mettre a jour history, log
   - candidat.score <= champion.score → ROLLBACK
     → unload candidat, reload champion, log
9. Ecrire resultats dans benchmark_history.json
```

### Modeles a tester (ordre de priorite)

1. `qwen3-coder-30b` — deja telecharge sur M1, specialise code
2. `devstral` — deja telecharge sur M1, dev-focused Mistral
3. `gpt-oss-20b` — deja telecharge sur M1, plus petit = potentiellement plus rapide
4. Phase 2 : telecharger les plus prometteurs selon benchmarks HuggingFace

### Fichier

`C:/Users/franc/jarvis_model_arena.py` — CLI on-demand.

### Usage

```bash
python3 jarvis_model_arena.py qwen3-coder-30b          # teste un modele
python3 jarvis_model_arena.py --all                     # teste tous les on-demand
python3 jarvis_model_arena.py --history                 # affiche l'historique
```

---

## 3. Benchmark continu & historique

### Principe

Chaque run de benchmark (autotest ou arena) sauvegarde ses resultats dans un historique JSON persistant. Permet de tracer l'evolution des scores et detecter les regressions.

### Stockage

`C:/Users/franc/jarvis_benchmark_history.json`

```json
{
  "runs": [
    {
      "timestamp": "2026-02-25T20:15:00",
      "type": "autotest",
      "model_m1": "qwen3-30b-a3b-2507",
      "config_m1": {"context_length": 8192, "temperature": 0.2},
      "score_composite": 9.2,
      "pass_rate": 100,
      "avg_latency_ms": 11265,
      "total_tests": 60,
      "by_node": {
        "M1": {"pass": 34, "total": 34, "avg_latency": 11265},
        "OL1": {"pass": 16, "total": 16, "avg_latency": 2636}
      },
      "by_domain": {
        "code": {"pass": 8, "total": 8},
        "math": {"pass": 8, "total": 8}
      }
    }
  ],
  "champion": {
    "model": "qwen/qwen3-30b-a3b-2507",
    "score": 9.2,
    "since": "2026-02-25",
    "config": {"context_length": 8192, "temperature": 0.2}
  }
}
```

### Detection de regression

Si le score composite baisse de >10% entre 2 runs consecutifs du meme type :
- Le healer marque le noeud principal comme "degraded"
- Alerte console : `[REGRESSION] M1 score 9.2 → 7.8 (-15%)`
- Le healer peut declencher un mini-arena pour verifier si le probleme est le modele ou temporaire

### Integration avec autotest existant

Modification mineure de `jarvis_autotest.py` : apres `save_results()`, appeler `append_to_history()` pour ecrire dans le fichier historique.

---

## 4. Integration des modules

### Architecture

```
jarvis_cluster_healer.py      daemon 60s    ping + repair + rollback + regression detect
jarvis_model_arena.py          CLI on-demand tournoi modeles + score composite
jarvis_benchmark_history.json  stockage      partage entre healer, arena, autotest
jarvis_autotest.py             existant      alimente historique apres chaque run
```

### Flux de donnees

```
autotest.py ──run──→ results.json
     │
     └──append──→ benchmark_history.json ←──append── arena.py
                          │
                          └──read── healer.py (regression detect)

healer.py ──ping 60s──→ noeuds cluster
     │
     ├──reload──→ LM Studio API /models/load
     ├──mini-bench──→ 3 questions test
     └──rollback──→ last_known_good config
```

### Nouvelles commandes plugin jarvis-turbo

| Commande | Description |
|----------|-------------|
| `/heal-status` | Etat du healer : noeuds, dernier check, actions recentes |
| `/arena [modele]` | Lance un tournoi pour un modele candidat |
| `/benchmark-history` | 10 derniers scores + tendance + champion actuel |

### Ordre d'implementation

1. **benchmark_history.json** + fonction `append_to_history()` dans autotest.py
2. **jarvis_cluster_healer.py** — watchdog + reload + mini-benchmark + rollback
3. **jarvis_model_arena.py** — tournoi + score composite + rollback
4. **Commandes plugin** — `/heal-status`, `/arena`, `/benchmark-history`
5. **Tests end-to-end** — simuler panne, verifier healing, lancer arena

---

## 5. Contraintes et risques

| Risque | Mitigation |
|--------|-----------|
| Reload modele pendant requete active | Healer attend 10s apres detection avant action |
| Arena bloque M1 pendant tournoi (~30min) | Warning console, mode --quick (2 cycles) disponible |
| VRAM saturee par nouveau modele | Toujours unload avant load, verifier taille modele |
| Historique JSON trop gros | Garder max 500 runs, rotation automatique |
| Faux positif regression (variance naturelle) | Seuil >10% sur 2 runs consecutifs, pas 1 seul |

---

## 6. Criteres de succes

- [ ] Healer detecte une panne simulee et reload le modele en < 2min
- [ ] Healer rollback si mini-benchmark echoue
- [ ] Arena compare 2 modeles et designe le champion correctement
- [ ] Score composite calcule et coherent (champion actuel ~9.2)
- [ ] Historique accumule les runs et detecte regression >10%
- [ ] Commandes plugin fonctionnelles
