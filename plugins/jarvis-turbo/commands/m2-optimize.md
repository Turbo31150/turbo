---
name: m2-optimize
description: Optimise M2 en dechargent les modeles non-essentiels pour liberer la VRAM
---

Verifie les modeles charges sur M2 et decharge ceux qui ne sont pas le modele principal (deepseek-coder-v2-lite).

## Etape 1 — Lister les modeles charges

```bash
curl -s --max-time 5 http://192.168.1.26:1234/api/v1/models -H "Authorization: Bearer sk-lm-keRZkUya:St9kRjCg3VXTX6Getdp4" 2>/dev/null | python3 -c "
import sys,json
d = json.loads(sys.stdin.read())
for m in d.get('models',[]):
    instances = m.get('loaded_instances',[])
    if instances:
        name = m.get('key', m.get('display_name','?'))
        print(f'LOADED: {name}')
"
```

## Etape 2 — Decharger les modeles non-essentiels

Pour chaque modele charge qui N'EST PAS `deepseek-coder-v2-lite-instruct`, decharger :

```bash
curl -s -X POST http://192.168.1.26:1234/v1/models/unload -H "Content-Type: application/json" -H "Authorization: Bearer sk-lm-keRZkUya:St9kRjCg3VXTX6Getdp4" -d '{"model":"MODEL_ID"}' 2>/dev/null
```

## Etape 3 — Verifier

```bash
curl -s --max-time 5 http://192.168.1.26:1234/v1/chat/completions -H "Content-Type: application/json" -H "Authorization: Bearer sk-lm-keRZkUya:St9kRjCg3VXTX6Getdp4" -d '{"model":"deepseek-coder-v2-lite-instruct","messages":[{"role":"user","content":"test"}],"max_tokens":5,"stream":false}' 2>/dev/null && echo "M2 OK"
```

Presenter le resultat avec la VRAM liberee et la latence avant/apres.
