---
name: canvas-status
description: Verifie le statut du canvas JARVIS (proxy + autolearn engine)
---

Verifie le statut complet du canvas JARVIS standalone.

Execute ces commandes en parallele :

**Proxy principal:**
```bash
curl -s --max-time 3 http://127.0.0.1:18800/health 2>/dev/null || echo "CANVAS PROXY OFFLINE"
```

**Autolearn engine:**
```bash
curl -s --max-time 3 http://127.0.0.1:18800/autolearn/status 2>/dev/null | python3 -c "import sys,json;d=json.load(sys.stdin);print('Autolearn:','RUNNING' if d.get('running') else 'STOPPED');print('Memory:',d.get('memory',{}).get('total_messages',0),'messages');print('Tuning: dernier cycle',d.get('tuning',{}).get('lastCycle','jamais'));print('Review: dernier cycle',d.get('review',{}).get('lastCycle','jamais'))" 2>/dev/null || echo "AUTOLEARN OFFLINE"
```

**Port 18800:**
```bash
netstat -ano | findstr :18800 | head -1
```

Presente un resume avec le statut de chaque composant.
