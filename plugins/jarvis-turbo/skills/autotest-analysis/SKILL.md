---
name: Autotest Analysis
description: Use when analyzing results from JARVIS cluster autotests — interpreting pass/fail patterns, identifying weak nodes/domains, and recommending routing adjustments.
version: 1.0.0
---

# Autotest Analysis — JARVIS Cluster

## Lire les resultats

```bash
python3 -c "
import json
with open('C:/Users/franc/jarvis_autotest_results.json') as f:
    d = json.load(f)
print(f'Cycles: {d[\"cycles\"]} | Total: {d[\"total\"]} | Pass: {d[\"pass\"]} ({d[\"pass\"]*100//max(d[\"total\"],1)}%) | Fail: {d[\"fail\"]} | Errors: {d[\"errors\"]}')
print()
print('Par noeud:')
for n, s in d['by_node'].items():
    rate = s['pass']*100//max(s['total'],1)
    print(f'  {n}: {rate}% pass ({s[\"total\"]} tests, avg {s.get(\"avg_latency\",\"?\")}ms)')
print()
print('Par domaine:')
for dom, s in d['by_domain'].items():
    rate = s['pass']*100//max(s['total'],1)
    print(f'  {dom}: {rate}% pass ({s[\"total\"]} tests)')
print()
print('Derniers echecs:')
for f in d.get('failures',[])[-10:]:
    print(f'  [{f[\"node\"]}/{f[\"domain\"]}] {f[\"question\"][:50]}... reason: {f[\"reason\"][:40]}')
"
```

## Patterns d'echec connus

| Pattern | Cause probable | Action |
|---------|---------------|--------|
| M2 timeout frequent | Modele surcharge ou GPU thermal | Augmenter timeout a 60s ou decharger modeles secondaires |
| M3 echoue math | mistral-7b pas optimise pour calcul | Router math vers OL1 ou M2 |
| OL1 echoue traduction | qwen3:1.7b trop petit pour traduction | Router traduction vers M2 ou M3 |
| M1 tous timeout | Normal — noeud lent | Ne pas utiliser sauf embedding |

## Actions correctives

### M2 instable
1. Verifier GPU thermal: `curl -s http://192.168.1.26:1234/api/v1/models` — latence?
2. Decharger modeles secondaires si VRAM plein
3. Augmenter timeout de 30s a 60s dans le script de test
4. Si persistent: redemarrer LM Studio sur M2

### M3 faible en math
- Ajouter instruction systeme: "Calcule etape par etape avant de donner la reponse finale"
- Considerer router les taches math vers OL1 (plus rapide et meilleur en calcul)

### OL1 faible en traduction
- Augmenter max_tokens pour les taches de traduction
- Ajouter instruction: "Traduis de maniere precise, mot a mot si necessaire"
- Alternative: utiliser OL1-cloud (minimax) pour traduction (meilleur modele)

## Relancer les tests
```bash
python3 C:/Users/franc/jarvis_autotest.py 10 15
```
