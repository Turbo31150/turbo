# LinkedIn Pipeline — Commandes Rapides

## Via Terminal (scripts/linkedin_pipeline.py)
```bash
# Generer un post
python scripts/linkedin_pipeline.py generate --theme "IA locale"

# Generer 5 posts d'avance
python scripts/linkedin_pipeline.py batch --count 5

# Lister les posts
python scripts/linkedin_pipeline.py list

# Valider par consensus cluster (M1+OL1+Claude+Minimax+M2)
python scripts/linkedin_pipeline.py validate --id 1

# Planifier publication
python scripts/linkedin_pipeline.py schedule --id 1 --at "2026-03-07 09:00"

# Verifier posts a publier maintenant
python scripts/linkedin_pipeline.py check

# Marquer pret a publier
python scripts/linkedin_pipeline.py publish --id 1

# Statut routine du jour
python scripts/linkedin_pipeline.py status
```

## Via Telegram Bot
```
/post                    — Menu complet
/post gen [theme]        — Generer 1 post (dry-run)
/post batch [n]          — Generer n posts d'avance
/post list               — Lister tous les posts
/post validate <id>      — Valider par consensus cluster
/post schedule <id> [dt] — Planifier publication
/post check              — Posts a publier maintenant
/post publish <texte>    — Publier directement
/post history            — Historique
/post comment <url> <txt>— Commenter
/post routine            — Statut routine du jour
/post notif              — Notifications
```

## Via Claude Code (Playwright MCP)
```
1. browser_navigate → linkedin.com/feed
2. browser_click → "Commencer un post"
3. browser_evaluate → inject HTML dans textbox
4. browser_click → "Publier"
5. Verifier notification "Le post a bien ete publie"
```

## Via WhisperFlow (Voice Commands)
```
"JARVIS, publie un post LinkedIn"
"JARVIS, genere un post sur [theme]"
"JARVIS, scroll LinkedIn"
"JARVIS, verifie les notifications LinkedIn"
```

## Pipeline Complet
```
1. GENERATION  → M1/qwen3-8b ou OL1/qwen3:1.7b
2. FACT-CHECK  → Verification GitHub README + claims vs reality
3. VALIDATION  → Consensus cluster (M1+OL1+Claude+Minimax+M2)
4. PLANIFICATION → Schedule en DB avec date/heure
5. PUBLICATION → Playwright MCP via Claude Code ou Comet
6. LOGGING     → linkedin_actions + linkedin_scheduled_posts en DB
7. INTERACTION → Scroll feed, like, comment, reply, notifs
```

## Tables SQLite (jarvis.db)
- `linkedin_scheduled_posts` — Posts prepares et planifies
- `linkedin_daily_routine` — Log des routines quotidiennes
- `linkedin_actions` — Log de chaque action individuelle
- `linkedin_pipeline` — 18 etapes pipeline reusable

## Cluster Validation Weights
| Agent | Poids | Role |
|-------|-------|------|
| M1    | 1.8   | Generation + evaluation |
| Claude| 1.5   | Qualite contenu |
| OL1   | 1.3   | Evaluation rapide |
| Minimax| 1.2  | Tendances web |
| M2    | 1.5   | Reasoning profond |
