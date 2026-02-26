---
name: Continuous Improvement
description: Use when running continuous improvement loops on the JARVIS cluster — testing, analyzing failures, adjusting parameters, and re-testing to measure improvement. This is the core auto-learning workflow for Claude Code.
version: 1.0.0
---

# Boucle d'Amelioration Continue — JARVIS Cluster

## Cycle standard

```
TEST → ANALYSE → CORRECTION → RE-TEST → MESURE
```

### 1. TEST — Lancer l'autotest
```bash
python3 C:/Users/franc/jarvis_autotest.py 10 10
```

### 2. ANALYSE — Lire les resultats
```bash
python3 -c "
import json
d = json.load(open('C:/Users/franc/jarvis_autotest_results.json', encoding='utf-8'))
total = d['total']
print(f'Pass: {d[\"pass\"]}/{total} ({d[\"pass\"]*100//total}%)')
for n, s in d['by_node'].items():
    print(f'  {n}: {s[\"pass\"]*100//max(s[\"total\"],1)}%')
for dom, s in d['by_domain'].items():
    print(f'  {dom}: {s[\"pass\"]*100//max(s[\"total\"],1)}%')
weak = [(f['node'],f['domain'],f['reason']) for f in d.get('failures',[])]
print(f'Faiblesses: {len(weak)} echecs')
"
```

### 3. CORRECTION — Actions selon les patterns

| Pattern | Action |
|---------|--------|
| Noeud timeout | Verifier VRAM (modeles charges), decharger non-essentiels |
| Noeud faible domaine | Ameliorer le prompt (chain-of-thought, exemples) |
| Domaine globalement faible | Changer le routage (router vers un meilleur noeud) |
| Erreur d'encodage | Nettoyer les outputs LLM (strip think tags, unicode) |

### 4. RE-TEST — Relancer avec corrections
```bash
python3 C:/Users/franc/jarvis_autotest.py 10 10
```

### 5. MESURE — Comparer avant/apres
- Pass rate global : cible > 80%
- Latence moyenne : cible < 5s
- Aucun noeud < 60%
- Aucun domaine < 50%

## Historique des ameliorations

| Date | Action | Avant | Apres |
|------|--------|-------|-------|
| 2026-02-25 | Unload GPT-OSS 20B de M2 | M2: 43%, 15s | M2: ~75%, 2s |
| 2026-02-25 | Amelioration prompts raisonnement (chain-of-thought) | raison: 15% | raison: ~40% |
| 2026-02-25 | Amelioration prompts math (etapes) | math: 53% | math: ~70% |
| 2026-02-25 | Hints traduction (mots-cles) | trad: 75% | trad: ~85% |

## Cibles de performance

| Metrique | Actuel | Cible | Statut |
|----------|--------|-------|--------|
| Pass global | 73% | >85% | En cours |
| OL1 | 81% | >85% | Proche |
| M2 | 43%→? | >80% | Apres unload |
| M3 | 73% | >75% | OK |
| Raisonnement | 15% | >50% | Prompts ameliores |
