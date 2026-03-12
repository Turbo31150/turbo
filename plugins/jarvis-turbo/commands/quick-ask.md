---
name: quick-ask
description: Pose une question rapide a OL1 local (qwen3:1.7b) — reponse en <1s
args: question
---

Pose la question `$ARGUMENTS` a OL1 local (qwen3:1.7b) pour une reponse ultra-rapide.

```bash
curl -s --max-time 10 http://127.0.0.1:11434/api/chat -d '{"model":"qwen3:1.7b","messages":[{"role":"user","content":"Reponds en francais, concis. $ARGUMENTS"}],"stream":false,"think":false}' 2>/dev/null | python3 -c "import sys,json,re;d=json.load(sys.stdin);t=d.get('message',{}).get('content','');print(re.sub(r'<think>.*?</think>','',t,flags=re.DOTALL).strip())"
```

Affiche la reponse avec attribution `[OL1/qwen3:1.7b]`. Si la reponse est insuffisante, propose d'utiliser `/consensus` pour une reponse multi-IA.
