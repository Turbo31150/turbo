---
name: arena
description: Lance un tournoi de modeles sur M1 — compare un candidat au champion actuel
args: model_name
---

Lance un tournoi Model Arena sur M1. Compare le modele $MODEL_NAME au champion actuel.

**ATTENTION:** Cette commande decharge le modele actuel de M1 pendant le tournoi (~30min). M1 sera indisponible pour les autres taches.

**Si model_name est fourni:**
```bash
python3 C:/Users/franc/jarvis_model_arena.py --quick $MODEL_NAME
```

**Si model_name est "all":**
```bash
python3 C:/Users/franc/jarvis_model_arena.py --all --quick
```

**Si pas de model_name, afficher l'historique:**
```bash
python3 C:/Users/franc/jarvis_model_arena.py --history
```

Modeles disponibles: qwen3-coder-30b, devstral, gpt-oss-20b
