---
name: prompt-lib
description: "Bibliotheque de prompts multi-IA — recherche, suggestion, scoring, amelioration. 397+ prompts indexés, 14 categories, auto-selection par intent."
arguments:
  - name: action
    description: "Action: search|suggest|score|improve|stats|index|export (default: stats)"
    required: false
  - name: query
    description: "Terme de recherche ou description de tache"
    required: false
---

Bibliotheque de Prompts Multi-IA — 397+ prompts, 14 categories IA.

## Utilisation

Selon l'action demandee :

### Stats (defaut)
```bash
python3 F:/BUREAU/turbo/scripts/prompt_library.py --stats
```

### Recherche
```bash
python3 F:/BUREAU/turbo/scripts/prompt_library.py --search "QUERY" --json
```

### Auto-suggestion (par contexte)
```bash
python3 F:/BUREAU/turbo/scripts/prompt_library.py --suggest "DESCRIPTION_TACHE" --json
```

### Scoring qualite
```bash
python3 F:/BUREAU/turbo/scripts/prompt_library.py --score --json
```

### Ameliorations suggerees
```bash
python3 F:/BUREAU/turbo/scripts/prompt_library.py --improve --json
```

### Re-indexation
```bash
python3 F:/BUREAU/turbo/scripts/prompt_library.py --index
```

### Export JSON complet
```bash
python3 F:/BUREAU/turbo/scripts/prompt_library.py --export
```

Lire le contenu du prompt suggere avec Read tool pour le presenter a l'utilisateur.

## Boucle amelioration

1. Executer `--improve` pour trouver les prompts basse qualite
2. Lire chaque prompt identifie
3. Ameliorer: ajouter exemples, restructurer, completer metadata
4. Re-indexer avec `--index`
5. Verifier le score avec `--score`
