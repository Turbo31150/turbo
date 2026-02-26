---
name: cluster-check
description: Health check rapide de tous les noeuds du cluster JARVIS (M1/M2/M3/OL1/GEMINI/CLAUDE)
---

Lance un health check complet du cluster JARVIS en parallele. Pour chaque noeud :
- Ping HTTP avec timeout 3s
- Affiche latence, modeles charges, statut GPU
- Resume en tableau avec OK/OFFLINE

Execute ces commandes en PARALLELE via Bash :

```bash
curl -s --max-time 3 http://127.0.0.1:11434/api/tags 2>/dev/null | python3 -c "import sys,json;d=json.load(sys.stdin);print('OL1 OK:',len(d.get('models',[])),'modeles')" || echo "OL1 OFFLINE"
```

```bash
curl -s --max-time 3 http://192.168.1.26:1234/api/v1/models -H "Authorization: Bearer LMSTUDIO_KEY_M2_REDACTED" 2>/dev/null | python3 -c "import sys,json;d=json.load(sys.stdin);print('M2 OK:',len([m for m in d.get('models',[]) if m.get('loaded_instances')]),'modeles charges')" || echo "M2 OFFLINE"
```

```bash
curl -s --max-time 3 http://192.168.1.113:1234/api/v1/models -H "Authorization: Bearer LMSTUDIO_KEY_M3_REDACTED" 2>/dev/null | python3 -c "import sys,json;d=json.load(sys.stdin);print('M3 OK:',len([m for m in d.get('models',[]) if m.get('loaded_instances')]),'modeles charges')" || echo "M3 OFFLINE"
```

```bash
curl -s --max-time 3 http://10.5.0.2:1234/api/v1/models -H "Authorization: Bearer LMSTUDIO_KEY_M1_REDACTED" 2>/dev/null | python3 -c "import sys,json;d=json.load(sys.stdin);print('M1 OK:',len([m for m in d.get('models',[]) if m.get('loaded_instances')]),'modeles charges')" || echo "M1 OFFLINE"
```

```bash
node F:/BUREAU/turbo/gemini-proxy.js --ping 2>/dev/null && echo "GEMINI OK" || echo "GEMINI OFFLINE"
```

Presente les resultats en tableau markdown avec colonnes: Noeud | Statut | Latence | Details.
Si un noeud est OFFLINE, indique-le en rouge. Resume le nombre de noeuds en ligne sur le total.
