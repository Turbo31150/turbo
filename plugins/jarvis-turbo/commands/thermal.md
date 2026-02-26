---
name: thermal
description: Monitoring thermique GPU detaille avec alertes et recommandations
---

Lance un check thermique complet des GPU locaux.

```bash
nvidia-smi --query-gpu=index,name,temperature.gpu,temperature.gpu.tlimit,memory.used,memory.total,utilization.gpu,power.draw,power.limit,fan.speed --format=csv,noheader 2>/dev/null
```

Analyse les resultats et presente :

1. **Tableau** avec colonnes : GPU | Temp | Limit | VRAM | Usage | Power | Fan
2. **Alertes** :
   - Vert (<70C) : Normal
   - Orange (70-75C) : Attention — surveiller
   - Rouge (75-85C) : Warning — reduire la charge, proposer unload modeles
   - Critique (>85C) : STOP — recommander arret immediat des jobs non-essentiels
3. **Recommendations** : Si un GPU est chaud, proposer les actions concretes (quel modele decharger, quel noeud basculer)
4. **Tendance** : Si possible, comparer avec le check precedent

Si nvidia-smi n'est pas disponible, indiquer que les GPU ne sont pas accessibles.
