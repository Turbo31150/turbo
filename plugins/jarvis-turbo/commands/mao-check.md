---
name: mao-check
description: Health check MAO complet — 6 noeuds IA + Claude proxy + Canvas autolearn
---

Health check MAO (Multi-Agent Orchestrator) exhaustif. Lance TOUT en parallele :

**Noeuds LM Studio (M1/M2/M3):**
```bash
curl -s --max-time 3 http://192.168.1.26:1234/api/v1/models -H "Authorization: Bearer sk-lm-keRZkUya:St9kRjCg3VXTX6Getdp4" 2>/dev/null | python3 -c "import sys,json;d=json.load(sys.stdin);loaded=[m for m in d.get('models',[]) if m.get('loaded_instances')];print('M2 OK:',len(loaded),'charge(s) -',', '.join(m['id'] for m in loaded)[:60])" || echo "M2 OFFLINE"
```
```bash
curl -s --max-time 3 http://192.168.1.113:1234/api/v1/models -H "Authorization: Bearer sk-lm-Zxbn5FZ1:M2PkaqHzwA4TilZ9EFux" 2>/dev/null | python3 -c "import sys,json;d=json.load(sys.stdin);loaded=[m for m in d.get('models',[]) if m.get('loaded_instances')];print('M3 OK:',len(loaded),'charge(s) -',', '.join(m['id'] for m in loaded)[:60])" || echo "M3 OFFLINE"
```
```bash
curl -s --max-time 5 http://10.5.0.2:1234/api/v1/models -H "Authorization: Bearer sk-lm-LOkUylwu:1PMZR74wuxj7OpeyISV7" 2>/dev/null | python3 -c "import sys,json;d=json.load(sys.stdin);loaded=[m for m in d.get('models',[]) if m.get('loaded_instances')];print('M1 OK:',len(loaded),'charge(s) -',', '.join(m['id'] for m in loaded)[:60])" || echo "M1 OFFLINE (timeout habituel)"
```

**Ollama (OL1):**
```bash
curl -s --max-time 3 http://127.0.0.1:11434/api/ps 2>/dev/null | python3 -c "import sys,json;d=json.load(sys.stdin);models=d.get('models',[]);print('OL1 OK:',len(models),'actif(s) -',', '.join(m.get('name','?') for m in models)[:60])" || echo "OL1 OFFLINE"
```

**Gemini proxy:**
```bash
node F:/BUREAU/turbo/gemini-proxy.js --ping 2>/dev/null && echo "GEMINI OK" || echo "GEMINI OFFLINE"
```

**Claude proxy:**
```bash
node F:/BUREAU/turbo/claude-proxy.js --ping 2>/dev/null && echo "CLAUDE OK" || echo "CLAUDE OFFLINE"
```

**Canvas + Autolearn:**
```bash
curl -s --max-time 3 http://127.0.0.1:18800/autolearn/status 2>/dev/null | python3 -c "import sys,json;d=json.load(sys.stdin);p=d.get('pillars',{});m=p.get('memory',{});print('CANVAS OK | Autolearn:','ACTIF' if d.get('running') else 'OFF','|',m.get('total_messages',0),'msgs |',p.get('tuning',{}).get('history_count',0),'tuning cycles')" || echo "CANVAS OFFLINE"
```

**GPU locaux:**
```bash
nvidia-smi --query-gpu=index,name,temperature.gpu,memory.used,memory.total --format=csv,noheader 2>/dev/null || echo "nvidia-smi indisponible"
```

Presente en tableau markdown clair. Compte total: X/7 en ligne (M1, M2, M3, OL1, GEMINI, CLAUDE, CANVAS).
