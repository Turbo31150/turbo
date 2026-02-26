---
name: Failover Recovery
description: Use when a cluster node goes offline, a service crashes, or when you need to implement automatic failover between JARVIS cluster nodes. Provides step-by-step recovery procedures.
version: 1.0.0
---

# Failover Recovery — JARVIS Cluster

## Cascade de fallback

| Priorite | Noeud | Latence | Role |
|----------|-------|---------|------|
| 1 | M2 (deepseek) | 1.3s | Champion code |
| 2 | M3 (mistral) | 2.5s | General solide |
| 3 | OL1 (qwen3) | 0.5s | Rapide local |
| 4 | GEMINI (proxy) | variable | Architecture |
| 5 | CLAUDE (proxy) | 12-18s | Raisonnement |
| 6 | M1 (qwen3-30b) | 12s+ | Dernier recours |

## Procedure de recovery

### 1. Detection
```bash
# Ping rapide avec timeout 3s
curl -s --max-time 3 http://HOST:PORT/endpoint || echo "OFFLINE"
```

### 2. Diagnostic
- **Connection refused** → Service arrete, machine up → Redemarrer le service
- **Timeout** → Service surcharge ou network → Verifier charge GPU, ping machine
- **HTTP 500/502** → Erreur interne → Check logs, restart
- **Machine unreachable** → Probleme reseau/hardware → Ping, check cable

### 3. Actions par noeud

**OL1 offline** (127.0.0.1:11434):
1. `tasklist | findstr ollama` → processus vivant ?
2. `ollama serve` → relancer
3. Fallback: M3 pour les taches rapides

**M2 offline** (192.168.1.26:1234):
1. `ping -n 1 192.168.1.26` → machine joignable ?
2. Si oui: redemarrer LM Studio sur M2
3. Fallback: M3 pour code review, OL1 pour questions

**M3 offline** (192.168.1.113:1234):
1. `ping -n 1 192.168.1.113` → machine joignable ?
2. Fallback: M2 prend tout (surcharge acceptee)

**M1 offline** (10.5.0.2:1234):
1. Impact minimal — M1 reserve embedding
2. Aucune action urgente requise

**GEMINI offline**:
1. `node F:/BUREAU/turbo/gemini-proxy.js --ping`
2. API quota? Attendre 60s
3. Fallback: CLAUDE pour architecture

### 4. Verification post-recovery
```bash
# Tester que le noeud repond correctement
curl -s --max-time 5 http://HOST:PORT/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"MODEL","messages":[{"role":"user","content":"ping"}],"max_tokens":10,"stream":false}'
```

### 5. Post-mortem
- Logger l'incident dans `F:\BUREAU\turbo\data\incidents.json`
- Si 3+ incidents en 24h sur le meme noeud → investigation approfondie
