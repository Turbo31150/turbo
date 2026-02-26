---
name: Security Audit
description: Use when performing security audits of the JARVIS cluster — checking for exposed credentials, insecure configurations, open ports, and API key management.
version: 1.0.0
---

# Security Audit — JARVIS Cluster

## Checklist

### 1. Credentials
- API keys dans settings.json → doivent etre en env vars, pas en clair
- Bearer tokens LM Studio (M1/M2/M3) → LAN-only, risque faible mais documenter
- n8n MCP token → CRITIQUE si expose publiquement
- Telegram chat_id → risque si repo public
- MEXC API keys → JAMAIS dans un fichier non-gitignored

### 2. Network
- Tous les services ecoutent sur IPs specifiques (pas 0.0.0.0 sauf necessaire)
- Firewall Windows actif pour ports LM Studio (1234)
- Ollama (11434) → local seulement (127.0.0.1)
- Canvas proxy (18800) → local seulement

### 3. Fichiers sensibles
```
# A VERIFIER — ne doivent PAS etre dans git
etoile.db          # Contient API keys
.env               # Variables d'environnement
settings.json      # Tokens en clair
trading.db         # Donnees de trading
*.key, *.pem       # Certificats
```

### 4. Scan rapide
```bash
# Chercher des patterns de secrets dans les fichiers
grep -r "sk-lm-\|Bearer \|api_key\|secret\|password" F:/BUREAU/turbo/src/ --include="*.py" -l
```

```bash
# Verifier les ports ouverts
netstat -an | findstr LISTENING | findstr "1234\|11434\|18800\|5678\|8080\|9742"
```

### 5. Recommendations
- Utiliser des variables d'environnement pour tous les secrets
- Ajouter `.gitignore` avec patterns de fichiers sensibles
- Activer HTTPS pour les communications inter-noeuds si possible
- Rotation des API keys LM Studio trimestrielle
