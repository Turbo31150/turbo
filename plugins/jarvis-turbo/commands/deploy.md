---
name: deploy
description: Commit + push rapide du projet turbo avec message auto-genere
---

Deploy rapide du projet JARVIS turbo. Equivalent de git add + commit + push.

Etapes :
1. `cd F:/BUREAU/turbo && git status -u` — voir les changements
2. `git diff --stat` — resume des modifications
3. `git log --oneline -3` — style des commits recents

Analyse les changements et genere un message de commit concis en francais.
Ajoute UNIQUEMENT les fichiers modifies pertinents (pas les .db, pas les .env, pas les credentials).

Puis :
4. `git add <fichiers pertinents>`
5. `git commit -m "<message>"` avec Co-Authored-By
6. `git push`

IMPORTANT : Ne commit PAS les fichiers sensibles (etoile.db, .env, credentials, api keys).
Demande confirmation avant le push si plus de 10 fichiers sont modifies.
