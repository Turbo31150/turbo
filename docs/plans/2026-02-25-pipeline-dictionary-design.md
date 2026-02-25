# Pipeline Dictionary + Ponderation Multi-Scenario

## Goal
Creer un dictionnaire structure dans etoile.db qui lie agents, mots-cles, scenarios, ponderations et chaines domino. Integrer les commandes vocales avec jarvis.ps1.

## Nouvelles tables etoile.db

### agent_keywords
Mots-cles par agent avec ponderation par scenario.
- agent TEXT, keyword TEXT, domain TEXT, weight REAL, scenario TEXT

### pipeline_dictionary
Dictionnaire d'utilisation des 738 commandes/pipelines.
- pipeline_id TEXT, trigger TEXT, steps TEXT, category TEXT, agents_involved TEXT, avg_duration_ms INT, usage_count INT

### scenario_weights
Ponderation par scenario (trading_urgent, code_review, etc.)
- scenario TEXT, agent TEXT, weight REAL, priority INT, chain_next TEXT

### domino_chains
Effet domino — une commande en declenche une autre.
- trigger_cmd TEXT, condition TEXT, next_cmd TEXT, delay_ms INT, auto BOOL

## Remplissage
- commands.py (472) + commands_pipelines.py (266) → pipeline_dictionary
- config.py routing (22 regles) → scenario_weights
- Keywords extraits des triggers → agent_keywords
- Dominos: status→heal, ask_fail→fallback, consensus→log

## Integration
- jarvis.ps1 utilise scenario_weights pour routage enrichi
- Commandes vocales: ask, status, consensus, scores, heal
- Auto-apprentissage: chaque resultat enrichit agent_keywords
