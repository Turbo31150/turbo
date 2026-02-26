---
name: n8n-trigger
description: Declenche un workflow n8n par son ID ou nom
args: workflow
---

Declenche un workflow n8n. Argument `$ARGUMENTS` = ID ou nom du workflow.

## Workflows disponibles

| Nom | ID |
|-----|-----|
| trading_ultimate | 4ovJaOxtAzITyJEd |
| multi_ia_consensus | lJEz0hbG66DceXYA |
| ancrage_manager | jGlSm9FWTYb7OKZF |
| scanner_pro | PruXHoV67xhxwRZC |
| telegram_signals | HtIDKlxK6UWHJux8 |
| claire_ultimate | n7lQHhg1oWn9bs8c |
| cluster_monitor | 4vb15uEx3j4A9YPT |
| trading_v2_multi_ia | 6ssOxO4AOlWiCKNY |

## Execution

```bash
curl -s --max-time 30 -X POST "http://127.0.0.1:5678/api/v1/workflows/$WORKFLOW_ID/activate" -H "Content-Type: application/json" 2>/dev/null || echo "n8n non accessible (port 5678)"
```

Si l'argument est un nom (ex: "trading_ultimate"), resoudre l'ID dans la table ci-dessus.
Affiche le statut de l'execution et les eventuels resultats.
