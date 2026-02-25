# Plan d'Implementation — JARVIS Cockpit Autonome v1

**Design**: `2026-02-25-cockpit-autonome-design.md`
**Fichiers a modifier**: `canvas/direct-proxy.js` + `canvas/index.html`

---

## Task 1: Tool Engine dans direct-proxy.js

**Fichier**: `canvas/direct-proxy.js`
**Objectif**: Ajouter les 10 tools systeme executables cote serveur

### Steps:
1. Lire `direct-proxy.js` pour comprendre la structure actuelle
2. Ajouter un objet `TOOLS` avec les 10 fonctions:
   - `exec(cmd)` — child_process.execFileSync (securise, timeout 60s)
   - `read_file(path)` — fs.readFileSync avec limite 100KB
   - `write_file(path, content)` — fs.writeFileSync
   - `edit_file(path, old, new)` — read + replace + write
   - `list_dir(path, recursive)` — fs.readdirSync avec stats
   - `mkdir(path)` — fs.mkdirSync recursive
   - `delete(path)` — marquer comme "pending_confirm" (pas executer)
   - `query_db(sql, db)` — child_process sqlite3 CLI
   - `pipeline(name, args)` — lookup dans etoile.db map + exec
   - `web_search(query)` — appel OL1 minimax cloud
3. Ajouter endpoint `POST /tool` pour execution directe
4. Tester chaque tool individuellement via curl

Note securite: pour `exec`, utiliser execFile avec tableau d'args
quand possible. Pour les commandes shell complexes, valider l'input
et sanitizer avant execution. Le Safety Gate (Task 3) filtre les
patterns dangereux.

### Verification:
```bash
curl -s http://127.0.0.1:18800/tool -d '{"name":"list_dir","args":{"path":"F:/BUREAU/turbo"}}'
curl -s http://127.0.0.1:18800/tool -d '{"name":"read_file","args":{"path":"F:/BUREAU/turbo/README.md"}}'
```

---

## Task 2: Boucle Agentique dans direct-proxy.js

**Fichier**: `canvas/direct-proxy.js`
**Objectif**: Le /chat fait tourner l'IA en boucle avec tool calls

### Steps:
1. Modifier la fonction `handleChat()` existante
2. Ajouter le system prompt agent (avec liste des 10 tools)
3. Apres chaque reponse IA, parser pour `[TOOL:name:args_json]`
4. Si tool call detecte:
   a. Executer le tool via TOOLS[name](args)
   b. Ajouter le resultat au contexte
   c. Renvoyer a l'IA pour continuation
5. Si pas de tool call, reponse finale retournee au frontend
6. Limite: max 15 tours (anti-boucle)
7. Accumuler les tool calls executes dans metadata pour le frontend

### Verification:
```bash
curl -s http://127.0.0.1:18800/chat -d '{"text":"liste les fichiers sur mon bureau","agent":"main"}'
# Doit retourner la liste reelle des fichiers
```

---

## Task 3: Safety Gate

**Fichier**: `canvas/direct-proxy.js`
**Objectif**: Bloquer les operations dangereuses et demander confirmation

### Steps:
1. Creer liste DANGEROUS_PATTERNS:
   - exec: rm, del, rmdir, format, drop, truncate, push --force, reset --hard
   - delete: toujours
   - write_file: .env, credentials, system32
   - query_db: DELETE, DROP, TRUNCATE, ALTER
2. Avant execution, checker si pattern dangereux
3. Si dangereux: retourner `{needs_confirm: true, action: "...", description: "..."}`
4. Ajouter endpoint `POST /confirm` pour accepter/refuser
5. Stocker les actions en attente dans un Map avec TTL 60s

### Verification:
```bash
curl -s http://127.0.0.1:18800/chat -d '{"text":"supprime le dossier temp","agent":"main"}'
# Doit retourner needs_confirm: true
```

---

## Task 4: Rendu Chat Enrichi dans index.html

**Fichier**: `canvas/index.html`
**Objectif**: Afficher les resultats des tools avec rendu riche

### Steps:
1. Modifier la fonction `md()` (markdown renderer) pour detecter les blocs speciaux
2. Ajouter rendu pour chaque type:
   - `[EXEC_OUTPUT]...[/EXEC_OUTPUT]` bloc terminal noir mono
   - `[FILE:path]...[/FILE]` bloc avec coloration syntaxique (highlight.js CDN)
   - `[DIFF]...[/DIFF]` lignes vertes (+) et rouges (-)
   - `[TREE]...[/TREE]` arborescence avec icones
   - `[ERROR]...[/ERROR]` bloc rouge
   - `[PIPELINE:name:status]` badge avec nom et statut
3. Ajouter modal de confirmation pour Safety Gate:
   - Quand `needs_confirm: true`, afficher modal avec action + boutons Oui/Non
   - Sur Oui envoyer POST /confirm avec id de l'action
   - Sur Non afficher message "Action annulee"
4. Ajouter boutons d'action inline:
   - "Copier" sur les blocs de code
   - "Rollback" sur les edits (stocke ancien contenu)
   - "Ouvrir" sur les fichiers (read_file + afficher)

### Verification:
- Envoyer "lis le fichier direct-proxy.js" doit afficher avec coloration
- Envoyer "cree un fichier test.txt sur le bureau" doit montrer le fichier cree
- Envoyer "supprime test.txt" doit afficher modal confirmation

---

## Task 5: Integration etoile.db + Pipelines

**Fichier**: `canvas/direct-proxy.js`
**Objectif**: JARVIS connait toutes ses commandes et peut les declencher

### Steps:
1. Au demarrage du proxy, charger etoile.db:
   - Lire table `map` (268 commandes/pipelines)
   - Lire table `api_keys` (5 cles)
   - Lire table `agents` (4 agents)
2. Injecter un resume dans le system prompt:
   - "Tu as 268 commandes disponibles. Les principales: ..."
   - "Pipelines disponibles: trading-scan, trading-feedback, gpu-pipeline, ..."
3. Tool `pipeline`: lookup dans map, extraire la commande, executer
4. Tool `query_db`: executer SQL avec sqlite3 CLI

### Verification:
```bash
curl -s http://127.0.0.1:18800/chat -d '{"text":"quels pipelines sont disponibles?","agent":"main"}'
# Doit lister les pipelines depuis etoile.db
```

---

## Task 6: Test End-to-End + Polish

### Steps:
1. Tester 5 scenarios complets:
   - "cree un dossier MonApp sur le bureau"
   - "lis server.py et dis-moi ce qu'il fait"
   - "cherche sur le web les dernieres news crypto"
   - "lance le pipeline trading-scan"
   - "supprime le dossier MonApp" (doit demander confirmation)
2. Verifier le rendu de chaque type de resultat
3. Verifier les fallbacks (M2 offline puis M3 puis OL1)
4. Verifier la limite de 15 tours
5. Restart du proxy et test de persistence

### Verification:
- Tous les 5 scenarios passent sans erreur
- Le rendu est lisible et interactif
- Les confirmations fonctionnent
