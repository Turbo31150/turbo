---
name: heal-cluster
description: Diagnostic et auto-reparation du cluster — detecte les noeuds en panne et bascule le routage
---

Lance un diagnostic complet du cluster et tente l'auto-reparation.

## Etape 1 — Ping tous les noeuds (PARALLELE)

```bash
curl -s --max-time 3 http://127.0.0.1:11434/api/tags 2>/dev/null | python3 -c "import sys,json,time;t=time.time();d=json.load(sys.stdin);print(f'OL1 OK ({(time.time()-t)*1000:.0f}ms):',len(d.get('models',[])),'modeles')" || echo "OL1 OFFLINE"
```

```bash
curl -s --max-time 3 http://192.168.1.26:1234/api/v1/models -H "Authorization: Bearer sk-lm-keRZkUya:St9kRjCg3VXTX6Getdp4" 2>/dev/null | python3 -c "import sys,json,time;t=time.time();d=json.load(sys.stdin);print(f'M2 OK ({(time.time()-t)*1000:.0f}ms):',len([m for m in d.get('models',[]) if m.get('loaded_instances')]),'charges')" || echo "M2 OFFLINE"
```

```bash
curl -s --max-time 3 http://192.168.1.113:1234/api/v1/models -H "Authorization: Bearer sk-lm-Zxbn5FZ1:M2PkaqHzwA4TilZ9EFux" 2>/dev/null | python3 -c "import sys,json,time;t=time.time();d=json.load(sys.stdin);print(f'M3 OK ({(time.time()-t)*1000:.0f}ms):',len([m for m in d.get('models',[]) if m.get('loaded_instances')]),'charges')" || echo "M3 OFFLINE"
```

```bash
curl -s --max-time 5 http://10.5.0.2:1234/api/v1/models -H "Authorization: Bearer sk-lm-LOkUylwu:1PMZR74wuxj7OpeyISV7" 2>/dev/null | python3 -c "import sys,json,time;t=time.time();d=json.load(sys.stdin);print(f'M1 OK ({(time.time()-t)*1000:.0f}ms):',len([m for m in d.get('models',[]) if m.get('loaded_instances')]),'charges')" || echo "M1 OFFLINE"
```

## Etape 2 — GPU thermal check

```bash
nvidia-smi --query-gpu=index,name,temperature.gpu,memory.used,memory.total,utilization.gpu --format=csv,noheader
```

## Etape 3 — Analyse et recommandations

Pour chaque noeud OFFLINE ou LENT (>3s) :
1. Verifier si la machine repond au ping (`ping -n 1 IP`)
2. Proposer un fallback automatique selon la matrice : M2→M3→OL1→GEMINI→CLAUDE→M1
3. Si GPU > 75C, recommander de decharger les modeles non-essentiels

Pour chaque noeud OK :
- Verifier que le modele par defaut est bien charge
- Verifier la latence est dans les normes (<3s)

Presenter un tableau de sante complet + plan d'action si probleme.
