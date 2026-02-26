---
name: Cluster Management
description: Use when managing the JARVIS cluster — loading/unloading models, checking GPU thermal status, recovering nodes, or performing maintenance operations on LM Studio and Ollama instances.
version: 1.0.0
---

# Gestion du Cluster JARVIS

## Noeuds

| Noeud | URL | GPU | VRAM | Modele par defaut |
|-------|-----|-----|------|-------------------|
| OL1 | http://127.0.0.1:11434 | 5 GPU (RTX3080+2060+3x1660S) | 40GB | qwen3:1.7b |
| M2 | http://192.168.1.26:1234 | 3 GPU | 24GB | deepseek-coder-v2-lite |
| M3 | http://192.168.1.113:1234 | 1 GPU | 8GB | mistral-7b |
| M1 | http://10.5.0.2:1234 | 6 GPU | 46GB | qwen3-30b (LENT) |

## Health check rapide

```bash
# OL1
curl -s --max-time 3 http://127.0.0.1:11434/api/tags | python3 -c "import sys,json;print('OL1:',len(json.load(sys.stdin).get('models',[])),'modeles')"

# M2
curl -s --max-time 3 http://192.168.1.26:1234/api/v1/models -H "Authorization: Bearer sk-lm-keRZkUya:St9kRjCg3VXTX6Getdp4" | python3 -c "import sys,json;d=json.load(sys.stdin);print('M2:',len([m for m in d.get('models',[]) if m.get('loaded_instances')]),'charges')"

# GPU local
nvidia-smi --query-gpu=index,name,temperature.gpu,memory.used,memory.total --format=csv,noheader
```

## Gestion modeles LM Studio

**Charger un modele:**
```bash
curl -s http://HOST:1234/v1/models/load -H "Content-Type: application/json" -H "Authorization: Bearer KEY" -d '{"model":"MODEL_ID","gpu_offload":"max","context_length":32768}'
```

**Decharger un modele:**
```bash
curl -s http://HOST:1234/v1/models/unload -H "Content-Type: application/json" -H "Authorization: Bearer KEY" -d '{"model":"MODEL_ID"}'
```

**CLI local (M1 seulement):**
```bash
"C:\Users\franc\.lmstudio\bin\lms.exe" load MODEL_ID --gpu max --context-length 32768
"C:\Users\franc\.lmstudio\bin\lms.exe" unload MODEL_ID
"C:\Users\franc\.lmstudio\bin\lms.exe" ps
```

## Seuils thermiques GPU

| Niveau | Temp | Action |
|--------|------|--------|
| Normal | <70C | Aucune |
| Warning | 75C+ | Surveiller, reduire batch |
| Critical | 85C+ | Re-routage cascade, reduire charge |
| Emergency | 90C+ | Arreter les jobs non-essentiels |

## Modeles disponibles par noeud

**M1**: qwen3-30b-a3b (defaut), qwen3-coder-30b, devstral, gpt-oss-20b (on-demand)
**M2**: deepseek-coder-v2-lite (defaut)
**M3**: mistral-7b-instruct (defaut), context max 8192
**OL1 local**: qwen3:1.7b
**OL1 cloud**: minimax-m2.5, glm-5, kimi-k2.5

## Procedures de recovery

**Noeud offline:**
1. Ping HTTP avec timeout 3s
2. Si offline, verifier si la machine repond (`ping -n 1 IP`)
3. Si machine up mais service down → redemarrage LM Studio
4. Si machine down → fallback sur noeud suivant

**GPU thermal critical:**
1. Reduire la charge (unload modeles non-essentiels)
2. Re-router vers un noeud plus frais
3. Attendre retour <70C avant de recharger
