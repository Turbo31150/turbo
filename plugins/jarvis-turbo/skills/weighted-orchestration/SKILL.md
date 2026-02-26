---
name: Weighted Orchestration
description: Use when orchestrating multi-agent tasks with weighted routing across the JARVIS cluster. Handles 5-level ponderation (node weight, domain, adaptive, thermal, autolearn), dual-model M1 dispatch, and consensus voting.
version: 1.0.0
---

# Weighted Orchestration — Ponderation Multiple 5 Niveaux

## Vue d'ensemble

L'orchestration ponderee distribue les taches sur le cluster JARVIS en combinant 5 niveaux de ponderation pour choisir le noeud optimal a chaque requete.

## Les 5 Niveaux de Ponderation

### Niveau 1 — Poids de noeud (statique, consensus)

Utilise pour le vote pondere lors des decisions de consensus.

| Noeud | Poids | Justification |
|-------|-------|---------------|
| **M1** | **1.8** | 100% benchmark, qwen3-8b rapide (2.4s), qwen3-30b profond |
| **M2** | **1.4** | 100% benchmark, deepseek champion code (3.9s) |
| **OL1** | **1.3** | 100% benchmark, ultra-rapide (1.96s) |
| **GEMINI** | **1.2** | Architecture, vision (instable sur longs prompts) |
| **CLAUDE** | **1.2** | Raisonnement cloud profond (12-18s) |
| **M3** | **1.0** | 100% general mais PAS raisonnement |

**Quorum**: `SUM(opinion * poids) / SUM(poids) >= 0.65`

### Niveau 2 — Ponderation par domaine (benchmark-driven)

Distribution probabiliste par type de tache (benchmark v3, 2026-02-26):

```
code:           M1(50%) M2(30%) M3(15%) OL1(5%)
math:           M1(50%) OL1(30%) M2(15%) M3(5%)
raisonnement:   M1(60%) M2(25%) OL1(15%) [M3 EXCLU]
traduction:     OL1(40%) M1(30%) M3(20%) M2(10%)
systeme:        M1(40%) OL1(35%) M3(15%) M2(10%)
trading:        OL1(35%) M1(30%) M2(20%) M3(15%)
securite:       M1(45%) M2(30%) M3(15%) OL1(10%)
web:            OL1(40%) M1(30%) M3(20%) M2(10%)
```

### Niveau 3 — Ponderation adaptative (etoile.db, temps reel)

Table `adaptive_routing` dans etoile.db, mise a jour a chaque requete:
```sql
SELECT domain, node, score, avg_latency_ms, success_count, fail_count
FROM adaptive_routing
ORDER BY domain, score DESC;
```

Formule: `score = base_score * (success_rate/100) * (1 - latency_penalty)`
- `latency_penalty = min(0.3, avg_latency_ms / 30000)`
- Score max: 10.0, Score critique: <7.0 (declenche re-routage)

### Niveau 4 — Ponderation thermique (GPU temps reel)

```bash
nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader
```

| Temperature | Multiplicateur | Action |
|-------------|---------------|--------|
| <70C | x1.0 | Normal |
| 70-75C | x0.9 | Monitoring accru |
| 75-85C | x0.7 | Reduire charge, eviter batch lourds |
| >85C | **x0.0** | EXCLU — cascade failover |

### Niveau 5 — Ponderation autolearn (canvas/autolearn.js, continu)

Le moteur autolearn reordonne le ROUTING toutes les 5 min:
```
final_score = speed * 0.3 + quality * 0.5 + reliability * 0.2
```

API: `curl http://127.0.0.1:18800/autolearn/scores`

## Score Final Combine

```
score_final(noeud, domaine) =
    poids_noeud                              (N1)
  * ponderation_domaine[domaine][noeud]       (N2)
  * score_adaptatif / 10                      (N3)
  * multiplicateur_thermique                  (N4)
  * score_autolearn / 10                      (N5)
```

Le noeud avec le `score_final` le plus eleve recoit la tache.

## Dual-Model M1

M1 possede 2 modeles:
- **qwen3-8b** (defaut): taches courantes, <3s
- **qwen3-30b** (on-demand): raisonnement profond, architecture, >5s

### Decision tree
```
Tache recue
    |
    ├── Complexite simple (<50 tokens sortie) → qwen3-8b
    ├── Code <100 lignes → qwen3-8b
    ├── Traduction/systeme/commande → qwen3-8b
    ├── Math elementaire → qwen3-8b
    |
    ├── Raisonnement multi-etapes (>3) → qwen3-30b
    ├── Analyse code >200 lignes → qwen3-30b
    ├── Architecture complete → qwen3-30b
    └── Consensus critique → qwen3-30b
```

## Workflow d'orchestration

```
1. CLASSIFIER la tache (M1 qwen3-8b, 0.6s)
   → domaine: code|math|raisonnement|traduction|systeme|trading|securite|web
   → complexite: simple|moyen|profond

2. CALCULER score_final pour chaque noeud
   → Combiner les 5 niveaux de ponderation
   → Exclure noeuds offline ou GPU >85C

3. DISPATCHER au meilleur noeud
   → Si complexite=profond ET noeud=M1: utiliser qwen3-30b
   → Sinon: utiliser le modele par defaut du noeud

4. MESURER performance
   → Latence, qualite reponse, succes/echec
   → Mettre a jour adaptive_routing dans etoile.db

5. FALLBACK si echec
   → Cascade: M1→M2→OL1→M3→GEMINI→CLAUDE
   → Re-enrichir le prompt (CoT, etapes detaillees)
```

## 7 Agents Disponibles

| Agent | Role | Poids | Couleur |
|-------|------|-------|---------|
| **cluster-ops** | Operations, health, GPU | — | cyan |
| **code-architect** | Architecture, code review | — | blue |
| **trading-analyst** | Signaux trading, consensus | — | green |
| **debug-specialist** | Debug systematique | — | red |
| **performance-monitor** | Metriques, regression | — | yellow |
| **smart-dispatcher** | Routage intelligent | — | magenta |
| **auto-healer** | Reparation automatique | — | red |

## Commandes liees

- `/cluster-check` — Health check tous noeuds
- `/consensus [question]` — Vote pondere multi-IA
- `/heal-cluster` — Diagnostic + auto-repair
- `/cluster-benchmark` — Benchmark complet
- `/audit` — Audit systeme 10 sections
