# JARVIS Autolearn Engine — Design Document
**Date**: 2026-02-25
**Statut**: Approuvé
**Localisation**: `F:\BUREAU\turbo\canvas\`

## Objectif
Rendre JARVIS Canvas autonome en apprentissage continu — mémoire conversationnelle, auto-tuning du routage, et auto-review des prompts via le cluster distribué (M1/M2/M3/OL1).

## Architecture — 3 Piliers parallèles dans direct-proxy.js

```
direct-proxy.js (port 18800)
├── Chat Handler (/chat)            ← existant, enrichi avec mémoire
├── Health/Cluster Handlers         ← existants
│
├── PILIER 1 — Memory Engine
│   ├── Stocke chaque échange (50 derniers)
│   ├── Profil utilisateur auto-détecté
│   ├── Résumé profond via M1 (toutes les 10 conversations)
│   └── Injection contexte dans prompts système
│
├── PILIER 2 — Auto-Tuning Loop (cycle 5 min)
│   ├── Score par réponse: rapidité(0.3) + qualité(0.5) + fiabilité(0.2)
│   ├── Qualité notée par OL1 (1-10)
│   ├── Analyse tendances via M1 (background)
│   └── Réordonne ROUTING dynamiquement
│
└── PILIER 3 — Auto-Review Cycle (cycle 30 min)
    ├── M2 analyse réponses faibles → propose améliorations
    ├── M3 valide les propositions
    ├── M1 méta-review (vote 3 machines)
    └── Hot-swap prompts si consensus > 0.7
```

## Distribution cluster

| Pilier | Tâche | Machine | Timeout |
|--------|-------|---------|---------|
| Mémoire | Résumé/extraction profil | M1 | 120s + fallback OL1 |
| Tuning | Scoring qualité rapide | OL1 | 10s |
| Tuning | Analyse tendances | M1 | 120s |
| Review | Analyse faiblesses | M2 | 60s |
| Review | Validation propositions | M3 | 60s |
| Review | Méta-review architecture | M1 | 120s + fallback skip |

## Fichiers de données

| Fichier | Contenu | Max |
|---------|---------|-----|
| `data/memory.json` | 50 échanges + profil utilisateur | 500 KB |
| `data/routing_scores.json` | Scores noeud×catégorie + historique | 50 KB |
| `data/autolearn_history.json` | Log cycles review + patchs | 200 KB (rotation 200 entrées) |

## Endpoints API

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/autolearn/status` | GET | État 3 piliers |
| `/autolearn/memory` | GET | Profil + stats mémoire |
| `/autolearn/scores` | GET | Scores noeud×catégorie |
| `/autolearn/history` | GET | Historique améliorations |
| `/autolearn/trigger` | POST | Force cycle review immédiat |

## Sécurités

- Rollback auto si 3 cycles dégradent les scores
- Max 1 appel qualité OL1 par réponse
- Pas de modification fichiers source — tout runtime + JSON
- Rotation logs: max 200 entrées dans history
- M1 timeout → cycle continue sans lui (Promise.race)

## Score qualité

```
score_final = (rapidité × 0.3) + (qualité × 0.5) + (fiabilité × 0.2)
rapidité: <2s=10, 2-5s=7, 5-10s=4, >10s=2
qualité: OL1 note 1-10
fiabilité: succès sur 20 dernières requêtes (0-10)
```

## Consensus auto-review

Seuil application: score_validation > 0.7 (M3) ET (M1 approuve OU M1 timeout)
Rollback: si score moyen catégorie baisse de >15% sur 3 cycles → revert prompt précédent
