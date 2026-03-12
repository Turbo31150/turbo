# Reflexive Multi-IA Chain + Smart Anti-Loop — Design

**Date**: 2026-02-25
**Status**: Approved

## Problème

Le cockpit autonome souffre de deux problèmes majeurs :

1. **Boucles infinies** : OL1/qwen3:1.7b appelle `list_dir` 15x sur le même répertoire, chaque appel réussit → l'anti-loop actuel (`MAX_SAME_FAIL=3`) ne détecte que les échecs, pas les répétitions réussies. `MAX_TOOL_TURNS=15` est trop élevé.

2. **Réponses incomplètes** : Un seul petit modèle (OL1 1.7B) gère toute la chaîne recherche + raisonnement + rédaction. Résultat : réponses superficielles, outils inconnus appelés (`move_file`, `ls`), format `[TOOL:name:args]` mal respecté.

## Solution

### 1. Chaîne Réflexive (OL1 → M1 → M2)

Pipeline multi-IA où chaque noeud enrichit le travail du précédent :

| Étape | Noeud | Rôle | Budget |
|-------|-------|------|--------|
| 1 | OL1 (qwen3:1.7b) | Recherche & outils — collecte les données brutes | Max 4 tours |
| 2 | M1 (qwen3-30b) | Analyse & raisonnement — synthétise, déduit | Max 3 tours |
| 3 | M2 (deepseek-coder) | Review & validation — corrige, complète | Max 2 tours |

**Budget global** : 8 tours max (au lieu de 15).

Chaque étape reçoit le contexte accumulé des étapes précédentes. M1 reçoit les résultats d'outils d'OL1. M2 reçoit la synthèse de M1.

### 2. Auto-détection (simple vs complexe)

Le proxy décide automatiquement quand utiliser la chaîne :

**Mode simple** (1 noeud, comme aujourd'hui) :
- Questions courtes (<50 chars)
- Pas de mots-clés complexes
- Catégorie `simple` dans le routing

**Mode réflexif** (3 noeuds) :
- Messages longs ou multi-parties
- Mots-clés : "analyse", "compare", "cherche et explique", "détaillé"
- Catégories : `code`, `archi`, `data-analyst`, `raisonnement`
- Requêtes impliquant des outils (query_db, pipeline, etc.)

**Classifieur** : Fonction `classifyComplexity(message, route)` retourne `"simple"` ou `"reflexive"`.

### 3. Anti-loop v2 (détection par répétition)

Remplace le système actuel basé uniquement sur les échecs :

**Mécanisme** : Hash de `tool_name + JSON.stringify(args)`. Si le même hash apparaît 2x dans une étape → stop immédiat de cette étape.

```
callHashes = new Set()
hash = md5(toolName + JSON.stringify(args))
if (callHashes.has(hash)) → STOP étape, passer à la suivante
callHashes.add(hash)
```

**Budgets par étape** : Chaque étape a son propre compteur de tours (4/3/2). Pas de compteur global partagé — chaque étape est indépendante.

**Sécurité** : Si une étape échoue complètement (0 résultat utile), la chaîne continue quand même — l'étape suivante travaille avec ce qui est disponible.

### 4. UI — Badges de chaîne collapsibles

Dans l'interface, chaque message affiche les étapes de la chaîne :

```
[OL1 ▸ 2 tours] [M1 ▸ 1 tour] [M2 ▸ 1 tour]  ← badges cliquables
```

Cliquer sur un badge déplie le détail de cette étape (outils appelés, résultats, durée). Replié par défaut pour garder l'interface propre.

### 5. API — Format de réponse

`POST /chat` retourne :

```json
{
  "reply": "Réponse finale complète",
  "mode": "reflexive",
  "turns": 4,
  "chain": [
    {
      "node": "OL1",
      "model": "qwen3:1.7b",
      "turns": 2,
      "tools_used": [{"name": "query_db", "args": {...}, "result": {...}}],
      "duration_ms": 1200
    },
    {
      "node": "M1",
      "model": "qwen3-30b",
      "turns": 1,
      "tools_used": [],
      "duration_ms": 3400
    },
    {
      "node": "M2",
      "model": "deepseek-coder-v2",
      "turns": 1,
      "tools_used": [],
      "duration_ms": 1800
    }
  ],
  "tools_used": [...]
}
```

Mode simple retourne le format actuel avec `"mode": "simple"`.

## Fichiers à modifier

| Fichier | Modifications |
|---------|---------------|
| `canvas/direct-proxy.js` | Nouvelle `reflexiveChat()`, `classifyComplexity()`, anti-loop v2 dans `agenticChat()`, réduction `MAX_TOOL_TURNS` à 8 |
| `canvas/index.html` | Badges de chaîne collapsibles dans `addCockpitMsg()`, CSS pour les badges |

## Risques et mitigations

- **M1 offline** : Fallback — skip M1, OL1 → M2 directement
- **Latence** : 3 appels séquentiels ~7-10s total. Acceptable pour des réponses complètes.
- **Budget réduit (8 vs 15)** : Les tests montrent que 15 tours = toujours une boucle. 8 tours avec 3 IA > 15 tours avec 1 IA.
