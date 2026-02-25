# JARVIS Cockpit Autonome v1 — Design

**Date**: 2026-02-25
**Auteur**: Claude Opus 4.6 + Turbo
**Statut**: Approuve

## Vision

Le Canvas Command Center v2 (port 18800) devient un cockpit conversationnel autonome.
L'utilisateur parle (texte ou voix), JARVIS execute tout : code, fichiers, commandes, pipelines.
L'utilisateur ne touche jamais au code — il discute, JARVIS agit.

## Architecture

```
UTILISATEUR (voix / clavier)
       |
       v
+--------------------------------------+
|   CANVAS COCKPIT (index.html)        |
|   Chat + rendu riche interactif      |
|   Terminal inline, diffs, actions    |
+--------------------------------------+
       | POST /chat
       v
+--------------------------------------+
|   DIRECT-PROXY.JS v2 (port 18800)   |
|                                      |
|   1. Route message -> IA cluster     |
|   2. IA repond avec TOOL CALLS       |
|   3. TOOL ENGINE execute localement  |
|   4. Resultat renvoye a l'IA        |
|   5. Boucle jusqu'a reponse finale  |
|   6. Safety gate si op dangereuse    |
+--------------------------------------+
       |            |           |
       v            v           v
   IA CLUSTER   TOOL ENGINE   SAFETY GATE
   M1/M2/M3    10 tools      confirm si
   OL1/GEMINI  systeme       destructif
```

## 10 Tools Systeme

| Tool | Args | Description |
|------|------|-------------|
| `exec` | `{cmd}` | Commande shell PowerShell/bash, stream output |
| `read_file` | `{path}` | Lire fichier (tout le systeme) |
| `write_file` | `{path, content}` | Creer/ecrire fichier |
| `edit_file` | `{path, old, new}` | Remplacer section dans fichier |
| `list_dir` | `{path, recursive?}` | Lister dossier |
| `mkdir` | `{path}` | Creer dossier |
| `delete` | `{path}` | Supprimer (CONFIRMATION requise) |
| `query_db` | `{sql, db?}` | SQL sur etoile.db (defaut) |
| `pipeline` | `{name, args?}` | Declencher pipeline JARVIS (278 dispo) |
| `web_search` | `{query}` | Recherche web via OL1 minimax cloud |

## Boucle Agentique

1. User envoie message
2. Proxy route vers IA (M2 pour code, OL1 pour rapide, etc.)
3. System prompt inclut la liste des tools + instructions
4. IA repond avec du texte OU un tool call: `[TOOL:nom:args_json]`
5. Proxy parse le tool call, execute via Tool Engine
6. Resultat renvoye a l'IA comme contexte supplementaire
7. IA continue (nouveau tool call ou reponse finale)
8. Max 15 tours par requete (anti-boucle infinie)
9. Reponse finale affichee avec rendu riche

## System Prompt Agent

```
Tu es JARVIS, un assistant IA autonome avec acces complet au systeme Windows.
Tu as 10 outils a ta disposition. Pour les utiliser, reponds avec:
[TOOL:nom_outil:{"arg1":"val1"}]

Outils disponibles:
- exec: executer une commande shell
- read_file: lire un fichier
- write_file: creer/ecrire un fichier
- edit_file: modifier une partie d'un fichier
- list_dir: lister un dossier
- mkdir: creer un dossier
- delete: supprimer (sera confirme par l'utilisateur)
- query_db: requete SQL sur etoile.db
- pipeline: declencher un pipeline JARVIS
- web_search: chercher sur le web

Regles:
- Un seul tool call par message
- Attends le resultat avant de continuer
- Apres execution, synthetise ce que tu as fait
- Si une operation est dangereuse, previens l'utilisateur
- Contexte systeme: Windows 11, disques C:\ et F:\, user franc
```

## Safety Gate

Operations necessitant confirmation utilisateur:
- `delete` (tout fichier/dossier)
- `exec` avec: rm, del, format, drop, truncate, push --force, reset --hard
- `write_file` sur fichiers systeme (.env, credentials, registre)
- `query_db` avec DELETE, DROP, TRUNCATE

Implementation: le proxy detecte le pattern dangereux, renvoie un message
de confirmation au frontend, attend la reponse avant d'executer.

## Rendu Chat Enrichi

| Type de resultat | Rendu |
|-----------------|-------|
| Commande exec | Bloc terminal noir avec output, exit code |
| Fichier lu/ecrit | Coloration syntaxique (highlight.js) |
| Edit file | Diff vert/rouge inline |
| Erreur | Bloc rouge avec message + suggestion |
| Pipeline | Badge avec nom + statut (running/done/error) |
| Arborescence | Tree view collapsible |
| Confirmation | Modal avec boutons Oui/Non |

## Acces Complets

### etoile.db
- 268 entrees `map` (commandes vocales + pipelines)
- 5 API keys
- 22 memories
- 4 agents enregistres
- Accessible via tool `query_db`

### Pipelines JARVIS (278)
- Trading: scan, feedback, gpu pipeline
- Systeme: nettoyage, diagnostic, backup
- Modes: gaming, stream, cinema, musique, code, focus
- Routines: matin, soir, reveil
- Maintenance: heal-cluster, benchmark
- Accessible via tool `pipeline`

### MCP Tools (88 handlers)
- Accessible via tool `exec` (appel aux scripts MCP)
- Ou integration directe dans le Tool Engine

## Fichiers a Modifier

1. `canvas/direct-proxy.js` — ajouter Tool Engine + boucle agentique
2. `canvas/index.html` — ajouter rendu riche + modal confirmation
3. Aucun nouveau fichier necessaire

## Metriques de Succes

- L'utilisateur peut dire "cree un dossier X sur le bureau" et c'est fait
- L'utilisateur peut dire "lis server.py et corrige le bug" et l'IA le fait
- L'utilisateur peut dire "lance le pipeline trading" et ca se declenche
- Les operations dangereuses demandent confirmation
- Le tout en < 5s pour les actions simples, < 30s pour les complexes
