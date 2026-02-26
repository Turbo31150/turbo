---
name: benchmark-history
description: Affiche l'historique des benchmarks — scores, tendance, champion actuel
---

Affiche l'historique des benchmarks du cluster JARVIS.

```bash
python3 C:/Users/franc/jarvis_model_arena.py --history
```

Aussi, lire le fichier brut pour analyse detaillee:
```bash
python3 -c "
import json
d = json.load(open('C:/Users/franc/jarvis_benchmark_history.json', encoding='utf-8'))
ch = d.get('champion', {})
print(f'Champion: {ch.get(\"model\",\"?\")} (score={ch.get(\"score\",0)}, depuis {ch.get(\"since\",\"?\")})')
runs = d.get('runs', [])
print(f'Total runs: {len(runs)}')
if len(runs) >= 2:
    trend = runs[-1]['score_composite'] - runs[-2]['score_composite']
    print(f'Tendance: {\"amelioration\" if trend > 0 else \"regression\"} ({trend:+.2f})')
for r in runs[-10:]:
    print(f'  [{r[\"timestamp\"]}] {r[\"type\"]:8s} score={r[\"score_composite\"]:5.2f} pass={r[\"pass_rate\"]:.0f}%')
"
```

Presenter sous forme de tableau avec tendance.
