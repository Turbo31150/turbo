---
name: cluster-benchmark
description: Benchmark rapide du cluster — ping chaque noeud avec une question simple et mesure la latence
---

Benchmark de latence du cluster JARVIS. Execute en PARALLELE un test simple sur chaque noeud.

**OL1** (qwen3:1.7b):
```bash
time curl -s --max-time 10 http://127.0.0.1:11434/api/chat -d '{"model":"qwen3:1.7b","messages":[{"role":"user","content":"Reponds juste OK"}],"stream":false,"think":false}' 2>/dev/null | python3 -c "import sys,json;print('OL1:',json.load(sys.stdin).get('message',{}).get('content','ERR')[:20])"
```

**M2** (deepseek-coder):
```bash
time curl -s --max-time 15 http://192.168.1.26:1234/v1/chat/completions -H "Content-Type: application/json" -H "Authorization: Bearer sk-lm-keRZkUya:St9kRjCg3VXTX6Getdp4" -d '{"model":"deepseek-coder-v2-lite-instruct","messages":[{"role":"user","content":"Reponds juste OK"}],"max_tokens":10,"stream":false}' 2>/dev/null | python3 -c "import sys,json;print('M2:',json.load(sys.stdin).get('choices',[{}])[0].get('message',{}).get('content','ERR')[:20])"
```

**M3** (mistral-7b):
```bash
time curl -s --max-time 15 http://192.168.1.113:1234/v1/chat/completions -H "Content-Type: application/json" -H "Authorization: Bearer sk-lm-Zxbn5FZ1:M2PkaqHzwA4TilZ9EFux" -d '{"model":"mistral-7b-instruct-v0.3","messages":[{"role":"user","content":"Reponds juste OK"}],"max_tokens":10,"stream":false}' 2>/dev/null | python3 -c "import sys,json;print('M3:',json.load(sys.stdin).get('choices',[{}])[0].get('message',{}).get('content','ERR')[:20])"
```

Presenter un tableau avec : Noeud | Latence | Statut | Comparaison benchmark (OL1: 0.5s, M2: 1.3s, M3: 2.5s).
