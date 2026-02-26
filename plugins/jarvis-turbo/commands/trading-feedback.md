---
name: trading-feedback
description: Analyse retroactive des signaux trading — compare predictions vs resultats reels
---

Analyse les signaux trading recents et compare avec les resultats reels pour evaluer la qualite des predictions.

## Etape 1 — Recuperer les derniers signaux et positions

```bash
python3 -c "
import sqlite3, json
db = sqlite3.connect('F:/BUREAU/carV1/database/trading_latest.db')
db.row_factory = sqlite3.Row
cur = db.cursor()
# Dernieres positions fermees
cur.execute('SELECT * FROM trades WHERE status=\"closed\" ORDER BY close_time DESC LIMIT 10')
trades = [dict(r) for r in cur.fetchall()]
print(json.dumps(trades, indent=2, default=str))
db.close()
" 2>/dev/null || echo "DB non accessible"
```

## Etape 2 — Analyser

Pour chaque trade ferme :
1. Signal initial (direction, score, confiance)
2. Resultat reel (PnL %, duree)
3. Ecart prediction vs realite
4. Quel(s) noeud(s) IA avai(en)t raison / tort

## Etape 3 — Synthese

Presenter un tableau avec : Pair | Direction | Score Signal | PnL Reel | Accurate?
Calculer le taux de precision global.
Si precision < 60%, recommander de re-calibrer le consensus ou d'ajuster les poids des IAs.
