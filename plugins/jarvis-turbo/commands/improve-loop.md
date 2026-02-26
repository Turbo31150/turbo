---
name: improve-loop
description: Lance une boucle d'amelioration automatique — test → analyse → correction → re-test
args: cycles
---

Lance une boucle d'amelioration continue du cluster JARVIS.

## Etape 1 — Lancer les tests
```bash
python3 C:/Users/franc/jarvis_autotest.py $CYCLES 10 2>&1 | tail -20
```
Ou $CYCLES = nombre de cycles (defaut 10 si pas d'argument).

## Etape 2 — Analyser les resultats
```bash
python3 -c "
import json
d = json.load(open('C:/Users/franc/jarvis_autotest_results.json', encoding='utf-8'))
total = d['total']
print(f'Pass: {d[\"pass\"]}/{total} ({d[\"pass\"]*100//total}%)')
weak_nodes = [(n,s['pass']*100//max(s['total'],1)) for n,s in d['by_node'].items() if s['pass']*100//max(s['total'],1) < 80]
weak_domains = [(dom,s['pass']*100//max(s['total'],1)) for dom,s in d['by_domain'].items() if s['pass']*100//max(s['total'],1) < 70]
if weak_nodes: print('Noeuds faibles:', weak_nodes)
if weak_domains: print('Domaines faibles:', weak_domains)
print('Echecs recents:')
for f in d.get('failures',[])[-5:]:
    print(f'  [{f[\"node\"]}/{f[\"domain\"]}] {f[\"reason\"][:50]}')
"
```

## Etape 3 — Corriger automatiquement
Pour chaque faiblesse identifiee, proposer et appliquer la correction :
- Noeud lent → verifier VRAM, decharger modeles secondaires
- Domaine faible → ameliorer les prompts (chain-of-thought, hints)
- Timeout → augmenter timeout ou router vers noeud plus rapide
- Erreur encodage → fix UTF-8

## Etape 4 — Comparer avec le benchmark precedent
Le benchmark de reference est : 93% global (2026-02-25 apres optimisation M2).
Si le score baisse, identifier la regression et corriger.
