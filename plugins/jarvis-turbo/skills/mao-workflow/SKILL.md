---
name: MAO Workflow
description: Use when performing multi-agent operations, consensus queries, or distributed code reviews across the JARVIS cluster. Provides the MAO (Multi-Agent Orchestrator) protocol for parallel agent dispatch and weighted synthesis.
version: 1.0.0
---

# Protocole MAO — Multi-Agent Orchestrator

## Quand utiliser

- Decisions architecturales ou techniques complexes
- Code review necesitant plusieurs perspectives
- Consensus sur une question technique
- Debug multi-composants

## Flux

1. **Decomposer** la tache en sous-questions independantes
2. **Dispatcher** en parallele vers les agents adaptes (voir matrice)
3. **Collecter** les reponses JSON, extraire le contenu
4. **Synthetiser** en comparant, ponderer par poids
5. **Presenter** avec attribution claire

## Matrice de routage (M1 PRIORITAIRE, benchmark 2026-02-26)

| Tache | Principal | Secondaire | Poids |
|-------|-----------|------------|-------|
| Code nouveau | **M1/qwen3-8b** | M2 review | **M1:1.8**, M2:1.4 |
| Bug fix | **M1** | M2 patch | **M1:1.8**, M2:1.4 |
| Architecture | GEMINI | **M1** validation | GEM:1.2, **M1:1.8** |
| Raisonnement | **M1** (100%) | M2 analyse | **M1:1.8** — JAMAIS M3 |
| Math/Calcul | **M1** | OL1 rapide | **M1:1.8**, OL1:1.3 |
| Question simple | OL1/qwen3 | M3 fallback | OL1:1.3, M3:1.0 |
| Consensus | **M1**+M2+OL1+M3 | +GEMINI+CLAUDE | Vote pondere 5 niveaux |

## Appels paralleles

Lancer TOUJOURS les appels independants en parallele (plusieurs Bash tool calls).

**M1** (PRIORITAIRE, 0.6-2.5s):
```bash
curl -s --max-time 30 http://10.5.0.2:1234/api/v1/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-lm-LOkUylwu:1PMZR74wuxj7OpeyISV7" \
  -d '{"model":"qwen/qwen3-8b","input":"/nothink\nPROMPT","temperature":0.2,"max_output_tokens":1024,"stream":false,"store":false}'
```
Extraction M1: dernier element `type=message` dans `.output[]` (skip reasoning block)

**M2** (champion code, 3.9s):
```bash
curl -s --max-time 60 http://192.168.1.26:1234/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-lm-keRZkUya:St9kRjCg3VXTX6Getdp4" \
  -d '{"model":"deepseek-coder-v2-lite-instruct","messages":[{"role":"user","content":"PROMPT"}],"temperature":0.3,"max_tokens":4096,"stream":false}'
```

**OL1** (rapide, 0.5s):
```bash
curl -s --max-time 30 http://127.0.0.1:11434/api/chat \
  -d '{"model":"qwen3:1.7b","messages":[{"role":"user","content":"PROMPT"}],"stream":false,"think":false}'
```

**M3** (solide, 2.5s):
```bash
curl -s --max-time 60 http://192.168.1.113:1234/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-lm-Zxbn5FZ1:M2PkaqHzwA4TilZ9EFux" \
  -d '{"model":"mistral-7b-instruct-v0.3","messages":[{"role":"user","content":"PROMPT"}],"temperature":0.3,"max_tokens":4096,"stream":false}'
```

## Extraction reponses

- **M1 (Responses API)**: dernier `output[].type=="message"` → `.content` (skip reasoning blocks)
- LM Studio (Chat API): `.choices[0].message.content`
- Ollama: `.message.content`
- Gemini/Claude: stdout du proxy

## Regles imperatives

- JAMAIS simuler une reponse — TOUJOURS utiliser curl/proxy reel
- JAMAIS `localhost` — TOUJOURS `127.0.0.1`
- `think:false` OBLIGATOIRE pour Ollama cloud
- Timeout: 60s M2/M3, 30s OL1, 120s GEMINI/CLAUDE
- Fallback: M1→M2→OL1→M3→GEMINI→CLAUDE
- M1 /nothink OBLIGATOIRE (prefix input)
- Ponderation 5 niveaux: noeud × domaine × adaptatif × thermique × autolearn
