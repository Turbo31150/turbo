---
name: trading-scan
description: Lance un scan trading GPU pipeline avec consensus IA (modes quick/fast/full)
args: mode
---

Lance le pipeline GPU trading v2.3 JARVIS. Argument `$ARGUMENTS` determine le mode :
- `quick` ou vide → mode rapide 2 IA (~19s)
- `fast` → mode sans Gemini 5 IA (~30s)
- `full` → mode complet 6 IA (~90s)

Etapes :
1. Verifie que le cluster est en ligne (au moins OL1 + M2)
2. Lance le pipeline avec le mode choisi
3. Affiche les resultats (top coins, scores, signaux)

```bash
cd "F:/BUREAU/turbo/scripts/trading_v2" && python3 gpu_pipeline.py --coins 100 --top 10 --json $ARGUMENTS_MODE_FLAG 2>&1 | tail -50
```

Ou $ARGUMENTS_MODE_FLAG est :
- mode quick/vide → `--quick`
- mode fast → `--no-gemini`
- mode full → (rien)

Presente les resultats sous forme de tableau avec : Coin | Score | Signal | Confiance | TP/SL.
Ajoute un avertissement si DRY_RUN=true.
