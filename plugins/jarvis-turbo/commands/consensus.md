---
name: consensus
description: Pose une question a tous les noeuds du cluster et synthetise par vote pondere
args: question
---

Lance un consensus multi-IA sur la question `$ARGUMENTS`. Interroge M2 + OL1 + M3 en parallele.

Execute ces 3 appels SIMULTANEMENT :

**M2/deepseek (champion code, poids 1.4):**
```bash
curl -s --max-time 60 http://192.168.1.26:1234/v1/chat/completions -H "Content-Type: application/json" -H "Authorization: Bearer sk-lm-keRZkUya:St9kRjCg3VXTX6Getdp4" -d '{"model":"deepseek-coder-v2-lite-instruct","messages":[{"role":"user","content":"$ARGUMENTS"}],"temperature":0.3,"max_tokens":2048,"stream":false}' 2>/dev/null | python3 -c "import sys,json,re;d=json.load(sys.stdin);t=d.get('choices',[{}])[0].get('message',{}).get('content','');print(re.sub(r'<think>.*?</think>','',t,flags=re.DOTALL).strip()[:500])"
```

**OL1/qwen3 (rapide, poids 1.3):**
```bash
curl -s --max-time 30 http://127.0.0.1:11434/api/chat -d '{"model":"qwen3:1.7b","messages":[{"role":"user","content":"$ARGUMENTS"}],"stream":false,"think":false}' 2>/dev/null | python3 -c "import sys,json,re;d=json.load(sys.stdin);t=d.get('message',{}).get('content','');print(re.sub(r'<think>.*?</think>','',t,flags=re.DOTALL).strip()[:500])"
```

**M3/mistral (solide, poids 1.0):**
```bash
curl -s --max-time 60 http://192.168.1.113:1234/v1/chat/completions -H "Content-Type: application/json" -H "Authorization: Bearer sk-lm-Zxbn5FZ1:M2PkaqHzwA4TilZ9EFux" -d '{"model":"mistral-7b-instruct-v0.3","messages":[{"role":"user","content":"$ARGUMENTS"}],"temperature":0.3,"max_tokens":2048,"stream":false}' 2>/dev/null | python3 -c "import sys,json,re;d=json.load(sys.stdin);t=d.get('choices',[{}])[0].get('message',{}).get('content','');print(re.sub(r'<think>.*?</think>','',t,flags=re.DOTALL).strip()[:500])"
```

Apres avoir recu les 3 reponses, SYNTHETISE en :
1. Identifiant les points d'accord (consensus)
2. Notant les divergences
3. Ponderant par poids : M2 (1.4) > OL1 (1.3) > M3 (1.0)
4. Attributant chaque point : `[M2/deepseek]`, `[OL1/qwen3]`, `[M3/mistral]`

Conclusion finale avec niveau de confiance (fort/moyen/faible selon convergence).
