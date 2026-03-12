---
name: heal-status
description: Affiche l'etat du cluster healer — statut de chaque noeud, dernier check, actions recentes
---

Verifie l'etat du cluster healer JARVIS.

**Quick check (pas de daemon requis):**
```bash
python3 C:/Users/franc/jarvis_cluster_healer.py --status
```

**Log recents:**
```bash
tail -20 C:/Users/franc/jarvis_healer.log
```

Presenter un tableau avec : Noeud | Statut | Dernier Check | Actions recentes.
