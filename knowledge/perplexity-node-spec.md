# Perplexity Node Spec — Integration Cluster JARVIS

## Identite

- **Nom**: PERPLEXITY
- **Type**: Noeud externe cloud (MCP via tunnel Cloudflare)
- **Poids consensus**: 1.3 (equivalent OL1)
- **Specialite**: Recherche web, analyse financiere, rapports structures, raisonnement long

## Quand JARVIS appelle Perplexity

| Situation | Appeler Perplexity | Raison |
|-----------|-------------------|--------|
| Recherche web / actualites | OUI (prioritaire) | Sources a jour, citations, croisement |
| Analyse financiere fondamentale | OUI | DCF, screening, earnings analysis |
| Rapport structure long | OUI | Meilleur en synthese argumentee |
| Code / debug | NON | M1/gpt-oss sont meilleurs |
| Raisonnement math/logique | NON | M1/M2 deepseek-r1 superieurs |
| Commandes systeme | NON | Pas d'acces direct, overhead MCP |
| Trading temps reel | NON | Trop lent (tunnel + API) |
| Consensus critique | OUI (1 voix) | Perspective differente des LLMs locaux |

## Ce que JARVIS fait confiance a Perplexity

- **Haute confiance**: Recherche factuelle, citations, synthese de sources multiples
- **Confiance moyenne**: Analyse financiere, recommandations marche
- **Confiance basse**: Code generation, system commands, real-time decisions
- **Jamais**: Execution directe de trades, modification systeme sans validation

## Ce que Perplexity fait confiance a JARVIS

- **Total**: Donnees systeme (GPU, processes, network, disk)
- **Total**: Donnees trading (positions, signaux, strategies, backtests)
- **Total**: Etat cluster (noeuds, modeles, latences, health)
- **Verification**: Brain/memory (peut contenir des donnees obsoletes)
- **Prudence**: Actions (powershell_run, kill_process, trading_execute)

## Protocol de communication

### JARVIS → Perplexity
- Via MCP tools/call sur le tunnel Cloudflare
- Timeout: 60s par appel
- Format: JSON-RPC 2.0 over SSE
- Retry: 1 tentative, pas de boucle

### Perplexity → JARVIS
- Via MCP tools/call (121 outils disponibles)
- Toujours commencer par un outil de STATUS avant un outil d'ACTION
- Sequence: status → analyse → decision → action (si autorise)

## Limites

- **Latence**: Tunnel Cloudflare ajoute ~200-500ms par appel
- **Disponibilite**: Quick tunnel = URL change au restart de cloudflared
- **Contexte**: 121 outils consomment ~3600 tokens de descriptions
- **Parallelisme**: Perplexity fait des appels sequentiels (pas de batch MCP)
- **Securite**: Pas d'auth sur le tunnel quick (accessible publiquement)

## Metriques de suivi

JARVIS devrait tracker:
- Nombre d'appels Perplexity/jour
- Latence moyenne tunnel
- Taux de succes des appels
- Types d'outils les plus appeles
- Qualite des reponses (si feedback disponible)

## Evolutionss prevues

1. **Tunnel permanent**: Named tunnel Cloudflare avec URL fixe et auth
2. **Auth MCP**: Ajouter Bearer token sur le serveur SSE
3. **Tier dynamique**: Adapter les outils exposes selon la mission en cours
4. **Bidirectionnel**: JARVIS appelle Perplexity API directement (pas juste MCP)
5. **Cache**: Cacher les resultats de recherche web pour eviter les appels redondants
