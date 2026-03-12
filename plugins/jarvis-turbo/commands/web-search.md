---
name: web-search
description: Recherche web via Ollama cloud (minimax-m2.5) avec synthese rapide
args: query
---

Lance une recherche web via OL1 cloud (minimax-m2.5) pour la question `$ARGUMENTS`.

```bash
curl -s --max-time 30 http://127.0.0.1:11434/api/chat -d '{"model":"minimax-m2.5:cloud","messages":[{"role":"user","content":"$ARGUMENTS"}],"stream":false,"think":false}' 2>/dev/null | python3 -c "import sys,json,re;d=json.load(sys.stdin);t=d.get('message',{}).get('content','');print(re.sub(r'<think>.*?</think>','',t,flags=re.DOTALL).strip())"
```

Presente la reponse de maniere structuree. Si la reponse est vide ou erreur, indique que OL1-cloud est peut-etre offline.
