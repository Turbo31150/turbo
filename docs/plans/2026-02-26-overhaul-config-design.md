# JARVIS v10.3 Overhaul — Config + Benchmark + Agents + Hooks + Pondération

> **Date**: 2026-02-26
> **Statut**: Approuvé

## Objectif

Mettre à jour l'ensemble du système JARVIS après le switch M1 qwen3-30b → qwen3-8b (10x plus rapide) : README, routing dynamique, benchmark, 3 nouveaux agents, 3 hooks, pondération consensus.

## 1. Routing dynamique (direct-proxy.js)

**Principe** : ROUTING hardcodé = fallback. `callNode()` consulte d'abord autolearn scores.

```
Requête → classifyComplexity() → catégorie
  → autolearn.getBestNode(catégorie)
    → si score disponible : noeud le mieux noté (speed*0.3 + quality*0.5 + reliability*0.2)
    → sinon : fallback ROUTING hardcodé
```

**ROUTING hardcodé mis à jour** (M1 prioritaire) :

| Catégorie | Chaîne |
|-----------|--------|
| code | M1, M2, M3, OL1 |
| archi | M1, M2, GEMINI, M3 |
| trading | OL1, M1, M2, M3 |
| math | M1, OL1, M2 (NOUVEAU) |
| raison | M1, M2, OL1 (NOUVEAU, JAMAIS M3) |
| system | M3, M2, OL1 |
| ia | M1, M2, GEMINI, CLAUDE |
| web | OL1, GEMINI, M2, M3 |
| default | M1, M2, M3, OL1 |

**Poids consensus** :

| Agent | Poids | Spécialité |
|-------|-------|------------|
| M1 | 1.6 | Rapide + précis (qwen3-8b dual-instance) |
| M2 | 1.4 | Review solide (deepseek-coder) |
| OL1 | 1.3 | Ultra-rapide 0.5s |
| GEMINI | 1.2 | Architecture, vision |
| CLAUDE | 1.2 | Raisonnement cloud |
| M3 | 0.8 | Général (PAS raisonnement) |

## 2. README — Sections ciblées

- M1 model : qwen3-30b → qwen3-8b, VRAM 40GB → 4.7GB, latence 2-50s → 0.6-2.5s
- Routing matrix : M1 prioritaire partout sauf web/media
- Benchmark results : refresh avec scores Feb-26
- Agents : ajouter 3 nouveaux agents plugin
- Consensus : poids mis à jour (M1: 1.6, M3: 0.8)
- Slash commands : 17 → 27

## 3. Sept schémas de workflow

1. Architecture globale du cluster (6 noeuds, VRAM, latences)
2. Routing dynamique (autolearn + fallback)
3. Consensus vote pondéré (dispatch parallèle, quorum 0.65)
4. Autolearn Engine (3 piliers: mémoire, tuning 5min, review 30min)
5. Pipeline Hook (4 hooks: thermal, VRAM/model, routing logger, metrics saver)
6. Agents plugin (4 existants + 3 nouveaux)
7. Workflow complet requête-à-réponse (simple vs reflexive)

## 4. Trois nouveaux agents plugin

| Agent | Modèle | Couleur | Rôle |
|-------|--------|---------|------|
| raisonnement-specialist | sonnet | purple | Logique, math, raisonnement. M1 prioritaire, JAMAIS M3 |
| benchmark-runner | haiku | yellow | Lance benchmarks, analyse résultats, compare avant/après |
| routing-optimizer | sonnet | orange | Tune poids autolearn, intègre scores→routing, audit |

## 5. Trois hooks essentiels

| Hook | Event | Action |
|------|-------|--------|
| vram-check | SessionStart | VRAM libre M1 via API. Warning <8GB, critical <4GB |
| routing-logger | PreToolUse | Log routing decisions dans etoile.db |
| metrics-saver | Stop | Sauvegarde métriques session dans etoile.db |

## 6. Benchmark fresh

- Relancer benchmark_cluster.py avec M1/qwen3-8b
- Relancer benchmark_real_test.py (10 niveaux)
- Sauvegarder data/benchmark_report_2026-02-26.json
- Scores alimentent autolearn routing_scores.json
