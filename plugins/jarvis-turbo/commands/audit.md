---
name: audit
description: Audit systeme complet JARVIS — cluster, GPU, securite, readiness scores
args: mode
---

Lance l'audit systeme distribue JARVIS. Argument `$ARGUMENTS` :
- vide → audit complet (~30s)
- `quick` → audit rapide sans tests reseau (~10s)
- `save` → audit complet + sauvegarde JSON

```bash
cd "F:/BUREAU/turbo" && uv run python scripts/system_audit.py $ARGUMENTS_FLAGS 2>&1
```

Ou $ARGUMENTS_FLAGS :
- mode vide → (rien)
- mode quick → `--quick`
- mode save → `--save`

L'audit produit :
- 10 sections de diagnostic
- 6 scores readiness (0-100) : Stability, Resilience, Security, Scalability, Multimodal, Observability
- Grade global A-F
- Liste des SPOFs et issues securite

Presente les resultats avec le grade en gros, puis les scores en barres de progression.
