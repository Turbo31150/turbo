---
name: canvas-restart
description: Redemarrer le proxy canvas JARVIS (port 18800) avec autolearn
---

Redemarrer le proxy canvas direct-proxy.js sur le port 18800.

Etapes :
1. Trouver et tuer le processus existant sur le port 18800
2. Attendre 1 seconde
3. Relancer le proxy en background
4. Verifier que le serveur repond

```bash
# Trouver PID sur port 18800
netstat -ano | grep 18800 | grep LISTEN
```

Si un PID est trouve, le tuer avec `taskkill //PID <PID> //F`.

Puis relancer :
```bash
cd "F:/BUREAU/turbo/canvas" && node direct-proxy.js &
```

Attends 2 secondes puis verifie :
```bash
sleep 2 && curl -s http://127.0.0.1:18800/health | python3 -c "import sys,json;d=json.load(sys.stdin);print('Canvas OK' if d.get('ok') else 'Canvas FAIL','- Noeuds:',sum(1 for n in d.get('nodes',[]) if n.get('ok')),'/',len(d.get('nodes',[])))"
```

Et verifie l'autolearn :
```bash
curl -s http://127.0.0.1:18800/autolearn/status | python3 -c "import sys,json;d=json.load(sys.stdin);print('Autolearn:','ACTIF' if d.get('running') else 'INACTIF')"
```
