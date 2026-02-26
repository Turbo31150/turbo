---
name: gpu-status
description: Affiche temperatures GPU, VRAM et charge sur toutes les machines du cluster
---

Recupere le statut GPU complet du cluster. Execute en parallele :

1. **GPUs locaux (Machine 1)** — nvidia-smi sur la machine locale :
```bash
nvidia-smi --query-gpu=index,name,temperature.gpu,memory.used,memory.total,utilization.gpu --format=csv,noheader,nounits 2>/dev/null || echo "nvidia-smi indisponible"
```

2. **Canvas autolearn status** (si le proxy tourne) :
```bash
curl -s --max-time 3 http://127.0.0.1:18800/autolearn/status 2>/dev/null | python3 -c "import sys,json;d=json.load(sys.stdin);p=d.get('pillars',{});print('Autolearn:','ACTIF' if d.get('running') else 'OFF','|',p.get('memory',{}).get('total_messages',0),'msgs |',p.get('tuning',{}).get('history_count',0),'cycles tuning')" || echo "Canvas proxy OFF"
```

3. **Ollama GPU usage** :
```bash
curl -s --max-time 3 http://127.0.0.1:11434/api/ps 2>/dev/null | python3 -c "import sys,json;d=json.load(sys.stdin);models=d.get('models',[]);print('OL1 GPU:',len(models),'modeles charges' if models else 'aucun modele')" || echo "OL1 OFF"
```

Presente en tableau. Alerte si temperature > 75C (warning) ou > 85C (critical).
Calcule le total VRAM utilisee / disponible.
