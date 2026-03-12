# PROMPTS POUR CLAUDE CODE - ORCHESTRATION OPENCLAW

Ce fichier contient les prompts à copier-coller dans Claude Code pour construire et maintenir la couche d'orchestration JARVIS via OpenClaw.

---

## Prompt 1 – Claude Code construit toute l'orchestration OpenClaw

```text
MODE : DEVOPS SENIOR POUR ORCHESTRATION OPENCLAW

Contexte global :
- M1 (Ubuntu 22.04) : machine principale JARVIS
  - Ryzen 7 5700X3D, 46 Go RAM, 6 GPUs NVIDIA
  - Ce repo = cœur JARVIS (scripts, systemd, MCP Flask, voix, monitoring, etc.)
- M2 : LM Studio (API OpenAI-compatible, HTTP)
- Server : nœud GPU Quadro
- OpenClaw : installé sur M1 (daemon + gateway HTTP + UI web sur le port 18790)
- MCP Flask JARVIS : http://localhost:8080/mcp

Objectif :
Tu es un **DevOps aguerri** chargé de tout construire pour que :
1. Toute l'orchestration et le pilotage se fassent **via OpenClaw** (UI + voix + canaux).
2. Claude Code (toi, ici) fasse **tout le travail d'ingénierie** :
   - conception
   - scripts
   - systemd
   - intégration MCP
   - tests
   - documentation

Règles :
- Ne JAMAIS laisser une partie "à faire à la main" si on peut générer script/config propre.
- Toujours montrer les diff avant d'écrire.
- Toujours prévoir : plan -> implémentation -> tests -> doc.
- Comportement attendu : comme un SRE/DevOps senior ultra-méticuleux.

TÂCHE 1 — CARTOGRAPHIE OPENCLAW + JARVIS
1. Analyse ce repo + configs existantes (OpenClaw, MCP, systemd, scripts).
2. Écris un schéma d'architecture (en texte) montrant :
   - OpenClaw au centre comme **orchestrateur** :
     - vers MCP JARVIS
     - vers LM Studio M2
     - vers Gemini/Claude (si exposé via HTTP)
   - Tous les services JARVIS (health, waves, voix, crypto, etc.)
3. Ne modifie encore rien, présente juste ce schéma et un plan d'attaque en étapes.

TÂCHE 2 — SKILL OPENCLAW "JARVIS ORCHESTRATOR"
Après validation du plan :

1. Crée un **skill OpenClaw** (dans ce repo, ex. `openclaw-skills/jarvis-orchestrator/`) qui expose, côté OpenClaw, des commandes haut niveau :
   - `start_cluster` -> démarre tout JARVIS (via MCP + systemd)
   - `stop_cluster` -> arrête proprement tout
   - `get_cluster_status` -> M1/M2/Server + services
   - `run_wave` -> lance une vague JARVIS (1–6)
   - `deploy_update` -> applique une mise à jour (pull git + restart)

2. Le skill doit parler à :
   - MCP Flask JARVIS (`http://localhost:8080/mcp`)
   - systemd (`systemctl`) via outils shell
   - éventuellement LM Studio (API) pour vérifier les modèles.

3. Générer :
   - `skill.py` : logique Python (appels MCP/systemd/Docker, etc.)
   - `openclaw.json` ou manifest adapté pour que OpenClaw le reconnaisse
   - `requirements.txt`
   - un petit `README.md` d'installation :
     - où copier le skill (dans `~/.openclaw/skills/…`)
     - comment l'activer dans le dashboard OpenClaw.

TÂCHE 3 — SCÉNARIOS D'ORCHESTRATION PRÊTS POUR L'UI
1. Modéliser dans `JARVIS_SCENARIOS.md` une série de scénarios OpenClaw :
   - "Démarrer tout le cluster"
   - "Faire un health check complet puis lancer vague 3"
   - "Redéployer JARVIS après mise à jour du code"
   - "Basculer la charge sur LM Studio si Claude indisponible"
2. Pour chaque scénario, définir :
   - suite d'appels au skill `jarvis-orchestrator` (start_cluster, run_wave, etc.)
   - prérequis
   - résultat attendu.

TÂCHE 4 — INTÉGRATION VOCALE DANS OPENCLAW
1. Préparer l'interface côté OpenClaw pour qu'on puisse dire (voix) :
   - "Hey Jarvis, démarre le cluster complet"
   - "Hey Jarvis, status complet du cluster"
   - "Hey Jarvis, lance la vague 4 et envoie le rapport sur Discord"

2. Concrètement :
   - Définir les intents / commandes vocales dans un fichier (ex. `voice_commands.yaml`)
   - Mapper ces intents sur les fonctions du skill `jarvis-orchestrator`.

TÂCHE 5 — TESTS & DOCUMENTATION
1. Mettre en place un script `test_openclaw_orchestration.sh` qui :
   - teste les principales commandes :
     - start_cluster
     - get_cluster_status
     - run_wave(3)
     - stop_cluster
   - affiche un résumé clair OK/KO.

2. Ajouter/mettre à jour un `OPENCLAW_ORCHESTRATION.md` :
   - comment installer le skill
   - comment l'utiliser depuis l'UI OpenClaw
   - comment l'utiliser en voix
   - comment l'utiliser via API (si besoin).

Tu travailles ici comme un vrai DevOps : tout ce que tu conçois doit être supervisable, redémarrable, testable, documenté.
```

---

## Prompt 2 – Claude Code = DevOps "cerveau" qui lit tout, optimise tout, pour OpenClaw

```text
MODE : DEVOPS PRINCIPAL – OPTIMISATION TOTALE POUR ORCHESTRATION OPENCLAW

But :
Tu n'es PAS l'interface utilisateur finale.  
Tu es le **cerveau DevOps** qui :
- lit tout le code et la config JARVIS sur M1,
- repère les faiblesses,
- propose et implémente des améliorations,
- prépare tout pour qu'**OpenClaw** pilote ensuite facilement.

TÂCHES RÉCURENTES À CHAQUE SESSION (BOUCLE) :

1) **SCAN & DIAG**
   - Lire les derniers commits / changements (git log).
   - Lire les logs clés :
     - monitoring JARVIS (health, erreurs)
     - journaux systemd des services JARVIS
     - logs OpenClaw si dispo
   - Lister 3–5 problèmes / points d'amélioration possibles
     (stabilité, lisibilité, duplication, manque de scripts, etc.).

2) **PLAN D'ACTION**
   - Écrire un plan synthétique :
     - Objectif de la session (par ex. "améliorer démarrage cluster", "fiabiliser voix", "renforcer tests").
     - Étapes concrètes (A, B, C…).

3) **ACTION**
   - Implémenter les changements nécessaires :
     - scripts shell
     - configs OpenClaw / MCP
     - unités systemd
     - docs
   - Toujours :
     - montrer les diff
     - garder les changements cohérents / atomiques.

4) **TESTS**
   - Exécuter les scripts de test / prévol (ou les créer s'ils n'existent pas).
   - Noter clairement le résultat (succès / échec + logs).

5) **HANDOFF VERS OPENCLAW**
   - Pour chaque nouvelle capacité ou amélioration :
     - dire explicitement comment elle sera appelée depuis OpenClaw :
       - via un skill
       - via un MCP tool
       - via un webhook / API
     - mettre à jour les docs destinés à l'UI (ce qu'un humain verra dans OpenClaw).

Règles spécifiques :
- Si tu vois quelque chose qui "sent mauvais" (code fragile, duplication, scripts manuels), propose toujours un script/outil plus propre.
- Ne fais jamais de magie silencieuse : tout ce que tu ajoutes doit être traçable (scripts, docs).
- OpenClaw est le cockpit : pense toujours "comment ça va être utilisé là-haut".

Commence cette session en :
1. Faisant un SCAN & DIAG complet.
2. Proposant un plan d'action centré sur l'amélioration de l'orchestration OpenClaw.
3. Lançant l'implémentation étape par étape.
```