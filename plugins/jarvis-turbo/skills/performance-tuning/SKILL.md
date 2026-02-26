---
name: Performance Tuning
description: Use when optimizing JARVIS cluster performance — reducing latency, improving throughput, tuning model parameters, or managing GPU resources for maximum efficiency.
version: 1.0.0
---

# Performance Tuning — JARVIS Cluster

## Metriques cles

| Metrique | Cible | Actuel | Action |
|----------|-------|--------|--------|
| OL1 latence | <500ms | ~500ms | OK |
| M2 latence | <2s | ~1.3s | OK |
| M3 latence | <3s | ~2.5s | OK |
| GPU temp max | <75C | variable | Monitor |
| VRAM usage | <80% | variable | Check |

## Techniques d'optimisation

### 1. Routage intelligent
- Questions simples → OL1 (0.5s) au lieu de M2 (1.3s) = 2.6x plus rapide
- Code review → M2+M3 en parallele, pas sequentiel
- Architecture → GEMINI seul suffit, pas besoin de consensus

### 2. Parallelisation
- Lancer les appels cluster en PARALLELE (pas sequentiels)
- Utiliser `asyncio.gather` ou multiple Bash tool calls simultanes
- Ne pas attendre M1 pour les taches rapides (timeout 5s max)

### 3. Context length
- OL1 (qwen3:1.7b) → garder prompts courts (<2000 tokens)
- M2 (deepseek) → context 16K OK pour code review
- M3 (mistral) → context_length=8192 max, ne pas depasser
- M1 (qwen3-30b) → context 32K mais LENT, eviter les gros prompts

### 4. Temperature par usage
- Code generation → 0.2-0.3 (precision)
- Creative/brainstorm → 0.7-0.8 (diversite)
- Consensus vote → 0.3 (coherence)
- Trading signals → 0.1-0.2 (determinisme)

### 5. GPU VRAM management
- Surveiller avec `nvidia-smi` regulierement
- Decharger les modeles inutilises (`/model-swap unload MODEL`)
- Prioriser les modeles actifs sur les GPU les plus rapides
- RTX 3080 (10GB) → modeles principaux OL1
- RTX 2060 (12GB) → overflow et batch
- GTX 1660S (6GB x3) → petits modeles, embedding

### 6. Batch processing
- Trading pipeline: `--coins 50` au lieu de 100 si urgence
- Mode `--quick` (2 IA) pour validation rapide
- Mode `--no-gemini` pour eviter le bottleneck Gemini (60-90s)

## Benchmark
```bash
# Benchmark rapide du cluster
curl -s --max-time 3 http://127.0.0.1:11434/api/chat -d '{"model":"qwen3:1.7b","messages":[{"role":"user","content":"ping"}],"stream":false,"think":false}' | python3 -c "import sys,json,time;t=time.time();d=json.load(sys.stdin);print(f'OL1: {(time.time()-t)*1000:.0f}ms')"
```
