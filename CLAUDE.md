# JARVIS Turmont – CLAUDE.md

## Rôle de ce projet

Ce dépôt contient le cœur de **JARVIS Turmont** sur M1 (Ubuntu 22.04) :
- Machine principale de création et d'orchestration (M1) :
  - CPU : Ryzen 7 5700X3D
  - RAM : 46 Go
  - GPUs : 6 cartes NVIDIA (4x1660S, 1x2060, 1x3080)
- Ce repo gère :
  - Les scripts JARVIS (santé, vagues, orchestration, voix, crypto, etc.)
  - Les services systemd / timers
  - Le serveur MCP Flask JARVIS
  - Les intégrations OpenClaw, WhisperFlow, Porcupine, Gemini CLI, LM Studio.

Ton objectif principal en tant qu'agent : **améliorer et orchestrer ce système de cluster IA** sans casser la prod.

---

## Architecture haute niveau

### Machines / nœuds

- **M1 (cette machine)** : orchestration, MCP Flask, OpenClaw client, Gemini CLI, scripts système.
- **M2 (LMT2)** : LM Studio avec modèles locaux (API OpenAI-compatible, HTTP).
- **Server (Quadro)** : nœud de calcul additionnel (3x Quadro).

### Composants logiciels clés

- `mcp-flask-server/` : serveur MCP (Flask) exposant des tools pour le cluster (gpu_scale, run_wave, get_cluster_status, etc.).
- `monitoring/` : scripts health (GPU, CPU, Docker, cluster).
- `jarvis-voice-control/` : wake word Porcupine, STT, intégration voix.
- `systemd/` : fichiers .service/.timer générés côté projet (à copier ensuite dans `/etc/systemd/system` ou `~/.config/systemd/user/`).
- Intégrations externes :
  - **OpenClaw** (daemon + gateway HTTP sur M1, port 18790)
  - **WhisperFlow** (STT temps réel)
  - **Porcupine** (wake word "Hey Jarvis")
  - **Gemini CLI / Claude Code** (orchestration + codage)
  - **LM Studio** (modèles locaux via API HTTP sur M2).

---

## Commandes standard à privilégier

Merci d'utiliser ces commandes plutôt que d'en inventer d'autres :

### Démarrage / arrêt cluster (une fois qu'ils existent)

- Prévol :
  - `./jarvis_preflight_check.sh`
- Démarrer tout le cluster :
  - `./jarvis_cluster_start.sh`
- Arrêter proprement tout :
  - `./jarvis_cluster_stop.sh`

### MCP Flask JARVIS

- Dossier : `mcp-flask-server/`
- Lancement manuel :
  - `cd mcp-flask-server && source venv/bin/activate && python app.py`

### Monitoring & dashboards

- Dashboard Electron JARVIS Etoile :
  - `cd ~/jarvis/electron && npm start`
- Dashboard tmux JARVIS (si alias existant) :
  - `jdash`

### OpenClaw

- Statut daemon + gateway :
  - `openclaw daemon status && openclaw gateway status`
- UI web :
  - `http://127.0.0.1:18790/`

### LM Studio (M2)

- Test API (remplacer `M2_IP` par `192.168.1.26`) :
  - `curl http://192.168.1.26:1234/v1/models`

---

## Règles de travail importantes

### 1. Sécurité et "zones sensibles"

- Ne **jamais** :
  - Toucher directement aux fichiers système critiques hors `~/.config/systemd/user/` et `/opt/jarvis` sans plan explicite.
  - Supprimer des fichiers de configuration existants sans backup.
- Toujours :
  - Montrer les diff avant d'écrire les fichiers importants.
  - Prévoir un rollback simple (via `git revert` ou sauvegarde `.bak`).
  - Utiliser SUDO sans mot de passe si configuré, ou assumer le mode root selon les instructions.

### 2. Workflow attendu

Pour toute tâche non triviale :
1. **Explorer** : lire fichiers, logs, vérifier l'architecture -> ne pas coder tout de suite.
2. **Planifier** : écrire un plan clair en étapes (A/B/C...).
3. **Implémenter** : appliquer les changements par petites étapes.
4. **Tester** : utiliser les scripts de tests / health déjà présents ou à créer.
5. **Documenter** : mettre à jour README / fichiers `.md` concernés.

---

## Distribution des tâches entre moteurs (routing)

- **Claude Code (toi)** : Architecture du cluster, gros refactors, système de timers, orchestration globale. Création/modification de scripts système, pipelines CI.
- **Gemini CLI** : Scripts shell, petites automations, génération rapide de fichiers, "bricolage" DevOps. Tâches longues et répétitives.
- **LM Studio (M2)** : Agent de debug continu, analyse de gros volumes de code/logs, optimisation long-terme.
- **OpenClaw** : Interface utilisateur (web, voix, mobile), multi-canaux.
- **MCP Flask JARVIS** : Pont unique pour parler au cluster (GPU, vagues, stats, etc.) depuis les agents.

---

## Comportement attendu pour les gros travaux

- Toujours commencer par un **plan écrit** (et me le montrer) pour :
  - lancer/arrêter tout le cluster,
  - refactorer des modules importants,
  - intégrer un nouveau modèle ou un nouveau service.
- Éviter de modifier 20 fichiers en une seule passe sans étapes intermédiaires.

Ce fichier est versionné dans git et fait office de "mémoire projet" pour les agents.