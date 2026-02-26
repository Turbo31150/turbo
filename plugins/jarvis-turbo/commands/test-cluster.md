---
name: test-cluster
description: Lance un test automatise du cluster JARVIS (multi-domaines, multi-noeuds)
args: cycles
---

Lance le script d'autotest JARVIS sur le cluster. Argument `$ARGUMENTS` = nombre de cycles (defaut 5).

```bash
python3 C:/Users/franc/jarvis_autotest.py $CYCLES 8 2>&1 | tail -30
```

Ou $CYCLES est le nombre de cycles (defaut 5 si pas d'argument).

Apres les tests, lis les resultats :

```bash
python3 -c "import json; d=json.load(open('C:/Users/franc/jarvis_autotest_results.json')); print(f'Pass: {d[\"pass\"]}/{d[\"total\"]} ({d[\"pass\"]*100//max(d[\"total\"],1)}%)'); [print(f'  {n}: {s[\"pass\"]*100//max(s[\"total\"],1)}%') for n,s in d['by_node'].items()]"
```

Presente les resultats en tableau et recommande des actions correctives si le taux de succes est < 80%.
