# Missions Type Perplexity — Pilotage JARVIS

## Mission 1: Audit Quotidien Complet

**Objectif**: Rapport complet sur l'etat du cluster, des strategies trading, et du systeme.

**Prompt Perplexity**:
> Lance un audit complet JARVIS: cluster health, GPU, strategies evolution, signaux trading actifs, et securite. Resume en sections avec scores.

**Sequence d'outils**:
1. `lm_cluster_status` — Etat des 4 noeuds
2. `gpu_info` — Temperatures, VRAM
3. `health_summary` — Score sante global
4. `trading_status` — Etat trading
5. `trading_pending_signals` — Signaux en attente
6. `trading_strategy_rankings` — Top strategies
7. `orch_dashboard` — Orchestration metrics
8. `metrics_snapshot` — Metriques globales
9. `security_score` — Score securite
10. `brain_status` — Etat cerveau JARVIS

**Criteres de succes**:
- 10 sections avec donnees reelles (pas de simulation)
- Scores chiffres pour chaque domaine
- Alertes flaggees si anomalie detectee
- Temps total < 2 minutes

---

## Mission 2: Conception & Test de Nouvelle Strategie

**Objectif**: Concevoir une nouvelle famille de strategies basee sur l'analyse du marche actuel, puis l'injecter dans l'evolution.

**Prompt Perplexity**:
> Analyse le marche crypto actuel via JARVIS, identifie le regime (trending/ranging/volatile), puis conçois 5 strategies adaptees a ce regime. Injecte-les dans l'evolution et verifie qu'elles sont prises en compte.

**Sequence d'outils**:
1. `ollama_web_search` — Tendances crypto actuelles
2. `lm_query` (M1) — Analyse technique des top coins
3. `trading_strategy_rankings` — Strategies existantes (eviter doublons)
4. `consensus` (M1+OL1) — Consensus sur parametres optimaux
5. `write_text_file` — Ecrire les strategies en JSON
6. `lm_query` (M1) — Valider les parametres via backtest mental
7. `read_text_file` — Verifier le fichier genere

**Criteres de succes**:
- 5 strategies avec DNA valide (EMA, RSI, TP, SL, features)
- Adaptees au regime de marche detecte
- Differentes des top 10 existantes
- Parametres dans les ranges valides

---

## Mission 3: Diagnostic Automatique d'Anomalie

**Objectif**: Quand un noeud ou worker se comporte anormalement, diagnostiquer et proposer une correction.

**Prompt Perplexity**:
> Le cluster JARVIS semble lent/instable. Diagnostique: quel noeud pose probleme, pourquoi, et comment corriger. Teste chaque noeud individuellement.

**Sequence d'outils**:
1. `lm_cluster_status` — Vue d'ensemble
2. `diagnostics_quick` — Diagnostic rapide
3. `orch_node_stats` — Stats par noeud (latence, erreurs)
4. `gpu_info` — Temperatures (throttling?)
5. `list_processes` (filter: python) — Workers en cours
6. `lm_query` (chaque noeud) — Test direct M1, M2, M3
7. `ollama_query` — Test OL1
8. `system_info` — CPU/RAM/Disk

**Criteres de succes**:
- Noeud problematique identifie avec preuve (latence, erreur, timeout)
- Cause racine proposee (saturation, modele pas charge, GPU chaud, etc.)
- Action corrective concrete (restart, kill process, unload model, etc.)
- Verification post-correction

---

## Mission 4: Recherche & Rapport de Marche

**Objectif**: Produire un rapport structure sur un sujet marche/crypto utilisant la recherche web + le cluster IA.

**Prompt Perplexity**:
> Recherche les dernieres nouvelles crypto impactantes (24h), croise avec les donnees JARVIS (signaux, positions, regime), et produis un rapport de 500 mots avec recommandations trading.

**Sequence d'outils**:
1. `ollama_web_search` — Actualites crypto 24h
2. `trading_status` — Positions actuelles
3. `trading_pending_signals` — Signaux detectes
4. `consensus` — Avis multi-IA sur le sentiment
5. `memory_recall` (query: "trading") — Historique decisions
6. `write_text_file` — Sauvegarder le rapport

**Criteres de succes**:
- Sources web citees
- Donnees JARVIS reelles integrees
- Recommandations actionables (BUY/SELL/HOLD par coin)
- Rapport sauvegarde dans data/reports/

---

## Mission 5: Auto-Optimisation du Cluster

**Objectif**: Analyser les performances du cluster et optimiser automatiquement la configuration.

**Prompt Perplexity**:
> Analyse les metriques du cluster JARVIS sur les dernieres heures: quels noeuds sont sous-utilises? Quels workers consomment trop? Propose des optimisations et applique-les si safe.

**Sequence d'outils**:
1. `orch_dashboard` — Vue complete orchestration
2. `orch_node_stats` — Stats detaillees par noeud
3. `metrics_summary` — Resume metriques
4. `cluster_analytics` — Analytics cluster
5. `lb_status` — Load balancer
6. `brain_analyze` — Patterns d'utilisation
7. `optimizer_stats` — Stats optimiseur

**Criteres de succes**:
- Noeuds sous-utilises identifies (< 10% utilisation)
- Workers redondants signales
- 3+ recommandations concretes
- Pas d'action destructive sans confirmation
