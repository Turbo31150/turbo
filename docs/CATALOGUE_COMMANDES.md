# JARVIS Turbo — Catalogue Complet des Commandes Vocales

> **1695 commandes** au total | Genere automatiquement le 2026-02-22

## Table des matieres

- [Accessibilite](#accessibilite) — 10 commandes
- [App](#app) — 23 commandes
- [Clipboard](#clipboard) — 13 commandes
- [Developpement & Outils](#developpement--outils) — 268 commandes
- [Gestion des Fenetres](#gestion-des-fenetres) — 13 commandes
- [Fichiers](#fichiers) — 45 commandes
- [Jarvis](#jarvis) — 12 commandes
- [Launcher](#launcher) — 12 commandes
- [Media & Volume](#media--volume) — 7 commandes
- [Navigation Web](#navigation-web) — 323 commandes
- [Pipelines Multi-Etapes](#pipelines-multi-etapes) — 278 commandes (278 pipelines)
- [Saisie](#saisie) — 3 commandes
- [Systeme & Maintenance](#systeme--maintenance) — 669 commandes
- [Trading](#trading) — 19 commandes

---

## Accessibilite

**10 commandes**

| # | Nom | Description | Declencheurs | Type | Params | Confirm |
|---|-----|-------------|--------------|------|--------|---------|
| 1 | `taille_texte_grand` | Agrandir la taille du texte systeme | `texte plus grand`, `agrandis le texte`, `taille texte grande` +2 | ms_settings | — | — |
| 2 | `clavier_virtuel` | Ouvrir le clavier virtuel | `clavier virtuel`, `ouvre le clavier virtuel`, `clavier a l'ecran` +2 | powershell | — | — |
| 3 | `filtre_couleur` | Activer/desactiver le filtre de couleur | `filtre de couleur`, `active le filtre couleur`, `mode daltonien` +2 | ms_settings | — | — |
| 4 | `sous_titres` | Parametres des sous-titres | `sous-titres`, `parametres sous-titres`, `active les sous-titres` +2 | ms_settings | — | — |
| 5 | `contraste_eleve_toggle` | Activer/desactiver le contraste eleve | `contraste eleve`, `high contrast`, `active le contraste` +2 | powershell | — | — |
| 6 | `sous_titres_live` | Activer les sous-titres en direct | `sous titres en direct`, `live captions`, `active les sous titres` +2 | powershell | — | — |
| 7 | `filtre_couleur_toggle` | Activer les filtres de couleur | `filtre de couleur`, `color filter`, `daltonien` +2 | powershell | — | — |
| 8 | `taille_curseur` | Changer la taille du curseur | `agrandis le curseur`, `curseur plus grand`, `taille curseur` +2 | powershell | — | — |
| 9 | `narrateur_toggle` | Activer/desactiver le narrateur | `active le narrateur`, `narrateur windows`, `desactive le narrateur` +2 | powershell | — | — |
| 10 | `sticky_keys_toggle` | Activer/desactiver les touches remanentes | `active les touches remanentes`, `desactive les touches remanentes`, `sticky keys` +1 | powershell | — | — |

## App

**23 commandes**

| # | Nom | Description | Declencheurs | Type | Params | Confirm |
|---|-----|-------------|--------------|------|--------|---------|
| 1 | `ouvrir_vscode` | Ouvrir Visual Studio Code | `ouvre vscode`, `ouvrir vscode`, `lance vscode` +8 | app_open | — | — |
| 2 | `ouvrir_terminal` | Ouvrir un terminal | `ouvre le terminal`, `ouvrir le terminal`, `lance powershell` +5 | app_open | — | — |
| 3 | `ouvrir_lmstudio` | Ouvrir LM Studio | `ouvre lm studio`, `lance lm studio`, `demarre lm studio` +2 | app_open | — | — |
| 4 | `ouvrir_discord` | Ouvrir Discord | `ouvre discord`, `lance discord`, `va sur discord` +2 | app_open | — | — |
| 5 | `ouvrir_spotify` | Ouvrir Spotify | `ouvre spotify`, `lance spotify`, `mets spotify` +2 | app_open | — | — |
| 6 | `ouvrir_task_manager` | Ouvrir le gestionnaire de taches | `ouvre le gestionnaire de taches`, `task manager`, `gestionnaire de taches` +3 | app_open | — | — |
| 7 | `ouvrir_notepad` | Ouvrir Notepad | `ouvre notepad`, `ouvre bloc notes`, `ouvre le bloc notes` +2 | app_open | — | — |
| 8 | `ouvrir_calculatrice` | Ouvrir la calculatrice | `ouvre la calculatrice`, `lance la calculatrice`, `calculatrice` +1 | app_open | — | — |
| 9 | `fermer_app` | Fermer une application | `ferme {app}`, `fermer {app}`, `quitte {app}` +2 | jarvis_tool | app | — |
| 10 | `ouvrir_app` | Ouvrir une application par nom | `ouvre {app}`, `ouvrir {app}`, `lance {app}` +1 | app_open | app | — |
| 11 | `ouvrir_paint` | Ouvrir Paint | `ouvre paint`, `lance paint`, `ouvrir paint` +1 | app_open | — | — |
| 12 | `ouvrir_wordpad` | Ouvrir WordPad | `ouvre wordpad`, `lance wordpad`, `ouvrir wordpad` | app_open | — | — |
| 13 | `ouvrir_snipping` | Ouvrir l'Outil Capture | `ouvre l'outil capture`, `lance l'outil capture`, `outil de capture` +2 | app_open | — | — |
| 14 | `ouvrir_magnifier` | Ouvrir la loupe Windows | `ouvre la loupe windows`, `loupe windows`, `loupe ecran` | hotkey | — | — |
| 15 | `fermer_loupe` | Fermer la loupe Windows | `ferme la loupe`, `desactive la loupe`, `arrete la loupe` | hotkey | — | — |
| 16 | `ouvrir_obs` | Ouvrir OBS Studio | `ouvre obs`, `lance obs`, `obs studio` +2 | app_open | — | — |
| 17 | `ouvrir_vlc` | Ouvrir VLC Media Player | `ouvre vlc`, `lance vlc`, `ouvrir vlc` +1 | app_open | — | — |
| 18 | `ouvrir_7zip` | Ouvrir 7-Zip | `ouvre 7zip`, `lance 7zip`, `ouvrir 7zip` +2 | app_open | — | — |
| 19 | `store_ouvrir` | Ouvrir le Microsoft Store | `ouvre le store`, `microsoft store`, `ouvre le magasin` +2 | powershell | — | — |
| 20 | `store_updates` | Verifier les mises a jour du Store | `mises a jour store`, `store updates`, `update les apps` +2 | powershell | — | — |
| 21 | `ouvrir_phone_link` | Ouvrir Phone Link (liaison telephone) | `ouvre phone link`, `liaison telephone`, `phone link` +2 | powershell | — | — |
| 22 | `terminal_settings` | Ouvrir les parametres Windows Terminal | `parametres du terminal`, `reglages terminal`, `settings terminal` +1 | powershell | — | — |
| 23 | `copilot_lancer` | Lancer Windows Copilot | `lance copilot`, `ouvre copilot`, `copilot` +2 | hotkey | — | — |

## Clipboard

**13 commandes**

| # | Nom | Description | Declencheurs | Type | Params | Confirm |
|---|-----|-------------|--------------|------|--------|---------|
| 1 | `copier` | Copier la selection | `copie`, `copier`, `copy` +2 | hotkey | — | — |
| 2 | `coller` | Coller le contenu | `colle`, `coller`, `paste` +2 | hotkey | — | — |
| 3 | `couper` | Couper la selection | `coupe`, `couper`, `cut` +1 | hotkey | — | — |
| 4 | `tout_selectionner` | Selectionner tout | `selectionne tout`, `tout selectionner`, `select all` +2 | hotkey | — | — |
| 5 | `annuler` | Annuler la derniere action | `annule`, `annuler`, `undo` +2 | hotkey | — | — |
| 6 | `ecrire_texte` | Ecrire du texte au clavier | `ecris {texte}`, `tape {texte}`, `saisis {texte}` +2 | jarvis_tool | texte | — |
| 7 | `sauvegarder` | Sauvegarder le fichier actif | `sauvegarde`, `enregistre`, `save` +3 | hotkey | — | — |
| 8 | `refaire` | Refaire la derniere action annulee | `refais`, `redo`, `refaire` +3 | hotkey | — | — |
| 9 | `recherche_page` | Rechercher dans la page | `recherche dans la page`, `cherche dans la page`, `find` +2 | hotkey | — | — |
| 10 | `lire_presse_papier` | Lire le contenu du presse-papier | `lis le presse-papier`, `qu'est-ce qui est copie`, `contenu du presse-papier` +1 | jarvis_tool | — | — |
| 11 | `historique_clipboard` | Historique du presse-papier | `historique du presse-papier`, `clipboard history`, `historique presse-papier` +1 | hotkey | — | — |
| 12 | `clipboard_historique` | Ouvrir l'historique du presse-papier | `historique presse papier`, `clipboard history`, `ouvre l'historique clipboard` +2 | hotkey | — | — |
| 13 | `coller_sans_format` | Coller sans mise en forme | `colle sans format`, `coller sans mise en forme`, `colle en texte brut` +1 | hotkey | — | — |

## Developpement & Outils

**268 commandes**

| # | Nom | Description | Declencheurs | Type | Params | Confirm |
|---|-----|-------------|--------------|------|--------|---------|
| 1 | `docker_ps` | Lister les conteneurs Docker | `liste les conteneurs`, `docker ps`, `conteneurs docker` +2 | powershell | — | — |
| 2 | `docker_images` | Lister les images Docker | `images docker`, `docker images`, `quelles images` +1 | powershell | — | — |
| 3 | `docker_stop_all` | Arreter tous les conteneurs Docker | `arrete tous les conteneurs`, `docker stop all`, `stoppe docker` +1 | powershell | — | Oui |
| 4 | `git_status` | Git status du projet courant | `git status`, `statut git`, `etat du repo` +2 | powershell | — | — |
| 5 | `git_log` | Git log recent | `git log`, `historique git`, `derniers commits` +2 | powershell | — | — |
| 6 | `git_pull` | Git pull origin main | `git pull`, `tire les changements`, `pull git` +2 | powershell | — | — |
| 7 | `git_push` | Git push origin main | `git push`, `pousse les commits`, `push git` +2 | powershell | — | Oui |
| 8 | `pip_list` | Lister les packages Python installes | `pip list`, `packages python`, `quels packages` +2 | powershell | — | — |
| 9 | `python_version` | Version Python et uv | `version python`, `quelle version python`, `python version` +1 | powershell | — | — |
| 10 | `ouvrir_n8n` | Ouvrir n8n dans le navigateur | `ouvre n8n`, `lance n8n`, `n8n` +2 | browser | — | — |
| 11 | `lm_studio_restart` | Relancer LM Studio | `relance lm studio`, `redemarre lm studio`, `restart lm studio` +1 | powershell | — | — |
| 12 | `ouvrir_jupyter` | Ouvrir Jupyter dans le navigateur | `ouvre jupyter`, `lance jupyter`, `jupyter notebook` +2 | browser | — | — |
| 13 | `wsl_lancer` | Lancer WSL (Windows Subsystem for Linux) | `lance wsl`, `ouvre wsl`, `lance linux` +3 | powershell | — | — |
| 14 | `wsl_liste` | Lister les distributions WSL installees | `liste les distributions wsl`, `wsl liste`, `distributions linux` | powershell | — | — |
| 15 | `wsl_shutdown` | Arreter toutes les distributions WSL | `arrete wsl`, `stoppe wsl`, `ferme wsl` +1 | powershell | — | — |
| 16 | `git_branches` | Lister les branches git | `branches git`, `quelles branches`, `liste les branches` +2 | powershell | — | — |
| 17 | `git_diff` | Voir les modifications non commitees | `git diff`, `modifications en cours`, `quelles modifications` +2 | powershell | — | — |
| 18 | `git_stash` | Sauvegarder les modifications en stash | `git stash`, `stash les changements`, `sauvegarde les modifs` +1 | powershell | — | — |
| 19 | `git_stash_pop` | Restaurer les modifications du stash | `git stash pop`, `restaure le stash`, `recupere le stash` +1 | powershell | — | — |
| 20 | `git_last_commit` | Voir le dernier commit en detail | `dernier commit`, `last commit`, `montre le dernier commit` +1 | powershell | — | — |
| 21 | `git_count` | Compter les commits du projet | `combien de commits`, `nombre de commits`, `git count` +1 | powershell | — | — |
| 22 | `node_version` | Version de Node.js | `version node`, `quelle version node`, `node version` +1 | powershell | — | — |
| 23 | `npm_list_global` | Packages NPM globaux | `packages npm globaux`, `npm global`, `npm list global` +1 | powershell | — | — |
| 24 | `ollama_restart` | Redemarrer Ollama | `redemarre ollama`, `restart ollama`, `relance ollama` +1 | powershell | — | — |
| 25 | `ollama_pull` | Telecharger un modele Ollama | `telecharge le modele {model}`, `ollama pull {model}`, `installe le modele {model}` +1 | powershell | model | — |
| 26 | `ollama_list` | Lister les modeles Ollama installes | `liste les modeles ollama`, `modeles ollama installes`, `ollama list` +1 | powershell | — | — |
| 27 | `ollama_remove` | Supprimer un modele Ollama | `supprime le modele {model}`, `ollama rm {model}`, `desinstalle le modele {model}` +1 | powershell | model | Oui |
| 28 | `lm_studio_models` | Modeles charges dans LM Studio (M1, M2, M3) | `modeles lm studio`, `quels modeles lm studio`, `modeles charges lm studio` | powershell | — | — |
| 29 | `uv_sync` | Synchroniser les dependances uv | `uv sync`, `synchronise les dependances`, `sync les packages` +1 | powershell | — | — |
| 30 | `python_test` | Lancer les tests Python du projet | `lance les tests`, `run tests`, `pytest` +2 | powershell | — | — |
| 31 | `python_lint` | Verifier le code avec ruff | `lint le code`, `ruff check`, `verifie le code` +2 | powershell | — | — |
| 32 | `docker_logs` | Voir les logs d'un conteneur Docker | `logs docker de {container}`, `docker logs {container}`, `montre les logs de {container}` | powershell | container | — |
| 33 | `docker_restart` | Redemarrer un conteneur Docker | `redemarre le conteneur {container}`, `docker restart {container}`, `relance {container}` | powershell | container | — |
| 34 | `docker_prune` | Nettoyer les ressources Docker inutilisees | `nettoie docker`, `docker prune`, `clean docker` +1 | powershell | — | Oui |
| 35 | `docker_stats` | Statistiques des conteneurs Docker | `stats docker`, `docker stats`, `ressources docker` +1 | powershell | — | — |
| 36 | `turbo_lines` | Compter les lignes de code du projet turbo | `combien de lignes de code`, `lignes de code turbo`, `lines of code` +2 | powershell | — | — |
| 37 | `turbo_size` | Taille totale du projet turbo | `taille du projet turbo`, `poids du projet`, `combien pese turbo` +1 | powershell | — | — |
| 38 | `turbo_files` | Compter les fichiers du projet turbo | `combien de fichiers turbo`, `nombre de fichiers`, `fichiers du projet` +1 | powershell | — | — |
| 39 | `lms_status` | Statut du serveur LM Studio local | `statut lm studio`, `lm studio status`, `etat lm studio` +2 | powershell | — | — |
| 40 | `lms_list_loaded` | Modeles actuellement charges dans LM Studio local | `modeles charges locaux`, `lms loaded`, `quels modeles tourment` +2 | powershell | — | — |
| 41 | `lms_load_model` | Charger un modele dans LM Studio local | `charge le modele {model}`, `lms load {model}`, `load {model} dans lm studio` +1 | powershell | model | — |
| 42 | `lms_unload_model` | Decharger un modele de LM Studio local | `decharge le modele {model}`, `lms unload {model}`, `unload {model}` +1 | powershell | model | — |
| 43 | `lms_list_available` | Lister les modeles disponibles sur le disque | `modeles disponibles lm studio`, `lms list`, `quels modeles j'ai` +1 | powershell | — | — |
| 44 | `git_status_turbo` | Statut git du projet turbo | `git status`, `statut git`, `etat du repo` +1 | powershell | — | — |
| 45 | `git_log_short` | Derniers 10 commits (resume) | `historique git`, `git log`, `derniers commits` +2 | powershell | — | — |
| 46 | `git_remote_info` | Informations sur le remote git | `remote git`, `git remote`, `quel remote` +2 | powershell | — | — |
| 47 | `ouvrir_telegram` | Ouvrir Telegram Desktop | `ouvre telegram`, `lance telegram`, `va sur telegram` +1 | app_open | — | — |
| 48 | `ouvrir_whatsapp` | Ouvrir WhatsApp Desktop | `ouvre whatsapp`, `lance whatsapp`, `va sur whatsapp` +1 | app_open | — | — |
| 49 | `ouvrir_slack` | Ouvrir Slack Desktop | `ouvre slack`, `lance slack`, `va sur slack` +1 | app_open | — | — |
| 50 | `ouvrir_teams` | Ouvrir Microsoft Teams | `ouvre teams`, `lance teams`, `va sur teams` +2 | app_open | — | — |
| 51 | `bun_version` | Version de Bun | `version bun`, `quelle version bun`, `bun version` | powershell | — | — |
| 52 | `deno_version` | Version de Deno | `version deno`, `quelle version deno`, `deno version` | powershell | — | — |
| 53 | `rust_version` | Version de Rust/Cargo | `version rust`, `quelle version rust`, `rustc version` +2 | powershell | — | — |
| 54 | `python_uv_version` | Version de Python et uv | `version python`, `quelle version python`, `python version` +1 | powershell | — | — |
| 55 | `turbo_recent_changes` | Fichiers modifies recemment dans turbo | `fichiers recents turbo`, `modifications recentes`, `quoi de modifie recemment` +1 | powershell | — | — |
| 56 | `turbo_todo` | Lister les TODO dans le code turbo | `liste les todo`, `todo dans le code`, `quels todo reste` +2 | powershell | — | — |
| 57 | `git_blame_file` | Git blame sur un fichier | `git blame de {fichier}`, `blame {fichier}`, `qui a modifie {fichier}` +1 | powershell | fichier | — |
| 58 | `git_clean_branches` | Nettoyer les branches git mergees | `nettoie les branches`, `clean branches`, `supprime les branches mergees` +1 | powershell | — | — |
| 59 | `git_contributors` | Lister les contributeurs du projet | `contributeurs git`, `qui a contribue`, `git contributors` +1 | powershell | — | — |
| 60 | `git_file_history` | Historique d'un fichier | `historique du fichier {fichier}`, `git log de {fichier}`, `modifications de {fichier}` | powershell | fichier | — |
| 61 | `git_undo_last` | Annuler le dernier commit (soft reset) | `annule le dernier commit`, `undo last commit`, `git undo` +1 | powershell | — | Oui |
| 62 | `npm_audit` | Audit de securite NPM | `npm audit`, `audit securite npm`, `vulnerabilites npm` +1 | powershell | — | — |
| 63 | `npm_outdated` | Packages NPM obsoletes | `npm outdated`, `packages npm a jour`, `quels packages npm a mettre a jour` +1 | powershell | — | — |
| 64 | `pip_outdated` | Packages Python obsoletes | `pip outdated`, `packages python a mettre a jour`, `quels packages python perime` | powershell | — | — |
| 65 | `python_repl` | Lancer un REPL Python | `lance python`, `python repl`, `ouvre python` +1 | powershell | — | — |
| 66 | `kill_port` | Tuer le processus sur un port specifique | `tue le port {port}`, `kill port {port}`, `libere le port {port}` +1 | powershell | port | Oui |
| 67 | `qui_ecoute_port` | Quel processus ecoute sur un port | `qui ecoute sur le port {port}`, `quel process sur {port}`, `port {port} utilise par` +1 | powershell | port | — |
| 68 | `ports_dev_status` | Statut des ports dev courants (3000, 5173, 8080, 8000, 9742) | `statut des ports dev`, `ports dev`, `quels ports dev tournent` +1 | powershell | — | — |
| 69 | `ollama_vram_detail` | Detail VRAM utilisee par chaque modele Ollama | `vram ollama detail`, `ollama vram`, `memoire ollama` +1 | powershell | — | — |
| 70 | `ollama_stop_all` | Decharger tous les modeles Ollama de la VRAM | `decharge tous les modeles ollama`, `ollama stop all`, `libere la vram ollama` +1 | powershell | — | Oui |
| 71 | `git_reflog` | Voir le reflog git (historique complet) | `git reflog`, `reflog`, `historique complet git` +1 | powershell | — | — |
| 72 | `git_tag_list` | Lister les tags git | `tags git`, `git tags`, `liste les tags` +2 | powershell | — | — |
| 73 | `git_search_commits` | Rechercher dans les messages de commit | `cherche dans les commits {requete}`, `git search {requete}`, `commit contenant {requete}` +1 | powershell | requete | — |
| 74 | `git_repo_size` | Taille du depot git | `taille du repo git`, `poids du git`, `git size` +1 | powershell | — | — |
| 75 | `git_stash_list` | Lister les stash git | `liste les stash`, `git stash list`, `stash en attente` +1 | powershell | — | — |
| 76 | `git_diff_staged` | Voir les modifications stagees (pret a commit) | `diff staged`, `git diff staged`, `quoi va etre commite` +1 | powershell | — | — |
| 77 | `docker_images_list` | Lister les images Docker locales | `images docker`, `docker images`, `liste les images docker` +1 | powershell | — | — |
| 78 | `docker_volumes` | Lister les volumes Docker | `volumes docker`, `docker volumes`, `liste les volumes docker` +1 | powershell | — | — |
| 79 | `docker_networks` | Lister les reseaux Docker | `reseaux docker`, `docker networks`, `liste les networks docker` +1 | powershell | — | — |
| 80 | `docker_disk_usage` | Espace disque utilise par Docker | `espace docker`, `docker disk usage`, `combien pese docker` +1 | powershell | — | — |
| 81 | `winget_search` | Rechercher un package via winget | `winget search {requete}`, `cherche {requete} sur winget`, `package winget {requete}` +1 | powershell | requete | — |
| 82 | `winget_list_installed` | Lister les apps installees via winget | `winget list`, `apps winget`, `inventaire winget` +1 | powershell | — | — |
| 83 | `winget_upgrade_all` | Mettre a jour toutes les apps via winget | `winget upgrade all`, `mets a jour tout winget`, `update tout winget` +1 | powershell | — | Oui |
| 84 | `code_extensions_list` | Lister les extensions VSCode installees | `extensions vscode`, `liste les extensions`, `vscode extensions` +1 | powershell | — | — |
| 85 | `code_install_ext` | Installer une extension VSCode | `installe l'extension {ext}`, `vscode install {ext}`, `ajoute l'extension {ext}` +1 | powershell | ext | — |
| 86 | `ssh_keys_list` | Lister les cles SSH | `cles ssh`, `ssh keys`, `liste les cles ssh` +1 | powershell | — | — |
| 87 | `npm_cache_clean` | Nettoyer le cache NPM | `nettoie le cache npm`, `npm cache clean`, `clean npm cache` +1 | powershell | — | — |
| 88 | `uv_pip_tree` | Arbre de dependances Python du projet | `arbre de dependances`, `pip tree`, `dependency tree` +2 | powershell | — | — |
| 89 | `pip_show_package` | Details d'un package Python installe | `details du package {package}`, `pip show {package}`, `info sur {package}` +1 | powershell | package | — |
| 90 | `turbo_imports` | Imports utilises dans le projet turbo | `imports du projet`, `quels imports`, `dependances importees` +1 | powershell | — | — |
| 91 | `python_format_check` | Verifier le formatage Python avec ruff format | `verifie le formatage`, `ruff format check`, `check formatting` +1 | powershell | — | — |
| 92 | `python_type_check` | Verifier les types Python (pyright/mypy) | `verifie les types`, `type check`, `pyright check` +2 | powershell | — | — |
| 93 | `curl_test_endpoint` | Tester un endpoint HTTP | `teste l'endpoint {url}`, `curl {url}`, `ping http {url}` +1 | powershell | url | — |
| 94 | `n8n_workflows_list` | Lister les workflows n8n actifs | `workflows n8n`, `liste les workflows`, `n8n actifs` +1 | powershell | — | — |
| 95 | `git_worktree_list` | Lister les worktrees git | `worktrees git`, `git worktrees`, `liste les worktrees` +1 | powershell | — | — |
| 96 | `git_submodule_status` | Statut des submodules git | `submodules git`, `git submodules`, `etat des submodules` +1 | powershell | — | — |
| 97 | `git_cherry_unpicked` | Commits non cherry-picked entre branches | `git cherry`, `commits non picks`, `cherry pick restant` +1 | powershell | — | — |
| 98 | `git_branch_age` | Age de chaque branche git | `age des branches`, `branches vieilles`, `quand les branches ont ete crees` +1 | powershell | — | — |
| 99 | `git_commit_stats` | Statistiques de commits (par jour/semaine) | `stats commits`, `frequence commits`, `git stats` +1 | powershell | — | — |
| 100 | `docker_compose_up` | Docker compose up (demarrer les services) | `docker compose up`, `lance les conteneurs`, `demarre docker compose` +1 | powershell | — | — |
| 101 | `docker_compose_down` | Docker compose down (arreter les services) | `docker compose down`, `arrete les conteneurs`, `stop docker compose` +1 | powershell | — | — |
| 102 | `docker_compose_logs` | Voir les logs Docker Compose | `logs docker compose`, `compose logs`, `docker compose logs` +1 | powershell | — | — |
| 103 | `docker_compose_ps` | Statut des services Docker Compose | `services docker compose`, `compose ps`, `docker compose status` +1 | powershell | — | — |
| 104 | `uv_cache_clean` | Nettoyer le cache uv | `nettoie le cache uv`, `uv cache clean`, `clean cache python` +1 | powershell | — | — |
| 105 | `uv_pip_install` | Installer un package Python via uv | `installe {package} python`, `uv pip install {package}`, `ajoute {package}` +1 | powershell | package | — |
| 106 | `turbo_test_file` | Lancer un fichier de test specifique | `teste le fichier {fichier}`, `pytest {fichier}`, `lance le test {fichier}` +1 | powershell | fichier | — |
| 107 | `turbo_coverage` | Couverture de tests du projet turbo | `coverage turbo`, `couverture de tests`, `test coverage` +2 | powershell | — | — |
| 108 | `openssl_version` | Version d'OpenSSL | `version openssl`, `openssl version`, `quelle version ssl` | powershell | — | — |
| 109 | `git_version` | Version de Git | `version git`, `git version`, `quelle version git` | powershell | — | — |
| 110 | `cuda_version` | Version de CUDA installee | `version cuda`, `cuda version`, `quelle version cuda` +1 | powershell | — | — |
| 111 | `powershell_version` | Version de PowerShell | `version powershell`, `powershell version`, `quelle version powershell` | powershell | — | — |
| 112 | `dotnet_version` | Versions de .NET installees | `version dotnet`, `dotnet version`, `quelle version net` +1 | powershell | — | — |
| 113 | `turbo_skills_count` | Compter les skills et commandes vocales du projet | `combien de skills`, `nombre de commandes vocales`, `inventaire skills` +1 | powershell | — | — |
| 114 | `turbo_find_duplicates` | Detecter les commandes vocales en doublon | `cherche les doublons`, `duplicates commands`, `commandes en double` +1 | powershell | — | — |
| 115 | `turbo_generate_docs` | Regenerer la documentation des commandes vocales | `regenere la doc`, `update la doc vocale`, `genere la doc commandes` +1 | powershell | — | — |
| 116 | `turbo_generate_readme` | Regenerer la section commandes du README | `regenere le readme`, `update le readme`, `genere le readme commandes` +1 | powershell | — | — |
| 117 | `check_all_versions` | Toutes les versions d'outils installes | `toutes les versions`, `all versions`, `inventaire outils` +1 | powershell | — | — |
| 118 | `env_check_paths` | Verifier que les outils essentiels sont dans le PATH | `check le path`, `outils disponibles`, `verifier le path` +1 | powershell | — | — |
| 119 | `disk_space_summary` | Resume espace disque pour le dev | `espace disque dev`, `combien de place pour coder`, `place restante` +1 | powershell | — | — |
| 120 | `git_today` | Commits d'aujourd'hui | `commits du jour`, `git today`, `quoi de neuf aujourd'hui` +1 | powershell | — | — |
| 121 | `git_this_week` | Commits de cette semaine | `commits de la semaine`, `git this week`, `cette semaine en git` +1 | powershell | — | — |
| 122 | `git_push_turbo` | Pusher les commits du projet turbo | `push turbo`, `git push`, `pousse le code` +1 | powershell | — | Oui |
| 123 | `git_pull_turbo` | Puller les commits du projet turbo | `pull turbo`, `git pull`, `recupere les commits` +1 | powershell | — | — |
| 124 | `wt_split_horizontal` | Diviser le terminal Windows horizontalement | `split terminal horizontal`, `divise le terminal`, `terminal cote a cote` +1 | powershell | — | — |
| 125 | `wt_split_vertical` | Diviser le terminal Windows verticalement | `split terminal vertical`, `divise le terminal vertical`, `nouveau panneau vertical` | powershell | — | — |
| 126 | `wt_new_tab` | Nouvel onglet dans Windows Terminal | `nouvel onglet terminal`, `new tab terminal`, `nouveau tab wt` +1 | powershell | — | — |
| 127 | `wt_new_tab_powershell` | Nouvel onglet PowerShell dans Windows Terminal | `terminal powershell`, `onglet powershell`, `ouvre un powershell` +1 | powershell | — | — |
| 128 | `wt_new_tab_cmd` | Nouvel onglet CMD dans Windows Terminal | `terminal cmd`, `onglet cmd`, `ouvre un cmd` +1 | powershell | — | — |
| 129 | `wt_quake_mode` | Ouvrir le terminal en mode quake (dropdown) | `terminal quake`, `quake mode`, `terminal dropdown` +1 | hotkey | — | — |
| 130 | `vscode_zen_mode` | Activer le mode zen dans VSCode | `mode zen vscode`, `zen mode`, `vscode zen` +2 | hotkey | — | — |
| 131 | `vscode_format_document` | Formater le document dans VSCode | `formate le document`, `format code`, `prettier` +2 | hotkey | — | — |
| 132 | `vscode_word_wrap` | Basculer le retour a la ligne dans VSCode | `word wrap vscode`, `retour a la ligne`, `toggle wrap` +2 | hotkey | — | — |
| 133 | `vscode_minimap` | Afficher/masquer la minimap VSCode | `minimap vscode`, `toggle minimap`, `carte du code` +1 | powershell | — | — |
| 134 | `vscode_multi_cursor_down` | Ajouter un curseur en dessous dans VSCode | `multi curseur bas`, `curseur en dessous`, `ctrl alt down` +1 | hotkey | — | — |
| 135 | `vscode_multi_cursor_up` | Ajouter un curseur au dessus dans VSCode | `multi curseur haut`, `curseur au dessus`, `ctrl alt up` +1 | hotkey | — | — |
| 136 | `vscode_rename_symbol` | Renommer un symbole dans VSCode (refactoring) | `renomme le symbole`, `rename symbol`, `refactor rename` +2 | hotkey | — | — |
| 137 | `vscode_go_to_definition` | Aller a la definition dans VSCode | `va a la definition`, `go to definition`, `f12 vscode` +1 | hotkey | — | — |
| 138 | `vscode_peek_definition` | Apercu de la definition (peek) dans VSCode | `peek definition`, `apercu definition`, `alt f12` +1 | hotkey | — | — |
| 139 | `vscode_find_all_references` | Trouver toutes les references dans VSCode | `toutes les references`, `find references`, `shift f12` +2 | hotkey | — | — |
| 140 | `vscode_fold_all` | Plier tout le code dans VSCode | `plie tout le code`, `fold all`, `ferme les blocs` +2 | hotkey | — | — |
| 141 | `vscode_unfold_all` | Deplier tout le code dans VSCode | `deplie tout le code`, `unfold all`, `ouvre les blocs` +2 | hotkey | — | — |
| 142 | `vscode_toggle_comment` | Commenter/decommenter la ligne ou selection | `commente`, `decommente`, `toggle comment` +2 | hotkey | — | — |
| 143 | `vscode_problems_panel` | Ouvrir le panneau des problemes VSCode | `panneau problemes`, `errors vscode`, `problems panel` +2 | hotkey | — | — |
| 144 | `docker_ps_all` | Lister tous les conteneurs Docker | `tous les conteneurs`, `docker ps all`, `conteneurs docker` +1 | powershell | — | — |
| 145 | `docker_logs_last` | Logs du dernier conteneur lance | `logs docker`, `docker logs`, `logs du conteneur` +1 | powershell | — | — |
| 146 | `pytest_turbo` | Lancer les tests pytest du projet turbo | `lance les tests`, `pytest`, `run tests` +2 | powershell | — | — |
| 147 | `pytest_last_failed` | Relancer les tests qui ont echoue | `relance les tests echoues`, `pytest lf`, `rerun failed` +1 | powershell | — | — |
| 148 | `ruff_check` | Lancer ruff (linter Python) sur turbo | `ruff check`, `lint python`, `verifie le code python` +1 | powershell | — | — |
| 149 | `ruff_format` | Formater le code Python avec ruff format | `ruff format`, `formate le python`, `format python` +1 | powershell | — | — |
| 150 | `mypy_check` | Verifier les types Python avec mypy | `mypy check`, `verifie les types`, `type check python` +1 | powershell | — | — |
| 151 | `pip_list_turbo` | Lister les packages Python du projet turbo | `packages python`, `pip list`, `quels packages python` +2 | powershell | — | — |
| 152 | `count_lines_python` | Compter les lignes de code Python du projet | `combien de lignes de code`, `lignes python`, `count lines` +2 | powershell | — | — |
| 153 | `sqlite_jarvis` | Ouvrir la base JARVIS en SQLite | `ouvre la base jarvis`, `sqlite jarvis`, `base de donnees jarvis` +1 | powershell | — | — |
| 154 | `sqlite_etoile` | Explorer la base etoile.db | `ouvre etoile db`, `base etoile`, `sqlite etoile` +1 | powershell | — | — |
| 155 | `sqlite_tables` | Lister les tables d'une base SQLite | `tables sqlite {db}`, `quelles tables dans {db}`, `schema {db}` +1 | powershell | db | — |
| 156 | `redis_ping` | Ping Redis local | `ping redis`, `redis ok`, `test redis` +1 | powershell | — | — |
| 157 | `redis_info` | Informations Redis (memoire, clients) | `info redis`, `redis info`, `etat redis` +1 | powershell | — | — |
| 158 | `turbo_file_count` | Nombre de fichiers par type dans turbo | `combien de fichiers turbo`, `types de fichiers`, `file count` +1 | powershell | — | — |
| 159 | `turbo_todo_scan` | Scanner les TODO/FIXME/HACK dans le code | `trouve les todo`, `scan todo`, `fixme dans le code` +2 | powershell | — | — |
| 160 | `turbo_import_graph` | Voir les imports entre modules turbo | `graph des imports`, `imports turbo`, `dependances modules` +1 | powershell | — | — |
| 161 | `git_cherry_pick` | Cherry-pick un commit specifique | `cherry pick {hash}`, `git cherry pick {hash}`, `prends le commit {hash}` | powershell | hash | — |
| 162 | `git_tags` | Lister les tags git | `tags git`, `quels tags`, `git tags` +2 | powershell | — | — |
| 163 | `git_branch_create` | Creer une nouvelle branche git | `cree une branche {branch}`, `nouvelle branche {branch}`, `git branch {branch}` | powershell | branch | — |
| 164 | `git_branch_delete` | Supprimer une branche git locale | `supprime la branche {branch}`, `delete branch {branch}`, `git branch delete {branch}` | powershell | branch | Oui |
| 165 | `git_branch_switch` | Changer de branche git | `va sur la branche {branch}`, `switch {branch}`, `checkout {branch}` +1 | powershell | branch | — |
| 166 | `git_merge_branch` | Merger une branche dans la branche actuelle | `merge {branch}`, `fusionne {branch}`, `git merge {branch}` +1 | powershell | branch | — |
| 167 | `ssh_keygen` | Generer une nouvelle cle SSH | `genere une cle ssh`, `ssh keygen`, `nouvelle cle ssh` +1 | powershell | — | — |
| 168 | `ssh_pubkey` | Afficher la cle publique SSH | `montre ma cle ssh`, `cle publique ssh`, `ssh public key` +1 | powershell | — | — |
| 169 | `ssh_known_hosts` | Voir les hosts SSH connus | `hosts ssh connus`, `known hosts`, `serveurs ssh` +1 | powershell | — | — |
| 170 | `cargo_build` | Compiler un projet Rust (cargo build) | `cargo build`, `compile en rust`, `build rust` +1 | powershell | — | — |
| 171 | `cargo_test` | Lancer les tests Rust (cargo test) | `cargo test`, `tests rust`, `test en rust` +1 | powershell | — | — |
| 172 | `cargo_clippy` | Lancer le linter Rust (clippy) | `cargo clippy`, `lint rust`, `clippy rust` +1 | powershell | — | — |
| 173 | `npm_run_dev` | Lancer npm run dev | `npm run dev`, `lance le dev node`, `start node dev` +1 | powershell | — | — |
| 174 | `npm_run_build` | Lancer npm run build | `npm run build`, `build node`, `compile le frontend` +1 | powershell | — | — |
| 175 | `python_profile_turbo` | Profiler le startup de JARVIS | `profile jarvis`, `temps de demarrage`, `performance startup` +1 | powershell | — | — |
| 176 | `python_memory_usage` | Mesurer la memoire Python du projet | `memoire python`, `python memory`, `consommation python` +1 | powershell | — | — |
| 177 | `uv_add_package` | Ajouter un package Python avec uv | `uv add {package}`, `installe {package}`, `ajoute le package {package}` +1 | powershell | package | — |
| 178 | `uv_remove_package` | Supprimer un package Python avec uv | `uv remove {package}`, `desinstalle {package}`, `enleve {package}` +1 | powershell | package | — |
| 179 | `uv_lock` | Regenerer le lockfile uv | `uv lock`, `lock les deps`, `regenere le lockfile` +1 | powershell | — | — |
| 180 | `port_in_use` | Trouver quel processus utilise un port | `qui utilise le port {port}`, `port {port} occupe`, `process sur port {port}` +1 | powershell | port | — |
| 181 | `env_var_get` | Lire une variable d'environnement | `variable {var}`, `env {var}`, `valeur de {var}` +1 | powershell | var | — |
| 182 | `tree_turbo` | Arborescence du projet turbo (2 niveaux) | `arborescence turbo`, `tree turbo`, `structure du projet` +1 | powershell | — | — |
| 183 | `gh_create_issue` | Creer une issue GitHub | `cree une issue {titre}`, `nouvelle issue {titre}`, `github issue {titre}` +1 | powershell | titre | — |
| 184 | `gh_list_issues` | Lister les issues GitHub ouvertes | `liste les issues`, `issues ouvertes`, `github issues` +1 | powershell | — | — |
| 185 | `gh_list_prs` | Lister les pull requests GitHub | `liste les pr`, `pull requests`, `github prs` +1 | powershell | — | — |
| 186 | `gh_view_pr` | Voir les details d'une PR | `montre la pr {num}`, `detail pr {num}`, `github pr {num}` +1 | powershell | num | — |
| 187 | `gh_pr_checks` | Voir les checks d'une PR | `checks de la pr {num}`, `status pr {num}`, `ci pr {num}` +1 | powershell | num | — |
| 188 | `gh_repo_view` | Voir les infos du repo GitHub courant | `info du repo`, `github repo info`, `details du repo` +1 | powershell | — | — |
| 189 | `gh_workflow_list` | Lister les workflows GitHub Actions | `workflows github`, `github actions`, `liste les workflows` +1 | powershell | — | — |
| 190 | `gh_release_list` | Lister les releases GitHub | `releases github`, `liste les releases`, `versions publiees` +1 | powershell | — | — |
| 191 | `go_build` | Compiler un projet Go | `go build`, `compile en go`, `build le projet go` | powershell | — | — |
| 192 | `go_test` | Lancer les tests Go | `go test`, `tests go`, `lance les tests go` +1 | powershell | — | — |
| 193 | `go_fmt` | Formater le code Go | `go fmt`, `formate le go`, `gofmt` | powershell | — | — |
| 194 | `go_mod_tidy` | Nettoyer les dependances Go | `go mod tidy`, `nettoie les deps go`, `clean go modules` | powershell | — | — |
| 195 | `venv_create` | Creer un environnement virtuel Python | `cree un venv`, `nouveau virtualenv`, `python venv` +1 | powershell | — | — |
| 196 | `venv_activate` | Activer le virtualenv courant | `active le venv`, `activate venv`, `source venv` | powershell | — | — |
| 197 | `conda_list_envs` | Lister les environnements Conda | `conda envs`, `liste les envs conda`, `quels environnements conda` | powershell | — | — |
| 198 | `conda_install_pkg` | Installer un package Conda | `conda install {package}`, `installe avec conda {package}` | powershell | package | — |
| 199 | `curl_get` | Faire un GET sur une URL | `curl get {url}`, `requete get {url}`, `test api {url}` +1 | powershell | url | — |
| 200 | `curl_post_json` | Faire un POST JSON sur une URL | `curl post {url}`, `post json {url}`, `envoie a {url}` | powershell | url | — |
| 201 | `api_health_check` | Verifier si une API repond (ping HTTP) | `ping api {url}`, `api en ligne {url}`, `health check {url}` +1 | powershell | url | — |
| 202 | `api_response_time` | Mesurer le temps de reponse d'une URL | `temps de reponse {url}`, `latence de {url}`, `speed test {url}` | powershell | url | — |
| 203 | `lint_ruff_check` | Linter Python avec Ruff | `ruff check`, `lint python`, `verifie le code python` +1 | powershell | — | — |
| 204 | `lint_ruff_fix` | Auto-fixer les erreurs Ruff | `ruff fix`, `fixe le lint`, `corrige ruff` +1 | powershell | — | — |
| 205 | `format_black` | Formater Python avec Black | `black format`, `formate avec black`, `black le code` | powershell | — | — |
| 206 | `lint_mypy` | Verifier les types Python avec mypy | `mypy check`, `verifie les types`, `type check python` +1 | powershell | — | — |
| 207 | `lint_eslint` | Linter JavaScript avec ESLint | `eslint`, `lint javascript`, `verifie le js` +1 | powershell | — | — |
| 208 | `format_prettier` | Formater JS/TS avec Prettier | `prettier format`, `formate avec prettier`, `prettier le code` | powershell | — | — |
| 209 | `logs_turbo` | Voir les derniers logs JARVIS | `logs jarvis`, `dernieres logs`, `montre les logs` +1 | powershell | — | — |
| 210 | `logs_windows_errors` | Voir les erreurs recentes Windows | `erreurs windows`, `logs erreurs systeme`, `event log errors` +1 | powershell | — | — |
| 211 | `logs_clear_turbo` | Vider les logs JARVIS | `vide les logs`, `efface les logs`, `clear les logs` +1 | powershell | — | — |
| 212 | `logs_search` | Chercher dans les logs JARVIS | `cherche dans les logs {pattern}`, `grep les logs {pattern}`, `logs contenant {pattern}` | powershell | pattern | — |
| 213 | `netstat_listen` | Voir les ports en ecoute | `ports en ecoute`, `quels ports ouverts`, `netstat listen` +1 | powershell | — | — |
| 214 | `whois_domain` | Whois d'un domaine | `whois {domaine}`, `info domaine {domaine}`, `proprietaire de {domaine}` | powershell | domaine | — |
| 215 | `ssl_check` | Verifier le certificat SSL d'un site | `check ssl {domaine}`, `certificat ssl {domaine}`, `expire quand {domaine}` +1 | powershell | domaine | — |
| 216 | `dns_lookup` | Resoudre un domaine (DNS lookup complet) | `dns {domaine}`, `resoudre {domaine}`, `ip de {domaine}` +1 | powershell | domaine | — |
| 217 | `pytest_verbose` | Lancer pytest en mode verbose | `tests verbose`, `pytest verbose`, `lance les tests en detail` +1 | powershell | — | — |
| 218 | `pytest_file` | Lancer pytest sur un fichier specifique | `teste le fichier {fichier}`, `pytest {fichier}`, `lance les tests de {fichier}` | powershell | fichier | — |
| 219 | `pytest_coverage` | Lancer pytest avec couverture de code | `tests avec couverture`, `pytest coverage`, `code coverage` +1 | powershell | — | — |
| 220 | `pytest_markers` | Lister les markers pytest disponibles | `markers pytest`, `pytest markers`, `quels markers` | powershell | — | — |
| 221 | `pytest_quick` | Tests rapides (fail at first error) | `tests rapides`, `pytest quick`, `teste vite fait` +1 | powershell | — | — |
| 222 | `sqlite_query` | Executer une requete SQLite | `sqlite {requete}`, `requete sqlite {requete}`, `query sqlite {requete}` | powershell | requete | — |
| 223 | `sqlite_schema` | Voir le schema d'une table | `schema de {table}`, `structure table {table}`, `describe {table}` | powershell | table | — |
| 224 | `etoile_count` | Compter les entrees dans etoile.db | `combien dans etoile`, `entries etoile`, `taille etoile db` | powershell | — | — |
| 225 | `etoile_query` | Requete sur etoile.db | `query etoile {requete}`, `etoile db {requete}`, `cherche dans etoile {requete}` | powershell | requete | — |
| 226 | `db_size_all` | Taille de toutes les bases de donnees | `taille des bases`, `poids des db`, `db sizes` +1 | powershell | — | — |
| 227 | `json_validate` | Valider un fichier JSON | `valide le json {fichier}`, `json valide {fichier}`, `check json {fichier}` | powershell | fichier | — |
| 228 | `json_pretty_file` | Formatter un fichier JSON (pretty print) | `formate le json {fichier}`, `pretty json {fichier}`, `indente le json {fichier}` | powershell | fichier | — |
| 229 | `csv_to_json` | Convertir un CSV en JSON | `csv en json {fichier}`, `convertis le csv {fichier}`, `csv to json {fichier}` | powershell | fichier | — |
| 230 | `count_lines_file` | Compter les lignes d'un fichier | `combien de lignes {fichier}`, `lines count {fichier}`, `compte les lignes {fichier}` | powershell | fichier | — |
| 231 | `count_lines_src` | Compter les lignes de code du projet turbo | `lignes de code turbo`, `combien de lignes de code`, `loc turbo` +1 | powershell | — | — |
| 232 | `pip_audit` | Auditer les deps Python (vulnerabilites) | `pip audit`, `vulnerabilites python`, `securite deps python` +1 | powershell | — | — |
| 233 | `bandit_scan` | Scanner Python avec Bandit (securite) | `bandit scan`, `securite code python`, `scan bandit` +1 | powershell | — | — |
| 234 | `electron_dev` | Lancer Electron en mode dev | `electron dev`, `lance electron`, `electron en dev` +1 | powershell | — | — |
| 235 | `electron_build` | Builder l'app Electron | `electron build`, `build electron`, `compile electron` +1 | powershell | — | — |
| 236 | `vite_dev` | Lancer Vite en mode dev | `vite dev`, `lance vite`, `serveur vite` +1 | powershell | — | — |
| 237 | `vite_build` | Builder avec Vite | `vite build`, `build vite`, `compile vite` | powershell | — | — |
| 238 | `vite_preview` | Previsualiser le build Vite | `vite preview`, `preview build`, `previsualise le build` | powershell | — | — |
| 239 | `python_profile` | Profiler un script Python | `profile python {script}`, `profiling {script}`, `benchmark python {script}` | powershell | script | — |
| 240 | `benchmark_import_time` | Mesurer le temps d'import de turbo | `temps d'import turbo`, `import time`, `benchmark import` +1 | powershell | — | — |
| 241 | `memory_usage_python` | Utilisation memoire de Python | `memoire python`, `ram python`, `python memory` | powershell | — | — |
| 242 | `n8n_status` | Verifier si n8n tourne | `n8n status`, `est ce que n8n tourne`, `n8n en ligne` | powershell | — | — |
| 243 | `n8n_open` | Ouvrir n8n dans le navigateur | `ouvre n8n`, `va sur n8n`, `lance n8n` | browser | — | — |
| 244 | `n8n_workflows_count` | Compter les workflows n8n | `combien de workflows n8n`, `n8n workflows`, `nombre workflows` | powershell | — | — |
| 245 | `tsc_compile` | Compiler TypeScript | `tsc compile`, `compile typescript`, `typescript build` +1 | powershell | — | — |
| 246 | `tsc_watch` | Lancer TypeScript en mode watch | `tsc watch`, `typescript watch`, `surveille les fichiers ts` | powershell | — | — |
| 247 | `tsc_version` | Version de TypeScript installee | `version typescript`, `tsc version`, `quel typescript` | powershell | — | — |
| 248 | `tsc_check` | Type-check sans compiler | `type check`, `tsc check`, `verifie les types ts` | powershell | — | — |
| 249 | `pip_show` | Infos sur un package Python installe | `pip show {package}`, `info package {package}`, `details de {package}` | powershell | package | — |
| 250 | `npm_info` | Infos sur un package NPM | `npm info {package}`, `details npm {package}`, `package npm {package}` | powershell | package | — |
| 251 | `git_blame` | Voir l'auteur de chaque ligne d'un fichier | `git blame {fichier}`, `qui a ecrit {fichier}`, `blame {fichier}` | powershell | fichier | — |
| 252 | `git_bisect_start` | Demarrer git bisect pour trouver un bug | `git bisect`, `cherche le bug`, `bisect start` | powershell | — | — |
| 253 | `which_command` | Trouver l'emplacement d'une commande | `ou est {cmd}`, `which {cmd}`, `chemin de {cmd}` +1 | powershell | cmd | — |
| 254 | `dev_env_summary` | Resume de l'environnement de dev | `resume dev`, `environnement dev`, `quels outils installes` +1 | powershell | — | — |
| 255 | `redis_keys_count` | Compter les cles Redis | `combien de cles redis`, `redis keys count`, `taille redis` | powershell | — | — |
| 256 | `redis_flush` | Vider la base Redis (ATTENTION) | `vide redis`, `redis flush`, `clear redis` | powershell | — | Oui |
| 257 | `json_path_query` | Extraire une valeur d'un fichier JSON (jq-like) | `extrait du json {fichier} {path}`, `json extract {fichier} {path}` | powershell | fichier, path | — |
| 258 | `yaml_to_json` | Convertir YAML en JSON | `yaml en json {fichier}`, `convertis le yaml {fichier}`, `yaml to json {fichier}` | powershell | fichier | — |
| 259 | `diff_files` | Comparer deux fichiers | `compare {f1} et {f2}`, `diff {f1} {f2}`, `difference entre {f1} {f2}` | powershell | f1, f2 | — |
| 260 | `base64_encode_file` | Encoder un fichier en Base64 | `encode en base64 {fichier}`, `base64 fichier {fichier}` | powershell | fichier | — |
| 261 | `serve_static` | Lancer un serveur HTTP statique (Python) | `serveur http`, `serve static`, `lance un serveur web` +1 | powershell | — | — |
| 262 | `lmstudio_status` | Status des serveurs LM Studio | `status lm studio`, `lm studio en ligne`, `serveurs ia status` | powershell | — | — |
| 263 | `ollama_models_local` | Lister les modeles Ollama disponibles localement | `modeles ollama locaux`, `ollama list`, `quels modeles ollama` | powershell | — | — |
| 264 | `run_python_expr` | Evaluer une expression Python | `python eval {expr}`, `calcule en python {expr}`, `execute python {expr}` | powershell | expr | — |
| 265 | `run_powershell_expr` | Evaluer une expression PowerShell | `powershell eval {expr}`, `execute {expr}` | powershell | expr | — |
| 266 | `generate_uuid` | Generer un UUID et le copier | `genere un uuid`, `nouvel uuid`, `random uuid` +1 | powershell | — | — |
| 267 | `generate_password` | Generer un mot de passe aleatoire | `genere un mot de passe`, `password aleatoire`, `random password` +1 | powershell | — | — |
| 268 | `generate_timestamp` | Generer un timestamp UNIX | `timestamp unix`, `epoch time`, `genere un timestamp` | powershell | — | — |

## Gestion des Fenetres

**13 commandes**

| # | Nom | Description | Declencheurs | Type | Params | Confirm |
|---|-----|-------------|--------------|------|--------|---------|
| 1 | `minimiser_tout` | Minimiser toutes les fenetres | `minimise tout`, `montre le bureau`, `affiche le bureau` +3 | hotkey | — | — |
| 2 | `alt_tab` | Basculer entre les fenetres | `change de fenetre`, `fenetre suivante`, `bascule` +3 | hotkey | — | — |
| 3 | `fermer_fenetre` | Fermer la fenetre active | `ferme la fenetre`, `ferme ca`, `ferme cette fenetre` +2 | hotkey | — | — |
| 4 | `maximiser_fenetre` | Maximiser la fenetre active | `maximise`, `plein ecran`, `maximiser la fenetre` +2 | hotkey | — | — |
| 5 | `minimiser_fenetre` | Minimiser la fenetre active | `minimise`, `reduis la fenetre`, `minimiser` +2 | hotkey | — | — |
| 6 | `fenetre_gauche` | Fenetre a gauche | `fenetre a gauche`, `mets a gauche`, `snap gauche` +2 | hotkey | — | — |
| 7 | `fenetre_droite` | Fenetre a droite | `fenetre a droite`, `mets a droite`, `snap droite` +2 | hotkey | — | — |
| 8 | `focus_fenetre` | Mettre le focus sur une fenetre | `focus sur {titre}`, `va sur la fenetre {titre}`, `montre {titre}` +1 | jarvis_tool | titre | — |
| 9 | `liste_fenetres` | Lister les fenetres ouvertes | `quelles fenetres sont ouvertes`, `liste les fenetres`, `montre les fenetres` +1 | jarvis_tool | — | — |
| 10 | `fenetre_haut_gauche` | Fenetre en haut a gauche | `fenetre en haut a gauche`, `snap haut gauche`, `coin haut gauche` +1 | powershell | — | — |
| 11 | `fenetre_haut_droite` | Fenetre en haut a droite | `fenetre en haut a droite`, `snap haut droite`, `coin haut droite` +1 | powershell | — | — |
| 12 | `fenetre_bas_gauche` | Fenetre en bas a gauche | `fenetre en bas a gauche`, `snap bas gauche`, `coin bas gauche` +1 | powershell | — | — |
| 13 | `fenetre_bas_droite` | Fenetre en bas a droite | `fenetre en bas a droite`, `snap bas droite`, `coin bas droite` +1 | powershell | — | — |

## Fichiers

**45 commandes**

| # | Nom | Description | Declencheurs | Type | Params | Confirm |
|---|-----|-------------|--------------|------|--------|---------|
| 1 | `ouvrir_documents` | Ouvrir le dossier Documents | `ouvre mes documents`, `ouvrir mes documents`, `ouvre documents` +3 | powershell | — | — |
| 2 | `ouvrir_bureau` | Ouvrir le dossier Bureau | `ouvre le bureau`, `ouvrir le bureau`, `affiche le bureau` +4 | powershell | — | — |
| 3 | `ouvrir_dossier` | Ouvrir un dossier specifique | `ouvre le dossier {dossier}`, `ouvrir le dossier {dossier}`, `va dans {dossier}` +1 | powershell | dossier | — |
| 4 | `ouvrir_telechargements` | Ouvrir Telechargements | `ouvre les telechargements`, `ouvre mes telechargements`, `ouvrir telechargements` +1 | powershell | — | — |
| 5 | `ouvrir_images` | Ouvrir le dossier Images | `ouvre mes images`, `ouvre mes photos`, `ouvre le dossier images` +2 | powershell | — | — |
| 6 | `ouvrir_musique` | Ouvrir le dossier Musique | `ouvre ma musique`, `ouvre le dossier musique`, `va dans ma musique` | powershell | — | — |
| 7 | `ouvrir_projets` | Ouvrir le dossier projets | `ouvre mes projets`, `va dans les projets`, `ouvre le dossier turbo` +2 | powershell | — | — |
| 8 | `ouvrir_explorateur` | Ouvrir l'explorateur de fichiers | `ouvre l'explorateur`, `ouvre l'explorateur de fichiers`, `explorateur de fichiers` +1 | hotkey | — | — |
| 9 | `lister_dossier` | Lister le contenu d'un dossier | `que contient {dossier}`, `liste le dossier {dossier}`, `contenu du dossier {dossier}` +1 | jarvis_tool | dossier | — |
| 10 | `creer_dossier` | Creer un nouveau dossier | `cree un dossier {nom}`, `nouveau dossier {nom}`, `cree le dossier {nom}` +4 | jarvis_tool | nom | — |
| 11 | `chercher_fichier` | Chercher un fichier | `cherche le fichier {nom}`, `trouve le fichier {nom}`, `ou est le fichier {nom}` +1 | jarvis_tool | nom | — |
| 12 | `ouvrir_recents` | Ouvrir les fichiers recents | `fichiers recents`, `ouvre les recents`, `derniers fichiers` +1 | powershell | — | — |
| 13 | `ouvrir_temp` | Ouvrir le dossier temporaire | `ouvre le dossier temp`, `fichiers temporaires`, `dossier temp` +1 | powershell | — | — |
| 14 | `ouvrir_appdata` | Ouvrir le dossier AppData | `ouvre appdata`, `dossier appdata`, `ouvre app data` +1 | powershell | — | — |
| 15 | `espace_dossier` | Taille d'un dossier | `taille du dossier {dossier}`, `combien pese {dossier}`, `espace utilise par {dossier}` +1 | powershell | dossier | — |
| 16 | `nombre_fichiers` | Compter les fichiers dans un dossier | `combien de fichiers dans {dossier}`, `nombre de fichiers {dossier}`, `compte les fichiers dans {dossier}` | powershell | dossier | — |
| 17 | `compresser_dossier` | Compresser un dossier en ZIP | `compresse {dossier}`, `zip {dossier}`, `archive {dossier}` +2 | powershell | dossier | — |
| 18 | `decompresser_zip` | Decompresser un fichier ZIP | `decompresse {fichier}`, `unzip {fichier}`, `extrais {fichier}` +2 | powershell | fichier | — |
| 19 | `hash_fichier` | Calculer le hash SHA256 d'un fichier | `hash de {fichier}`, `sha256 de {fichier}`, `checksum de {fichier}` +2 | powershell | fichier | — |
| 20 | `chercher_contenu` | Chercher du texte dans les fichiers | `cherche {texte} dans les fichiers`, `grep {texte}`, `trouve {texte} dans les fichiers` +1 | powershell | texte | — |
| 21 | `derniers_fichiers` | Derniers fichiers modifies | `derniers fichiers modifies`, `fichiers recents`, `quoi de nouveau` +2 | powershell | — | — |
| 22 | `doublons_fichiers` | Trouver les fichiers en double | `fichiers en double`, `doublons`, `trouve les doublons` +2 | powershell | — | — |
| 23 | `gros_fichiers` | Trouver les plus gros fichiers | `plus gros fichiers`, `fichiers les plus lourds`, `gros fichiers` +2 | powershell | — | — |
| 24 | `fichiers_type` | Lister les fichiers d'un type | `fichiers {ext}`, `tous les {ext}`, `liste les {ext}` +2 | powershell | ext | — |
| 25 | `renommer_masse` | Renommer des fichiers en masse | `renomme les fichiers {ancien} en {nouveau}`, `remplace {ancien} par {nouveau} dans les noms` | powershell | ancien, nouveau | — |
| 26 | `dossiers_vides` | Trouver les dossiers vides | `dossiers vides`, `repertoires vides`, `trouve les dossiers vides` +1 | powershell | — | — |
| 27 | `proprietes_fichier` | Proprietes detaillees d'un fichier | `proprietes de {fichier}`, `details de {fichier}`, `info sur {fichier}` +2 | powershell | fichier | — |
| 28 | `copier_fichier` | Copier un fichier vers un dossier | `copie {source} dans {destination}`, `copie {source} vers {destination}`, `duplique {source} dans {destination}` | powershell | source, destination | — |
| 29 | `deplacer_fichier` | Deplacer un fichier | `deplace {source} dans {destination}`, `deplace {source} vers {destination}`, `bouge {source} dans {destination}` | powershell | source, destination | — |
| 30 | `explorer_nouvel_onglet` | Nouvel onglet dans l'Explorateur | `nouvel onglet explorateur`, `onglet explorateur`, `new tab explorer` +1 | powershell | — | — |
| 31 | `dossier_captures` | Ouvrir le dossier captures d'ecran | `dossier captures`, `ouvre les captures`, `dossier screenshots` +2 | powershell | — | — |
| 32 | `taille_dossiers_bureau` | Taille de chaque dossier dans F:\BUREAU | `taille des projets`, `poids des dossiers bureau`, `combien pese chaque projet` +1 | powershell | — | — |
| 33 | `compresser_fichier` | Compresser un dossier en ZIP | `compresse en zip`, `zip le dossier`, `cree un zip` +2 | powershell | — | — |
| 34 | `decompresser_fichier` | Decompresser un fichier ZIP | `decompresse le zip`, `unzip`, `extrais l'archive` +2 | powershell | — | — |
| 35 | `compresser_turbo` | Compresser le projet turbo en ZIP (sans .git ni venv) | `zip turbo`, `archive turbo`, `compresse le projet` +1 | powershell | — | — |
| 36 | `vider_dossier_temp` | Supprimer les fichiers temporaires | `vide le temp`, `nettoie les temporaires`, `clean temp` +1 | powershell | — | Oui |
| 37 | `lister_fichiers_recents` | Lister les 20 fichiers les plus recents sur le bureau | `fichiers recents`, `derniers fichiers`, `quoi de recent` +1 | powershell | — | — |
| 38 | `chercher_gros_fichiers` | Trouver les fichiers > 100 MB sur F: | `gros fichiers partout`, `fichiers enormes`, `quoi prend toute la place` +1 | powershell | — | — |
| 39 | `doublons_bureau` | Detecter les doublons potentiels par nom dans F:\BUREAU | `doublons bureau`, `fichiers en double`, `trouve les doublons` +2 | powershell | — | — |
| 40 | `taille_telechargements` | Taille du dossier Telechargements | `taille telechargements`, `poids downloads`, `combien dans les telechargements` +1 | powershell | — | — |
| 41 | `vider_telechargements` | Vider le dossier Telechargements (fichiers > 30 jours) | `vide les telechargements`, `nettoie les downloads`, `clean downloads` +1 | powershell | — | Oui |
| 42 | `lister_telechargements` | Derniers fichiers telecharges | `derniers telechargements`, `quoi de telecharge`, `recent downloads` +1 | powershell | — | — |
| 43 | `ouvrir_bureau_dossier` | Ouvrir F:\BUREAU dans l'explorateur | `ouvre le bureau`, `dossier bureau`, `va dans bureau` +1 | powershell | — | — |
| 44 | `fichier_recent_modifie` | Trouver le dernier fichier modifie partout | `dernier fichier modifie`, `quoi vient de changer`, `last modified` +1 | powershell | — | — |
| 45 | `compter_fichiers_type` | Compter les fichiers par extension dans un dossier | `compte les fichiers par type`, `extensions dans {path}`, `quels types de fichiers dans {path}` | powershell | path | — |

## Jarvis

**12 commandes**

| # | Nom | Description | Declencheurs | Type | Params | Confirm |
|---|-----|-------------|--------------|------|--------|---------|
| 1 | `historique_commandes` | Voir l'historique des commandes JARVIS | `historique des commandes`, `quelles commandes j'ai utilise`, `dernieres commandes` +1 | powershell | — | — |
| 2 | `jarvis_aide` | Afficher l'aide JARVIS | `aide`, `help`, `quelles commandes` +5 | list_commands | — | — |
| 3 | `jarvis_stop` | Arreter JARVIS | `jarvis stop`, `jarvis arrete`, `arrete jarvis` +11 | exit | — | — |
| 4 | `jarvis_repete` | Repeter la derniere reponse | `repete`, `redis`, `repete ca` +3 | jarvis_repeat | — | — |
| 5 | `jarvis_scripts` | Lister les scripts disponibles | `quels scripts sont disponibles`, `liste les scripts`, `montre les scripts` +1 | jarvis_tool | — | — |
| 6 | `jarvis_projets` | Lister les projets indexes | `quels projets existent`, `liste les projets`, `montre les projets` +1 | jarvis_tool | — | — |
| 7 | `jarvis_notification` | Envoyer une notification | `notifie {message}`, `notification {message}`, `envoie une notification {message}` +1 | jarvis_tool | message | — |
| 8 | `jarvis_skills` | Lister les skills/pipelines appris | `quels skills existent`, `liste les skills`, `montre les skills` +3 | list_commands | — | — |
| 9 | `jarvis_suggestions` | Suggestions d'actions | `que me suggeres tu`, `suggestions`, `quoi faire` +2 | list_commands | — | — |
| 10 | `jarvis_brain_status` | Etat du cerveau JARVIS | `etat du cerveau`, `brain status`, `cerveau jarvis` +2 | jarvis_tool | — | — |
| 11 | `jarvis_brain_learn` | Apprendre de nouveaux patterns | `apprends`, `brain learn`, `auto apprends` +2 | jarvis_tool | — | — |
| 12 | `jarvis_brain_suggest` | Demander une suggestion de skill a l'IA | `suggere un skill`, `brain suggest`, `invente un skill` +2 | jarvis_tool | — | — |

## Launcher

**12 commandes**

| # | Nom | Description | Declencheurs | Type | Params | Confirm |
|---|-----|-------------|--------------|------|--------|---------|
| 1 | `launch_pipeline_10` | Lancer le Pipeline 10 Cycles | `lance le pipeline 10 cycles`, `pipeline 10 cycles`, `pipeline 10` +4 | script | — | Oui |
| 2 | `launch_sniper_10` | Lancer le Sniper 10 Cycles | `lance le sniper 10 cycles`, `sniper 10 cycles`, `sniper 10` +2 | script | — | Oui |
| 3 | `launch_sniper_breakout` | Lancer le Sniper Breakout | `lance sniper breakout`, `sniper breakout`, `detection breakout` +2 | script | — | Oui |
| 4 | `launch_trident` | Lancer Trident Execute (dry run) | `lance trident`, `trident execute`, `execute trident` +2 | script | — | Oui |
| 5 | `launch_hyper_scan` | Lancer l'Hyper Scan V2 | `lance hyper scan`, `hyper scan v2`, `grid computing scan` +2 | script | — | — |
| 6 | `launch_monitor_river` | Lancer le Monitor RIVER Scalp | `lance river`, `monitor river`, `lance le monitor river` +3 | script | — | Oui |
| 7 | `launch_command_center` | Ouvrir le JARVIS Command Center (GUI) | `ouvre le command center`, `command center`, `lance le cockpit` +4 | script | — | — |
| 8 | `launch_electron_app` | Ouvrir JARVIS Electron App | `lance electron`, `jarvis electron`, `ouvre l'application jarvis` +2 | script | — | — |
| 9 | `launch_widget` | Ouvrir le Widget JARVIS | `lance le widget jarvis`, `jarvis widget`, `widget trading` +2 | script | — | — |
| 10 | `launch_disk_cleaner` | Lancer le nettoyeur de disque | `nettoie le disque`, `disk cleaner`, `lance le nettoyeur` +3 | script | — | — |
| 11 | `launch_master_node` | Lancer le Master Interaction Node | `lance le master node`, `master interaction`, `noeud principal` +2 | script | — | — |
| 12 | `launch_fs_agent` | Lancer l'agent fichiers JARVIS | `lance l'agent fichiers`, `fs agent`, `agent systeme fichiers` +2 | script | — | — |

## Media & Volume

**7 commandes**

| # | Nom | Description | Declencheurs | Type | Params | Confirm |
|---|-----|-------------|--------------|------|--------|---------|
| 1 | `media_play_pause` | Play/Pause media | `play`, `pause`, `mets pause` +11 | hotkey | — | — |
| 2 | `media_next` | Piste suivante | `suivant`, `piste suivante`, `chanson suivante` +6 | hotkey | — | — |
| 3 | `media_previous` | Piste precedente | `precedent`, `piste precedente`, `chanson precedente` +9 | hotkey | — | — |
| 4 | `volume_haut` | Augmenter le volume | `monte le volume`, `augmente le volume`, `volume plus fort` +4 | hotkey | — | — |
| 5 | `volume_bas` | Baisser le volume | `baisse le volume`, `diminue le volume`, `volume moins fort` +4 | hotkey | — | — |
| 6 | `muet` | Couper/activer le son | `coupe le son`, `mute`, `silence` +4 | hotkey | — | — |
| 7 | `volume_precis` | Mettre le volume a un niveau precis | `mets le volume a {niveau}`, `volume a {niveau}`, `regle le volume a {niveau}` +1 | powershell | niveau | — |

## Navigation Web

**323 commandes**

| # | Nom | Description | Declencheurs | Type | Params | Confirm |
|---|-----|-------------|--------------|------|--------|---------|
| 1 | `ouvrir_chrome` | Ouvrir Google Chrome | `ouvre chrome`, `ouvrir chrome`, `lance chrome` +7 | app_open | — | — |
| 2 | `ouvrir_comet` | Ouvrir Comet Browser | `ouvre comet`, `ouvrir comet`, `lance comet` +1 | app_open | — | — |
| 3 | `aller_sur_site` | Naviguer vers un site web | `va sur {site}`, `ouvre {site}`, `navigue vers {site}` +5 | browser | site | — |
| 4 | `chercher_google` | Rechercher sur Google | `cherche {requete}`, `recherche {requete}`, `google {requete}` +4 | browser | requete | — |
| 5 | `chercher_youtube` | Rechercher sur YouTube | `cherche sur youtube {requete}`, `youtube {requete}`, `recherche sur youtube {requete}` +1 | browser | requete | — |
| 6 | `ouvrir_gmail` | Ouvrir Gmail | `ouvre gmail`, `ouvrir gmail`, `ouvre mes mails` +6 | browser | — | — |
| 7 | `ouvrir_youtube` | Ouvrir YouTube | `ouvre youtube`, `va sur youtube`, `lance youtube` +2 | browser | — | — |
| 8 | `ouvrir_github` | Ouvrir GitHub | `ouvre github`, `va sur github`, `ouvrir github` | browser | — | — |
| 9 | `ouvrir_tradingview` | Ouvrir TradingView | `ouvre tradingview`, `va sur tradingview`, `lance tradingview` +2 | browser | — | — |
| 10 | `ouvrir_mexc` | Ouvrir MEXC | `ouvre mexc`, `va sur mexc`, `lance mexc` +5 | browser | — | — |
| 11 | `nouvel_onglet` | Ouvrir un nouvel onglet | `nouvel onglet`, `nouveau tab`, `ouvre un nouvel onglet` +1 | hotkey | — | — |
| 12 | `fermer_onglet` | Fermer l'onglet actif | `ferme l'onglet`, `ferme cet onglet`, `ferme le tab` +2 | hotkey | — | — |
| 13 | `mode_incognito` | Ouvrir Chrome en mode incognito | `mode incognito`, `navigation privee`, `ouvre en prive` +2 | powershell | — | — |
| 14 | `historique_chrome` | Ouvrir l'historique Chrome | `historique chrome`, `ouvre l'historique`, `historique navigateur` +1 | hotkey | — | — |
| 15 | `favoris_chrome` | Ouvrir les favoris Chrome | `ouvre les favoris`, `favoris`, `bookmarks` +2 | hotkey | — | — |
| 16 | `telecharger_chrome` | Ouvrir les telechargements Chrome | `telechargements chrome`, `ouvre les downloads`, `mes telechargements navigateur` | hotkey | — | — |
| 17 | `onglet_precedent` | Onglet precedent Chrome | `onglet precedent`, `tab precedent`, `onglet d'avant` +1 | hotkey | — | — |
| 18 | `onglet_suivant` | Onglet suivant Chrome | `onglet suivant`, `tab suivant`, `prochain onglet` +1 | hotkey | — | — |
| 19 | `rouvrir_onglet` | Rouvrir le dernier onglet ferme | `rouvre l'onglet`, `rouvrir onglet`, `restaure l'onglet` +2 | hotkey | — | — |
| 20 | `chrome_favoris` | Ouvrir les favoris Chrome | `ouvre les favoris`, `mes favoris`, `bookmarks` +2 | hotkey | — | — |
| 21 | `chrome_telechargements` | Ouvrir les telechargements Chrome | `telechargements chrome`, `mes telechargements chrome`, `fichiers telecharges` +1 | hotkey | — | — |
| 22 | `chrome_plein_ecran` | Chrome en plein ecran (F11) | `plein ecran`, `chrome plein ecran`, `fullscreen` +2 | hotkey | — | — |
| 23 | `chrome_zoom_plus` | Zoom avant Chrome | `zoom avant chrome`, `agrandir la page`, `plus grand` +2 | hotkey | — | — |
| 24 | `chrome_zoom_moins` | Zoom arriere Chrome | `zoom arriere chrome`, `reduire la page`, `plus petit` +2 | hotkey | — | — |
| 25 | `chrome_zoom_reset` | Reinitialiser le zoom Chrome | `zoom normal`, `zoom 100`, `reinitialise le zoom` +2 | hotkey | — | — |
| 26 | `meteo` | Afficher la meteo | `meteo`, `la meteo`, `quelle meteo` +9 | browser | — | — |
| 27 | `ouvrir_twitter` | Ouvrir Twitter/X | `ouvre twitter`, `va sur twitter`, `ouvre x` +2 | browser | — | — |
| 28 | `ouvrir_reddit` | Ouvrir Reddit | `ouvre reddit`, `va sur reddit`, `lance reddit` +1 | browser | — | — |
| 29 | `ouvrir_linkedin` | Ouvrir LinkedIn | `ouvre linkedin`, `va sur linkedin`, `lance linkedin` +1 | browser | — | — |
| 30 | `ouvrir_instagram` | Ouvrir Instagram | `ouvre instagram`, `va sur instagram`, `lance instagram` +2 | browser | — | — |
| 31 | `ouvrir_tiktok` | Ouvrir TikTok | `ouvre tiktok`, `va sur tiktok`, `lance tiktok` | browser | — | — |
| 32 | `ouvrir_twitch` | Ouvrir Twitch | `ouvre twitch`, `va sur twitch`, `lance twitch` +1 | browser | — | — |
| 33 | `ouvrir_chatgpt` | Ouvrir ChatGPT | `ouvre chatgpt`, `va sur chatgpt`, `lance chatgpt` +2 | browser | — | — |
| 34 | `ouvrir_claude` | Ouvrir Claude AI | `ouvre claude`, `va sur claude`, `lance claude` +2 | browser | — | — |
| 35 | `ouvrir_perplexity` | Ouvrir Perplexity | `ouvre perplexity`, `va sur perplexity`, `lance perplexity` +1 | browser | — | — |
| 36 | `ouvrir_huggingface` | Ouvrir Hugging Face | `ouvre hugging face`, `va sur hugging face`, `lance hugging face` +1 | browser | — | — |
| 37 | `ouvrir_wikipedia` | Ouvrir Wikipedia | `ouvre wikipedia`, `va sur wikipedia`, `lance wikipedia` +1 | browser | — | — |
| 38 | `ouvrir_amazon` | Ouvrir Amazon | `ouvre amazon`, `va sur amazon`, `lance amazon` +1 | browser | — | — |
| 39 | `ouvrir_leboncoin` | Ouvrir Leboncoin | `ouvre leboncoin`, `va sur leboncoin`, `lance leboncoin` +2 | browser | — | — |
| 40 | `ouvrir_netflix` | Ouvrir Netflix | `ouvre netflix`, `va sur netflix`, `lance netflix` | browser | — | — |
| 41 | `ouvrir_spotify_web` | Ouvrir Spotify Web Player | `ouvre spotify web`, `spotify web`, `lance spotify en ligne` +1 | browser | — | — |
| 42 | `ouvrir_disney_plus` | Ouvrir Disney+ | `ouvre disney plus`, `va sur disney plus`, `lance disney` +1 | browser | — | — |
| 43 | `ouvrir_stackoverflow` | Ouvrir Stack Overflow | `ouvre stackoverflow`, `va sur stackoverflow`, `ouvre stack overflow` +1 | browser | — | — |
| 44 | `ouvrir_npmjs` | Ouvrir NPM | `ouvre npm`, `va sur npm`, `ouvre npmjs` +1 | browser | — | — |
| 45 | `ouvrir_pypi` | Ouvrir PyPI | `ouvre pypi`, `va sur pypi`, `lance pypi` +1 | browser | — | — |
| 46 | `ouvrir_docker_hub` | Ouvrir Docker Hub | `ouvre docker hub`, `va sur docker hub`, `lance docker hub` | browser | — | — |
| 47 | `ouvrir_google_drive` | Ouvrir Google Drive | `ouvre google drive`, `va sur google drive`, `ouvre drive` +2 | browser | — | — |
| 48 | `ouvrir_google_docs` | Ouvrir Google Docs | `ouvre google docs`, `va sur google docs`, `ouvre docs` +1 | browser | — | — |
| 49 | `ouvrir_google_sheets` | Ouvrir Google Sheets | `ouvre google sheets`, `va sur google sheets`, `ouvre sheets` +1 | browser | — | — |
| 50 | `ouvrir_google_maps` | Ouvrir Google Maps | `ouvre google maps`, `va sur google maps`, `ouvre maps` +2 | browser | — | — |
| 51 | `ouvrir_google_calendar` | Ouvrir Google Calendar | `ouvre google calendar`, `ouvre l'agenda`, `ouvre le calendrier` +2 | browser | — | — |
| 52 | `ouvrir_notion` | Ouvrir Notion | `ouvre notion`, `va sur notion`, `lance notion` +1 | browser | — | — |
| 53 | `chercher_images` | Rechercher des images sur Google | `cherche des images de {requete}`, `images de {requete}`, `google images {requete}` +1 | browser | requete | — |
| 54 | `chercher_reddit` | Rechercher sur Reddit | `cherche sur reddit {requete}`, `reddit {requete}`, `recherche reddit {requete}` | browser | requete | — |
| 55 | `chercher_wikipedia` | Rechercher sur Wikipedia | `cherche sur wikipedia {requete}`, `wikipedia {requete}`, `wiki {requete}` | browser | requete | — |
| 56 | `chercher_amazon` | Rechercher sur Amazon | `cherche sur amazon {requete}`, `amazon {requete}`, `recherche amazon {requete}` +1 | browser | requete | — |
| 57 | `ouvrir_tradingview_web` | Ouvrir TradingView | `ouvre tradingview`, `va sur tradingview`, `lance tradingview` +1 | browser | — | — |
| 58 | `ouvrir_coingecko` | Ouvrir CoinGecko | `ouvre coingecko`, `va sur coingecko`, `lance coingecko` +1 | browser | — | — |
| 59 | `ouvrir_coinmarketcap` | Ouvrir CoinMarketCap | `ouvre coinmarketcap`, `va sur coinmarketcap`, `lance coinmarketcap` +1 | browser | — | — |
| 60 | `ouvrir_mexc_exchange` | Ouvrir MEXC Exchange | `ouvre mexc`, `va sur mexc`, `lance mexc` +1 | browser | — | — |
| 61 | `ouvrir_dexscreener` | Ouvrir DexScreener | `ouvre dexscreener`, `va sur dexscreener`, `lance dexscreener` +1 | browser | — | — |
| 62 | `ouvrir_telegram_web` | Ouvrir Telegram Web | `ouvre telegram web`, `telegram web`, `telegram en ligne` +1 | browser | — | — |
| 63 | `ouvrir_whatsapp_web` | Ouvrir WhatsApp Web | `ouvre whatsapp web`, `whatsapp web`, `whatsapp en ligne` +1 | browser | — | — |
| 64 | `ouvrir_slack_web` | Ouvrir Slack Web | `ouvre slack web`, `slack web`, `slack en ligne` +1 | browser | — | — |
| 65 | `ouvrir_teams_web` | Ouvrir Microsoft Teams Web | `ouvre teams web`, `teams web`, `teams en ligne` +1 | browser | — | — |
| 66 | `ouvrir_youtube_music` | Ouvrir YouTube Music | `ouvre youtube music`, `youtube music`, `lance youtube music` +1 | browser | — | — |
| 67 | `ouvrir_prime_video` | Ouvrir Amazon Prime Video | `ouvre prime video`, `va sur prime video`, `lance prime video` +1 | browser | — | — |
| 68 | `ouvrir_crunchyroll` | Ouvrir Crunchyroll | `ouvre crunchyroll`, `va sur crunchyroll`, `lance crunchyroll` +1 | browser | — | — |
| 69 | `ouvrir_github_web` | Ouvrir GitHub | `ouvre github`, `va sur github`, `lance github` +1 | browser | — | — |
| 70 | `ouvrir_vercel` | Ouvrir Vercel | `ouvre vercel`, `va sur vercel`, `lance vercel` | browser | — | — |
| 71 | `ouvrir_crates_io` | Ouvrir crates.io (Rust packages) | `ouvre crates io`, `va sur crates`, `crates rust` +1 | browser | — | — |
| 72 | `chercher_video_youtube` | Rechercher sur YouTube | `cherche sur youtube {requete}`, `youtube {requete}`, `recherche youtube {requete}` +1 | browser | requete | — |
| 73 | `chercher_github` | Rechercher sur GitHub | `cherche sur github {requete}`, `github {requete}`, `recherche github {requete}` +1 | browser | requete | — |
| 74 | `chercher_stackoverflow` | Rechercher sur Stack Overflow | `cherche sur stackoverflow {requete}`, `stackoverflow {requete}`, `stack overflow {requete}` | browser | requete | — |
| 75 | `chercher_npm` | Rechercher un package NPM | `cherche sur npm {requete}`, `npm {requete}`, `recherche npm {requete}` +1 | browser | requete | — |
| 76 | `chercher_pypi` | Rechercher un package PyPI | `cherche sur pypi {requete}`, `pypi {requete}`, `recherche pypi {requete}` +1 | browser | requete | — |
| 77 | `ouvrir_google_translate` | Ouvrir Google Translate | `ouvre google translate`, `traducteur`, `google traduction` +2 | browser | — | — |
| 78 | `ouvrir_google_news` | Ouvrir Google Actualites | `ouvre google news`, `google actualites`, `lance les news` +1 | browser | — | — |
| 79 | `ouvrir_figma` | Ouvrir Figma | `ouvre figma`, `va sur figma`, `lance figma` | browser | — | — |
| 80 | `ouvrir_canva` | Ouvrir Canva | `ouvre canva`, `va sur canva`, `lance canva` | browser | — | — |
| 81 | `ouvrir_pinterest` | Ouvrir Pinterest | `ouvre pinterest`, `va sur pinterest`, `lance pinterest` | browser | — | — |
| 82 | `ouvrir_udemy` | Ouvrir Udemy | `ouvre udemy`, `va sur udemy`, `lance udemy` +1 | browser | — | — |
| 83 | `ouvrir_regex101` | Ouvrir Regex101 (testeur de regex) | `ouvre regex101`, `testeur regex`, `lance regex101` +1 | browser | — | — |
| 84 | `ouvrir_jsonformatter` | Ouvrir un formatteur JSON en ligne | `ouvre json formatter`, `formatte du json`, `json en ligne` +1 | browser | — | — |
| 85 | `ouvrir_speedtest` | Ouvrir Speedtest | `ouvre speedtest`, `lance un speed test`, `test de debit` +1 | browser | — | — |
| 86 | `ouvrir_excalidraw` | Ouvrir Excalidraw (tableau blanc) | `ouvre excalidraw`, `tableau blanc`, `lance excalidraw` +1 | browser | — | — |
| 87 | `ouvrir_soundcloud` | Ouvrir SoundCloud | `ouvre soundcloud`, `va sur soundcloud`, `lance soundcloud` | browser | — | — |
| 88 | `ouvrir_google_scholar` | Ouvrir Google Scholar | `ouvre google scholar`, `google scholar`, `recherche academique` +1 | browser | — | — |
| 89 | `chercher_traduction` | Traduire un texte via Google Translate | `traduis {requete}`, `traduction de {requete}`, `translate {requete}` +1 | browser | requete | — |
| 90 | `chercher_google_scholar` | Rechercher sur Google Scholar | `cherche sur scholar {requete}`, `article sur {requete}`, `recherche academique {requete}` +1 | browser | requete | — |
| 91 | `chercher_huggingface` | Rechercher un modele sur Hugging Face | `cherche sur hugging face {requete}`, `modele {requete} huggingface`, `hugging face {requete}` | browser | requete | — |
| 92 | `chercher_docker_hub` | Rechercher une image Docker Hub | `cherche sur docker hub {requete}`, `image docker {requete}`, `docker hub {requete}` | browser | requete | — |
| 93 | `ouvrir_gmail_web` | Ouvrir Gmail | `ouvre gmail`, `va sur gmail`, `lance gmail` +2 | browser | — | — |
| 94 | `ouvrir_google_keep` | Ouvrir Google Keep (notes) | `ouvre google keep`, `ouvre keep`, `lance keep` +2 | browser | — | — |
| 95 | `ouvrir_google_photos` | Ouvrir Google Photos | `ouvre google photos`, `va sur google photos`, `mes photos` +2 | browser | — | — |
| 96 | `ouvrir_google_meet` | Ouvrir Google Meet | `ouvre google meet`, `lance meet`, `google meet` +2 | browser | — | — |
| 97 | `ouvrir_deepl` | Ouvrir DeepL Traducteur | `ouvre deepl`, `va sur deepl`, `lance deepl` +2 | browser | — | — |
| 98 | `ouvrir_wayback_machine` | Ouvrir la Wayback Machine (archive web) | `ouvre wayback machine`, `wayback machine`, `archive internet` +2 | browser | — | — |
| 99 | `ouvrir_codepen` | Ouvrir CodePen | `ouvre codepen`, `va sur codepen`, `lance codepen` +2 | browser | — | — |
| 100 | `ouvrir_jsfiddle` | Ouvrir JSFiddle | `ouvre jsfiddle`, `va sur jsfiddle`, `lance jsfiddle` +1 | browser | — | — |
| 101 | `ouvrir_dev_to` | Ouvrir dev.to (communaute dev) | `ouvre dev to`, `va sur dev to`, `lance dev.to` +2 | browser | — | — |
| 102 | `ouvrir_medium` | Ouvrir Medium | `ouvre medium`, `va sur medium`, `lance medium` +1 | browser | — | — |
| 103 | `ouvrir_hacker_news` | Ouvrir Hacker News | `ouvre hacker news`, `va sur hacker news`, `lance hacker news` +2 | browser | — | — |
| 104 | `ouvrir_producthunt` | Ouvrir Product Hunt | `ouvre product hunt`, `va sur product hunt`, `lance product hunt` +2 | browser | — | — |
| 105 | `ouvrir_coursera` | Ouvrir Coursera | `ouvre coursera`, `va sur coursera`, `lance coursera` +2 | browser | — | — |
| 106 | `ouvrir_kaggle` | Ouvrir Kaggle | `ouvre kaggle`, `va sur kaggle`, `lance kaggle` +2 | browser | — | — |
| 107 | `ouvrir_arxiv` | Ouvrir arXiv (articles scientifiques) | `ouvre arxiv`, `va sur arxiv`, `lance arxiv` +2 | browser | — | — |
| 108 | `ouvrir_gitlab` | Ouvrir GitLab | `ouvre gitlab`, `va sur gitlab`, `lance gitlab` | browser | — | — |
| 109 | `ouvrir_bitbucket` | Ouvrir Bitbucket | `ouvre bitbucket`, `va sur bitbucket`, `lance bitbucket` | browser | — | — |
| 110 | `ouvrir_leetcode` | Ouvrir LeetCode | `ouvre leetcode`, `va sur leetcode`, `lance leetcode` +2 | browser | — | — |
| 111 | `ouvrir_codewars` | Ouvrir Codewars | `ouvre codewars`, `va sur codewars`, `lance codewars` +2 | browser | — | — |
| 112 | `chercher_deepl` | Traduire via DeepL | `traduis avec deepl {requete}`, `deepl {requete}`, `traduction deepl {requete}` +1 | browser | requete | — |
| 113 | `chercher_arxiv` | Rechercher sur arXiv | `cherche sur arxiv {requete}`, `arxiv {requete}`, `paper sur {requete}` +1 | browser | requete | — |
| 114 | `chercher_kaggle` | Rechercher sur Kaggle | `cherche sur kaggle {requete}`, `kaggle {requete}`, `dataset {requete}` +1 | browser | requete | — |
| 115 | `chercher_leetcode` | Rechercher un probleme LeetCode | `cherche sur leetcode {requete}`, `leetcode {requete}`, `probleme {requete} leetcode` | browser | requete | — |
| 116 | `chercher_medium` | Rechercher sur Medium | `cherche sur medium {requete}`, `medium {requete}`, `article medium {requete}` | browser | requete | — |
| 117 | `chercher_hacker_news` | Rechercher sur Hacker News | `cherche sur hacker news {requete}`, `hn {requete}`, `hacker news {requete}` | browser | requete | — |
| 118 | `ouvrir_linear` | Ouvrir Linear (gestion de projet dev) | `ouvre linear`, `va sur linear`, `lance linear` +2 | browser | — | — |
| 119 | `ouvrir_miro` | Ouvrir Miro (whiteboard collaboratif) | `ouvre miro`, `va sur miro`, `lance miro` +2 | browser | — | — |
| 120 | `ouvrir_loom` | Ouvrir Loom (enregistrement ecran) | `ouvre loom`, `va sur loom`, `lance loom` +1 | browser | — | — |
| 121 | `ouvrir_supabase` | Ouvrir Supabase | `ouvre supabase`, `va sur supabase`, `lance supabase` +1 | browser | — | — |
| 122 | `ouvrir_firebase` | Ouvrir Firebase Console | `ouvre firebase`, `va sur firebase`, `lance firebase` +1 | browser | — | — |
| 123 | `ouvrir_railway` | Ouvrir Railway (deploy) | `ouvre railway`, `va sur railway`, `lance railway` +1 | browser | — | — |
| 124 | `ouvrir_cloudflare` | Ouvrir Cloudflare Dashboard | `ouvre cloudflare`, `va sur cloudflare`, `lance cloudflare` +1 | browser | — | — |
| 125 | `ouvrir_render` | Ouvrir Render (hosting) | `ouvre render`, `va sur render`, `lance render` +1 | browser | — | — |
| 126 | `ouvrir_fly_io` | Ouvrir Fly.io | `ouvre fly io`, `va sur fly`, `lance fly io` +1 | browser | — | — |
| 127 | `ouvrir_mdn` | Ouvrir MDN Web Docs | `ouvre mdn`, `va sur mdn`, `docs mdn` +2 | browser | — | — |
| 128 | `ouvrir_devdocs` | Ouvrir DevDocs.io (toute la doc dev) | `ouvre devdocs`, `va sur devdocs`, `lance devdocs` +2 | browser | — | — |
| 129 | `ouvrir_can_i_use` | Ouvrir Can I Use (compatibilite navigateurs) | `ouvre can i use`, `can i use`, `compatibilite navigateur` +1 | browser | — | — |
| 130 | `ouvrir_bundlephobia` | Ouvrir Bundlephobia (taille des packages) | `ouvre bundlephobia`, `bundlephobia`, `taille package npm` +1 | browser | — | — |
| 131 | `ouvrir_w3schools` | Ouvrir W3Schools | `ouvre w3schools`, `va sur w3schools`, `tuto w3schools` +1 | browser | — | — |
| 132 | `ouvrir_python_docs` | Ouvrir la documentation Python officielle | `ouvre la doc python`, `doc python`, `python docs` +1 | browser | — | — |
| 133 | `ouvrir_rust_docs` | Ouvrir la documentation Rust (The Book) | `ouvre la doc rust`, `doc rust`, `rust book` +1 | browser | — | — |
| 134 | `ouvrir_replit` | Ouvrir Replit (IDE en ligne) | `ouvre replit`, `va sur replit`, `lance replit` +1 | browser | — | — |
| 135 | `ouvrir_codesandbox` | Ouvrir CodeSandbox | `ouvre codesandbox`, `va sur codesandbox`, `lance codesandbox` +1 | browser | — | — |
| 136 | `ouvrir_stackblitz` | Ouvrir StackBlitz | `ouvre stackblitz`, `va sur stackblitz`, `lance stackblitz` +1 | browser | — | — |
| 137 | `ouvrir_typescript_playground` | Ouvrir TypeScript Playground | `ouvre typescript playground`, `typescript playground`, `teste du typescript` +1 | browser | — | — |
| 138 | `ouvrir_rust_playground` | Ouvrir Rust Playground | `ouvre rust playground`, `rust playground`, `teste du rust` +1 | browser | — | — |
| 139 | `ouvrir_google_trends` | Ouvrir Google Trends | `ouvre google trends`, `google trends`, `tendances google` +1 | browser | — | — |
| 140 | `ouvrir_alternativeto` | Ouvrir AlternativeTo (alternatives logiciels) | `ouvre alternativeto`, `alternativeto`, `alternative a un logiciel` +1 | browser | — | — |
| 141 | `ouvrir_downdetector` | Ouvrir DownDetector (status services) | `ouvre downdetector`, `downdetector`, `c'est en panne` +2 | browser | — | — |
| 142 | `ouvrir_virustotal` | Ouvrir VirusTotal (scan fichiers/URLs) | `ouvre virustotal`, `virustotal`, `scan un fichier` +1 | browser | — | — |
| 143 | `ouvrir_haveibeenpwned` | Ouvrir Have I Been Pwned (verification email) | `ouvre have i been pwned`, `haveibeenpwned`, `mon email a ete pirate` +2 | browser | — | — |
| 144 | `chercher_crates_io` | Rechercher un crate Rust | `cherche sur crates {requete}`, `crate rust {requete}`, `package rust {requete}` | browser | requete | — |
| 145 | `chercher_alternativeto` | Chercher une alternative a un logiciel | `alternative a {requete}`, `cherche une alternative a {requete}`, `remplace {requete}` | browser | requete | — |
| 146 | `chercher_mdn` | Rechercher sur MDN Web Docs | `cherche sur mdn {requete}`, `mdn {requete}`, `doc web {requete}` | browser | requete | — |
| 147 | `chercher_can_i_use` | Verifier la compatibilite d'une feature web | `can i use {requete}`, `compatibilite de {requete}`, `support de {requete}` | browser | requete | — |
| 148 | `ouvrir_chatgpt_plugins` | Ouvrir ChatGPT (avec GPTs) | `ouvre les gpts`, `chatgpt gpts`, `custom gpt` +1 | browser | — | — |
| 149 | `ouvrir_anthropic_console` | Ouvrir la console Anthropic API | `ouvre anthropic console`, `console anthropic`, `api anthropic` +1 | browser | — | — |
| 150 | `ouvrir_openai_platform` | Ouvrir la plateforme OpenAI API | `ouvre openai platform`, `console openai`, `api openai` +1 | browser | — | — |
| 151 | `ouvrir_google_colab` | Ouvrir Google Colab | `ouvre google colab`, `colab`, `lance colab` +2 | browser | — | — |
| 152 | `ouvrir_overleaf` | Ouvrir Overleaf (LaTeX en ligne) | `ouvre overleaf`, `va sur overleaf`, `latex en ligne` +1 | browser | — | — |
| 153 | `ouvrir_whimsical` | Ouvrir Whimsical (diagrams & flowcharts) | `ouvre whimsical`, `whimsical`, `diagrammes whimsical` +1 | browser | — | — |
| 154 | `ouvrir_grammarly` | Ouvrir Grammarly | `ouvre grammarly`, `grammarly`, `correcteur anglais` +1 | browser | — | — |
| 155 | `ouvrir_remove_bg` | Ouvrir Remove.bg (supprimer arriere-plan) | `ouvre remove bg`, `supprime l'arriere plan`, `remove background` +1 | browser | — | — |
| 156 | `ouvrir_tinypng` | Ouvrir TinyPNG (compression images) | `ouvre tinypng`, `compresse une image`, `tiny png` +1 | browser | — | — |
| 157 | `ouvrir_draw_io` | Ouvrir draw.io (diagrammes) | `ouvre draw io`, `drawio`, `diagramme en ligne` +1 | browser | — | — |
| 158 | `ouvrir_notion_calendar` | Ouvrir Notion Calendar | `ouvre notion calendar`, `calendrier notion`, `notion agenda` +1 | browser | — | — |
| 159 | `ouvrir_todoist` | Ouvrir Todoist (gestion de taches) | `ouvre todoist`, `va sur todoist`, `mes taches todoist` +1 | browser | — | — |
| 160 | `ouvrir_google_finance` | Ouvrir Google Finance | `ouvre google finance`, `google finance`, `cours de bourse` +1 | browser | — | — |
| 161 | `ouvrir_yahoo_finance` | Ouvrir Yahoo Finance | `ouvre yahoo finance`, `yahoo finance`, `yahoo bourse` +1 | browser | — | — |
| 162 | `ouvrir_coindesk` | Ouvrir CoinDesk (news crypto) | `ouvre coindesk`, `news crypto`, `coindesk` +1 | browser | — | — |
| 163 | `ouvrir_meteo` | Ouvrir la meteo | `ouvre la meteo`, `quel temps fait il`, `meteo` +2 | browser | — | — |
| 164 | `chercher_google_colab` | Rechercher un notebook Colab | `cherche un notebook {requete}`, `colab {requete}`, `notebook sur {requete}` | browser | requete | — |
| 165 | `chercher_perplexity` | Rechercher sur Perplexity AI | `cherche sur perplexity {requete}`, `perplexity {requete}`, `demande a perplexity {requete}` | browser | requete | — |
| 166 | `chercher_google_maps` | Rechercher sur Google Maps | `cherche sur maps {requete}`, `maps {requete}`, `trouve {requete} sur la carte` +1 | browser | requete | — |
| 167 | `ouvrir_impots` | Ouvrir impots.gouv.fr | `ouvre les impots`, `impots gouv`, `va sur les impots` +2 | browser | — | — |
| 168 | `ouvrir_ameli` | Ouvrir Ameli (Assurance Maladie) | `ouvre ameli`, `assurance maladie`, `va sur ameli` +2 | browser | — | — |
| 169 | `ouvrir_caf` | Ouvrir la CAF | `ouvre la caf`, `allocations familiales`, `va sur la caf` +1 | browser | — | — |
| 170 | `ouvrir_sncf` | Ouvrir SNCF Connect (trains) | `ouvre sncf`, `billets de train`, `va sur sncf` +2 | browser | — | — |
| 171 | `ouvrir_doctolib` | Ouvrir Doctolib (rendez-vous medical) | `ouvre doctolib`, `prends un rdv medical`, `va sur doctolib` +2 | browser | — | — |
| 172 | `ouvrir_la_poste` | Ouvrir La Poste (suivi colis) | `ouvre la poste`, `suivi colis`, `va sur la poste` +2 | browser | — | — |
| 173 | `ouvrir_pole_emploi` | Ouvrir France Travail (ex Pole Emploi) | `ouvre pole emploi`, `france travail`, `va sur pole emploi` +1 | browser | — | — |
| 174 | `ouvrir_service_public` | Ouvrir Service-Public.fr | `service public`, `demarches administratives`, `va sur service public` +1 | browser | — | — |
| 175 | `ouvrir_fnac` | Ouvrir Fnac.com | `ouvre la fnac`, `va sur la fnac`, `fnac en ligne` +1 | browser | — | — |
| 176 | `ouvrir_cdiscount` | Ouvrir Cdiscount | `ouvre cdiscount`, `va sur cdiscount`, `cdiscount` +1 | browser | — | — |
| 177 | `ouvrir_amazon_fr` | Ouvrir Amazon France | `ouvre amazon france`, `amazon fr`, `va sur amazon` +1 | browser | — | — |
| 178 | `ouvrir_boursorama` | Ouvrir Boursorama (banque/bourse) | `ouvre boursorama`, `va sur boursorama`, `banque en ligne` +1 | browser | — | — |
| 179 | `ouvrir_free_mobile` | Ouvrir Free Mobile (espace client) | `ouvre free`, `espace client free`, `va sur free` +1 | browser | — | — |
| 180 | `ouvrir_edf` | Ouvrir EDF (electricite) | `ouvre edf`, `mon compte edf`, `facture electricite` +1 | browser | — | — |
| 181 | `ouvrir_aws_console` | Ouvrir AWS Console | `ouvre aws`, `console aws`, `va sur aws` +2 | browser | — | — |
| 182 | `ouvrir_azure_portal` | Ouvrir Azure Portal | `ouvre azure`, `portal azure`, `va sur azure` +2 | browser | — | — |
| 183 | `ouvrir_gcp_console` | Ouvrir Google Cloud Console | `ouvre google cloud`, `gcp console`, `va sur google cloud` +2 | browser | — | — |
| 184 | `ouvrir_netlify` | Ouvrir Netlify (deploiement) | `ouvre netlify`, `va sur netlify`, `netlify dashboard` +1 | browser | — | — |
| 185 | `ouvrir_digitalocean` | Ouvrir DigitalOcean | `ouvre digitalocean`, `va sur digital ocean`, `digital ocean` +1 | browser | — | — |
| 186 | `ouvrir_le_monde` | Ouvrir Le Monde | `ouvre le monde`, `actualites le monde`, `va sur le monde` +2 | browser | — | — |
| 187 | `ouvrir_le_figaro` | Ouvrir Le Figaro | `ouvre le figaro`, `actualites figaro`, `va sur le figaro` +1 | browser | — | — |
| 188 | `ouvrir_liberation` | Ouvrir Liberation | `ouvre liberation`, `actualites liberation`, `va sur libe` +1 | browser | — | — |
| 189 | `ouvrir_france_info` | Ouvrir France Info | `ouvre france info`, `actualites france`, `va sur france info` +1 | browser | — | — |
| 190 | `ouvrir_techcrunch` | Ouvrir TechCrunch (tech news) | `ouvre techcrunch`, `news tech`, `va sur techcrunch` +1 | browser | — | — |
| 191 | `ouvrir_hackernews` | Ouvrir Hacker News | `ouvre hacker news`, `va sur hacker news`, `ycombinator news` +2 | browser | — | — |
| 192 | `ouvrir_ars_technica` | Ouvrir Ars Technica | `ouvre ars technica`, `va sur ars technica`, `ars technica` +1 | browser | — | — |
| 193 | `ouvrir_the_verge` | Ouvrir The Verge | `ouvre the verge`, `va sur the verge`, `the verge` +1 | browser | — | — |
| 194 | `ouvrir_deezer` | Ouvrir Deezer | `ouvre deezer`, `va sur deezer`, `musique deezer` +1 | browser | — | — |
| 195 | `ouvrir_mycanal` | Ouvrir MyCanal | `ouvre canal plus`, `va sur mycanal`, `canal+` +1 | browser | — | — |
| 196 | `chercher_leboncoin` | Rechercher sur Leboncoin | `cherche sur leboncoin {requete}`, `leboncoin {requete}`, `annonce {requete}` +1 | browser | requete | — |
| 197 | `ouvrir_khan_academy` | Ouvrir Khan Academy | `ouvre khan academy`, `va sur khan academy`, `khan academy` +1 | browser | — | — |
| 198 | `ouvrir_edx` | Ouvrir edX | `ouvre edx`, `va sur edx`, `mooc edx` +1 | browser | — | — |
| 199 | `ouvrir_freecodecamp` | Ouvrir freeCodeCamp | `ouvre freecodecamp`, `va sur freecodecamp`, `apprendre a coder` +1 | browser | — | — |
| 200 | `ouvrir_caniuse` | Ouvrir Can I Use (compatibilite navigateur) | `ouvre can i use`, `compatibilite navigateur`, `caniuse` +2 | browser | — | — |
| 201 | `ouvrir_frandroid` | Ouvrir Frandroid (tech FR) | `ouvre frandroid`, `va sur frandroid`, `actu tech frandroid` +1 | browser | — | — |
| 202 | `ouvrir_numerama` | Ouvrir Numerama (tech FR) | `ouvre numerama`, `va sur numerama`, `actu numerama` +1 | browser | — | — |
| 203 | `ouvrir_les_numeriques` | Ouvrir Les Numeriques (tests produits) | `ouvre les numeriques`, `les numeriques`, `tests produits` +1 | browser | — | — |
| 204 | `ouvrir_01net` | Ouvrir 01net (tech FR) | `ouvre 01net`, `va sur 01 net`, `01net` +1 | browser | — | — |
| 205 | `ouvrir_journal_du_net` | Ouvrir Le Journal du Net | `ouvre journal du net`, `jdn`, `journal du net` +1 | browser | — | — |
| 206 | `ouvrir_binance` | Ouvrir Binance | `ouvre binance`, `va sur binance`, `binance exchange` +1 | browser | — | — |
| 207 | `ouvrir_coinbase` | Ouvrir Coinbase | `ouvre coinbase`, `va sur coinbase`, `coinbase exchange` +1 | browser | — | — |
| 208 | `ouvrir_kraken` | Ouvrir Kraken | `ouvre kraken`, `va sur kraken`, `kraken exchange` +1 | browser | — | — |
| 209 | `ouvrir_etherscan` | Ouvrir Etherscan (explorateur Ethereum) | `ouvre etherscan`, `etherscan`, `explorateur ethereum` +1 | browser | — | — |
| 210 | `ouvrir_booking` | Ouvrir Booking.com (hotels) | `ouvre booking`, `reserve un hotel`, `va sur booking` +1 | browser | — | — |
| 211 | `ouvrir_airbnb` | Ouvrir Airbnb | `ouvre airbnb`, `va sur airbnb`, `location airbnb` +1 | browser | — | — |
| 212 | `ouvrir_google_flights` | Ouvrir Google Flights (vols) | `ouvre google flights`, `billets d'avion`, `cherche un vol` +2 | browser | — | — |
| 213 | `ouvrir_tripadvisor` | Ouvrir TripAdvisor | `ouvre tripadvisor`, `avis restaurants`, `va sur tripadvisor` +1 | browser | — | — |
| 214 | `ouvrir_blablacar` | Ouvrir BlaBlaCar (covoiturage) | `ouvre blablacar`, `covoiturage`, `va sur blablacar` +1 | browser | — | — |
| 215 | `ouvrir_legifrance` | Ouvrir Legifrance (textes de loi) | `ouvre legifrance`, `textes de loi`, `va sur legifrance` +2 | browser | — | — |
| 216 | `ouvrir_ants` | Ouvrir ANTS (carte d'identite, permis) | `ouvre ants`, `carte d'identite`, `va sur ants` +2 | browser | — | — |
| 217 | `ouvrir_prefecture` | Ouvrir la prise de RDV en prefecture | `rendez vous prefecture`, `ouvre la prefecture`, `va sur la prefecture` +1 | browser | — | — |
| 218 | `ouvrir_steam_store` | Ouvrir le Steam Store | `ouvre le store steam`, `magasin steam`, `steam shop` +2 | browser | — | — |
| 219 | `ouvrir_epic_games` | Ouvrir Epic Games Store | `ouvre epic games`, `va sur epic games`, `epic store` +2 | browser | — | — |
| 220 | `ouvrir_gog` | Ouvrir GOG.com (jeux sans DRM) | `ouvre gog`, `va sur gog`, `jeux gog` +1 | browser | — | — |
| 221 | `ouvrir_humble_bundle` | Ouvrir Humble Bundle | `ouvre humble bundle`, `humble bundle`, `bundle de jeux` +1 | browser | — | — |
| 222 | `ouvrir_vidal` | Ouvrir Vidal (medicaments) | `ouvre vidal`, `notice medicament`, `va sur vidal` +1 | browser | — | — |
| 223 | `ouvrir_doctissimo` | Ouvrir Doctissimo (sante) | `ouvre doctissimo`, `symptomes`, `va sur doctissimo` +1 | browser | — | — |
| 224 | `chercher_github_repos` | Rechercher un repo sur GitHub | `cherche un repo {requete}`, `github repo {requete}`, `projet github {requete}` | browser | requete | — |
| 225 | `chercher_huggingface_models` | Rechercher un modele sur Hugging Face | `cherche un modele {requete}`, `huggingface model {requete}`, `modele ia {requete}` | browser | requete | — |
| 226 | `ouvrir_grafana_cloud` | Ouvrir Grafana Cloud | `ouvre grafana`, `va sur grafana`, `dashboard grafana` +1 | browser | — | — |
| 227 | `ouvrir_datadog` | Ouvrir Datadog | `ouvre datadog`, `va sur datadog`, `monitoring datadog` +1 | browser | — | — |
| 228 | `ouvrir_sentry` | Ouvrir Sentry (error tracking) | `ouvre sentry`, `va sur sentry`, `erreurs sentry` +1 | browser | — | — |
| 229 | `ouvrir_pagerduty` | Ouvrir PagerDuty (alerting) | `ouvre pagerduty`, `alertes pagerduty`, `on call pagerduty` | browser | — | — |
| 230 | `ouvrir_newrelic` | Ouvrir New Relic (APM) | `ouvre new relic`, `va sur newrelic`, `performance newrelic` +1 | browser | — | — |
| 231 | `ouvrir_uptime_robot` | Ouvrir UptimeRobot (monitoring) | `ouvre uptime robot`, `status sites`, `monitoring uptime` | browser | — | — |
| 232 | `ouvrir_prometheus_docs` | Ouvrir la doc Prometheus | `doc prometheus`, `prometheus documentation`, `ouvre prometheus` | browser | — | — |
| 233 | `ouvrir_jenkins` | Ouvrir Jenkins | `ouvre jenkins`, `va sur jenkins`, `builds jenkins` | browser | — | — |
| 234 | `ouvrir_circleci` | Ouvrir CircleCI | `ouvre circleci`, `circle ci`, `builds circleci` | browser | — | — |
| 235 | `ouvrir_travis_ci` | Ouvrir Travis CI | `ouvre travis`, `travis ci`, `builds travis` | browser | — | — |
| 236 | `ouvrir_gitlab_ci` | Ouvrir GitLab CI/CD | `ouvre gitlab ci`, `gitlab pipelines`, `builds gitlab` | browser | — | — |
| 237 | `ouvrir_postman_web` | Ouvrir Postman Web | `ouvre postman`, `va sur postman`, `test api postman` +1 | browser | — | — |
| 238 | `ouvrir_swagger_editor` | Ouvrir Swagger Editor | `ouvre swagger`, `swagger editor`, `editeur openapi` | browser | — | — |
| 239 | `ouvrir_rapidapi` | Ouvrir RapidAPI (marketplace API) | `ouvre rapidapi`, `va sur rapidapi`, `marketplace api` +1 | browser | — | — |
| 240 | `ouvrir_httpbin` | Ouvrir HTTPBin (test HTTP) | `ouvre httpbin`, `test http`, `httpbin test` | browser | — | — |
| 241 | `ouvrir_reqbin` | Ouvrir ReqBin (HTTP client en ligne) | `ouvre reqbin`, `client http en ligne`, `tester une requete` | browser | — | — |
| 242 | `ouvrir_malt` | Ouvrir Malt (freelance FR) | `ouvre malt`, `va sur malt`, `freelance malt` +1 | browser | — | — |
| 243 | `ouvrir_fiverr` | Ouvrir Fiverr | `ouvre fiverr`, `va sur fiverr`, `services fiverr` | browser | — | — |
| 244 | `ouvrir_upwork` | Ouvrir Upwork | `ouvre upwork`, `va sur upwork`, `jobs upwork` +1 | browser | — | — |
| 245 | `ouvrir_welcome_jungle` | Ouvrir Welcome to the Jungle (emploi tech) | `ouvre welcome to the jungle`, `offres d'emploi tech`, `welcome jungle` +1 | browser | — | — |
| 246 | `ouvrir_indeed` | Ouvrir Indeed | `ouvre indeed`, `va sur indeed`, `offres d'emploi` +1 | browser | — | — |
| 247 | `ouvrir_uber_eats` | Ouvrir Uber Eats | `ouvre uber eats`, `commande uber eats`, `uber eats` +1 | browser | — | — |
| 248 | `ouvrir_deliveroo` | Ouvrir Deliveroo | `ouvre deliveroo`, `commande deliveroo`, `livraison deliveroo` | browser | — | — |
| 249 | `ouvrir_just_eat` | Ouvrir Just Eat | `ouvre just eat`, `commande just eat`, `livraison just eat` | browser | — | — |
| 250 | `ouvrir_tf1_plus` | Ouvrir TF1+ (replay TF1) | `ouvre tf1`, `replay tf1`, `tf1 plus` +1 | browser | — | — |
| 251 | `ouvrir_france_tv` | Ouvrir France.tv (replay France TV) | `ouvre france tv`, `replay france tv`, `france television` +1 | browser | — | — |
| 252 | `ouvrir_arte_replay` | Ouvrir Arte.tv (replay) | `ouvre arte`, `replay arte`, `arte tv` +1 | browser | — | — |
| 253 | `ouvrir_bfm_tv` | Ouvrir BFM TV en direct | `ouvre bfm`, `bfm tv`, `info en direct` +1 | browser | — | — |
| 254 | `ouvrir_cnews` | Ouvrir CNews | `ouvre cnews`, `c news`, `cnews en direct` | browser | — | — |
| 255 | `ouvrir_mediapart` | Ouvrir Mediapart | `ouvre mediapart`, `va sur mediapart`, `articles mediapart` | browser | — | — |
| 256 | `ouvrir_trello` | Ouvrir Trello | `ouvre trello`, `va sur trello`, `mes boards trello` +1 | browser | — | — |
| 257 | `ouvrir_asana` | Ouvrir Asana | `ouvre asana`, `va sur asana`, `projets asana` | browser | — | — |
| 258 | `ouvrir_monday` | Ouvrir Monday.com | `ouvre monday`, `va sur monday`, `monday com` | browser | — | — |
| 259 | `ouvrir_clickup` | Ouvrir ClickUp | `ouvre clickup`, `va sur clickup`, `projets clickup` | browser | — | — |
| 260 | `ouvrir_darty` | Ouvrir Darty | `ouvre darty`, `va sur darty`, `electromenager darty` | browser | — | — |
| 261 | `ouvrir_boulanger` | Ouvrir Boulanger | `ouvre boulanger`, `va sur boulanger`, `electromenager boulanger` | browser | — | — |
| 262 | `ouvrir_leroy_merlin` | Ouvrir Leroy Merlin (bricolage) | `ouvre leroy merlin`, `bricolage`, `va sur leroy merlin` | browser | — | — |
| 263 | `ouvrir_castorama` | Ouvrir Castorama (bricolage) | `ouvre castorama`, `va sur castorama`, `bricolage castorama` | browser | — | — |
| 264 | `ouvrir_vinted` | Ouvrir Vinted | `ouvre vinted`, `va sur vinted`, `vetements vinted` | browser | — | — |
| 265 | `ouvrir_revolut` | Ouvrir Revolut | `ouvre revolut`, `va sur revolut`, `compte revolut` | browser | — | — |
| 266 | `ouvrir_n26` | Ouvrir N26 (banque en ligne) | `ouvre n26`, `va sur n26`, `banque n26` | browser | — | — |
| 267 | `ouvrir_bankin` | Ouvrir Bankin (agrégateur comptes) | `ouvre bankin`, `va sur bankin`, `mes comptes bankin` +1 | browser | — | — |
| 268 | `ouvrir_dribbble` | Ouvrir Dribbble (inspiration design) | `ouvre dribbble`, `inspiration design`, `va sur dribbble` | browser | — | — |
| 269 | `ouvrir_unsplash` | Ouvrir Unsplash (photos libres) | `ouvre unsplash`, `photos gratuites`, `images libres` +1 | browser | — | — |
| 270 | `ouvrir_coolors` | Ouvrir Coolors (palettes couleurs) | `ouvre coolors`, `palette de couleurs`, `generateur couleurs` | browser | — | — |
| 271 | `ouvrir_fontawesome` | Ouvrir Font Awesome (icones) | `ouvre font awesome`, `icones font awesome`, `cherche une icone` | browser | — | — |
| 272 | `ouvrir_claude_ai` | Ouvrir Claude AI | `ouvre claude`, `va sur claude`, `lance claude ai` | browser | — | — |
| 273 | `ouvrir_gemini_web` | Ouvrir Google Gemini | `ouvre gemini web`, `va sur gemini`, `google gemini` | browser | — | — |
| 274 | `ouvrir_midjourney` | Ouvrir Midjourney | `ouvre midjourney`, `va sur midjourney`, `genere une image ia` | browser | — | — |
| 275 | `ouvrir_replicate` | Ouvrir Replicate (ML APIs) | `ouvre replicate`, `va sur replicate`, `api ml replicate` | browser | — | — |
| 276 | `ouvrir_together_ai` | Ouvrir Together AI (inference) | `ouvre together ai`, `va sur together`, `together inference` | browser | — | — |
| 277 | `ouvrir_ollama_web` | Ouvrir Ollama (modeles locaux) | `ouvre ollama site`, `va sur ollama`, `site ollama` | browser | — | — |
| 278 | `ouvrir_openrouter` | Ouvrir OpenRouter (multi-model API) | `ouvre openrouter`, `va sur openrouter`, `api openrouter` | browser | — | — |
| 279 | `ouvrir_geeksforgeeks` | Ouvrir GeeksForGeeks | `ouvre geeksforgeeks`, `geeks for geeks`, `gfg` | browser | — | — |
| 280 | `ouvrir_digitalocean_docs` | Ouvrir DigitalOcean Tutorials | `ouvre digitalocean`, `tutos digitalocean`, `digital ocean docs` | browser | — | — |
| 281 | `ouvrir_realpython` | Ouvrir Real Python (tutos Python) | `ouvre real python`, `tutos python`, `real python` | browser | — | — |
| 282 | `ouvrir_css_tricks` | Ouvrir CSS-Tricks | `ouvre css tricks`, `astuces css`, `css tricks` | browser | — | — |
| 283 | `ouvrir_web_dev` | Ouvrir web.dev (Google) | `ouvre web dev`, `web dev google`, `bonnes pratiques web` | browser | — | — |
| 284 | `ouvrir_bandcamp` | Ouvrir Bandcamp | `ouvre bandcamp`, `va sur bandcamp`, `musique bandcamp` | browser | — | — |
| 285 | `ouvrir_data_gouv` | Ouvrir data.gouv.fr (open data) | `ouvre data gouv`, `open data france`, `donnees publiques` | browser | — | — |
| 286 | `ouvrir_seloger` | Ouvrir SeLoger | `ouvre seloger`, `va sur seloger`, `cherche un appart` +1 | browser | — | — |
| 287 | `ouvrir_pap` | Ouvrir PAP (particulier a particulier) | `ouvre pap`, `pap immobilier`, `de particulier a particulier` | browser | — | — |
| 288 | `ouvrir_bienici` | Ouvrir Bien'ici (immobilier) | `ouvre bienici`, `bien ici`, `immobilier bienici` | browser | — | — |
| 289 | `ouvrir_logic_immo` | Ouvrir Logic-Immo | `ouvre logic immo`, `logic immo`, `logement logic immo` | browser | — | — |
| 290 | `ouvrir_ratp` | Ouvrir RATP (metro Paris) | `ouvre ratp`, `metro paris`, `plan ratp` +1 | browser | — | — |
| 291 | `ouvrir_citymapper` | Ouvrir Citymapper (itineraires) | `ouvre citymapper`, `itineraire transport`, `citymapper` | browser | — | — |
| 292 | `ouvrir_onedrive_web` | Ouvrir OneDrive Web | `ouvre onedrive`, `va sur onedrive`, `one drive web` | browser | — | — |
| 293 | `ouvrir_dropbox` | Ouvrir Dropbox | `ouvre dropbox`, `va sur dropbox`, `fichiers dropbox` | browser | — | — |
| 294 | `ouvrir_mega` | Ouvrir Mega (stockage chiffre) | `ouvre mega`, `va sur mega`, `mega cloud` | browser | — | — |
| 295 | `ouvrir_discord_web` | Ouvrir Discord Web | `ouvre discord web`, `discord en ligne`, `va sur discord` | browser | — | — |
| 296 | `ouvrir_zoom` | Ouvrir Zoom | `ouvre zoom`, `va sur zoom`, `lance zoom` +1 | browser | — | — |
| 297 | `ouvrir_heroku` | Ouvrir Heroku | `ouvre heroku`, `va sur heroku`, `apps heroku` | browser | — | — |
| 298 | `ouvrir_nuget` | Ouvrir NuGet (packages .NET) | `ouvre nuget`, `va sur nuget`, `packages dotnet` | browser | — | — |
| 299 | `ouvrir_wired` | Ouvrir Wired | `ouvre wired`, `va sur wired`, `news wired` | browser | — | — |
| 300 | `ouvrir_semantic_scholar` | Ouvrir Semantic Scholar (IA papers) | `ouvre semantic scholar`, `semantic scholar`, `papers ia` | browser | — | — |
| 301 | `ouvrir_researchgate` | Ouvrir ResearchGate | `ouvre researchgate`, `va sur researchgate`, `recherche researchgate` | browser | — | — |
| 302 | `ouvrir_pubmed` | Ouvrir PubMed (medecine) | `ouvre pubmed`, `recherche pubmed`, `articles medicaux` | browser | — | — |
| 303 | `ouvrir_marmiton` | Ouvrir Marmiton (recettes) | `ouvre marmiton`, `va sur marmiton`, `recettes marmiton` +1 | browser | — | — |
| 304 | `ouvrir_750g` | Ouvrir 750g (recettes) | `ouvre 750g`, `recettes 750g`, `va sur 750 grammes` | browser | — | — |
| 305 | `ouvrir_cuisine_az` | Ouvrir Cuisine AZ | `ouvre cuisine az`, `recettes cuisine az`, `va sur cuisine az` | browser | — | — |
| 306 | `ouvrir_pexels` | Ouvrir Pexels (photos/videos gratuites) | `ouvre pexels`, `photos pexels`, `videos gratuites pexels` | browser | — | — |
| 307 | `ouvrir_pixabay` | Ouvrir Pixabay (images libres) | `ouvre pixabay`, `images pixabay`, `photos pixabay` | browser | — | — |
| 308 | `ouvrir_vimeo` | Ouvrir Vimeo | `ouvre vimeo`, `va sur vimeo`, `videos vimeo` | browser | — | — |
| 309 | `ouvrir_codecademy` | Ouvrir Codecademy | `ouvre codecademy`, `va sur codecademy`, `apprendre a coder` | browser | — | — |
| 310 | `ouvrir_outlook_web` | Ouvrir Outlook Web | `ouvre outlook`, `va sur outlook`, `mails outlook` | browser | — | — |
| 311 | `ouvrir_protonmail` | Ouvrir ProtonMail (mail chiffre) | `ouvre protonmail`, `va sur protonmail`, `mail securise` | browser | — | — |
| 312 | `ouvrir_windy` | Ouvrir Windy (meteo avancee) | `ouvre windy`, `meteo windy`, `carte meteo` +1 | browser | — | — |
| 313 | `ouvrir_openstreetmap` | Ouvrir OpenStreetMap | `ouvre openstreetmap`, `osm`, `carte libre` | browser | — | — |
| 314 | `ouvrir_waze` | Ouvrir Waze (trafic) | `ouvre waze`, `trafic waze`, `embouteillages` | browser | — | — |
| 315 | `ouvrir_jsoncrack` | Ouvrir JSON Crack (visualiser JSON) | `ouvre json crack`, `visualise du json`, `json viewer` | browser | — | — |
| 316 | `ouvrir_molotov` | Ouvrir Molotov TV (TV en direct) | `ouvre molotov`, `tv en direct`, `molotov tv` | browser | — | — |
| 317 | `ouvrir_defillama` | Ouvrir DeFi Llama (TVL tracker) | `ouvre defi llama`, `tvl defi`, `defi llama` | browser | — | — |
| 318 | `ouvrir_dune` | Ouvrir Dune Analytics (blockchain data) | `ouvre dune`, `analytics blockchain`, `dune analytics` | browser | — | — |
| 319 | `ouvrir_uniswap` | Ouvrir Uniswap (DEX) | `ouvre uniswap`, `swap crypto`, `uniswap dex` | browser | — | — |
| 320 | `ouvrir_zapper` | Ouvrir Zapper (portfolio DeFi) | `ouvre zapper`, `portfolio defi`, `zapper fi` | browser | — | — |
| 321 | `ouvrir_archive_org` | Ouvrir Internet Archive / Wayback Machine | `ouvre archive org`, `wayback machine`, `internet archive` | browser | — | — |
| 322 | `ouvrir_temp_mail` | Ouvrir Temp Mail (email jetable) | `email jetable`, `temp mail`, `mail temporaire` | browser | — | — |
| 323 | `ouvrir_pastebin` | Ouvrir Pastebin | `ouvre pastebin`, `va sur pastebin`, `colle du texte` | browser | — | — |

## Pipelines Multi-Etapes

**278 commandes**

| # | Nom | Description | Declencheurs | Type | Params | Confirm |
|---|-----|-------------|--------------|------|--------|---------|
| 1 | `range_bureau` | Ranger le bureau (minimiser toutes les fenetres) | `range mon bureau`, `range le bureau`, `nettoie le bureau` +6 | pipeline | — | — |
| 2 | `va_sur_mails_comet` | Ouvrir Comet et aller sur Gmail | `va sur mes mails`, `ouvre mes mails sur comet`, `check mes mails comet` +3 | pipeline | — | — |
| 3 | `mode_travail` | Mode travail: VSCode + Terminal | `mode travail`, `mode dev`, `setup dev` +4 | pipeline | — | — |
| 4 | `mode_trading` | Mode trading: TradingView + MEXC + Dashboard | `mode trading`, `ouvre mon setup trading`, `setup trading` +3 | pipeline | — | — |
| 5 | `rapport_matin` | Rapport du matin: Gmail Comet + TradingView + Dashboard | `rapport du matin`, `routine du matin`, `morning routine` +2 | pipeline | — | — |
| 6 | `bonne_nuit` | Bonne nuit: minimiser tout + verrouiller le PC | `bonne nuit`, `bonne nuit jarvis`, `verrouille tout` +3 | pipeline | — | Oui |
| 7 | `mode_focus` | Mode focus: minimiser tout + ne pas deranger | `mode focus`, `mode concentration`, `ne pas deranger` +4 | pipeline | — | — |
| 8 | `mode_cinema` | Mode cinema: minimiser tout + ouvrir Netflix | `mode cinema`, `mode film`, `lance le mode cinema` +3 | pipeline | — | — |
| 9 | `ouvre_youtube_comet` | Ouvrir YouTube dans Comet | `ouvre youtube sur comet`, `youtube comet`, `va sur youtube comet` +1 | pipeline | — | — |
| 10 | `ouvre_github_comet` | Ouvrir GitHub dans Comet | `ouvre github sur comet`, `ouvre github comet`, `github comet` +2 | pipeline | — | — |
| 11 | `ouvre_cluster` | Ouvrir Dashboard cluster + LM Studio | `ouvre le cluster`, `lance le cluster`, `dashboard cluster` +2 | pipeline | — | — |
| 12 | `ferme_tout` | Fermer toutes les fenetres | `ferme tout`, `ferme toutes les fenetres`, `close all` +2 | pipeline | — | Oui |
| 13 | `mode_musique` | Mode musique: minimiser tout + ouvrir Spotify | `mode musique`, `lance la musique en fond`, `ambiance musicale` +2 | pipeline | — | — |
| 14 | `mode_gaming` | Mode gaming: haute performance + Steam + Game Bar | `mode gaming`, `mode jeu`, `lance le mode gaming` +3 | pipeline | — | — |
| 15 | `mode_stream` | Mode stream: minimiser tout + OBS + Spotify | `mode stream`, `lance le stream`, `mode streaming` +2 | pipeline | — | — |
| 16 | `mode_presentation` | Mode presentation: dupliquer ecran + PowerPoint | `mode presentation`, `lance la presentation`, `mode pres` +2 | pipeline | — | — |
| 17 | `mode_lecture` | Mode lecture: nuit + minimiser + Comet | `mode lecture`, `mode lire`, `lance le mode lecture` +2 | pipeline | — | — |
| 18 | `mode_reunion` | Mode reunion: Discord + focus assist | `mode reunion`, `lance la reunion`, `mode meeting` +2 | pipeline | — | — |
| 19 | `mode_code_turbo` | Mode dev turbo: VSCode + Terminal + LM Studio + Dashboard | `mode code turbo`, `setup dev complet`, `mode turbo dev` +3 | pipeline | — | — |
| 20 | `mode_detente` | Mode detente: minimiser + Spotify + lumiere nocturne | `mode detente`, `mode relax`, `mode chill` +3 | pipeline | — | — |
| 21 | `routine_soir` | Routine du soir: TradingView + night light + minimiser | `routine du soir`, `routine soir`, `fin de journee` +2 | pipeline | — | — |
| 22 | `check_trading_rapide` | Check trading: TradingView + MEXC en parallele | `check trading rapide`, `check rapide trading`, `jette un oeil au trading` +2 | pipeline | — | — |
| 23 | `setup_ia` | Setup IA: LM Studio + Dashboard + Terminal | `setup ia`, `lance le setup ia`, `ouvre tout le cluster` +3 | pipeline | — | — |
| 24 | `nettoyage_express` | Nettoyage express: corbeille + temp + DNS | `nettoyage express`, `nettoyage rapide`, `clean express` +3 | pipeline | — | Oui |
| 25 | `diagnostic_complet` | Diagnostic complet: systeme + GPU + RAM + disques | `diagnostic complet`, `diagnostic du pc`, `check complet` +3 | pipeline | — | — |
| 26 | `debug_reseau` | Debug reseau: flush DNS + ping + diagnostic | `debug reseau`, `debug le reseau`, `diagnostic reseau rapide` +2 | pipeline | — | — |
| 27 | `veille_securisee` | Veille securisee: minimiser + verrouiller + veille | `veille securisee`, `mets en veille en securite`, `veille et verrouille` +1 | pipeline | — | Oui |
| 28 | `ouvre_reddit_comet` | Ouvrir Reddit dans Comet | `ouvre reddit sur comet`, `reddit comet`, `va sur reddit comet` +1 | pipeline | — | — |
| 29 | `ouvre_twitter_comet` | Ouvrir Twitter/X dans Comet | `ouvre twitter sur comet`, `twitter comet`, `x comet` +2 | pipeline | — | — |
| 30 | `ouvre_chatgpt_comet` | Ouvrir ChatGPT dans Comet | `ouvre chatgpt sur comet`, `chatgpt comet`, `va sur chatgpt comet` +1 | pipeline | — | — |
| 31 | `ouvre_claude_comet` | Ouvrir Claude AI dans Comet | `ouvre claude sur comet`, `claude comet`, `va sur claude comet` +1 | pipeline | — | — |
| 32 | `ouvre_linkedin_comet` | Ouvrir LinkedIn dans Comet | `ouvre linkedin sur comet`, `linkedin comet`, `va sur linkedin comet` | pipeline | — | — |
| 33 | `ouvre_amazon_comet` | Ouvrir Amazon dans Comet | `ouvre amazon sur comet`, `amazon comet`, `va sur amazon comet` | pipeline | — | — |
| 34 | `ouvre_twitch_comet` | Ouvrir Twitch dans Comet | `ouvre twitch sur comet`, `twitch comet`, `va sur twitch comet` +1 | pipeline | — | — |
| 35 | `ouvre_social_comet` | Ouvrir les reseaux sociaux dans Comet (Twitter + Reddit + Discord) | `ouvre les reseaux sociaux comet`, `social comet`, `lance les reseaux sociaux` +1 | pipeline | — | — |
| 36 | `ouvre_perplexity_comet` | Ouvrir Perplexity dans Comet | `ouvre perplexity sur comet`, `perplexity comet`, `va sur perplexity comet` +1 | pipeline | — | — |
| 37 | `ouvre_huggingface_comet` | Ouvrir Hugging Face dans Comet | `ouvre hugging face sur comet`, `huggingface comet`, `va sur hugging face comet` | pipeline | — | — |
| 38 | `mode_crypto` | Mode crypto: TradingView + MEXC + CoinGecko | `mode crypto`, `mode trading crypto`, `lance le mode crypto` +2 | pipeline | — | — |
| 39 | `mode_ia_complet` | Mode IA complet: LM Studio + Dashboard + Claude + HuggingFace | `mode ia complet`, `ouvre tout le cluster ia`, `lance toute l'ia` +2 | pipeline | — | — |
| 40 | `mode_debug` | Mode debug: Terminal + GPU monitoring + logs systeme | `mode debug`, `mode debogage`, `lance le mode debug` +2 | pipeline | — | — |
| 41 | `mode_monitoring` | Mode monitoring: Dashboard + GPU + cluster health | `mode monitoring`, `mode surveillance`, `lance le monitoring` +2 | pipeline | — | — |
| 42 | `mode_communication` | Mode communication: Discord + Telegram + WhatsApp | `mode communication`, `mode com`, `lance le mode com` +2 | pipeline | — | — |
| 43 | `mode_documentation` | Mode documentation: Notion + Google Docs + Drive | `mode documentation`, `mode docs`, `lance le mode docs` +2 | pipeline | — | — |
| 44 | `mode_focus_total` | Mode focus total: minimiser + focus assist + nuit + VSCode | `mode focus total`, `concentration maximale`, `mode deep work` +2 | pipeline | — | — |
| 45 | `mode_review` | Mode review: VSCode + navigateur Git + Terminal | `mode review`, `mode revue de code`, `lance le mode review` +2 | pipeline | — | — |
| 46 | `routine_matin` | Routine du matin: cluster + dashboard + trading + mails | `routine du matin`, `routine matin`, `bonjour jarvis` +3 | pipeline | — | — |
| 47 | `backup_express` | Backup express: git add + commit du projet turbo | `backup express`, `sauvegarde rapide`, `backup rapide` +2 | pipeline | — | Oui |
| 48 | `reboot_cluster` | Reboot cluster: redemarre Ollama + ping LM Studio | `reboot le cluster`, `redemarre le cluster`, `restart cluster ia` +2 | pipeline | — | — |
| 49 | `pause_travail` | Pause: minimiser + verrouiller ecran + Spotify | `pause travail`, `je fais une pause`, `mode pause` +2 | pipeline | — | — |
| 50 | `fin_journee` | Fin de journee: backup + nuit + fermer apps dev | `fin de journee`, `termine la journee`, `je finis pour aujourd'hui` +2 | pipeline | — | — |
| 51 | `ouvre_github_via_comet` | Ouvrir GitHub dans Comet | `ouvre github sur comet`, `github comet`, `va sur github comet` +1 | pipeline | — | — |
| 52 | `ouvre_youtube_via_comet` | Ouvrir YouTube dans Comet | `ouvre youtube sur comet`, `youtube comet`, `va sur youtube comet` +1 | pipeline | — | — |
| 53 | `ouvre_tradingview_comet` | Ouvrir TradingView dans Comet | `ouvre tradingview sur comet`, `tradingview comet`, `va sur tradingview comet` | pipeline | — | — |
| 54 | `ouvre_coingecko_comet` | Ouvrir CoinGecko dans Comet | `ouvre coingecko sur comet`, `coingecko comet`, `va sur coingecko comet` | pipeline | — | — |
| 55 | `ouvre_ia_comet` | Ouvrir toutes les IA dans Comet (ChatGPT + Claude + Perplexity) | `ouvre toutes les ia comet`, `ia comet`, `lance les ia sur comet` +1 | pipeline | — | — |
| 56 | `mode_cinema_complet` | Mode cinema complet: minimiser + nuit + plein ecran + Netflix | `mode cinema complet`, `soiree film`, `movie time` +2 | pipeline | — | — |
| 57 | `mode_workout` | Mode workout: Spotify energique + YouTube fitness + timer | `mode workout`, `mode sport`, `lance le sport` +3 | pipeline | — | — |
| 58 | `mode_etude` | Mode etude: focus + Wikipedia + Pomodoro mindset | `mode etude`, `mode revision`, `mode etudiant` +2 | pipeline | — | — |
| 59 | `mode_diner` | Mode diner: minimiser + ambiance calme + Spotify | `mode diner`, `ambiance diner`, `dinner time` +2 | pipeline | — | — |
| 60 | `routine_depart` | Routine depart: sauvegarder + minimiser + verrouiller + economie | `routine depart`, `je pars`, `je m'en vais` +3 | pipeline | — | Oui |
| 61 | `routine_retour` | Routine retour: performance + cluster + mails + dashboard | `routine retour`, `je suis rentre`, `je suis la` +2 | pipeline | — | — |
| 62 | `mode_nuit_totale` | Mode nuit: fermer tout + nuit + volume bas + verrouiller | `mode nuit totale`, `dodo`, `je vais dormir` +2 | pipeline | — | Oui |
| 63 | `dev_morning_setup` | Dev morning: git pull + Docker + VSCode + browser tabs travail | `dev morning`, `setup dev du matin`, `prepare le dev` +2 | pipeline | — | — |
| 64 | `dev_deep_work` | Deep work: fermer distractions + VSCode + focus + terminal | `deep work`, `travail profond`, `mode deep focus` +2 | pipeline | — | — |
| 65 | `dev_standup_prep` | Standup prep: git log hier + board + dashboard | `standup prep`, `prepare le standup`, `qu'est ce que j'ai fait hier` +2 | pipeline | — | — |
| 66 | `dev_deploy_check` | Pre-deploy check: tests + git status + Docker status | `check avant deploy`, `pre deploy`, `verification deploy` +2 | pipeline | — | — |
| 67 | `dev_friday_report` | Rapport vendredi: stats git semaine + dashboard + todos | `rapport vendredi`, `friday report`, `recap de la semaine` +2 | pipeline | — | — |
| 68 | `dev_code_review_setup` | Code review setup: GitHub PRs + VSCode + diff terminal | `setup code review`, `prepare la review`, `code review setup` +1 | pipeline | — | — |
| 69 | `audit_securite_complet` | Audit securite: Defender + ports + connexions + firewall + autorun | `audit securite complet`, `scan securite total`, `audit de securite` +2 | pipeline | — | — |
| 70 | `rapport_systeme_complet` | Rapport systeme: CPU + RAM + GPU + disques + uptime + reseau | `rapport systeme complet`, `rapport systeme`, `etat complet du pc` +2 | pipeline | — | — |
| 71 | `maintenance_totale` | Maintenance totale: corbeille + temp + prefetch + DNS + thumbnails + check updates | `maintenance totale`, `grand nettoyage`, `maintenance complete` +2 | pipeline | — | Oui |
| 72 | `sauvegarde_tous_projets` | Backup tous projets: git commit turbo + carV1 + serveur | `sauvegarde tous les projets`, `backup tous les projets`, `backup global` +1 | pipeline | — | Oui |
| 73 | `pomodoro_start` | Pomodoro: fermer distractions + focus + VSCode + timer 25min | `pomodoro`, `lance un pomodoro`, `pomodoro start` +2 | pipeline | — | — |
| 74 | `pomodoro_break` | Pause Pomodoro: minimiser + Spotify + 5 min | `pause pomodoro`, `break pomodoro`, `pomodoro break` +2 | pipeline | — | — |
| 75 | `mode_entretien` | Mode entretien/call: fermer musique + focus + navigateur | `mode entretien`, `j'ai un call`, `mode appel` +2 | pipeline | — | — |
| 76 | `mode_recherche` | Mode recherche: Perplexity + Google Scholar + Wikipedia + Claude | `mode recherche`, `lance le mode recherche`, `mode exploration` +2 | pipeline | — | — |
| 77 | `mode_youtube` | Mode YouTube: minimiser + plein ecran + YouTube | `mode youtube`, `lance youtube en grand`, `session youtube` +2 | pipeline | — | — |
| 78 | `mode_spotify_focus` | Spotify focus: minimiser + Spotify + focus assist | `spotify focus`, `musique et concentration`, `musique de travail` +1 | pipeline | — | — |
| 79 | `ouvre_tout_dev_web` | Dev web complet: VSCode + terminal + localhost + npm docs | `dev web complet`, `setup dev web`, `lance le dev web` +2 | pipeline | — | — |
| 80 | `mode_twitch_stream` | Mode stream Twitch: OBS + Twitch dashboard + Spotify + chat | `mode twitch`, `setup stream twitch`, `lance le stream twitch` +1 | pipeline | — | — |
| 81 | `mode_email_productif` | Email productif: Gmail + Calendar + fermer distractions | `mode email`, `traite les mails`, `session email` +2 | pipeline | — | — |
| 82 | `mode_podcast` | Mode podcast: minimiser + Spotify + volume confortable | `mode podcast`, `lance un podcast`, `ecoute un podcast` +2 | pipeline | — | — |
| 83 | `mode_apprentissage` | Mode apprentissage: focus + Udemy/Coursera + notes | `mode apprentissage`, `mode formation`, `lance une formation` +2 | pipeline | — | — |
| 84 | `mode_news` | Mode news: Google Actualites + Reddit + Twitter | `mode news`, `mode actualites`, `quoi de neuf dans le monde` +2 | pipeline | — | — |
| 85 | `mode_shopping` | Mode shopping: Amazon + Leboncoin + comparateur | `mode shopping`, `mode achats`, `session shopping` +2 | pipeline | — | — |
| 86 | `mode_design` | Mode design: Figma + Pinterest + Canva | `mode design`, `mode graphisme`, `lance le mode design` +2 | pipeline | — | — |
| 87 | `mode_musique_decouverte` | Decouverte musicale: Spotify + YouTube Music + SoundCloud | `decouverte musicale`, `explore la musique`, `nouvelle musique` +1 | pipeline | — | — |
| 88 | `routine_weekend` | Routine weekend: relax + news + musique + Netflix | `routine weekend`, `mode weekend`, `c'est le weekend` +2 | pipeline | — | — |
| 89 | `mode_social_complet` | Social complet: Twitter + Reddit + Instagram + LinkedIn + Discord | `mode social complet`, `tous les reseaux`, `ouvre tout les reseaux sociaux` +2 | pipeline | — | — |
| 90 | `mode_planning` | Mode planning: Calendar + Notion + Google Tasks | `mode planning`, `mode planification`, `organise ma semaine` +2 | pipeline | — | — |
| 91 | `mode_brainstorm` | Mode brainstorm: Claude + Notion + timer | `mode brainstorm`, `session brainstorm`, `lance un brainstorm` +2 | pipeline | — | — |
| 92 | `nettoyage_downloads` | Nettoyer les vieux telechargements (>30 jours) | `nettoie les telechargements`, `clean downloads`, `vide les vieux downloads` +1 | pipeline | — | Oui |
| 93 | `rapport_reseau_complet` | Rapport reseau: IP + DNS + latence + ports + WiFi | `rapport reseau complet`, `rapport reseau`, `bilan reseau` +2 | pipeline | — | — |
| 94 | `verif_toutes_mises_a_jour` | Verifier MAJ: Windows Update + pip + npm + ollama | `verifie toutes les mises a jour`, `check toutes les updates`, `mises a jour globales` +1 | pipeline | — | — |
| 95 | `snapshot_systeme` | Snapshot systeme: sauvegarder toutes les stats dans un fichier | `snapshot systeme`, `capture l'etat du systeme`, `sauvegarde les stats` +1 | pipeline | — | — |
| 96 | `dev_hotfix` | Hotfix: nouvelle branche + VSCode + tests | `hotfix`, `lance un hotfix`, `dev hotfix` +2 | pipeline | — | — |
| 97 | `dev_new_feature` | Nouvelle feature: branche + VSCode + terminal + tests | `nouvelle feature`, `dev new feature`, `lance une feature` +1 | pipeline | — | — |
| 98 | `dev_merge_prep` | Preparation merge: lint + tests + git status + diff | `prepare le merge`, `pre merge`, `merge prep` +2 | pipeline | — | — |
| 99 | `dev_database_check` | Check databases: taille + tables de jarvis.db et etoile.db | `check les databases`, `verifie les bases de donnees`, `etat des databases` +1 | pipeline | — | — |
| 100 | `dev_live_coding` | Live coding: OBS + VSCode + terminal + navigateur localhost | `live coding`, `mode live code`, `lance le live coding` +2 | pipeline | — | — |
| 101 | `dev_cleanup` | Dev cleanup: git clean + cache Python + node_modules check | `dev cleanup`, `nettoie le projet`, `clean le code` +2 | pipeline | — | — |
| 102 | `mode_double_ecran_dev` | Double ecran dev: etendre + VSCode gauche + navigateur droite | `mode double ecran dev`, `setup double ecran`, `dev deux ecrans` +1 | pipeline | — | — |
| 103 | `mode_presentation_zoom` | Presentation Zoom/Teams: fermer distractions + dupliquer ecran + app | `mode presentation zoom`, `setup presentation teams`, `je fais une presentation` +1 | pipeline | — | — |
| 104 | `mode_dashboard_complet` | Dashboard complet: JARVIS + TradingView + cluster + n8n | `dashboard complet`, `ouvre tous les dashboards`, `mode tableau de bord` +1 | pipeline | — | — |
| 105 | `ferme_tout_sauf_code` | Fermer tout sauf VSCode et terminal | `ferme tout sauf le code`, `garde juste vscode`, `nettoie sauf l'editeur` +1 | pipeline | — | — |
| 106 | `mode_detox_digital` | Detox digitale: fermer TOUT + verrouiller + night light | `detox digitale`, `mode detox`, `deconnexion totale` +2 | pipeline | — | Oui |
| 107 | `mode_musique_travail` | Musique de travail: Spotify + focus assist (pas de distractions) | `musique de travail`, `met de la musique pour bosser`, `musique focus` +1 | pipeline | — | — |
| 108 | `check_tout_rapide` | Check rapide tout: cluster + GPU + RAM + disques en 1 commande | `check tout rapide`, `etat rapide de tout`, `resume systeme` +2 | pipeline | — | — |
| 109 | `mode_hackathon` | Mode hackathon: timer + VSCode + terminal + GitHub + Claude | `mode hackathon`, `lance le hackathon`, `setup hackathon` +2 | pipeline | — | — |
| 110 | `mode_data_science` | Mode data science: Jupyter + Kaggle + docs Python + terminal | `mode data science`, `mode datascience`, `lance jupyter` +2 | pipeline | — | — |
| 111 | `mode_devops` | Mode DevOps: Docker + dashboard + terminal + GitHub Actions | `mode devops`, `mode ops`, `lance le mode devops` +2 | pipeline | — | — |
| 112 | `mode_securite_audit` | Mode audit securite: Defender + ports + connexions + terminal | `mode securite`, `mode audit securite`, `lance un audit de securite` +2 | pipeline | — | — |
| 113 | `mode_trading_scalp` | Mode scalping: TradingView multi-timeframe + MEXC + terminal | `mode scalping`, `mode scalp`, `trading scalp` +2 | pipeline | — | — |
| 114 | `routine_midi` | Routine midi: pause + news + trading check rapide | `routine midi`, `pause midi`, `lunch break` +2 | pipeline | — | — |
| 115 | `routine_nuit_urgence` | Mode urgence nuit: tout fermer + sauvegarder + veille immediate | `urgence nuit`, `extinction d'urgence`, `dors maintenant` +2 | pipeline | — | Oui |
| 116 | `setup_meeting_rapide` | Meeting rapide: micro check + fermer musique + Teams/Discord | `meeting rapide`, `setup meeting`, `prepare un call rapide` +2 | pipeline | — | — |
| 117 | `mode_veille_tech` | Veille tech: Hacker News + dev.to + Product Hunt + Reddit/programming | `veille tech`, `mode veille technologique`, `quoi de neuf en tech` +2 | pipeline | — | — |
| 118 | `mode_freelance` | Mode freelance: factures + mails + calendar + Notion | `mode freelance`, `mode client`, `session freelance` +2 | pipeline | — | — |
| 119 | `mode_debug_production` | Debug prod: logs + monitoring + terminal + dashboard | `debug production`, `mode debug prod`, `urgence production` +2 | pipeline | — | — |
| 120 | `mode_apprentissage_code` | Mode apprentissage code: LeetCode + VSCode + docs + timer | `mode apprentissage code`, `session leetcode`, `mode kata` +2 | pipeline | — | — |
| 121 | `mode_tutorial` | Mode tutorial: YouTube + VSCode + terminal + docs | `mode tutorial`, `mode tuto`, `suis un tuto` +2 | pipeline | — | — |
| 122 | `mode_backup_total` | Backup total: tous les projets + snapshot systeme + rapport | `backup total`, `sauvegarde totale`, `backup complet` +2 | pipeline | — | Oui |
| 123 | `ouvre_dashboards_trading` | Tous les dashboards trading: TV + MEXC + CoinGecko + CoinMarketCap + DexScreener | `tous les dashboards trading`, `ouvre tout le trading`, `full trading view` +2 | pipeline | — | — |
| 124 | `mode_photo_edit` | Mode retouche photo: Paint + navigateur refs + Pinterest | `mode photo`, `mode retouche`, `retouche photo` +2 | pipeline | — | — |
| 125 | `mode_writing` | Mode ecriture: Google Docs + focus + nuit + Claude aide | `mode ecriture`, `mode redaction`, `session ecriture` +2 | pipeline | — | — |
| 126 | `mode_video_marathon` | Mode marathon video: Netflix + nuit + plein ecran + snacks time | `mode marathon`, `marathon video`, `binge watching` +2 | pipeline | — | — |
| 127 | `ouvre_kaggle_comet` | Ouvrir Kaggle dans Comet | `ouvre kaggle sur comet`, `kaggle comet`, `va sur kaggle comet` | pipeline | — | — |
| 128 | `ouvre_arxiv_comet` | Ouvrir arXiv dans Comet | `ouvre arxiv sur comet`, `arxiv comet`, `va sur arxiv comet` | pipeline | — | — |
| 129 | `ouvre_notion_comet` | Ouvrir Notion dans Comet | `ouvre notion sur comet`, `notion comet`, `va sur notion comet` | pipeline | — | — |
| 130 | `ouvre_stackoverflow_comet` | Ouvrir Stack Overflow dans Comet | `ouvre stackoverflow sur comet`, `stackoverflow comet`, `va sur stackoverflow comet` | pipeline | — | — |
| 131 | `ouvre_medium_comet` | Ouvrir Medium dans Comet | `ouvre medium sur comet`, `medium comet`, `va sur medium comet` | pipeline | — | — |
| 132 | `ouvre_gmail_comet` | Ouvrir Gmail dans Comet | `ouvre gmail sur comet`, `gmail comet`, `va sur gmail comet` +1 | pipeline | — | — |
| 133 | `mode_go_live` | Go Live: OBS + Twitch dashboard + Spotify + chat overlay | `go live`, `lance le stream maintenant`, `on est en direct` +2 | pipeline | — | — |
| 134 | `mode_end_stream` | End stream: fermer OBS + Twitch + recap | `arrete le stream`, `fin du live`, `end stream` +2 | pipeline | — | — |
| 135 | `mode_daily_report` | Daily report: git log + stats code + dashboard + Google Sheets | `rapport quotidien`, `daily report`, `genere le rapport` +2 | pipeline | — | — |
| 136 | `mode_api_test` | Mode API testing: terminal + navigateur API docs + outils test | `mode api test`, `teste les api`, `mode postman` +2 | pipeline | — | — |
| 137 | `mode_conference_full` | Conference: fermer distractions + Teams + micro + focus assist | `mode conference`, `mode visio complete`, `setup conference` +2 | pipeline | — | — |
| 138 | `mode_end_meeting` | Fin meeting: fermer Teams/Discord/Zoom + restaurer musique | `fin du meeting`, `fin de la reunion`, `end meeting` +2 | pipeline | — | — |
| 139 | `mode_home_theater` | Home theater: minimiser + nuit + volume max + Disney+/Netflix plein ecran | `mode home theater`, `mode cinema maison`, `soiree film maison` +2 | pipeline | — | — |
| 140 | `mode_refactoring` | Mode refactoring: VSCode + ruff + tests + git diff | `mode refactoring`, `session refactoring`, `lance le refactoring` +2 | pipeline | — | — |
| 141 | `mode_testing_complet` | Mode tests complet: pytest + coverage + lint + terminal | `mode testing complet`, `lance tous les tests`, `session testing` +2 | pipeline | — | — |
| 142 | `mode_deploy_checklist` | Checklist deploy: tests + lint + status git + build check | `checklist deploy`, `mode deploy`, `pret pour le deploiement` +2 | pipeline | — | — |
| 143 | `mode_documentation_code` | Mode doc code: VSCode + readthedocs + terminal + Notion | `mode documentation code`, `documente le code`, `session docs code` +2 | pipeline | — | — |
| 144 | `mode_open_source` | Mode open source: GitHub issues + PRs + VSCode + terminal | `mode open source`, `mode contribution`, `session open source` +2 | pipeline | — | — |
| 145 | `mode_side_project` | Mode side project: VSCode + navigateur + terminal + timer 2h | `mode side project`, `mode projet perso`, `lance le side project` +2 | pipeline | — | — |
| 146 | `mode_admin_sys` | Mode sysadmin: terminal + Event Viewer + services + ports | `mode sysadmin`, `mode administrateur`, `mode admin systeme` +2 | pipeline | — | — |
| 147 | `mode_reseau_complet` | Mode reseau complet: ping + DNS + WiFi + ports + IP | `mode reseau complet`, `diagnostic reseau total`, `analyse reseau complete` +2 | pipeline | — | — |
| 148 | `mode_finance` | Mode finance: banque + budget + trading + calculatrice | `mode finance`, `mode budget`, `gere mes finances` +2 | pipeline | — | — |
| 149 | `mode_voyage` | Mode voyage: Google Flights + Maps + Booking + meteo | `mode voyage`, `planifie un voyage`, `mode vacances` +2 | pipeline | — | — |
| 150 | `routine_aperitif` | Routine apero: fermer le travail + musique + ambiance | `routine apero`, `aperitif`, `c'est l'heure de l'apero` +2 | pipeline | — | — |
| 151 | `mode_cuisine` | Mode cuisine: YouTube recettes + timer + Spotify musique | `mode cuisine`, `je fais a manger`, `mode recette` +2 | pipeline | — | — |
| 152 | `mode_meditation` | Mode meditation: minimiser + nuit + sons relaxants | `mode meditation`, `medite`, `mode calme` +2 | pipeline | — | — |
| 153 | `mode_pair_programming` | Pair programming: VSCode Live Share + terminal + Discord | `mode pair programming`, `pair prog`, `session pair programming` +2 | pipeline | — | — |
| 154 | `mode_retrospective` | Retrospective: bilan semaine + git stats + Notion + Calendar | `mode retro`, `retrospective`, `bilan de la semaine` +2 | pipeline | — | — |
| 155 | `mode_demo` | Mode demo: dupliquer ecran + navigateur + dashboard + presentation | `mode demo`, `prepare la demo`, `session demo` +2 | pipeline | — | — |
| 156 | `mode_scrum_master` | Mode Scrum: board + standup + Calendar + timer | `mode scrum`, `mode scrum master`, `session scrum` +2 | pipeline | — | — |
| 157 | `sim_reveil_complet` | Simulation reveil: cluster + mails + trading + news + dashboard + café | `demarre la journee complete`, `simulation reveil`, `boot complet` +3 | pipeline | — | — |
| 158 | `sim_check_matinal` | Check matinal rapide: cluster health + GPU + RAM + trading | `check matinal`, `tout va bien ce matin`, `etat du matin` +2 | pipeline | — | — |
| 159 | `sim_start_coding` | Demarrer une session de code: git pull + VSCode + terminal + snap | `je commence a coder`, `start coding session`, `session de code` +2 | pipeline | — | — |
| 160 | `sim_code_and_test` | Code + test: lancer les tests + lint + afficher résultats | `teste mon code`, `code and test`, `verifie tout mon code` +2 | pipeline | — | — |
| 161 | `sim_commit_and_push` | Commiter et pusher le code | `commit et push`, `sauvegarde et pousse`, `envoie le code` +2 | pipeline | — | Oui |
| 162 | `sim_debug_session` | Session debug: devtools + terminal + logs + monitoring | `session debug complete`, `je debug`, `mode debug complet` +2 | pipeline | — | — |
| 163 | `sim_avant_reunion` | Avant reunion: fermer distractions + notes + agenda + micro check | `prepare la reunion`, `avant le meeting`, `pre reunion` +2 | pipeline | — | — |
| 164 | `sim_rejoindre_reunion` | Rejoindre: ouvrir Discord/Teams + partage ecran pret | `rejoins la reunion`, `join meeting`, `entre en reunion` +2 | pipeline | — | — |
| 165 | `sim_presenter_ecran` | Presenter: dupliquer ecran + ouvrir dashboard + plein ecran | `presente mon ecran`, `partage ecran presentation`, `lance la presentation maintenant` +1 | pipeline | — | — |
| 166 | `sim_apres_reunion` | Après reunion: fermer visio + restaurer musique + reprendre le dev | `reunion terminee reprends`, `apres le meeting`, `fin de la visio reprends` +2 | pipeline | — | — |
| 167 | `sim_pause_cafe` | Pause cafe: minimiser + verrouiller + 10 min | `pause cafe`, `je prends un cafe`, `coffee break` +2 | pipeline | — | — |
| 168 | `sim_pause_longue` | Pause longue: save + musique + nuit + verrouiller | `longue pause`, `grande pause`, `je fais une grande pause` +2 | pipeline | — | — |
| 169 | `sim_retour_pause` | Retour de pause: performance + rouvrir le dev + check cluster | `je suis de retour`, `retour de pause`, `fin de la pause` +2 | pipeline | — | — |
| 170 | `sim_recherche_intensive` | Recherche intensive: Claude + Perplexity + Scholar + Wikipedia + notes | `recherche intensive`, `session recherche complete`, `lance une grosse recherche` +1 | pipeline | — | — |
| 171 | `sim_formation_video` | Formation video: YouTube + notes + VSCode + timer 2h | `formation video complete`, `session formation`, `apprends en video` +2 | pipeline | — | — |
| 172 | `sim_analyse_trading` | Analyse trading: multi-timeframe + indicateurs + news crypto | `analyse trading complete`, `session analyse trading`, `analyse les marches` +1 | pipeline | — | — |
| 173 | `sim_execution_trading` | Execution trading: MEXC + TradingView + terminal signaux | `execute le trading`, `passe les ordres`, `session execution trades` +2 | pipeline | — | — |
| 174 | `sim_monitoring_positions` | Monitoring positions: MEXC + alertes + DexScreener | `surveille mes positions`, `monitoring trading`, `check mes trades` +2 | pipeline | — | — |
| 175 | `sim_layout_dev_split` | Layout dev split: VSCode gauche + navigateur droite | `layout dev split`, `code a gauche navigateur a droite`, `split dev layout` +1 | pipeline | — | — |
| 176 | `sim_layout_triple` | Layout triple: code + terminal + navigateur en quadrants | `layout triple`, `trois fenetres organisees`, `quadrant layout` +2 | pipeline | — | — |
| 177 | `sim_tout_fermer_propre` | Fermeture propre: sauvegarder + fermer apps + minimiser + night light | `ferme tout proprement`, `clean shutdown apps`, `termine proprement` +2 | pipeline | — | — |
| 178 | `sim_fin_journee_complete` | Fin de journee complete: backup + stats + nuit + economie + verrouiller | `fin de journee complete`, `termine la journee proprement`, `bonne nuit complete` +2 | pipeline | — | Oui |
| 179 | `sim_weekend_mode` | Mode weekend: fermer tout le dev + musique + news + Netflix | `mode weekend complet`, `c'est le weekend enfin`, `plus de travail weekend` +1 | pipeline | — | — |
| 180 | `sim_urgence_gpu` | Urgence GPU: check temperatures + vram + killprocess gourmand | `urgence gpu`, `les gpu chauffent trop`, `gpu en surchauffe` +2 | pipeline | — | — |
| 181 | `sim_urgence_reseau` | Urgence reseau: flush DNS + reset adapter + ping + diagnostic | `urgence reseau`, `internet ne marche plus`, `plus de connexion` +2 | pipeline | — | — |
| 182 | `sim_urgence_espace` | Urgence espace disque: taille disques + temp + downloads + cache | `urgence espace disque`, `plus de place`, `disque plein` +2 | pipeline | — | — |
| 183 | `sim_urgence_performance` | Urgence performance: CPU + RAM + processus zombies + services en echec | `urgence performance`, `le pc rame`, `tout est lent` +2 | pipeline | — | — |
| 184 | `sim_multitask_dev_trading` | Multitask dev+trading: split code/charts + cluster monitoring | `multitask dev et trading`, `code et trade en meme temps`, `dev plus trading` +1 | pipeline | — | — |
| 185 | `sim_multitask_email_code` | Multitask email+code: mails a gauche + VSCode a droite | `mails et code`, `email et dev`, `reponds aux mails en codant` +2 | pipeline | — | — |
| 186 | `sim_focus_extreme` | Focus extreme: fermer TOUT sauf VSCode + mute + night + timer 3h | `focus extreme`, `concentration absolue`, `zero distraction` +2 | pipeline | — | — |
| 187 | `sim_soiree_gaming` | Soiree gaming: fermer dev + performance + Steam + Game Bar | `soiree gaming`, `session jeu video`, `mode gamer complet` +2 | pipeline | — | — |
| 188 | `sim_soiree_film` | Soiree film: fermer tout + nuit + volume + Netflix plein ecran | `soiree film complete`, `on regarde un film`, `movie night` +2 | pipeline | — | — |
| 189 | `sim_soiree_musique` | Soiree musique: minimiser + Spotify + ambiance + volume | `soiree musique`, `ambiance musicale complete`, `music night` +2 | pipeline | — | — |
| 190 | `sim_maintenance_hebdo` | Maintenance hebdo: temp + cache + corbeille + DNS + logs + updates | `maintenance hebdomadaire`, `grand nettoyage de la semaine`, `nettoyage hebdo` +1 | pipeline | — | Oui |
| 191 | `sim_backup_hebdo` | Backup hebdo: tous les projets + snapshot + stats | `backup hebdomadaire`, `sauvegarde de la semaine`, `backup weekly` +1 | pipeline | — | Oui |
| 192 | `sim_diag_reseau_complet` | Diagnostic reseau: ping + DNS + traceroute + ports + IP publique | `diagnostic reseau complet`, `probleme internet complet`, `analyse le reseau a fond` +1 | pipeline | — | — |
| 193 | `sim_diag_wifi` | Diagnostic WiFi: signal + SSID + vitesse + DNS + latence | `probleme wifi complet`, `diagnostic wifi`, `le wifi deconne` +1 | pipeline | — | — |
| 194 | `sim_diag_cluster_deep` | Diagnostic cluster profond: ping + models + GPU + latence | `diagnostic cluster profond`, `debug cluster complet`, `le cluster repond plus` +1 | pipeline | — | — |
| 195 | `sim_audit_securite` | Audit securite: ports + connexions + autorun + defender + RDP + admin | `audit securite complet`, `check securite`, `scan securite total` +2 | pipeline | — | — |
| 196 | `sim_hardening_check` | Check durcissement: firewall + UAC + BitLocker + updates | `check hardening`, `durcissement systeme`, `securite avancee` +1 | pipeline | — | — |
| 197 | `sim_audit_mots_de_passe` | Audit mots de passe: politique + comptes + expiration | `audit mots de passe`, `politique password`, `securite comptes` +1 | pipeline | — | — |
| 198 | `sim_new_project_python` | Nouveau projet Python: dossier + venv + git + VSCode | `nouveau projet python`, `init projet python`, `cree un projet python` +1 | pipeline | — | — |
| 199 | `sim_new_project_node` | Nouveau projet Node.js: dossier + npm init + git + VSCode | `nouveau projet node`, `init projet javascript`, `cree un projet node` +1 | pipeline | — | — |
| 200 | `sim_clone_and_setup` | Cloner un repo et l'ouvrir: git clone + VSCode + install deps | `clone et setup {repo}`, `git clone et ouvre {repo}`, `clone le projet {repo}` +1 | pipeline | repo | — |
| 201 | `sim_grand_nettoyage_disque` | Grand nettoyage: temp + cache + corbeille + thumbnails + crash dumps + pycache | `grand nettoyage du disque`, `mega clean`, `libere de l'espace` +2 | pipeline | — | Oui |
| 202 | `sim_archive_vieux_projets` | Archiver les projets non modifies depuis 30 jours | `archive les vieux projets`, `zip les anciens projets`, `range les projets inactifs` +1 | pipeline | — | — |
| 203 | `sim_scan_fichiers_orphelins` | Scanner fichiers orphelins: gros fichiers + doublons + anciens | `scan fichiers orphelins`, `nettoyage intelligent`, `analyse les fichiers` +1 | pipeline | — | — |
| 204 | `sim_design_review` | Design review: screen ruler + color picker + text extractor + screenshot | `review design complet`, `analyse visuelle`, `design review` +2 | pipeline | — | — |
| 205 | `sim_layout_productif` | Layout productif: FancyZones + always on top + snap windows | `layout productif`, `arrange mon ecran`, `organise mes fenetres` +1 | pipeline | — | — |
| 206 | `sim_copier_texte_image` | Copier du texte depuis une image: OCR + clipboard + notification | `copie le texte de l'image`, `ocr et copie`, `lis l'image` +1 | pipeline | — | — |
| 207 | `sim_db_health_check` | Health check bases: jarvis.db + etoile.db + taille + integrite | `health check des bases`, `check les db`, `bases de donnees ok` +1 | pipeline | — | — |
| 208 | `sim_db_backup` | Backup toutes les bases de donnees | `backup les bases`, `sauvegarde les db`, `copie les bases de donnees` +1 | pipeline | — | — |
| 209 | `sim_db_stats` | Statistiques des bases: tables, lignes, taille par table | `stats des bases`, `metriques db`, `combien dans les bases` +1 | pipeline | — | — |
| 210 | `sim_docker_full_status` | Status Docker complet: containers + images + volumes + espace | `status docker complet`, `etat complet docker`, `docker overview` +1 | pipeline | — | — |
| 211 | `sim_docker_cleanup` | Nettoyage Docker: prune containers + images + volumes + build cache | `nettoie docker a fond`, `docker cleanup total`, `purge docker complete` +1 | pipeline | — | Oui |
| 212 | `sim_docker_restart_all` | Redemarrer tous les conteneurs Docker | `redemarre docker`, `restart all containers`, `relance les conteneurs` +1 | pipeline | — | — |
| 213 | `sim_code_review_prep` | Preparer une code review: git diff + VSCode + browser GitHub | `prepare la code review`, `session review`, `revue de code` +1 | pipeline | — | — |
| 214 | `sim_code_review_split` | Layout code review: VSCode gauche + GitHub droite | `layout review`, `split code review`, `cote a cote review` +1 | pipeline | — | — |
| 215 | `sim_learn_topic` | Session apprentissage: YouTube + docs + notes | `session apprentissage {topic}`, `je veux apprendre {topic}`, `cours sur {topic}` +1 | pipeline | topic | — |
| 216 | `sim_learn_python` | Apprentissage Python: docs + exercices + REPL | `apprends moi python`, `session python`, `tuto python` +1 | pipeline | — | — |
| 217 | `sim_learn_rust` | Apprentissage Rust: The Book + playground | `apprends moi rust`, `session rust`, `tuto rust` +1 | pipeline | — | — |
| 218 | `sim_layout_4_quadrants` | Layout 4 quadrants: Code + Terminal + Browser + Dashboard | `4 quadrants`, `layout quatre fenetres`, `quatre ecrans` +2 | pipeline | — | — |
| 219 | `sim_layout_trading_full` | Layout trading: MEXC + CoinGecko + Terminal + Dashboard | `layout trading complet`, `ecran trading`, `multi fenetre trading` +1 | pipeline | — | — |
| 220 | `sim_layout_recherche` | Layout recherche: Perplexity + Claude + Notes | `layout recherche`, `ecran recherche`, `mode recherche multi` +1 | pipeline | — | — |
| 221 | `sim_remote_work_start` | Setup teletravail: VPN + Slack + Gmail + VSCode + focus | `mode teletravail`, `start remote work`, `je teletravaille` +1 | pipeline | — | — |
| 222 | `sim_standup_meeting` | Preparer le standup: git log hier + today + blocker check | `prepare le standup`, `daily standup`, `scrum preparation` +1 | pipeline | — | — |
| 223 | `sim_crypto_research` | Recherche crypto: CoinGecko + CoinDesk + Etherscan + Reddit | `recherche crypto complete`, `analyse crypto`, `research trading` +1 | pipeline | — | — |
| 224 | `sim_trading_session` | Session trading: MEXC + TradingView + Terminal signaux | `session trading complete`, `lance le trading`, `je vais trader` +1 | pipeline | — | — |
| 225 | `sim_post_crash_recovery` | Post-crash: check disques + logs + services + GPU + cluster | `recovery apres crash`, `le pc a plante`, `post crash check` +1 | pipeline | — | — |
| 226 | `sim_repair_system` | Reparation systeme: DISM + SFC + services restart | `repare le systeme`, `system repair`, `fix windows` +1 | pipeline | — | Oui |
| 227 | `sim_fullstack_build` | Build complet: lint + tests + build + rapport | `build complet du projet`, `full build`, `lance tout le build` +1 | pipeline | — | — |
| 228 | `sim_deploy_check` | Pre-deploy: git status + tests + deps check + commit | `check avant deploiement`, `pre deploy check`, `pret pour deployer` +1 | pipeline | — | — |
| 229 | `sim_git_release` | Release: tag + changelog + push tags | `fais une release`, `prepare la release`, `git release` +1 | pipeline | — | — |
| 230 | `sim_api_test_session` | Session API: Postman + docs + terminal HTTP | `session test api`, `teste les apis`, `ouvre le setup api` +1 | pipeline | — | — |
| 231 | `sim_api_endpoints_check` | Verifier tous les endpoints locaux (cluster) | `check tous les endpoints`, `verifie les apis du cluster`, `test endpoints locaux` +1 | pipeline | — | — |
| 232 | `sim_social_all` | Ouvrir tous les reseaux sociaux | `ouvre tous les reseaux sociaux`, `social media complet`, `lance tous les socials` +1 | pipeline | — | — |
| 233 | `sim_content_creation` | Setup creation contenu: Canva + Unsplash + notes | `setup creation contenu`, `je vais creer du contenu`, `mode creation` +1 | pipeline | — | — |
| 234 | `sim_design_session` | Session design: Figma + Dribbble + Coolors + Font Awesome | `session design`, `mode design`, `lance le design` +1 | pipeline | — | — |
| 235 | `sim_ui_inspiration` | Inspiration UI: Dribbble + Behance + Awwwards | `inspiration ui`, `inspiration design`, `montre moi du beau` +1 | pipeline | — | — |
| 236 | `sim_optimize_full` | Optimisation: temp + startup + services + defrag check | `optimise le systeme`, `full optimization`, `accelere le pc` +1 | pipeline | — | — |
| 237 | `sim_cleanup_aggressive` | Nettoyage agressif: temp + cache + logs + recycle bin | `nettoyage agressif`, `nettoie tout a fond`, `libere maximum` +1 | pipeline | — | Oui |
| 238 | `sim_learn_coding` | Learning code: YouTube + MDN + W3Schools + exercism | `session apprentissage code`, `je veux apprendre`, `mode apprentissage` +1 | pipeline | — | — |
| 239 | `sim_learn_ai` | Learning IA: HuggingFace + Papers + Cours + Playground | `session apprentissage ia`, `apprendre le machine learning`, `mode apprentissage ia` +1 | pipeline | — | — |
| 240 | `sim_pomodoro_25` | Pomodoro 25min: timer + focus assist + notification | `lance un pomodoro`, `pomodoro 25 minutes`, `timer pomodoro` +1 | pipeline | — | — |
| 241 | `sim_backup_turbo` | Backup turbo: git bundle + zip data + rapport | `backup le projet`, `sauvegarde turbo`, `backup complet` +1 | pipeline | — | — |
| 242 | `sim_backup_verify` | Verifier les backups: taille + date + integrite | `verifie les backups`, `check les sauvegardes`, `status backup` +1 | pipeline | — | — |
| 243 | `sim_morning_routine` | Routine matin: meteo + news + mails + cluster + standup | `routine du matin`, `bonjour jarvis`, `demarre la journee` +1 | pipeline | — | — |
| 244 | `sim_evening_shutdown` | Routine soir: git status + save + clear temp + veille | `routine du soir`, `bonsoir jarvis`, `fin de journee` +1 | pipeline | — | — |
| 245 | `sim_freelance_setup` | Setup freelance: Malt + factures + timer + mail | `mode freelance`, `setup freelance`, `session freelance` +1 | pipeline | — | — |
| 246 | `sim_client_meeting` | Prep meeting client: Teams + notes + projet + timer | `prepare le meeting client`, `meeting client`, `reunion client` +1 | pipeline | — | — |
| 247 | `sim_db_backup_all` | Backup toutes les DBs: jarvis + etoile + trading | `backup toutes les bases`, `sauvegarde les bases`, `db backup all` +1 | pipeline | — | — |
| 248 | `sim_security_full_audit` | Audit secu: ports + firewall + users + certs + deps | `audit securite complet`, `full security audit`, `scan securite total` +1 | pipeline | — | — |
| 249 | `sim_security_network` | Audit reseau: connexions + DNS + ARP + routes | `audit reseau`, `scan reseau complet`, `network security audit` +1 | pipeline | — | — |
| 250 | `sim_benchmark_system` | Benchmark: CPU + RAM + disque + GPU + reseau | `benchmark systeme`, `performance complete`, `teste les performances` +1 | pipeline | — | — |
| 251 | `sim_benchmark_cluster` | Benchmark cluster: ping tous les noeuds + latence | `benchmark cluster`, `teste le cluster`, `latence cluster` +1 | pipeline | — | — |
| 252 | `sim_doc_session` | Session docs: VSCode + docs + preview markdown | `session documentation`, `ecris la doc`, `mode documentation` +1 | pipeline | — | — |
| 253 | `sim_doc_generate` | Generer toute la doc: vocale + README + changelog | `genere toute la doc`, `regenere la documentation`, `update la doc` +1 | pipeline | — | — |
| 254 | `sim_ai_workspace` | Workspace IA: HuggingFace + Papers + GPU monitor + terminal | `workspace ia`, `espace de travail ia`, `mode machine learning` +1 | pipeline | — | — |
| 255 | `sim_model_eval` | Evaluation modele: benchmark cluster + comparaison | `evalue les modeles`, `benchmark modeles`, `compare les modeles` +1 | pipeline | — | — |
| 256 | `sim_home_office` | Home office: Teams + Mail + Spotify + cluster + news | `mode bureau`, `home office`, `mode teletravail` +1 | pipeline | — | — |
| 257 | `sim_focus_deep_work` | Deep work: ferme tout + focus assist + timer 90min + musique lo-fi | `mode deep work`, `concentration maximale`, `focus profond` +1 | pipeline | — | — |
| 258 | `sim_weekend_chill` | Weekend: Netflix + Spotify + food delivery + mode eco | `mode weekend`, `weekend chill`, `mode detente` +1 | pipeline | — | — |
| 259 | `sim_movie_night` | Soiree film: minimiser tout + Netflix + lumiere tamisee | `soiree film`, `movie night`, `mode cinema maison` +1 | pipeline | — | — |
| 260 | `sim_tech_news` | Veille tech: HN + TechCrunch + Reddit + The Verge | `veille tech`, `news tech`, `ouvre les news tech` +1 | pipeline | — | — |
| 261 | `sim_ai_news` | News IA: arXiv + HuggingFace + Semantic Scholar + Papers | `news ia`, `actualites intelligence artificielle`, `veille ia` +1 | pipeline | — | — |
| 262 | `sim_deploy_vercel` | Deploy Vercel: build + push + deploy + verify | `deploie sur vercel`, `deploy vercel`, `push vercel` +1 | pipeline | — | — |
| 263 | `sim_deploy_docker` | Deploy Docker: build image + tag + push registry | `deploie en docker`, `docker deploy`, `push docker image` +1 | pipeline | — | — |
| 264 | `sim_datascience_setup` | Data Science: Jupyter + HuggingFace + GPU monitor | `mode data science`, `setup data science`, `workspace datascience` +1 | pipeline | — | — |
| 265 | `sim_kaggle_session` | Session Kaggle: competitions + notebooks + datasets | `session kaggle`, `mode kaggle`, `ouvre kaggle` +1 | pipeline | — | — |
| 266 | `sim_interview_prep` | Prep entretien: LeetCode + GeeksForGeeks + docs + notes | `prepare l'entretien`, `mode interview`, `practice coding` +1 | pipeline | — | — |
| 267 | `sim_photo_edit` | Photo edit: Photopea + Pexels + Remove.bg + Canva | `mode edition photo`, `session photo`, `edite des photos` +1 | pipeline | — | — |
| 268 | `sim_system_hardening` | Hardening: firewall + users + ports + updates + audit | `renforce la securite`, `system hardening`, `securise le systeme` +1 | pipeline | — | — |
| 269 | `sim_meal_prep` | Meal prep: Marmiton + 750g + Uber Eats + notes | `meal prep`, `planifie les repas`, `qu'est ce qu'on mange` +1 | pipeline | — | — |
| 270 | `sim_monitoring_full` | Monitoring: GPU + cluster + ports + logs + disk | `monitoring complet`, `check tout le monitoring`, `surveillance totale` +1 | pipeline | — | — |
| 271 | `sim_jarvis_selfcheck` | Auto-diagnostic JARVIS: config + deps + DB + commands + cluster | `auto diagnostic jarvis`, `jarvis self check`, `verifie toi meme` +1 | pipeline | — | — |
| 272 | `sim_network_diag_full` | Diag reseau complet: wifi + ping + DNS + speed + ports | `diagnostic reseau complet`, `teste tout le reseau`, `reseau complet check` +1 | pipeline | — | — |
| 273 | `sim_opensource_session` | Open source: GitHub + issues + fork + terminal | `mode open source`, `session contribution`, `contribute au code` +1 | pipeline | — | — |
| 274 | `sim_stream_setup_full` | Stream setup: OBS + Twitch + Spotify + chat + high perf | `setup stream complet`, `je vais streamer`, `mode streamer pro` +1 | pipeline | — | — |
| 275 | `sim_crypto_portfolio` | Crypto portfolio: CoinGecko + DeFi Llama + Zapper + Dune | `portfolio crypto`, `check mes cryptos`, `gestion crypto complete` +1 | pipeline | — | — |
| 276 | `sim_emergency_recovery` | Recovery urgence: disques + events + services + GPU + restore points | `urgence recovery`, `le pc va mal`, `gros probleme` +1 | pipeline | — | — |
| 277 | `sim_weekly_review` | Review hebdo: commits semaine + issues + LOC + DB + cluster perf | `review hebdomadaire`, `bilan de la semaine`, `weekly review` +1 | pipeline | — | — |
| 278 | `sim_demo_prep` | Prep demo: clean bureau + full screen + terminal + slides | `prepare la demo`, `mode demo`, `setup presentation` +1 | pipeline | — | — |

## Saisie

**3 commandes**

| # | Nom | Description | Declencheurs | Type | Params | Confirm |
|---|-----|-------------|--------------|------|--------|---------|
| 1 | `texte_majuscule` | Convertir le presse-papier en majuscules | `en majuscules`, `tout en majuscules`, `texte en majuscules` +2 | powershell | — | — |
| 2 | `texte_minuscule` | Convertir le presse-papier en minuscules | `en minuscules`, `tout en minuscules`, `texte en minuscules` +1 | powershell | — | — |
| 3 | `ouvrir_dictee` | Activer la dictee vocale Windows | `dicte`, `dictee windows`, `active la dictee` +2 | hotkey | — | — |

## Systeme & Maintenance

**669 commandes**

| # | Nom | Description | Declencheurs | Type | Params | Confirm |
|---|-----|-------------|--------------|------|--------|---------|
| 1 | `verrouiller` | Verrouiller le PC | `verrouille le pc`, `verrouille l'ecran`, `lock` +2 | powershell | — | Oui |
| 2 | `eteindre` | Eteindre le PC | `eteins le pc`, `eteindre le pc`, `arrete le pc` +6 | powershell | — | Oui |
| 3 | `redemarrer` | Redemarrer le PC | `redemarre le pc`, `redemarrer le pc`, `reboot` +6 | powershell | — | Oui |
| 4 | `veille` | Mettre en veille | `mets en veille`, `veille`, `sleep` +3 | powershell | — | Oui |
| 5 | `capture_ecran` | Capture d'ecran | `capture ecran`, `screenshot`, `prends une capture` +3 | hotkey | — | — |
| 6 | `info_systeme` | Infos systeme | `info systeme`, `infos systeme`, `statut systeme` +5 | jarvis_tool | — | — |
| 7 | `info_gpu` | Infos GPU | `info gpu`, `infos gpu`, `statut gpu` +4 | jarvis_tool | — | — |
| 8 | `info_reseau` | Infos reseau | `info reseau`, `infos reseau`, `statut reseau` +3 | jarvis_tool | — | — |
| 9 | `processus` | Lister les processus | `liste les processus`, `montre les processus`, `quels processus tournent` +1 | jarvis_tool | — | — |
| 10 | `kill_process` | Tuer un processus | `tue le processus {nom}`, `kill {nom}`, `ferme le processus {nom}` +1 | jarvis_tool | nom | Oui |
| 11 | `wifi_scan` | Scanner les reseaux Wi-Fi | `scan wifi`, `wifi scan`, `reseaux wifi` +6 | jarvis_tool | — | — |
| 12 | `ping_host` | Ping un hote | `ping {host}`, `teste la connexion a {host}`, `verifie {host}` +1 | jarvis_tool | host | — |
| 13 | `vider_corbeille` | Vider la corbeille | `vide la corbeille`, `nettoie la corbeille`, `vider la corbeille` +1 | powershell | — | Oui |
| 14 | `mode_nuit` | Activer/desactiver le mode nuit | `mode nuit`, `lumiere bleue`, `filtre bleu` +3 | hotkey | — | — |
| 15 | `ouvrir_run` | Ouvrir la boite Executer | `ouvre executer`, `boite de dialogue executer`, `run` +2 | hotkey | — | — |
| 16 | `recherche_windows` | Recherche Windows | `recherche windows`, `cherche sur le pc`, `recherche sur le pc` +2 | hotkey | — | — |
| 17 | `centre_notifications` | Ouvrir le centre de notifications | `ouvre les notifications`, `notifications`, `centre de notifications` +1 | hotkey | — | — |
| 18 | `ouvrir_widgets` | Ouvrir les widgets | `ouvre les widgets`, `widgets`, `affiche les widgets` +1 | hotkey | — | — |
| 19 | `ouvrir_emojis` | Ouvrir le panneau emojis | `ouvre les emojis`, `emojis`, `panneau emojis` +1 | hotkey | — | — |
| 20 | `projeter_ecran` | Projeter l'ecran | `projette l'ecran`, `duplique l'ecran`, `mode ecran` +2 | hotkey | — | — |
| 21 | `vue_taches` | Vue des taches / bureaux virtuels | `vue des taches`, `bureaux virtuels`, `task view` +2 | hotkey | — | — |
| 22 | `bureau_suivant` | Passer au bureau virtuel suivant | `bureau suivant`, `prochain bureau`, `next desktop` +1 | hotkey | — | — |
| 23 | `bureau_precedent` | Passer au bureau virtuel precedent | `bureau precedent`, `bureau virtuel precedent`, `previous desktop` +1 | hotkey | — | — |
| 24 | `ouvrir_parametres` | Ouvrir les parametres Windows | `ouvre les parametres`, `parametres`, `reglages` +3 | ms_settings | — | — |
| 25 | `param_wifi` | Parametres Wi-Fi | `parametres wifi`, `reglages wifi`, `ouvre les parametres wifi` +1 | ms_settings | — | — |
| 26 | `param_bluetooth` | Parametres Bluetooth | `parametres bluetooth`, `reglages bluetooth`, `ouvre les parametres bluetooth` +1 | ms_settings | — | — |
| 27 | `param_affichage` | Parametres d'affichage | `parametres affichage`, `reglages ecran`, `parametres ecran` +1 | ms_settings | — | — |
| 28 | `param_son` | Parametres son | `parametres son`, `reglages audio`, `parametres audio` +1 | ms_settings | — | — |
| 29 | `param_stockage` | Espace disque et stockage | `espace disque`, `stockage`, `parametres stockage` +2 | ms_settings | — | — |
| 30 | `param_mises_a_jour` | Mises a jour Windows | `mises a jour`, `windows update`, `mise a jour` +2 | ms_settings | — | — |
| 31 | `param_alimentation` | Parametres d'alimentation | `parametres alimentation`, `economie energie`, `reglages alimentation` +1 | ms_settings | — | — |
| 32 | `bluetooth_on` | Activer le Bluetooth | `active le bluetooth`, `allume bluetooth`, `bluetooth on` +2 | powershell | — | — |
| 33 | `bluetooth_off` | Desactiver le Bluetooth | `desactive le bluetooth`, `coupe bluetooth`, `bluetooth off` +2 | powershell | — | — |
| 34 | `luminosite_haut` | Augmenter la luminosite | `augmente la luminosite`, `plus lumineux`, `luminosite plus` +1 | powershell | — | — |
| 35 | `luminosite_bas` | Baisser la luminosite | `baisse la luminosite`, `moins lumineux`, `luminosite moins` +1 | powershell | — | — |
| 36 | `lister_services` | Lister les services Windows | `liste les services`, `services windows`, `quels services` +1 | jarvis_tool | — | — |
| 37 | `demarrer_service` | Demarrer un service Windows | `demarre le service {nom}`, `start service {nom}`, `lance le service {nom}` | jarvis_tool | nom | — |
| 38 | `arreter_service` | Arreter un service Windows | `arrete le service {nom}`, `stop service {nom}`, `stoppe le service {nom}` | jarvis_tool | nom | Oui |
| 39 | `resolution_ecran` | Resolution de l'ecran | `resolution ecran`, `quelle resolution`, `resolution de l'ecran` +1 | jarvis_tool | — | — |
| 40 | `taches_planifiees` | Taches planifiees Windows | `taches planifiees`, `taches automatiques`, `scheduled tasks` +1 | jarvis_tool | — | — |
| 41 | `mode_avion_on` | Activer le mode avion | `active le mode avion`, `mode avion`, `mode avion on` +2 | ms_settings | — | — |
| 42 | `micro_mute` | Couper le microphone | `coupe le micro`, `mute le micro`, `micro off` +2 | powershell | — | — |
| 43 | `micro_unmute` | Reactiver le microphone | `reactive le micro`, `unmute micro`, `micro on` +2 | powershell | — | — |
| 44 | `param_camera` | Parametres camera | `parametres camera`, `reglages camera`, `config camera` +1 | ms_settings | — | — |
| 45 | `nouveau_bureau` | Creer un nouveau bureau virtuel | `nouveau bureau`, `cree un bureau`, `ajoute un bureau` +2 | hotkey | — | — |
| 46 | `fermer_bureau` | Fermer le bureau virtuel actif | `ferme le bureau`, `ferme ce bureau`, `supprime le bureau` +2 | hotkey | — | — |
| 47 | `zoom_avant` | Zoomer | `zoom avant`, `zoom plus`, `agrandis` +2 | hotkey | — | — |
| 48 | `zoom_arriere` | Dezoomer | `zoom arriere`, `zoom moins`, `retrecis` +2 | hotkey | — | — |
| 49 | `zoom_reset` | Reinitialiser le zoom | `zoom normal`, `zoom reset`, `taille normale` +1 | hotkey | — | — |
| 50 | `imprimer` | Imprimer | `imprime`, `imprimer`, `print` +2 | hotkey | — | — |
| 51 | `renommer` | Renommer le fichier selectionne | `renomme`, `renommer`, `rename` +2 | hotkey | — | — |
| 52 | `supprimer` | Supprimer le fichier/element selectionne | `supprime`, `supprimer`, `delete` +7 | hotkey | — | — |
| 53 | `proprietes` | Proprietes du fichier selectionne | `proprietes`, `proprietes du fichier`, `infos fichier` +1 | hotkey | — | — |
| 54 | `actualiser` | Actualiser la page ou le dossier | `actualise`, `rafraichis`, `refresh` +3 | hotkey | — | — |
| 55 | `verrouiller_rapide` | Verrouiller le PC rapidement | `verrouille`, `lock`, `verrouille vite` +1 | hotkey | — | — |
| 56 | `loupe` | Activer la loupe / zoom accessibilite | `active la loupe`, `loupe`, `magnifier` +2 | hotkey | — | — |
| 57 | `loupe_off` | Desactiver la loupe | `desactive la loupe`, `ferme la loupe`, `loupe off` +1 | hotkey | — | — |
| 58 | `narrateur` | Activer/desactiver le narrateur | `active le narrateur`, `narrateur`, `narrator` +2 | hotkey | — | — |
| 59 | `clavier_visuel` | Ouvrir le clavier visuel | `clavier visuel`, `ouvre le clavier`, `clavier ecran` +2 | powershell | — | — |
| 60 | `dictee` | Activer la dictee vocale Windows | `dictee`, `dictee vocale`, `lance la dictee` +3 | hotkey | — | — |
| 61 | `contraste_eleve` | Activer le mode contraste eleve | `contraste eleve`, `high contrast`, `mode contraste` +1 | hotkey | — | — |
| 62 | `param_accessibilite` | Parametres d'accessibilite | `parametres accessibilite`, `reglages accessibilite`, `accessibilite` +1 | ms_settings | — | — |
| 63 | `enregistrer_ecran` | Enregistrer l'ecran (Xbox Game Bar) | `enregistre l'ecran`, `lance l'enregistrement`, `record` +3 | hotkey | — | — |
| 64 | `game_bar` | Ouvrir la Xbox Game Bar | `ouvre la game bar`, `game bar`, `xbox game bar` +1 | hotkey | — | — |
| 65 | `snap_layout` | Ouvrir les dispositions Snap | `snap layout`, `disposition fenetre`, `snap` +2 | hotkey | — | — |
| 66 | `plan_performance` | Activer le mode performances | `mode performance`, `performances maximales`, `haute performance` +2 | powershell | — | — |
| 67 | `plan_equilibre` | Activer le mode equilibre | `mode equilibre`, `plan equilibre`, `balanced` +2 | powershell | — | — |
| 68 | `plan_economie` | Activer le mode economie d'energie | `mode economie`, `economie d'energie`, `power saver` +2 | powershell | — | — |
| 69 | `ipconfig` | Afficher la configuration IP | `montre l'ip`, `quelle est mon adresse ip`, `ipconfig` +2 | jarvis_tool | — | — |
| 70 | `vider_dns` | Vider le cache DNS | `vide le cache dns`, `flush dns`, `nettoie le dns` +2 | powershell | — | — |
| 71 | `param_vpn` | Parametres VPN | `parametres vpn`, `reglages vpn`, `config vpn` +2 | ms_settings | — | — |
| 72 | `param_proxy` | Parametres proxy | `parametres proxy`, `reglages proxy`, `config proxy` +1 | ms_settings | — | — |
| 73 | `etendre_ecran` | Etendre l'affichage sur un second ecran | `etends l'ecran`, `double ecran`, `ecran etendu` +2 | powershell | — | — |
| 74 | `dupliquer_ecran` | Dupliquer l'affichage | `duplique l'ecran`, `meme image`, `ecran duplique` +2 | powershell | — | — |
| 75 | `ecran_principal_seul` | Afficher uniquement sur l'ecran principal | `ecran principal seulement`, `un seul ecran`, `desactive le second ecran` +1 | powershell | — | — |
| 76 | `ecran_secondaire_seul` | Afficher uniquement sur le second ecran | `ecran secondaire seulement`, `second ecran uniquement`, `affiche sur l'autre ecran` +1 | powershell | — | — |
| 77 | `focus_assist_on` | Activer l'aide a la concentration (ne pas deranger) | `ne pas deranger`, `focus assist`, `mode silencieux` +2 | powershell | — | — |
| 78 | `focus_assist_off` | Desactiver l'aide a la concentration | `desactive ne pas deranger`, `reactive les notifications`, `focus assist off` +1 | powershell | — | — |
| 79 | `taskbar_hide` | Masquer la barre des taches | `cache la barre des taches`, `masque la taskbar`, `barre des taches invisible` +1 | powershell | — | — |
| 80 | `taskbar_show` | Afficher la barre des taches | `montre la barre des taches`, `affiche la taskbar`, `barre des taches visible` +1 | powershell | — | — |
| 81 | `night_light_on` | Activer l'eclairage nocturne | `active la lumiere nocturne`, `night light on`, `eclairage nocturne` +2 | powershell | — | — |
| 82 | `night_light_off` | Desactiver l'eclairage nocturne | `desactive la lumiere nocturne`, `night light off`, `lumiere normale` +1 | powershell | — | — |
| 83 | `info_disques` | Afficher l'espace disque | `espace disque`, `info disques`, `combien de place` +2 | powershell | — | — |
| 84 | `vider_temp` | Vider les fichiers temporaires | `vide les fichiers temporaires`, `nettoie les temp`, `supprime les temp` +1 | powershell | — | Oui |
| 85 | `ouvrir_alarmes` | Ouvrir l'application Horloge/Alarmes | `ouvre les alarmes`, `alarme`, `minuteur` +3 | app_open | — | — |
| 86 | `historique_activite` | Ouvrir l'historique d'activite Windows | `historique activite`, `timeline`, `activites recentes` +2 | ms_settings | — | — |
| 87 | `param_clavier` | Parametres clavier | `parametres clavier`, `reglages clavier`, `config clavier` +2 | ms_settings | — | — |
| 88 | `param_souris` | Parametres souris | `parametres souris`, `reglages souris`, `config souris` +2 | ms_settings | — | — |
| 89 | `param_batterie` | Parametres batterie | `parametres batterie`, `etat batterie`, `batterie` +2 | ms_settings | — | — |
| 90 | `param_comptes` | Parametres des comptes utilisateur | `parametres comptes`, `comptes utilisateur`, `mon compte` +1 | ms_settings | — | — |
| 91 | `param_heure` | Parametres date et heure | `parametres heure`, `reglages heure`, `date et heure` +2 | ms_settings | — | — |
| 92 | `param_langue` | Parametres de langue | `parametres langue`, `changer la langue`, `langue windows` +1 | ms_settings | — | — |
| 93 | `windows_security` | Ouvrir Windows Security | `ouvre la securite`, `securite windows`, `windows security` +3 | app_open | — | — |
| 94 | `pare_feu` | Parametres du pare-feu | `parametres pare-feu`, `firewall`, `ouvre le pare-feu` +2 | ms_settings | — | — |
| 95 | `partage_proximite` | Parametres de partage a proximite | `partage a proximite`, `nearby sharing`, `partage rapide` +2 | ms_settings | — | — |
| 96 | `hotspot` | Activer le point d'acces mobile | `point d'acces`, `hotspot`, `partage de connexion` +2 | ms_settings | — | — |
| 97 | `defrag_disque` | Optimiser les disques (defragmentation) | `defragmente`, `optimise les disques`, `defragmentation` +2 | powershell | — | — |
| 98 | `gestion_disques` | Ouvrir le gestionnaire de disques | `gestionnaire de disques`, `gestion des disques`, `disk manager` +2 | powershell | — | — |
| 99 | `variables_env` | Ouvrir les variables d'environnement | `variables d'environnement`, `variables env`, `env variables` +2 | powershell | — | — |
| 100 | `evenements_windows` | Ouvrir l'observateur d'evenements | `observateur d'evenements`, `event viewer`, `journaux windows` +2 | powershell | — | — |
| 101 | `moniteur_ressources` | Ouvrir le moniteur de ressources | `moniteur de ressources`, `resource monitor`, `ressources systeme` +2 | powershell | — | — |
| 102 | `info_systeme_detaille` | Ouvrir les informations systeme detaillees | `informations systeme detaillees`, `msinfo`, `infos systeme avancees` +2 | powershell | — | — |
| 103 | `nettoyage_disque` | Ouvrir le nettoyage de disque Windows | `nettoyage de disque`, `disk cleanup`, `nettoie le disque` +2 | powershell | — | — |
| 104 | `gestionnaire_peripheriques` | Ouvrir le gestionnaire de peripheriques | `gestionnaire de peripheriques`, `device manager`, `mes peripheriques` +2 | powershell | — | — |
| 105 | `connexions_reseau` | Ouvrir les connexions reseau | `connexions reseau`, `adaptateurs reseau`, `network connections` +2 | powershell | — | — |
| 106 | `programmes_installees` | Ouvrir programmes et fonctionnalites | `programmes installes`, `applications installees`, `liste des programmes` +1 | ms_settings | — | — |
| 107 | `demarrage_apps` | Gerer les applications au demarrage | `applications demarrage`, `programmes au demarrage`, `gere le demarrage` +2 | ms_settings | — | — |
| 108 | `param_confidentialite` | Parametres de confidentialite | `parametres confidentialite`, `privacy`, `confidentialite` +2 | ms_settings | — | — |
| 109 | `param_reseau_avance` | Parametres reseau avances | `parametres reseau avances`, `reseau avance`, `advanced network` +1 | ms_settings | — | — |
| 110 | `partager_ecran` | Partager l'ecran via Miracast | `partage l'ecran`, `miracast`, `cast` +3 | hotkey | — | — |
| 111 | `param_imprimantes` | Parametres imprimantes et scanners | `parametres imprimantes`, `imprimante`, `ouvre les imprimantes` +2 | ms_settings | — | — |
| 112 | `param_fond_ecran` | Personnaliser le fond d'ecran | `fond d'ecran`, `change le fond`, `wallpaper` +2 | ms_settings | — | — |
| 113 | `param_couleurs` | Personnaliser les couleurs Windows | `couleurs windows`, `couleur d'accent`, `theme couleur` +4 | ms_settings | — | — |
| 114 | `param_ecran_veille` | Parametres ecran de verrouillage | `ecran de veille`, `ecran de verrouillage`, `lock screen` +1 | ms_settings | — | — |
| 115 | `param_polices` | Gerer les polices installees | `polices`, `fonts`, `gere les polices` +2 | ms_settings | — | — |
| 116 | `param_themes` | Gerer les themes Windows | `themes windows`, `change le theme`, `personnalise le theme` +2 | ms_settings | — | — |
| 117 | `mode_sombre` | Activer le mode sombre Windows | `active le mode sombre`, `dark mode on`, `theme sombre` +2 | powershell | — | — |
| 118 | `mode_clair` | Activer le mode clair Windows | `active le mode clair`, `light mode on`, `theme clair` +2 | powershell | — | — |
| 119 | `param_son_avance` | Parametres audio avances | `parametres audio avances`, `son avance`, `mixer audio` +2 | ms_settings | — | — |
| 120 | `param_hdr` | Parametres HDR | `parametres hdr`, `active le hdr`, `hdr` +2 | ms_settings | — | — |
| 121 | `ouvrir_regedit` | Ouvrir l'editeur de registre | `ouvre le registre`, `regedit`, `editeur de registre` +1 | powershell | — | Oui |
| 122 | `ouvrir_mmc` | Ouvrir la console de gestion (MMC) | `console de gestion`, `mmc`, `ouvre mmc` +1 | powershell | — | — |
| 123 | `ouvrir_politique_groupe` | Ouvrir l'editeur de strategie de groupe | `politique de groupe`, `group policy`, `gpedit` +2 | powershell | — | — |
| 124 | `taux_rafraichissement` | Parametres taux de rafraichissement ecran | `taux de rafraichissement`, `hertz ecran`, `frequence ecran` +2 | ms_settings | — | — |
| 125 | `param_notifications_avance` | Parametres notifications avances | `parametres notifications avances`, `gere les notifications`, `quelles apps notifient` +1 | ms_settings | — | — |
| 126 | `param_multitache` | Parametres multitache Windows | `parametres multitache`, `multitasking`, `reglages multitache` +2 | ms_settings | — | — |
| 127 | `apps_par_defaut` | Gerer les applications par defaut | `applications par defaut`, `apps par defaut`, `ouvre avec` +2 | ms_settings | — | — |
| 128 | `param_stockage_avance` | Gestion du stockage et assistant | `assistant stockage`, `nettoyage automatique`, `stockage intelligent` +2 | ms_settings | — | — |
| 129 | `sauvegarder_windows` | Parametres de sauvegarde Windows | `sauvegarde windows`, `backup windows`, `parametres backup` +2 | ms_settings | — | — |
| 130 | `restauration_systeme` | Ouvrir la restauration du systeme | `restauration systeme`, `point de restauration`, `system restore` +2 | powershell | — | — |
| 131 | `a_propos_pc` | Informations sur le PC (A propos) | `a propos du pc`, `about pc`, `nom du pc` +3 | ms_settings | — | — |
| 132 | `param_ethernet` | Parametres Ethernet | `parametres ethernet`, `cable reseau`, `connexion filaire` +2 | ms_settings | — | — |
| 133 | `param_data_usage` | Utilisation des donnees reseau | `utilisation donnees`, `data usage`, `consommation reseau` +2 | ms_settings | — | — |
| 134 | `tracert` | Tracer la route vers un hote | `trace la route vers {host}`, `traceroute {host}`, `tracert {host}` +1 | powershell | host | — |
| 135 | `netstat` | Afficher les connexions reseau actives | `connexions actives`, `netstat`, `ports ouverts` +2 | powershell | — | — |
| 136 | `uptime` | Temps de fonctionnement du PC | `uptime`, `depuis quand le pc tourne`, `temps de fonctionnement` +2 | powershell | — | — |
| 137 | `temperature_cpu` | Temperature du processeur | `temperature cpu`, `temperature processeur`, `cpu temperature` +2 | powershell | — | — |
| 138 | `liste_utilisateurs` | Lister les utilisateurs du PC | `liste les utilisateurs`, `quels utilisateurs`, `comptes locaux` +2 | powershell | — | — |
| 139 | `adresse_mac` | Afficher les adresses MAC | `adresse mac`, `mac address`, `adresses mac` +1 | powershell | — | — |
| 140 | `vitesse_reseau` | Tester la vitesse de la carte reseau | `vitesse reseau`, `speed test`, `debit reseau` +2 | powershell | — | — |
| 141 | `param_optionnel` | Gerer les fonctionnalites optionnelles Windows | `fonctionnalites optionnelles`, `optional features`, `features windows` +2 | ms_settings | — | — |
| 142 | `ouvrir_sandbox` | Ouvrir Windows Sandbox | `ouvre la sandbox`, `sandbox`, `windows sandbox` +2 | powershell | — | — |
| 143 | `verifier_fichiers` | Verifier l'integrite des fichiers systeme | `verifie les fichiers systeme`, `sfc scan`, `scan integrite` +2 | powershell | — | Oui |
| 144 | `wifi_connecter` | Se connecter a un reseau Wi-Fi | `connecte moi au wifi {ssid}`, `connecte au wifi {ssid}`, `rejoins le wifi {ssid}` +1 | powershell | ssid | — |
| 145 | `wifi_deconnecter` | Se deconnecter du Wi-Fi | `deconnecte le wifi`, `deconnecte du wifi`, `wifi off` +2 | powershell | — | — |
| 146 | `wifi_profils` | Lister les profils Wi-Fi sauvegardes | `profils wifi`, `wifi sauvegardes`, `reseaux memorises` +2 | powershell | — | — |
| 147 | `clipboard_vider` | Vider le presse-papier | `vide le presse-papier`, `efface le clipboard`, `nettoie le presse-papier` +1 | powershell | — | — |
| 148 | `clipboard_compter` | Compter les caracteres du presse-papier | `combien de caracteres dans le presse-papier`, `taille du presse-papier`, `longueur du clipboard` | powershell | — | — |
| 149 | `recherche_everywhere` | Rechercher partout sur le PC | `recherche partout {terme}`, `cherche partout {terme}`, `trouve {terme} sur le pc` +1 | powershell | terme | — |
| 150 | `tache_planifier` | Creer une tache planifiee | `planifie une tache {nom}`, `cree une tache planifiee {nom}`, `programme {nom}` +1 | powershell | nom | — |
| 151 | `variables_utilisateur` | Afficher les variables d'environnement utilisateur | `variables utilisateur`, `mes variables`, `env utilisateur` +1 | powershell | — | — |
| 152 | `chemin_path` | Afficher le PATH systeme | `montre le path`, `affiche le path`, `variable path` +2 | powershell | — | — |
| 153 | `deconnexion_windows` | Deconnexion de la session Windows | `deconnecte moi`, `deconnexion`, `log out` +2 | powershell | — | Oui |
| 154 | `hibernation` | Mettre en hibernation | `hiberne`, `hibernation`, `mise en hibernation` +2 | powershell | — | Oui |
| 155 | `planifier_arret` | Planifier un arret dans X minutes | `eteins dans {minutes} minutes`, `arret dans {minutes} minutes`, `programme l'arret dans {minutes}` +6 | powershell | minutes | — |
| 156 | `annuler_arret` | Annuler un arret programme | `annule l'arret`, `annuler shutdown`, `cancel shutdown` +2 | powershell | — | — |
| 157 | `heure_actuelle` | Donner l'heure actuelle | `quelle heure est-il`, `quelle heure`, `l'heure` +6 | powershell | — | — |
| 158 | `date_actuelle` | Donner la date actuelle | `quelle date`, `quel jour on est`, `on est quel jour` +3 | powershell | — | — |
| 159 | `ecran_externe_etendre` | Etendre sur ecran externe | `etends l'ecran`, `ecran etendu`, `mode etendu` +2 | powershell | — | — |
| 160 | `ecran_duplique` | Dupliquer l'ecran | `duplique l'ecran`, `ecran duplique`, `mode duplique` +2 | powershell | — | — |
| 161 | `ecran_interne_seul` | Ecran interne uniquement | `ecran principal seulement`, `ecran interne seul`, `desactive l'ecran externe` +1 | powershell | — | — |
| 162 | `ecran_externe_seul` | Ecran externe uniquement | `ecran externe seulement`, `ecran externe seul`, `desactive l'ecran principal` +1 | powershell | — | — |
| 163 | `ram_usage` | Utilisation de la RAM | `utilisation ram`, `combien de ram`, `memoire utilisee` +2 | powershell | — | — |
| 164 | `cpu_usage` | Utilisation du processeur | `utilisation cpu`, `charge du processeur`, `combien de cpu` +2 | powershell | — | — |
| 165 | `cpu_info` | Informations sur le processeur | `quel processeur`, `info cpu`, `nom du processeur` +2 | powershell | — | — |
| 166 | `ram_info` | Informations detaillees sur la RAM | `info ram`, `details ram`, `combien de barrettes` +2 | powershell | — | — |
| 167 | `batterie_niveau` | Niveau de batterie | `niveau de batterie`, `combien de batterie`, `batterie restante` +2 | powershell | — | — |
| 168 | `disque_sante` | Sante des disques (SMART) | `sante des disques`, `etat des disques`, `smart disque` +2 | powershell | — | — |
| 169 | `carte_mere` | Informations carte mere | `info carte mere`, `quelle carte mere`, `modele carte mere` +2 | powershell | — | — |
| 170 | `bios_info` | Informations BIOS | `info bios`, `version bios`, `quel bios` +2 | powershell | — | — |
| 171 | `top_ram` | Top 10 processus par RAM | `quoi consomme la ram`, `top ram`, `processus gourmands ram` +2 | powershell | — | — |
| 172 | `top_cpu` | Top 10 processus par CPU | `quoi consomme le cpu`, `top cpu`, `processus gourmands cpu` +2 | powershell | — | — |
| 173 | `carte_graphique` | Informations carte graphique | `quelle carte graphique`, `info gpu detaille`, `specs gpu` +2 | powershell | — | — |
| 174 | `windows_version` | Version exacte de Windows | `version de windows`, `quelle version windows`, `build windows` +2 | powershell | — | — |
| 175 | `dns_changer_google` | Changer DNS vers Google (8.8.8.8) | `mets le dns google`, `change le dns en google`, `dns google` +2 | powershell | — | Oui |
| 176 | `dns_changer_cloudflare` | Changer DNS vers Cloudflare (1.1.1.1) | `mets le dns cloudflare`, `change le dns en cloudflare`, `dns cloudflare` +2 | powershell | — | Oui |
| 177 | `dns_reset` | Remettre le DNS en automatique | `dns automatique`, `reset le dns`, `dns par defaut` +2 | powershell | — | Oui |
| 178 | `ports_ouverts` | Lister les ports ouverts | `ports ouverts`, `quels ports sont ouverts`, `liste les ports` +2 | powershell | — | — |
| 179 | `ip_publique` | Obtenir l'IP publique | `mon ip publique`, `quelle est mon ip publique`, `ip externe` +2 | powershell | — | — |
| 180 | `partage_reseau` | Lister les partages reseau | `partages reseau`, `dossiers partages`, `quels dossiers sont partages` +2 | powershell | — | — |
| 181 | `connexions_actives` | Connexions reseau actives | `connexions actives`, `qui est connecte`, `connexions etablies` +2 | powershell | — | — |
| 182 | `arp_table` | Afficher la table ARP | `table arp`, `arp`, `appareils sur le reseau` +2 | powershell | — | — |
| 183 | `test_port` | Tester si un port est ouvert sur une machine | `teste le port {port} sur {host}`, `port {port} ouvert sur {host}`, `check port {port} {host}` +1 | powershell | host, port | — |
| 184 | `route_table` | Afficher la table de routage | `table de routage`, `routes reseau`, `route table` +2 | powershell | — | — |
| 185 | `nslookup` | Resolution DNS d'un domaine | `nslookup {domaine}`, `resous {domaine}`, `dns de {domaine}` +2 | powershell | domaine | — |
| 186 | `certificat_ssl` | Verifier le certificat SSL d'un site | `certificat ssl de {site}`, `check ssl {site}`, `verifie le ssl de {site}` +1 | powershell | site | — |
| 187 | `voir_logs` | Voir les logs systeme ou JARVIS | `les logs`, `voir les logs`, `montre les logs` +7 | powershell | — | — |
| 188 | `partage_proximite_on` | Activer le partage de proximite | `active le partage de proximite`, `nearby sharing on`, `partage proximite actif` +1 | powershell | — | — |
| 189 | `screen_recording` | Lancer l'enregistrement d'ecran (Game Bar) | `enregistre l'ecran`, `screen recording`, `capture video` +2 | hotkey | — | — |
| 190 | `parametres_notifications` | Ouvrir les parametres de notifications | `parametres notifications`, `gere les notifications`, `reglages notifications` +1 | powershell | — | — |
| 191 | `parametres_apps_defaut` | Ouvrir les apps par defaut | `apps par defaut`, `applications par defaut`, `change les apps par defaut` +1 | powershell | — | — |
| 192 | `parametres_about` | A propos de ce PC | `a propos du pc`, `about this pc`, `infos pc` +2 | powershell | — | — |
| 193 | `verifier_sante_disque` | Verifier la sante des disques | `sante des disques`, `health check disque`, `smart disque` +2 | powershell | — | — |
| 194 | `vitesse_internet` | Tester la vitesse internet | `test de vitesse`, `speed test`, `vitesse internet` +2 | powershell | — | — |
| 195 | `historique_mises_a_jour` | Voir l'historique des mises a jour Windows | `historique updates`, `dernieres mises a jour`, `updates windows recentes` +1 | powershell | — | — |
| 196 | `certificats_ssl` | Verifier un certificat SSL | `verifie le ssl de {site}`, `certificat ssl {site}`, `check ssl {site}` +1 | powershell | site | — |
| 197 | `audio_sortie` | Changer la sortie audio | `change la sortie audio`, `sortie audio`, `output audio` +2 | powershell | — | — |
| 198 | `audio_entree` | Configurer le microphone | `configure le micro`, `entree audio`, `input audio` +2 | powershell | — | — |
| 199 | `volume_app` | Mixer de volume par application | `mixer volume`, `volume par application`, `volume des apps` +2 | powershell | — | — |
| 200 | `micro_mute_toggle` | Couper/reactiver le micro | `coupe le micro`, `mute le micro`, `micro off` +3 | powershell | — | — |
| 201 | `liste_imprimantes` | Lister les imprimantes | `liste les imprimantes`, `quelles imprimantes`, `imprimantes disponibles` +2 | powershell | — | — |
| 202 | `imprimante_defaut` | Voir l'imprimante par defaut | `imprimante par defaut`, `quelle imprimante`, `default printer` +1 | powershell | — | — |
| 203 | `sandbox_ouvrir` | Ouvrir Windows Sandbox | `ouvre la sandbox`, `windows sandbox`, `lance la sandbox` +2 | powershell | — | — |
| 204 | `plan_alimentation_actif` | Voir le plan d'alimentation actif | `quel plan alimentation`, `power plan actif`, `plan energie actif` +1 | powershell | — | — |
| 205 | `batterie_rapport` | Generer un rapport de batterie | `rapport batterie`, `battery report`, `sante de la batterie` +2 | powershell | — | — |
| 206 | `ecran_timeout` | Configurer la mise en veille ecran | `timeout ecran`, `ecran en veille apres`, `delai mise en veille ecran` +1 | powershell | — | — |
| 207 | `detecter_ecrans` | Detecter les ecrans connectes | `detecte les ecrans`, `detect displays`, `cherche les ecrans` +2 | powershell | — | — |
| 208 | `kill_process_nom` | Tuer un processus par nom | `tue le processus {nom}`, `kill {nom}`, `ferme le processus {nom}` +2 | powershell | nom | Oui |
| 209 | `processus_details` | Details d'un processus | `details du processus {nom}`, `info processus {nom}`, `combien consomme {nom}` +1 | powershell | nom | — |
| 210 | `diagnostic_reseau` | Lancer un diagnostic reseau complet | `diagnostic reseau`, `diagnostique le reseau`, `probleme reseau` +2 | powershell | — | — |
| 211 | `wifi_mot_de_passe` | Afficher le mot de passe WiFi actuel | `mot de passe wifi`, `password wifi`, `cle wifi` +2 | powershell | — | — |
| 212 | `ouvrir_evenements` | Ouvrir l'observateur d'evenements | `observateur evenements`, `event viewer`, `journaux windows` +2 | powershell | — | — |
| 213 | `ouvrir_services` | Ouvrir les services Windows | `ouvre les services`, `services windows`, `gere les services` +1 | powershell | — | — |
| 214 | `ouvrir_moniteur_perf` | Ouvrir le moniteur de performances | `moniteur de performance`, `performance monitor`, `moniteur perf` +1 | powershell | — | — |
| 215 | `ouvrir_fiabilite` | Ouvrir le moniteur de fiabilite | `moniteur de fiabilite`, `reliability monitor`, `fiabilite windows` +1 | powershell | — | — |
| 216 | `action_center` | Ouvrir le centre de notifications | `centre de notifications`, `notification center`, `action center` +1 | hotkey | — | — |
| 217 | `quick_settings` | Ouvrir les parametres rapides | `parametres rapides`, `quick settings`, `raccourcis rapides` +1 | hotkey | — | — |
| 218 | `search_windows` | Ouvrir la recherche Windows | `recherche windows`, `windows search`, `ouvre la recherche` +1 | hotkey | — | — |
| 219 | `hyper_v_manager` | Ouvrir le gestionnaire Hyper-V | `ouvre hyper-v`, `lance hyper-v`, `gestionnaire hyper-v` +2 | powershell | — | — |
| 220 | `storage_sense` | Activer l'assistant de stockage | `active l'assistant de stockage`, `storage sense`, `nettoyage automatique` +1 | powershell | — | — |
| 221 | `creer_point_restauration` | Creer un point de restauration systeme | `cree un point de restauration`, `point de restauration`, `creer point de restauration` +1 | powershell | — | — |
| 222 | `voir_hosts` | Afficher le fichier hosts | `montre le fichier hosts`, `affiche hosts`, `ouvre hosts` +1 | powershell | — | — |
| 223 | `dxdiag` | Lancer le diagnostic DirectX | `lance dxdiag`, `diagnostic directx`, `dxdiag` +2 | powershell | — | — |
| 224 | `memoire_diagnostic` | Lancer le diagnostic memoire Windows | `diagnostic memoire`, `teste la memoire`, `test ram` +2 | powershell | — | — |
| 225 | `reset_reseau` | Reinitialiser la pile reseau | `reinitialise le reseau`, `reset reseau`, `reset network` +2 | powershell | — | — |
| 226 | `bitlocker_status` | Verifier le statut BitLocker | `statut bitlocker`, `etat bitlocker`, `bitlocker status` +1 | powershell | — | — |
| 227 | `windows_update_pause` | Mettre en pause les mises a jour Windows | `pause les mises a jour`, `suspends les mises a jour`, `mets en pause windows update` +1 | powershell | — | — |
| 228 | `mode_developpeur` | Activer/desactiver le mode developpeur | `active le mode developpeur`, `mode developpeur`, `developer mode` +1 | powershell | — | — |
| 229 | `remote_desktop` | Parametres Bureau a distance | `bureau a distance`, `remote desktop`, `ouvre remote desktop` +2 | powershell | — | — |
| 230 | `credential_manager` | Ouvrir le gestionnaire d'identifiants | `gestionnaire d'identifiants`, `credential manager`, `identifiants windows` +1 | powershell | — | — |
| 231 | `certmgr` | Ouvrir le gestionnaire de certificats | `gestionnaire de certificats`, `certificats windows`, `certmgr` +1 | powershell | — | — |
| 232 | `chkdsk_check` | Verifier les erreurs du disque | `verifie le disque`, `check disk`, `chkdsk` +2 | powershell | — | — |
| 233 | `file_history` | Parametres historique des fichiers | `historique des fichiers`, `file history`, `sauvegarde fichiers` +1 | powershell | — | — |
| 234 | `troubleshoot_reseau` | Lancer le depannage reseau | `depanne le reseau`, `depannage reseau`, `troubleshoot reseau` +1 | powershell | — | — |
| 235 | `troubleshoot_audio` | Lancer le depannage audio | `depanne le son`, `depannage audio`, `troubleshoot audio` +1 | powershell | — | — |
| 236 | `troubleshoot_update` | Lancer le depannage Windows Update | `depanne windows update`, `depannage mises a jour`, `troubleshoot update` +1 | powershell | — | — |
| 237 | `power_options` | Options d'alimentation avancees | `options d'alimentation`, `power options`, `alimentation avancee` +1 | powershell | — | — |
| 238 | `copilot_parametres` | Parametres de Copilot | `parametres copilot`, `reglages copilot`, `config copilot` +1 | ms_settings | — | — |
| 239 | `cortana_desactiver` | Desactiver Cortana | `desactive cortana`, `coupe cortana`, `cortana off` +2 | powershell | — | — |
| 240 | `capture_fenetre` | Capturer la fenetre active | `capture la fenetre`, `screenshot fenetre`, `capture fenetre active` +2 | hotkey | — | — |
| 241 | `capture_retardee` | Capture d'ecran avec delai | `capture retardee`, `screenshot retarde`, `capture dans 5 secondes` +2 | powershell | — | — |
| 242 | `planificateur_ouvrir` | Ouvrir le planificateur de taches | `planificateur de taches`, `ouvre le planificateur`, `task scheduler` +2 | powershell | — | — |
| 243 | `creer_tache_planifiee` | Creer une tache planifiee | `cree une tache planifiee`, `nouvelle tache planifiee`, `ajoute une tache planifiee` +1 | powershell | — | — |
| 244 | `lister_usb` | Lister les peripheriques USB connectes | `liste les usb`, `peripheriques usb`, `usb connectes` +2 | powershell | — | — |
| 245 | `ejecter_usb` | Ejecter un peripherique USB en securite | `ejecte l'usb`, `ejecter usb`, `retire l'usb` +2 | powershell | — | — |
| 246 | `peripheriques_connectes` | Lister tous les peripheriques connectes | `peripheriques connectes`, `liste les peripheriques`, `appareils connectes` +1 | powershell | — | — |
| 247 | `lister_adaptateurs` | Lister les adaptateurs reseau | `liste les adaptateurs reseau`, `adaptateurs reseau`, `interfaces reseau` +1 | powershell | — | — |
| 248 | `desactiver_wifi_adaptateur` | Desactiver l'adaptateur Wi-Fi | `desactive le wifi`, `coupe l'adaptateur wifi`, `wifi off adaptateur` +1 | powershell | — | — |
| 249 | `activer_wifi_adaptateur` | Activer l'adaptateur Wi-Fi | `active l'adaptateur wifi`, `reactive le wifi`, `wifi on adaptateur` +1 | powershell | — | — |
| 250 | `firewall_status` | Afficher le statut du pare-feu | `statut pare-feu`, `statut firewall`, `firewall status` +2 | powershell | — | — |
| 251 | `firewall_regles` | Lister les regles du pare-feu | `regles pare-feu`, `regles firewall`, `firewall rules` +1 | powershell | — | — |
| 252 | `firewall_reset` | Reinitialiser le pare-feu | `reinitialise le pare-feu`, `reset firewall`, `firewall reset` +1 | powershell | — | — |
| 253 | `ajouter_langue` | Ajouter une langue au systeme | `ajoute une langue`, `installer une langue`, `nouvelle langue` +1 | ms_settings | — | — |
| 254 | `ajouter_clavier` | Ajouter une disposition de clavier | `ajoute un clavier`, `nouveau clavier`, `ajouter disposition clavier` +1 | ms_settings | — | — |
| 255 | `langues_installees` | Lister les langues installees | `langues installees`, `quelles langues`, `liste des langues` +2 | powershell | — | — |
| 256 | `synchroniser_heure` | Synchroniser l'heure avec le serveur NTP | `synchronise l'heure`, `sync heure`, `mettre a l'heure` +2 | powershell | — | — |
| 257 | `serveur_ntp` | Afficher le serveur NTP configure | `serveur ntp`, `quel serveur ntp`, `serveur de temps` +2 | powershell | — | — |
| 258 | `windows_hello` | Parametres Windows Hello | `windows hello`, `hello biometrique`, `parametres hello` +2 | ms_settings | — | — |
| 259 | `securite_comptes` | Securite des comptes Windows | `securite des comptes`, `securite compte`, `protection compte` +2 | ms_settings | — | — |
| 260 | `activation_windows` | Verifier l'activation Windows | `activation windows`, `windows active`, `statut activation` +2 | powershell | — | — |
| 261 | `recuperation_systeme` | Options de recuperation systeme | `recuperation systeme`, `options de recuperation`, `recovery` +2 | ms_settings | — | — |
| 262 | `gpu_temperatures` | Temperatures GPU via nvidia-smi | `temperatures gpu`, `gpu temperature`, `chauffe les gpu` +2 | powershell | — | — |
| 263 | `vram_usage` | Utilisation VRAM de toutes les GPU | `utilisation vram`, `vram utilisee`, `combien de vram` +2 | powershell | — | — |
| 264 | `disk_io` | Activite I/O des disques | `activite des disques`, `io disques`, `disk io` +2 | powershell | — | — |
| 265 | `network_io` | Debit reseau en temps reel | `debit reseau`, `trafic reseau`, `network io` +2 | powershell | — | — |
| 266 | `services_failed` | Services Windows en echec | `services en echec`, `services plantes`, `services failed` +2 | powershell | — | — |
| 267 | `event_errors` | Dernières erreurs systeme (Event Log) | `erreurs systeme recentes`, `derniers errors`, `event log errors` +2 | powershell | — | — |
| 268 | `boot_time` | Temps de demarrage du dernier boot | `temps de demarrage`, `boot time`, `combien de temps au boot` +2 | powershell | — | — |
| 269 | `nettoyer_prefetch` | Nettoyer le dossier Prefetch | `nettoie prefetch`, `vide prefetch`, `clean prefetch` +1 | powershell | — | Oui |
| 270 | `nettoyer_thumbnails` | Nettoyer le cache des miniatures | `nettoie les miniatures`, `vide le cache miniatures`, `clean thumbnails` +1 | powershell | — | — |
| 271 | `nettoyer_logs` | Nettoyer les vieux logs | `nettoie les logs`, `supprime les vieux logs`, `clean logs` +2 | powershell | — | Oui |
| 272 | `scan_ports_local` | Scanner les ports ouverts localement | `scan mes ports`, `scan ports local`, `quels ports j'expose` +2 | powershell | — | — |
| 273 | `connexions_suspectes` | Verifier les connexions sortantes suspectes | `connexions suspectes`, `qui se connecte dehors`, `connexions sortantes` +1 | powershell | — | — |
| 274 | `autorun_check` | Verifier les programmes au demarrage | `quoi se lance au demarrage`, `autorun check`, `programmes auto start` +2 | powershell | — | — |
| 275 | `defender_scan_rapide` | Lancer un scan rapide Windows Defender | `scan antivirus`, `lance un scan defender`, `scan rapide` +2 | powershell | — | — |
| 276 | `defender_status` | Statut de Windows Defender | `statut defender`, `etat antivirus`, `defender ok` +2 | powershell | — | — |
| 277 | `top_cpu_processes` | Top 10 processus par CPU | `top cpu`, `processus gourmands cpu`, `qui mange le cpu` +2 | powershell | — | — |
| 278 | `top_ram_processes` | Top 10 processus par RAM | `top ram`, `processus gourmands ram`, `qui mange la ram` +2 | powershell | — | — |
| 279 | `uptime_system` | Uptime du systeme Windows | `uptime`, `depuis combien de temps le pc tourne`, `duree allumage` +1 | powershell | — | — |
| 280 | `windows_update_check` | Verifier les mises a jour Windows disponibles | `mises a jour windows`, `windows update`, `check updates` +2 | powershell | — | — |
| 281 | `ip_publique_externe` | Obtenir l'adresse IP publique | `ip publique`, `quelle est mon ip`, `mon ip publique` +2 | powershell | — | — |
| 282 | `latence_cluster` | Ping de latence vers les noeuds du cluster | `latence cluster`, `ping le cluster ia`, `latence des noeuds` +2 | powershell | — | — |
| 283 | `wifi_info` | Informations sur la connexion WiFi active | `info wifi`, `quel wifi`, `connexion wifi` +2 | powershell | — | — |
| 284 | `espace_disques` | Espace libre sur tous les disques | `espace disque`, `combien d'espace libre`, `espace libre` +2 | powershell | — | — |
| 285 | `gros_fichiers_bureau` | Top 10 plus gros fichiers du bureau | `plus gros fichiers`, `gros fichiers bureau`, `fichiers les plus lourds` +1 | powershell | — | — |
| 286 | `processus_zombies` | Detecter les processus qui ne repondent pas | `processus zombies`, `processus bloques`, `applications gelees` +2 | powershell | — | — |
| 287 | `dernier_crash` | Dernier crash ou erreur critique Windows | `dernier crash`, `derniere erreur critique`, `dernier plantage` +1 | powershell | — | — |
| 288 | `temps_allumage_apps` | Depuis combien de temps chaque app tourne | `duree des apps`, `depuis quand les apps tournent`, `temps d'execution des processus` +1 | powershell | — | — |
| 289 | `taille_cache_navigateur` | Taille des caches navigateur Chrome/Edge | `taille cache navigateur`, `cache chrome`, `cache edge` +1 | powershell | — | — |
| 290 | `nettoyer_cache_navigateur` | Vider les caches Chrome et Edge | `vide le cache navigateur`, `nettoie le cache chrome`, `clean cache web` +1 | powershell | — | Oui |
| 291 | `nettoyer_crash_dumps` | Supprimer les crash dumps Windows | `nettoie les crash dumps`, `supprime les dumps`, `clean crash dumps` +1 | powershell | — | — |
| 292 | `nettoyer_windows_old` | Taille du dossier Windows.old (ancien systeme) | `taille windows old`, `windows old`, `combien pese windows old` +1 | powershell | — | — |
| 293 | `gpu_power_draw` | Consommation electrique des GPU | `consommation gpu`, `watt gpu`, `puissance gpu` +2 | powershell | — | — |
| 294 | `gpu_fan_speed` | Vitesse des ventilateurs GPU | `ventilateurs gpu`, `fans gpu`, `vitesse fan gpu` +1 | powershell | — | — |
| 295 | `gpu_driver_version` | Version du driver NVIDIA | `version driver nvidia`, `driver gpu`, `nvidia driver` +1 | powershell | — | — |
| 296 | `cluster_latence_detaillee` | Latence detaillee de chaque noeud du cluster avec modeles | `latence detaillee cluster`, `ping detaille cluster`, `benchmark rapide cluster` +1 | powershell | — | — |
| 297 | `installed_apps_list` | Lister les applications installees | `liste les applications`, `apps installees`, `quelles apps j'ai` +2 | powershell | — | — |
| 298 | `hotfix_history` | Historique des correctifs Windows installes | `historique hotfix`, `correctifs installes`, `patches windows` +2 | powershell | — | — |
| 299 | `scheduled_tasks_active` | Taches planifiees actives | `taches planifiees actives`, `scheduled tasks`, `quelles taches auto` +2 | powershell | — | — |
| 300 | `tpm_info` | Informations sur le module TPM | `info tpm`, `tpm status`, `etat du tpm` +2 | powershell | — | — |
| 301 | `printer_list` | Imprimantes installees et leur statut | `liste les imprimantes`, `imprimantes installees`, `quelles imprimantes` +2 | powershell | — | — |
| 302 | `startup_impact` | Impact des programmes au demarrage sur le boot | `impact demarrage`, `startup impact`, `quoi ralentit le boot` +2 | powershell | — | — |
| 303 | `system_info_detaille` | Infos systeme detaillees (OS, BIOS, carte mere) | `infos systeme detaillees`, `system info`, `details du pc` +2 | powershell | — | — |
| 304 | `ram_slots_detail` | Details des barrettes RAM (type, vitesse, slots) | `details ram`, `barrettes ram`, `ram slots` +2 | powershell | — | — |
| 305 | `cpu_details` | Details du processeur (coeurs, threads, frequence) | `details cpu`, `info processeur`, `specs cpu` +2 | powershell | — | — |
| 306 | `network_adapters_list` | Adaptateurs reseau actifs et leur configuration | `adaptateurs reseau`, `interfaces reseau`, `network adapters` +2 | powershell | — | — |
| 307 | `dns_cache_view` | Voir le cache DNS local | `cache dns`, `dns cache`, `voir le cache dns` +2 | powershell | — | — |
| 308 | `recycle_bin_size` | Taille de la corbeille | `taille corbeille`, `poids corbeille`, `combien dans la corbeille` +2 | powershell | — | — |
| 309 | `temp_folder_size` | Taille du dossier temporaire | `taille du temp`, `dossier temp`, `poids du temp` +2 | powershell | — | — |
| 310 | `last_shutdown_time` | Heure du dernier arret du PC | `dernier arret`, `quand le pc s'est eteint`, `last shutdown` +2 | powershell | — | — |
| 311 | `bluescreen_history` | Historique des ecrans bleus (BSOD) | `ecrans bleus`, `bsod`, `bluescreen` +3 | powershell | — | — |
| 312 | `disk_smart_health` | Etat de sante SMART des disques | `sante disques`, `smart disques`, `disk health` +2 | powershell | — | — |
| 313 | `firewall_rules_count` | Nombre de regles firewall par profil | `regles firewall`, `combien de regles pare-feu`, `firewall count` +2 | powershell | — | — |
| 314 | `env_variables_key` | Variables d'environnement cles (PATH, TEMP, etc.) | `variables environnement`, `env vars`, `montre le path` +2 | powershell | — | — |
| 315 | `sfc_scan` | Lancer un scan d'integrite systeme (sfc /scannow) | `scan integrite`, `sfc scannow`, `verifie les fichiers systeme` +2 | powershell | — | Oui |
| 316 | `dism_health_check` | Verifier la sante de l'image Windows (DISM) | `dism health`, `sante windows`, `dism check` +2 | powershell | — | — |
| 317 | `system_restore_points` | Lister les points de restauration systeme | `points de restauration`, `restore points`, `sauvegardes systeme` +1 | powershell | — | — |
| 318 | `usb_devices_list` | Lister les peripheriques USB connectes | `peripheriques usb`, `usb connectes`, `quels usb` +2 | powershell | — | — |
| 319 | `bluetooth_devices` | Lister les peripheriques Bluetooth | `peripheriques bluetooth`, `bluetooth connectes`, `quels bluetooth` +2 | powershell | — | — |
| 320 | `certificates_list` | Certificats systeme installes (racine) | `certificats installes`, `certificates`, `liste les certificats` +2 | powershell | — | — |
| 321 | `page_file_info` | Configuration du fichier de pagination (swap) | `page file`, `fichier de pagination`, `swap windows` +2 | powershell | — | — |
| 322 | `windows_features` | Fonctionnalites Windows activees | `fonctionnalites windows`, `features windows`, `quelles features activees` +2 | powershell | — | — |
| 323 | `power_plan_active` | Plan d'alimentation actif et ses details | `plan alimentation`, `power plan`, `mode d'alimentation` +2 | powershell | — | — |
| 324 | `bios_version` | Version du BIOS et date | `version bios`, `bios info`, `quel bios` +2 | powershell | — | — |
| 325 | `windows_version_detail` | Version detaillee de Windows (build, edition) | `version windows`, `quelle version windows`, `build windows` +2 | powershell | — | — |
| 326 | `network_connections_count` | Nombre de connexions reseau actives par etat | `connexions reseau actives`, `combien de connexions`, `network connections` +2 | powershell | — | — |
| 327 | `drivers_probleme` | Pilotes en erreur ou problematiques | `pilotes en erreur`, `drivers probleme`, `drivers defaillants` +2 | powershell | — | — |
| 328 | `shared_folders` | Dossiers partages sur ce PC | `dossiers partages`, `partages reseau`, `shared folders` +2 | powershell | — | — |
| 329 | `focus_app_name` | Mettre le focus sur une application par son nom | `va sur {app}`, `bascule sur {app}`, `focus {app}` +2 | powershell | app | — |
| 330 | `fermer_app_name` | Fermer une application par son nom | `ferme {app}`, `tue {app}`, `arrete {app}` +2 | powershell | app | Oui |
| 331 | `liste_fenetres_ouvertes` | Lister toutes les fenetres ouvertes avec leur titre | `quelles fenetres sont ouvertes`, `liste les fenetres`, `fenetres actives` +2 | powershell | — | — |
| 332 | `fenetre_toujours_visible` | Rendre la fenetre active always-on-top | `toujours visible`, `always on top`, `epingle la fenetre` +2 | powershell | — | — |
| 333 | `deplacer_fenetre_moniteur` | Deplacer la fenetre active vers l'autre moniteur | `fenetre autre ecran`, `deplace sur l'autre ecran`, `bouge la fenetre` +2 | hotkey | — | — |
| 334 | `centrer_fenetre` | Centrer la fenetre active sur l'ecran | `centre la fenetre`, `fenetre au centre`, `center window` +1 | powershell | — | — |
| 335 | `switch_audio_output` | Lister et changer la sortie audio | `change la sortie audio`, `switch audio`, `quel sortie son` +2 | powershell | — | — |
| 336 | `toggle_wifi` | Activer/desactiver le WiFi | `toggle wifi`, `active le wifi`, `desactive le wifi` +2 | powershell | — | — |
| 337 | `toggle_bluetooth` | Activer/desactiver le Bluetooth | `toggle bluetooth`, `active le bluetooth`, `desactive le bluetooth` +2 | powershell | — | — |
| 338 | `toggle_dark_mode` | Basculer entre mode sombre et mode clair | `mode sombre`, `dark mode`, `toggle dark mode` +3 | powershell | — | — |
| 339 | `taper_date` | Taper la date du jour automatiquement | `tape la date`, `ecris la date`, `insere la date` +2 | powershell | — | — |
| 340 | `taper_heure` | Taper l'heure actuelle automatiquement | `tape l'heure`, `ecris l'heure`, `insere l'heure` +2 | powershell | — | — |
| 341 | `vider_clipboard` | Vider le presse-papier | `vide le presse papier`, `clear clipboard`, `efface le clipboard` +1 | powershell | — | — |
| 342 | `dismiss_notifications` | Fermer toutes les notifications Windows | `ferme les notifications`, `dismiss notifications`, `efface les notifs` +2 | hotkey | — | — |
| 343 | `ouvrir_gestionnaire_peripheriques` | Ouvrir le Gestionnaire de peripheriques | `gestionnaire de peripheriques`, `device manager`, `ouvre le gestionnaire peripheriques` +1 | powershell | — | — |
| 344 | `ouvrir_gestionnaire_disques` | Ouvrir la Gestion des disques | `gestion des disques`, `disk management`, `ouvre la gestion des disques` +1 | powershell | — | — |
| 345 | `ouvrir_services_windows` | Ouvrir la console Services Windows | `services windows`, `console services`, `ouvre les services` +1 | powershell | — | — |
| 346 | `ouvrir_registre` | Ouvrir l'editeur de registre | `editeur de registre`, `regedit`, `ouvre le registre` +1 | powershell | — | — |
| 347 | `ouvrir_event_viewer` | Ouvrir l'observateur d'evenements | `observateur d'evenements`, `event viewer`, `ouvre les logs windows` +1 | powershell | — | — |
| 348 | `hibernation_profonde` | Mettre le PC en hibernation profonde | `hiberne le pc maintenant`, `hibernation profonde`, `mode hibernation profonde` +1 | powershell | — | Oui |
| 349 | `restart_bios` | Redemarrer vers le BIOS/UEFI | `redemarre dans le bios`, `restart bios`, `acces uefi` +1 | powershell | — | Oui |
| 350 | `taskbar_app_1` | Lancer la 1ere app epinglee dans la taskbar | `premiere app taskbar`, `app 1 taskbar`, `lance l'app 1` +1 | hotkey | — | — |
| 351 | `taskbar_app_2` | Lancer la 2eme app epinglee dans la taskbar | `deuxieme app taskbar`, `app 2 taskbar`, `lance l'app 2` +1 | hotkey | — | — |
| 352 | `taskbar_app_3` | Lancer la 3eme app epinglee dans la taskbar | `troisieme app taskbar`, `app 3 taskbar`, `lance l'app 3` +1 | hotkey | — | — |
| 353 | `taskbar_app_4` | Lancer la 4eme app epinglee dans la taskbar | `quatrieme app taskbar`, `app 4 taskbar`, `lance l'app 4` +1 | hotkey | — | — |
| 354 | `taskbar_app_5` | Lancer la 5eme app epinglee dans la taskbar | `cinquieme app taskbar`, `app 5 taskbar`, `lance l'app 5` +1 | hotkey | — | — |
| 355 | `fenetre_autre_bureau` | Deplacer la fenetre vers le bureau virtuel suivant | `fenetre bureau suivant`, `deplace la fenetre sur l'autre bureau`, `move to next desktop` +1 | hotkey | — | — |
| 356 | `browser_retour` | Page precedente dans le navigateur | `page precedente`, `retour arriere`, `go back` +2 | hotkey | — | — |
| 357 | `browser_avancer` | Page suivante dans le navigateur | `page suivante`, `avance`, `go forward` +1 | hotkey | — | — |
| 358 | `browser_rafraichir` | Rafraichir la page web | `rafraichis la page`, `reload`, `refresh` +2 | hotkey | — | — |
| 359 | `browser_hard_refresh` | Rafraichir sans cache | `hard refresh`, `rafraichis sans cache`, `ctrl f5` +1 | hotkey | — | — |
| 360 | `browser_private` | Ouvrir une fenetre de navigation privee | `navigation privee`, `fenetre privee`, `incognito` +2 | hotkey | — | — |
| 361 | `browser_bookmark` | Ajouter la page aux favoris | `ajoute aux favoris`, `bookmark`, `favori cette page` +1 | hotkey | — | — |
| 362 | `browser_address_bar` | Aller dans la barre d'adresse | `barre d'adresse`, `address bar`, `tape une url` +1 | hotkey | — | — |
| 363 | `browser_fermer_tous_onglets` | Fermer tous les onglets sauf l'actif | `ferme tous les onglets`, `close all tabs`, `garde juste cet onglet` +1 | powershell | — | — |
| 364 | `browser_epingler_onglet` | Epingler/detacher l'onglet actif | `epingle l'onglet`, `pin tab`, `detache l'onglet` +1 | powershell | — | — |
| 365 | `texte_debut_ligne` | Aller au debut de la ligne | `debut de ligne`, `home`, `va au debut` +1 | hotkey | — | — |
| 366 | `texte_fin_ligne` | Aller a la fin de la ligne | `fin de ligne`, `end`, `va a la fin` +1 | hotkey | — | — |
| 367 | `texte_debut_document` | Aller au debut du document | `debut du document`, `tout en haut`, `ctrl home` +1 | hotkey | — | — |
| 368 | `texte_fin_document` | Aller a la fin du document | `fin du document`, `tout en bas`, `ctrl end` +1 | hotkey | — | — |
| 369 | `texte_selectionner_ligne` | Selectionner la ligne entiere | `selectionne la ligne`, `select line`, `prends toute la ligne` | hotkey | — | — |
| 370 | `texte_supprimer_ligne` | Supprimer la ligne entiere (VSCode) | `supprime la ligne`, `delete line`, `efface la ligne` +1 | hotkey | — | — |
| 371 | `texte_dupliquer_ligne` | Dupliquer la ligne (VSCode) | `duplique la ligne`, `duplicate line`, `copie la ligne en dessous` | hotkey | — | — |
| 372 | `texte_deplacer_ligne_haut` | Deplacer la ligne vers le haut (VSCode) | `monte la ligne`, `move line up`, `ligne vers le haut` | hotkey | — | — |
| 373 | `texte_deplacer_ligne_bas` | Deplacer la ligne vers le bas (VSCode) | `descends la ligne`, `move line down`, `ligne vers le bas` | hotkey | — | — |
| 374 | `vscode_palette` | Ouvrir la palette de commandes VSCode | `palette de commandes`, `command palette`, `ctrl shift p` +1 | hotkey | — | — |
| 375 | `vscode_terminal` | Ouvrir/fermer le terminal VSCode | `terminal vscode`, `ouvre le terminal intergre`, `toggle terminal` +1 | hotkey | — | — |
| 376 | `vscode_sidebar` | Afficher/masquer la sidebar VSCode | `sidebar vscode`, `panneau lateral`, `toggle sidebar` +2 | hotkey | — | — |
| 377 | `vscode_go_to_file` | Rechercher et ouvrir un fichier dans VSCode | `ouvre un fichier vscode`, `go to file`, `ctrl p` +1 | hotkey | — | — |
| 378 | `vscode_go_to_line` | Aller a une ligne dans VSCode | `va a la ligne`, `go to line`, `ctrl g` +1 | hotkey | — | — |
| 379 | `vscode_split_editor` | Diviser l'editeur VSCode en deux | `divise l'editeur`, `split editor`, `editeur cote a cote` +1 | hotkey | — | — |
| 380 | `vscode_close_all` | Fermer tous les fichiers ouverts dans VSCode | `ferme tous les fichiers vscode`, `close all tabs vscode`, `nettoie vscode` +1 | hotkey | — | — |
| 381 | `explorer_dossier_parent` | Remonter au dossier parent dans l'Explorateur | `dossier parent`, `remonte d'un dossier`, `go up folder` +1 | hotkey | — | — |
| 382 | `explorer_nouveau_dossier` | Creer un nouveau dossier dans l'Explorateur | `nouveau dossier`, `cree un dossier`, `new folder` +1 | hotkey | — | — |
| 383 | `explorer_afficher_caches` | Afficher les fichiers caches dans l'Explorateur | `montre les fichiers caches`, `fichiers caches`, `show hidden files` +1 | powershell | — | — |
| 384 | `explorer_masquer_caches` | Masquer les fichiers caches | `cache les fichiers caches`, `masque les fichiers invisibles`, `hide hidden files` +1 | powershell | — | — |
| 385 | `scroll_haut` | Scroller vers le haut | `scroll up`, `monte la page`, `scrolle vers le haut` +2 | hotkey | — | — |
| 386 | `scroll_bas` | Scroller vers le bas | `scroll down`, `descends la page`, `scrolle vers le bas` +2 | hotkey | — | — |
| 387 | `page_haut` | Page precedente (Page Up) | `page up`, `page precedente`, `monte d'une page` +2 | hotkey | — | — |
| 388 | `page_bas` | Page suivante (Page Down) | `page down`, `page suivante`, `descends d'une page` +2 | hotkey | — | — |
| 389 | `scroll_rapide_haut` | Scroller rapidement vers le haut (5 pages) | `scroll rapide haut`, `monte vite`, `remonte rapidement` +1 | hotkey | — | — |
| 390 | `scroll_rapide_bas` | Scroller rapidement vers le bas (5 pages) | `scroll rapide bas`, `descends vite`, `descends rapidement` +1 | hotkey | — | — |
| 391 | `snap_gauche` | Ancrer la fenetre a gauche (moitie ecran) | `fenetre a gauche`, `snap left`, `colle a gauche` +2 | hotkey | — | — |
| 392 | `snap_droite` | Ancrer la fenetre a droite (moitie ecran) | `fenetre a droite`, `snap right`, `colle a droite` +2 | hotkey | — | — |
| 393 | `snap_haut_gauche` | Ancrer la fenetre en haut a gauche (quart ecran) | `fenetre haut gauche`, `snap top left`, `quart haut gauche` +1 | hotkey | — | — |
| 394 | `snap_bas_gauche` | Ancrer la fenetre en bas a gauche (quart ecran) | `fenetre bas gauche`, `snap bottom left`, `quart bas gauche` +1 | hotkey | — | — |
| 395 | `snap_haut_droite` | Ancrer la fenetre en haut a droite (quart ecran) | `fenetre haut droite`, `snap top right`, `quart haut droite` +1 | hotkey | — | — |
| 396 | `snap_bas_droite` | Ancrer la fenetre en bas a droite (quart ecran) | `fenetre bas droite`, `snap bottom right`, `quart bas droite` +1 | hotkey | — | — |
| 397 | `restaurer_fenetre` | Restaurer la fenetre a sa taille precedente | `restaure la fenetre`, `taille normale`, `restore window` +2 | hotkey | — | — |
| 398 | `onglet_1` | Aller au 1er onglet | `onglet 1`, `premier onglet`, `tab 1` +1 | hotkey | — | — |
| 399 | `onglet_2` | Aller au 2eme onglet | `onglet 2`, `deuxieme onglet`, `tab 2` +1 | hotkey | — | — |
| 400 | `onglet_3` | Aller au 3eme onglet | `onglet 3`, `troisieme onglet`, `tab 3` +1 | hotkey | — | — |
| 401 | `onglet_4` | Aller au 4eme onglet | `onglet 4`, `quatrieme onglet`, `tab 4` +1 | hotkey | — | — |
| 402 | `onglet_5` | Aller au 5eme onglet | `onglet 5`, `cinquieme onglet`, `tab 5` +1 | hotkey | — | — |
| 403 | `onglet_dernier` | Aller au dernier onglet | `dernier onglet`, `last tab`, `va au dernier onglet` +1 | hotkey | — | — |
| 404 | `nouvel_onglet_vierge` | Ouvrir un nouvel onglet vierge | `nouvel onglet vierge`, `new tab blank`, `ouvre un onglet vide` +1 | hotkey | — | — |
| 405 | `mute_onglet` | Couper le son de l'onglet (clic droit requis) | `mute l'onglet`, `coupe le son de l'onglet`, `silence onglet` +1 | powershell | — | — |
| 406 | `browser_devtools` | Ouvrir les DevTools du navigateur | `ouvre les devtools`, `developer tools`, `ouvre la console` +2 | hotkey | — | — |
| 407 | `browser_devtools_console` | Ouvrir la console DevTools directement | `ouvre la console navigateur`, `console chrome`, `console edge` +2 | hotkey | — | — |
| 408 | `browser_source_view` | Voir le code source de la page | `voir le code source`, `view source`, `source de la page` +2 | hotkey | — | — |
| 409 | `curseur_mot_gauche` | Deplacer le curseur d'un mot a gauche | `mot precedent`, `word left`, `recule d'un mot` +1 | hotkey | — | — |
| 410 | `curseur_mot_droite` | Deplacer le curseur d'un mot a droite | `mot suivant`, `word right`, `avance d'un mot` +1 | hotkey | — | — |
| 411 | `selectionner_mot` | Selectionner le mot sous le curseur | `selectionne le mot`, `select word`, `prends le mot` +1 | hotkey | — | — |
| 412 | `selectionner_mot_gauche` | Etendre la selection d'un mot a gauche | `selection mot gauche`, `select word left`, `etends la selection a gauche` +1 | hotkey | — | — |
| 413 | `selectionner_mot_droite` | Etendre la selection d'un mot a droite | `selection mot droite`, `select word right`, `etends la selection a droite` +1 | hotkey | — | — |
| 414 | `selectionner_tout` | Selectionner tout le contenu | `selectionne tout`, `select all`, `tout selectionner` +2 | hotkey | — | — |
| 415 | `copier_texte` | Copier la selection | `copie`, `copy`, `copier` +2 | hotkey | — | — |
| 416 | `couper_texte` | Couper la selection | `coupe`, `cut`, `couper` +2 | hotkey | — | — |
| 417 | `coller_texte` | Coller le contenu du presse-papier | `colle`, `paste`, `coller` +2 | hotkey | — | — |
| 418 | `annuler_action` | Annuler la derniere action (undo) | `annule`, `undo`, `ctrl z` +2 | hotkey | — | — |
| 419 | `retablir_action` | Retablir l'action annulee (redo) | `retablis`, `redo`, `ctrl y` +2 | hotkey | — | — |
| 420 | `rechercher_dans_page` | Ouvrir la recherche dans la page | `cherche dans la page`, `find`, `ctrl f` +2 | hotkey | — | — |
| 421 | `rechercher_et_remplacer` | Ouvrir rechercher et remplacer | `cherche et remplace`, `find replace`, `ctrl h` +1 | hotkey | — | — |
| 422 | `supprimer_mot_gauche` | Supprimer le mot precedent | `supprime le mot precedent`, `delete word left`, `efface le mot avant` +1 | hotkey | — | — |
| 423 | `supprimer_mot_droite` | Supprimer le mot suivant | `supprime le mot suivant`, `delete word right`, `efface le mot apres` +1 | hotkey | — | — |
| 424 | `menu_contextuel` | Ouvrir le menu contextuel (clic droit) | `clic droit`, `menu contextuel`, `right click` +2 | hotkey | — | — |
| 425 | `valider_entree` | Appuyer sur Entree (valider) | `entree`, `valide`, `enter` +3 | hotkey | — | — |
| 426 | `echapper` | Appuyer sur Echap (annuler/fermer) | `echap`, `escape`, `annule` +2 | hotkey | — | — |
| 427 | `tabulation` | Naviguer au champ suivant (Tab) | `tab`, `champ suivant`, `element suivant` +2 | hotkey | — | — |
| 428 | `tabulation_inverse` | Naviguer au champ precedent (Shift+Tab) | `shift tab`, `champ precedent`, `element precedent` +2 | hotkey | — | — |
| 429 | `ouvrir_selection` | Ouvrir/activer l'element selectionne (Espace) | `espace`, `active`, `coche` +2 | hotkey | — | — |
| 430 | `media_suivant` | Piste suivante | `piste suivante`, `next track`, `chanson suivante` +2 | powershell | — | — |
| 431 | `media_precedent` | Piste precedente | `piste precedente`, `previous track`, `chanson precedente` +2 | powershell | — | — |
| 432 | `screenshot_complet` | Capture d'ecran complete (dans presse-papier) | `screenshot`, `capture d'ecran`, `print screen` +2 | hotkey | — | — |
| 433 | `screenshot_fenetre` | Capture d'ecran de la fenetre active | `screenshot fenetre`, `capture la fenetre`, `alt print screen` +1 | hotkey | — | — |
| 434 | `snip_screen` | Outil de capture d'ecran (selection libre) | `snip`, `outil capture`, `snipping tool` +2 | hotkey | — | — |
| 435 | `task_view` | Ouvrir la vue des taches (Task View) | `task view`, `vue des taches`, `montre les fenetres` +2 | hotkey | — | — |
| 436 | `creer_bureau_virtuel` | Creer un nouveau bureau virtuel | `nouveau bureau virtuel`, `cree un bureau`, `new desktop` +1 | hotkey | — | — |
| 437 | `fermer_bureau_virtuel` | Fermer le bureau virtuel actuel | `ferme le bureau virtuel`, `supprime ce bureau`, `close desktop` +1 | hotkey | — | — |
| 438 | `zoom_in` | Zoomer (agrandir) | `zoom in`, `zoome`, `agrandis` +3 | hotkey | — | — |
| 439 | `zoom_out` | Dezoomer (reduire) | `zoom out`, `dezoome`, `reduis` +3 | hotkey | — | — |
| 440 | `switch_app` | Basculer entre les applications (Alt+Tab) | `switch app`, `alt tab`, `change d'application` +2 | hotkey | — | — |
| 441 | `switch_app_inverse` | Basculer en arriere entre les apps | `app precedente alt tab`, `reverse alt tab`, `reviens a l'app precedente` +1 | hotkey | — | — |
| 442 | `ouvrir_start_menu` | Ouvrir le menu Demarrer | `ouvre le menu demarrer`, `start menu`, `menu demarrer` +2 | hotkey | — | — |
| 443 | `ouvrir_centre_notifications` | Ouvrir le centre de notifications | `ouvre les notifications`, `centre de notifications`, `notification center` +2 | hotkey | — | — |
| 444 | `ouvrir_clipboard_history` | Ouvrir l'historique du presse-papier | `historique presse papier`, `clipboard history`, `win v` +2 | hotkey | — | — |
| 445 | `ouvrir_emojis_clavier` | Ouvrir le panneau emojis | `panneau emojis`, `emoji keyboard`, `win point` +2 | hotkey | — | — |
| 446 | `plein_ecran_toggle` | Basculer en plein ecran (F11) | `plein ecran`, `fullscreen`, `f11` +2 | hotkey | — | — |
| 447 | `renommer_fichier` | Renommer le fichier/dossier selectionne (F2) | `renomme`, `rename`, `f2` +2 | hotkey | — | — |
| 448 | `supprimer_selection` | Supprimer la selection | `supprime`, `delete`, `supprimer` +2 | hotkey | — | — |
| 449 | `ouvrir_proprietes` | Voir les proprietes du fichier selectionne | `proprietes`, `properties`, `alt enter` +2 | hotkey | — | — |
| 450 | `fermer_fenetre_active` | Fermer la fenetre/app active (Alt+F4) | `ferme la fenetre`, `close window`, `alt f4` +2 | hotkey | — | — |
| 451 | `ouvrir_parametres_systeme` | Ouvrir les Parametres Windows | `ouvre les parametres`, `parametres windows`, `settings` +2 | hotkey | — | — |
| 452 | `ouvrir_centre_accessibilite` | Ouvrir les options d'accessibilite | `accessibilite`, `options accessibilite`, `ease of access` +2 | hotkey | — | — |
| 453 | `dictee_vocale_windows` | Activer la dictee vocale Windows | `dictee vocale`, `voice typing`, `win h` +2 | hotkey | — | — |
| 454 | `projection_ecran` | Options de projection ecran (etendre, dupliquer) | `projection ecran`, `project screen`, `win p` +2 | hotkey | — | — |
| 455 | `connecter_appareil` | Ouvrir le panneau de connexion d'appareils (Cast) | `connecter un appareil`, `cast screen`, `win k` +2 | hotkey | — | — |
| 456 | `ouvrir_game_bar_direct` | Ouvrir la Xbox Game Bar | `game bar directe`, `xbox game bar`, `win g direct` +1 | hotkey | — | — |
| 457 | `powertoys_color_picker` | Lancer le Color Picker PowerToys | `color picker`, `pipette couleur`, `capture une couleur` +2 | hotkey | — | — |
| 458 | `powertoys_text_extractor` | Extraire du texte de l'ecran (OCR PowerToys) | `text extractor`, `ocr ecran`, `lis le texte a l'ecran` +2 | hotkey | — | — |
| 459 | `powertoys_screen_ruler` | Mesurer des distances a l'ecran (Screen Ruler) | `screen ruler`, `regle ecran`, `mesure l'ecran` +2 | hotkey | — | — |
| 460 | `powertoys_always_on_top` | Epingler la fenetre au premier plan (PowerToys) | `pin powertoys`, `epingle powertoys`, `always on top powertoys` +1 | hotkey | — | — |
| 461 | `powertoys_paste_plain` | Coller en texte brut (PowerToys) | `colle en texte brut`, `paste plain`, `coller sans mise en forme` +2 | hotkey | — | — |
| 462 | `powertoys_fancyzones` | Activer FancyZones layout editor | `fancy zones`, `editeur de zones`, `layout fancyzones` +2 | hotkey | — | — |
| 463 | `powertoys_peek` | Apercu rapide de fichier (PowerToys Peek) | `peek fichier`, `apercu rapide`, `preview powertoys` +1 | hotkey | — | — |
| 464 | `powertoys_launcher` | Ouvrir PowerToys Run (lanceur rapide) | `powertoys run`, `lanceur rapide`, `quick launcher` +2 | hotkey | — | — |
| 465 | `traceroute_google` | Traceroute vers Google DNS | `traceroute`, `trace la route`, `tracert google` +2 | powershell | — | — |
| 466 | `ping_google` | Ping Google pour tester la connexion | `ping google`, `teste internet`, `j'ai internet` +2 | powershell | — | — |
| 467 | `ping_cluster_complet` | Ping tous les noeuds du cluster IA | `ping tout le cluster`, `tous les noeuds repondent`, `test cluster complet` +1 | powershell | — | — |
| 468 | `netstat_ecoute` | Ports en ecoute avec processus associes | `netstat listen`, `ports en ecoute`, `quels ports ecoutent` +1 | powershell | — | — |
| 469 | `flush_dns` | Purger le cache DNS | `flush dns`, `purge dns`, `vide le cache dns` +2 | powershell | — | — |
| 470 | `flush_arp` | Purger la table ARP | `flush arp`, `vide la table arp`, `purge arp` +1 | powershell | — | — |
| 471 | `ip_config_complet` | Configuration IP complete de toutes les interfaces | `ipconfig all`, `config ip complete`, `toutes les ips` +2 | powershell | — | — |
| 472 | `speed_test_rapide` | Test de debit internet rapide (download) | `speed test`, `test de vitesse`, `vitesse internet` +2 | powershell | — | — |
| 473 | `vpn_status` | Verifier l'etat des connexions VPN actives | `etat vpn`, `vpn status`, `suis je en vpn` +2 | powershell | — | — |
| 474 | `shutdown_timer_30` | Programmer l'extinction dans 30 minutes | `eteins dans 30 minutes`, `shutdown dans 30 min`, `timer extinction 30` +1 | powershell | — | Oui |
| 475 | `shutdown_timer_60` | Programmer l'extinction dans 1 heure | `eteins dans une heure`, `shutdown dans 1h`, `timer extinction 1h` +1 | powershell | — | Oui |
| 476 | `shutdown_timer_120` | Programmer l'extinction dans 2 heures | `eteins dans deux heures`, `shutdown dans 2h`, `timer extinction 2h` +1 | powershell | — | Oui |
| 477 | `annuler_shutdown` | Annuler l'extinction programmee | `annule l'extinction`, `cancel shutdown`, `arrete le timer` +2 | powershell | — | — |
| 478 | `restart_timer_30` | Programmer un redemarrage dans 30 minutes | `redemarre dans 30 minutes`, `restart dans 30 min`, `redemarrage programme 30` | powershell | — | Oui |
| 479 | `rappel_vocal` | Creer un rappel vocal avec notification | `rappelle moi dans {minutes} minutes`, `timer {minutes} min`, `alarme dans {minutes} minutes` +1 | powershell | minutes | — |
| 480 | `generer_mot_de_passe` | Generer un mot de passe securise aleatoire | `genere un mot de passe`, `password random`, `mot de passe aleatoire` +2 | powershell | — | — |
| 481 | `audit_rdp` | Verifier si le Bureau a distance est active | `rdp actif`, `bureau a distance`, `remote desktop status` +2 | powershell | — | — |
| 482 | `audit_admin_users` | Lister les utilisateurs administrateurs | `qui est admin`, `utilisateurs administrateurs`, `admin users` +2 | powershell | — | — |
| 483 | `sessions_actives` | Lister les sessions utilisateur actives | `sessions actives`, `qui est connecte`, `user sessions` +1 | powershell | — | — |
| 484 | `check_hash_fichier` | Calculer le hash SHA256 d'un fichier | `hash du fichier {path}`, `sha256 {path}`, `checksum {path}` +1 | powershell | path | — |
| 485 | `audit_software_recent` | Logiciels installes recemment (30 derniers jours) | `logiciels recemment installes`, `quoi de neuf installe`, `installations recentes` +1 | powershell | — | — |
| 486 | `firewall_toggle_profil` | Activer/desactiver le pare-feu pour le profil actif | `toggle firewall`, `active le pare feu`, `desactive le firewall` +2 | powershell | — | Oui |
| 487 | `luminosite_haute` | Monter la luminosite au maximum | `luminosite max`, `brightness max`, `ecran au maximum` +2 | powershell | — | — |
| 488 | `luminosite_basse` | Baisser la luminosite au minimum | `luminosite min`, `brightness low`, `ecran au minimum` +2 | powershell | — | — |
| 489 | `luminosite_moyenne` | Luminosite a 50% | `luminosite moyenne`, `brightness medium`, `luminosite normale` +2 | powershell | — | — |
| 490 | `info_moniteurs` | Informations sur les moniteurs connectes | `info moniteurs`, `quels ecrans`, `resolution ecran` +2 | powershell | — | — |
| 491 | `batterie_info` | Etat de la batterie (si laptop) | `etat batterie`, `battery status`, `niveau batterie` +2 | powershell | — | — |
| 492 | `power_events_recent` | Historique veille/reveil des dernieres 24h | `historique veille`, `quand le pc s'est endormi`, `power events` +1 | powershell | — | — |
| 493 | `night_light_toggle` | Basculer l'eclairage nocturne | `lumiere de nuit`, `night light`, `eclairage nocturne` +2 | powershell | — | — |
| 494 | `imprimer_page` | Imprimer la page/document actif | `imprime`, `print`, `lance l'impression` +2 | hotkey | — | — |
| 495 | `file_impression` | Voir la file d'attente d'impression | `file d'impression`, `print queue`, `quoi dans l'imprimante` +2 | powershell | — | — |
| 496 | `annuler_impressions` | Annuler toutes les impressions en attente | `annule les impressions`, `cancel print`, `arrete l'imprimante` +1 | powershell | — | — |
| 497 | `imprimante_par_defaut` | Voir l'imprimante par defaut | `quelle imprimante par defaut`, `default printer`, `imprimante principale` +1 | powershell | — | — |
| 498 | `kill_chrome` | Forcer la fermeture de Chrome | `tue chrome`, `kill chrome`, `force ferme chrome` +1 | powershell | — | Oui |
| 499 | `kill_edge` | Forcer la fermeture d'Edge | `tue edge`, `kill edge`, `force ferme edge` +1 | powershell | — | Oui |
| 500 | `kill_discord` | Forcer la fermeture de Discord | `tue discord`, `kill discord`, `ferme discord de force` +1 | powershell | — | Oui |
| 501 | `kill_spotify` | Forcer la fermeture de Spotify | `tue spotify`, `kill spotify`, `ferme spotify de force` +1 | powershell | — | Oui |
| 502 | `kill_steam` | Forcer la fermeture de Steam | `tue steam`, `kill steam`, `ferme steam de force` +1 | powershell | — | Oui |
| 503 | `priorite_haute` | Passer la fenetre active en priorite haute CPU | `priorite haute`, `high priority`, `boost le processus` +1 | powershell | — | — |
| 504 | `processus_reseau` | Processus utilisant le reseau actuellement | `qui utilise le reseau`, `processus reseau`, `network processes` +1 | powershell | — | — |
| 505 | `wsl_status` | Voir les distributions WSL installees | `distributions wsl`, `wsl list`, `quelles distros linux` +2 | powershell | — | — |
| 506 | `wsl_start` | Demarrer WSL (distribution par defaut) | `lance wsl`, `demarre linux`, `ouvre wsl` +2 | powershell | — | — |
| 507 | `wsl_disk_usage` | Espace disque utilise par WSL | `taille wsl`, `espace wsl`, `combien pese linux` +1 | powershell | — | — |
| 508 | `loupe_activer` | Activer la loupe Windows | `active la loupe`, `zoom ecran`, `magnifier on` +2 | hotkey | — | — |
| 509 | `loupe_desactiver` | Desactiver la loupe Windows | `desactive la loupe`, `arrete le zoom`, `magnifier off` +1 | hotkey | — | — |
| 510 | `haut_contraste_toggle` | Basculer en mode haut contraste | `haut contraste`, `high contrast`, `mode contraste` +1 | hotkey | — | — |
| 511 | `touches_remanentes` | Activer/desactiver les touches remanentes | `touches remanentes`, `sticky keys`, `touches collantes` +1 | powershell | — | — |
| 512 | `taille_texte_plus` | Augmenter la taille du texte systeme | `texte plus grand`, `agrandis le texte`, `bigger text` +1 | powershell | — | — |
| 513 | `ouvrir_melangeur_audio` | Ouvrir le melangeur de volume | `melangeur audio`, `volume mixer`, `mix audio` +2 | powershell | — | — |
| 514 | `ouvrir_param_son` | Ouvrir les parametres de son | `parametres son`, `reglages audio`, `sound settings` +2 | powershell | — | — |
| 515 | `lister_audio_devices` | Lister les peripheriques audio | `peripheriques audio`, `quelles sorties son`, `audio devices` +2 | powershell | — | — |
| 516 | `volume_50` | Mettre le volume a 50% | `volume a 50`, `moitie volume`, `volume moyen` +1 | powershell | — | — |
| 517 | `volume_25` | Mettre le volume a 25% | `volume a 25`, `volume bas`, `volume faible` +1 | powershell | — | — |
| 518 | `volume_max` | Mettre le volume au maximum | `volume a fond`, `volume maximum`, `volume 100` +1 | powershell | — | — |
| 519 | `storage_sense_on` | Activer Storage Sense (nettoyage auto) | `active storage sense`, `nettoyage automatique`, `auto clean` +1 | powershell | — | — |
| 520 | `disk_cleanup` | Lancer le nettoyage de disque Windows (cleanmgr) | `nettoyage de disque`, `disk cleanup`, `cleanmgr` +1 | powershell | — | — |
| 521 | `defrag_status` | Voir l'etat de fragmentation des disques | `etat defragmentation`, `defrag status`, `disques fragmentes` +1 | powershell | — | — |
| 522 | `optimiser_disques` | Optimiser/defragmenter les disques | `optimise les disques`, `defragmente`, `defrag` +1 | powershell | — | — |
| 523 | `focus_assist_alarms` | Focus Assist mode alarmes seulement | `alarmes seulement`, `focus alarms only`, `juste les alarmes` +1 | powershell | — | — |
| 524 | `startup_apps_list` | Lister les apps qui demarrent au boot | `apps au demarrage`, `startup apps`, `quoi se lance au boot` +1 | powershell | — | — |
| 525 | `startup_settings` | Ouvrir les parametres des apps au demarrage | `parametres demarrage`, `startup settings`, `gerer le demarrage` +1 | powershell | — | — |
| 526 | `credential_list` | Lister les identifiants Windows enregistres | `liste les identifiants`, `quels mots de passe`, `credentials saved` +1 | powershell | — | — |
| 527 | `dns_serveurs` | Voir les serveurs DNS configures | `quels serveurs dns`, `dns configures`, `dns servers` +2 | powershell | — | — |
| 528 | `sync_horloge` | Synchroniser l'horloge avec le serveur NTP | `synchronise l'horloge`, `sync ntp`, `mets l'heure a jour` +2 | powershell | — | — |
| 529 | `timezone_info` | Voir le fuseau horaire actuel | `quel fuseau horaire`, `timezone`, `heure locale` +2 | powershell | — | — |
| 530 | `calendrier_mois` | Afficher le calendrier du mois en cours | `calendrier`, `montre le calendrier`, `quel jour on est` +1 | powershell | — | — |
| 531 | `ouvrir_rdp` | Ouvrir le client Remote Desktop | `ouvre remote desktop`, `lance rdp`, `bureau a distance client` +2 | powershell | — | — |
| 532 | `rdp_connect` | Connexion Remote Desktop a une machine | `connecte en rdp a {host}`, `remote desktop {host}`, `bureau a distance sur {host}` +1 | powershell | host | — |
| 533 | `ssh_connect` | Connexion SSH a un serveur | `connecte en ssh a {host}`, `ssh {host}`, `terminal distant {host}` +1 | powershell | host | — |
| 534 | `changer_clavier` | Changer la disposition clavier (FR/EN) | `change le clavier`, `switch keyboard`, `clavier francais` +2 | hotkey | — | — |
| 535 | `clavier_suivant` | Passer a la disposition clavier suivante | `clavier suivant`, `next keyboard`, `alt shift` +1 | hotkey | — | — |
| 536 | `taskbar_cacher` | Cacher la barre des taches automatiquement | `cache la taskbar`, `hide taskbar`, `barre des taches invisible` +1 | powershell | — | — |
| 537 | `wallpaper_info` | Voir le fond d'ecran actuel | `quel fond d'ecran`, `wallpaper actuel`, `image de fond` +1 | powershell | — | — |
| 538 | `icones_bureau_toggle` | Afficher/masquer les icones du bureau | `cache les icones`, `montre les icones`, `icones bureau` +2 | powershell | — | — |
| 539 | `sandbox_launch` | Lancer Windows Sandbox | `lance la sandbox`, `windows sandbox`, `ouvre la sandbox` +1 | powershell | — | — |
| 540 | `hyperv_list_vms` | Lister les machines virtuelles Hyper-V | `liste les vms`, `virtual machines`, `hyper v vms` +2 | powershell | — | — |
| 541 | `hyperv_start_vm` | Demarrer une VM Hyper-V | `demarre la vm {vm}`, `start vm {vm}`, `lance la machine {vm}` +1 | powershell | vm | — |
| 542 | `hyperv_stop_vm` | Arreter une VM Hyper-V | `arrete la vm {vm}`, `stop vm {vm}`, `eteins la machine {vm}` +1 | powershell | vm | — |
| 543 | `service_start` | Demarrer un service Windows | `demarre le service {svc}`, `start service {svc}`, `lance le service {svc}` | powershell | svc | — |
| 544 | `service_stop` | Arreter un service Windows | `arrete le service {svc}`, `stop service {svc}`, `coupe le service {svc}` | powershell | svc | Oui |
| 545 | `service_restart` | Redemarrer un service Windows | `redemarre le service {svc}`, `restart service {svc}`, `relance le service {svc}` | powershell | svc | — |
| 546 | `service_status` | Voir l'etat d'un service Windows | `etat du service {svc}`, `status service {svc}`, `le service {svc} tourne` | powershell | svc | — |
| 547 | `partitions_list` | Lister toutes les partitions | `liste les partitions`, `partitions disque`, `volumes montes` +1 | powershell | — | — |
| 548 | `disques_physiques` | Voir les disques physiques installes | `disques physiques`, `quels disques`, `ssd hdd` +2 | powershell | — | — |
| 549 | `clipboard_contenu` | Voir le contenu actuel du presse-papier | `quoi dans le presse papier`, `clipboard content`, `montre le clipboard` +1 | powershell | — | — |
| 550 | `clipboard_en_majuscules` | Convertir le texte du clipboard en majuscules | `clipboard en majuscules`, `texte en majuscules`, `uppercase clipboard` +1 | powershell | — | — |
| 551 | `clipboard_en_minuscules` | Convertir le texte du clipboard en minuscules | `clipboard en minuscules`, `texte en minuscules`, `lowercase clipboard` +1 | powershell | — | — |
| 552 | `clipboard_compter_mots` | Compter les mots dans le presse-papier | `combien de mots copies`, `word count clipboard`, `compte les mots` +1 | powershell | — | — |
| 553 | `clipboard_trim` | Nettoyer les espaces du texte clipboard | `nettoie le clipboard`, `trim clipboard`, `enleve les espaces` +1 | powershell | — | — |
| 554 | `param_microphone` | Parametres de confidentialite microphone | `parametres microphone`, `privacy micro`, `autoriser le micro` +1 | powershell | — | — |
| 555 | `param_localisation` | Parametres de localisation/GPS | `parametres localisation`, `privacy location`, `active le gps` +2 | powershell | — | — |
| 556 | `param_gaming` | Parametres de jeu Windows | `parametres gaming`, `game settings`, `mode jeu settings` +2 | powershell | — | — |
| 557 | `param_connexion` | Parametres de connexion (PIN, mot de passe) | `options de connexion`, `sign in options`, `changer le pin` +2 | powershell | — | — |
| 558 | `param_apps_defaut` | Parametres des apps par defaut | `apps par defaut`, `default apps`, `navigateur par defaut` +1 | powershell | — | — |
| 559 | `param_fonctionnalites_optionnelles` | Fonctionnalites optionnelles Windows | `fonctionnalites optionnelles`, `optional features`, `ajouter une fonctionnalite` +1 | powershell | — | — |
| 560 | `param_phone_link` | Ouvrir Phone Link (connexion telephone) | `phone link`, `lien telephone`, `connecter mon telephone` +1 | powershell | — | — |
| 561 | `param_notifications_apps` | Parametres notifications par application | `notifications par app`, `gerer les notifications`, `notifs par app` +1 | powershell | — | — |
| 562 | `param_vpn_settings` | Parametres VPN Windows | `parametres vpn`, `vpn settings`, `configurer le vpn` +1 | powershell | — | — |
| 563 | `param_wifi_settings` | Parametres WiFi avances | `parametres wifi`, `wifi settings`, `reseaux connus` +1 | powershell | — | — |
| 564 | `param_update_avance` | Parametres Windows Update avances | `update avance`, `windows update settings`, `options de mise a jour` +1 | powershell | — | — |
| 565 | `param_recovery` | Options de recuperation systeme | `recovery options`, `reinitialiser le pc`, `restauration systeme` +1 | powershell | — | — |
| 566 | `param_developeurs` | Parametres developpeur Windows | `mode developpeur`, `developer settings`, `active le mode dev` +1 | powershell | — | — |
| 567 | `calculatrice_standard` | Ouvrir la calculatrice Windows | `ouvre la calculatrice`, `calculatrice`, `calc` +1 | powershell | — | — |
| 568 | `calculer_expression` | Calculer une expression mathematique | `calcule {expr}`, `combien fait {expr}`, `resultat de {expr}` +1 | powershell | expr | — |
| 569 | `convertir_temperature` | Convertir Celsius en Fahrenheit et inversement | `convertis {temp} degres`, `celsius en fahrenheit {temp}`, `fahrenheit en celsius {temp}` +1 | powershell | temp | — |
| 570 | `convertir_octets` | Convertir des octets en unites lisibles | `convertis {bytes} octets`, `combien de go fait {bytes}`, `bytes en gb {bytes}` +1 | powershell | bytes | — |
| 571 | `clipboard_base64_encode` | Encoder le clipboard en Base64 | `encode en base64`, `base64 encode`, `clipboard en base64` +1 | powershell | — | — |
| 572 | `clipboard_base64_decode` | Decoder le clipboard depuis Base64 | `decode le base64`, `base64 decode`, `clipboard depuis base64` +1 | powershell | — | — |
| 573 | `clipboard_url_encode` | Encoder le clipboard en URL (percent-encode) | `url encode`, `encode l'url`, `percent encode` +1 | powershell | — | — |
| 574 | `clipboard_json_format` | Formatter le JSON du clipboard avec indentation | `formate le json`, `json pretty`, `indente le json` +1 | powershell | — | — |
| 575 | `clipboard_md5` | Calculer le MD5 du texte dans le clipboard | `md5 du clipboard`, `hash md5 texte`, `md5 du texte copie` +1 | powershell | — | — |
| 576 | `clipboard_sort_lines` | Trier les lignes du clipboard par ordre alphabetique | `trie les lignes`, `sort lines clipboard`, `ordonne le clipboard` +1 | powershell | — | — |
| 577 | `clipboard_unique_lines` | Supprimer les lignes dupliquees du clipboard | `deduplique les lignes`, `unique lines`, `enleve les doublons texte` +1 | powershell | — | — |
| 578 | `clipboard_reverse` | Inverser le texte du clipboard | `inverse le texte`, `reverse clipboard`, `texte a l'envers` +1 | powershell | — | — |
| 579 | `power_performance` | Activer le plan d'alimentation Haute Performance | `mode performance`, `high performance`, `pleine puissance` +2 | powershell | — | — |
| 580 | `power_equilibre` | Activer le plan d'alimentation Equilibre | `mode equilibre`, `balanced power`, `plan normal` +1 | powershell | — | — |
| 581 | `power_economie` | Activer le plan d'alimentation Economie d'energie | `mode economie`, `power saver`, `economie energie` +2 | powershell | — | — |
| 582 | `power_plans_list` | Lister les plans d'alimentation disponibles | `quels plans alimentation`, `power plans`, `modes d'alimentation disponibles` +1 | powershell | — | — |
| 583 | `sleep_timer_30` | Mettre le PC en veille dans 30 minutes | `veille dans 30 minutes`, `sleep dans 30 min`, `dors dans une demi heure` +1 | powershell | — | Oui |
| 584 | `network_reset` | Reset complet de la pile reseau Windows | `reset reseau`, `reinitialise le reseau`, `network reset` +1 | powershell | — | Oui |
| 585 | `network_troubleshoot` | Lancer le depanneur reseau Windows | `depanne le reseau`, `network troubleshoot`, `diagnostic reseau windows` +1 | powershell | — | — |
| 586 | `nslookup_domain` | Resoudre un nom de domaine (nslookup) | `nslookup {domain}`, `resous {domain}`, `ip de {domain}` +1 | powershell | domain | — |
| 587 | `registry_backup` | Sauvegarder le registre complet | `backup registre`, `sauvegarde le registre`, `exporte le registre` +1 | powershell | — | Oui |
| 588 | `registry_search` | Chercher une cle dans le registre | `cherche dans le registre {cle}`, `registry search {cle}`, `trouve la cle {cle}` | powershell | cle | — |
| 589 | `registry_recent_changes` | Cles de registre recemment modifiees | `registre recent`, `changements registre`, `modifications registre` | powershell | — | — |
| 590 | `registry_startup_entries` | Lister les entrees de demarrage dans le registre | `startup registre`, `autorun registre`, `demarrage registre` | powershell | — | — |
| 591 | `fonts_list` | Lister les polices installees | `liste les polices`, `quelles fonts`, `polices installees` +1 | powershell | — | — |
| 592 | `fonts_count` | Compter les polices installees | `combien de polices`, `nombre de fonts`, `total polices` | powershell | — | — |
| 593 | `fonts_folder` | Ouvrir le dossier des polices | `dossier polices`, `ouvre les fonts`, `ouvrir dossier fonts` | powershell | — | — |
| 594 | `env_list_user` | Lister les variables d'environnement utilisateur | `variables utilisateur`, `env vars user`, `mes variables` +1 | powershell | — | — |
| 595 | `env_list_system` | Lister les variables d'environnement systeme | `variables systeme`, `env vars systeme`, `environnement systeme` | powershell | — | — |
| 596 | `env_set_user` | Definir une variable d'environnement utilisateur | `set variable {nom} {valeur}`, `definis {nom} a {valeur}`, `env set {nom} {valeur}` | powershell | nom, valeur | — |
| 597 | `env_path_entries` | Lister les dossiers dans le PATH | `montre le path`, `dossiers du path`, `contenu du path` +1 | powershell | — | — |
| 598 | `env_add_to_path` | Ajouter un dossier au PATH utilisateur | `ajoute au path {dossier}`, `path add {dossier}`, `rajoute {dossier} au path` | powershell | dossier | — |
| 599 | `schtask_running` | Lister les taches planifiees en cours d'execution | `taches en cours`, `scheduled tasks running`, `taches actives` | powershell | — | — |
| 600 | `schtask_next_run` | Prochaines taches planifiees | `prochaines taches`, `next scheduled tasks`, `quand les taches` | powershell | — | — |
| 601 | `schtask_history` | Historique des taches planifiees recentes | `historique taches`, `task history`, `dernieres taches executees` | powershell | — | — |
| 602 | `firewall_rules_list` | Lister les regles du pare-feu actives | `regles pare feu`, `firewall rules`, `liste les regles firewall` | powershell | — | — |
| 603 | `firewall_block_ip` | Bloquer une adresse IP dans le pare-feu | `bloque l'ip {ip}`, `firewall block {ip}`, `interdit {ip}` +1 | powershell | ip | Oui |
| 604 | `firewall_recent_blocks` | Voir les connexions recemment bloquees | `connexions bloquees`, `firewall blocks`, `qui est bloque` | powershell | — | — |
| 605 | `disk_smart_status` | Statut SMART des disques (sante) | `sante des disques`, `smart status`, `etat des disques` +1 | powershell | — | — |
| 606 | `disk_space_by_folder` | Espace utilise par dossier (top 15) | `espace par dossier`, `quels dossiers prennent de la place`, `gros dossiers` +1 | powershell | — | — |
| 607 | `disk_temp_files_age` | Fichiers temporaires les plus anciens | `vieux fichiers temp`, `anciens temp`, `temp files age` | powershell | — | — |
| 608 | `usb_list_devices` | Lister les peripheriques USB connectes | `peripheriques usb`, `usb connectes`, `quels usb` +1 | powershell | — | — |
| 609 | `usb_storage_list` | Lister les cles USB et disques amovibles | `cles usb`, `disques amovibles`, `usb storage` +1 | powershell | — | — |
| 610 | `usb_safely_eject` | Ejecter un peripherique USB en securite | `ejecte la cle usb`, `ejecter usb`, `safely eject` +1 | powershell | — | Oui |
| 611 | `usb_history` | Historique des peripheriques USB connectes | `historique usb`, `anciens usb`, `usb history` +1 | powershell | — | — |
| 612 | `screen_resolution` | Afficher la resolution de chaque ecran | `resolution ecran`, `quelle resolution`, `taille ecran` +1 | powershell | — | — |
| 613 | `screen_brightness_up` | Augmenter la luminosite | `augmente la luminosite`, `plus de lumiere`, `brightness up` +1 | powershell | — | — |
| 614 | `screen_brightness_down` | Baisser la luminosite | `baisse la luminosite`, `moins de lumiere`, `brightness down` +1 | powershell | — | — |
| 615 | `screen_night_light` | Activer/desactiver l'eclairage nocturne | `eclairage nocturne`, `night light`, `mode nuit ecran` +1 | powershell | — | — |
| 616 | `screen_refresh_rate` | Voir la frequence de rafraichissement | `frequence ecran`, `refresh rate`, `hertz ecran` +1 | powershell | — | — |
| 617 | `audio_list_devices` | Lister tous les peripheriques audio | `peripheriques audio`, `devices audio`, `quels hauts parleurs` +1 | powershell | — | — |
| 618 | `audio_default_speaker` | Voir le haut-parleur par defaut | `haut parleur par defaut`, `quel speaker`, `sortie audio` +1 | powershell | — | — |
| 619 | `audio_volume_level` | Voir le niveau de volume actuel | `quel volume`, `niveau du son`, `volume level` +1 | powershell | — | — |
| 620 | `audio_settings` | Ouvrir les parametres de son | `parametres son`, `reglages audio`, `settings audio` +1 | powershell | — | — |
| 621 | `process_by_memory` | Top 15 processus par memoire | `processus par memoire`, `qui consomme la ram`, `top ram` +1 | powershell | — | — |
| 622 | `process_by_cpu` | Top 15 processus par CPU | `processus par cpu`, `qui consomme le cpu`, `top cpu` +1 | powershell | — | — |
| 623 | `process_tree` | Arborescence des processus (parent-enfant) | `arbre des processus`, `process tree`, `qui lance quoi` +1 | powershell | — | — |
| 624 | `process_handles` | Processus avec le plus de handles ouverts | `handles ouverts`, `processus handles`, `qui a trop de handles` | powershell | — | — |
| 625 | `wu_check_updates` | Verifier les mises a jour Windows disponibles | `verifie les mises a jour`, `check updates`, `y a des updates` +1 | powershell | — | — |
| 626 | `wu_history` | Historique des mises a jour Windows | `historique updates`, `mises a jour recentes`, `update history` +1 | powershell | — | — |
| 627 | `wu_pause_updates` | Parametres pour suspendre les mises a jour | `pause les updates`, `suspends les mises a jour`, `pas d'update` | powershell | — | — |
| 628 | `wu_driver_updates` | Voir les mises a jour de pilotes optionnelles | `mises a jour pilotes`, `driver updates`, `updates optionnelles` | powershell | — | — |
| 629 | `wu_last_reboot_reason` | Raison du dernier redemarrage | `pourquoi le pc a redemarre`, `dernier reboot`, `raison redemarrage` +1 | powershell | — | — |
| 630 | `restore_point_create` | Creer un point de restauration systeme | `cree un point de restauration`, `restore point`, `sauvegarde systeme` +1 | powershell | — | Oui |
| 631 | `restore_point_list` | Lister les points de restauration | `liste les points de restauration`, `quels restore points`, `points de restauration disponibles` | powershell | — | — |
| 632 | `system_info_detailed` | Informations systeme detaillees | `info systeme detaille`, `systeminfo`, `tout sur le pc` +1 | powershell | — | — |
| 633 | `notif_clear_all` | Effacer toutes les notifications | `efface les notifications`, `clear notifications`, `vire les notifs` +1 | powershell | — | — |
| 634 | `notif_dnd_toggle` | Activer/desactiver Ne pas deranger | `ne pas deranger`, `do not disturb`, `mode silencieux` +1 | powershell | — | — |
| 635 | `notif_app_settings` | Parametres de notifications par application | `notifs par appli`, `reglages notifications`, `quelles applis notifient` | powershell | — | — |
| 636 | `default_browser_check` | Voir quel est le navigateur par defaut | `quel navigateur par defaut`, `default browser`, `navigateur principal` | powershell | — | — |
| 637 | `default_apps_settings` | Ouvrir les parametres d'applis par defaut | `applis par defaut`, `apps par defaut`, `default apps` +1 | powershell | — | — |
| 638 | `file_type_assoc` | Voir l'association d'un type de fichier | `quelle appli pour {ext}`, `association {ext}`, `qui ouvre les {ext}` | powershell | ext | — |
| 639 | `compress_folder` | Compresser un dossier en ZIP | `compresse {dossier}`, `zip {dossier}`, `archive {dossier}` +1 | powershell | dossier | — |
| 640 | `extract_archive` | Extraire une archive ZIP | `extrais {archive}`, `dezippe {archive}`, `decompresse {archive}` +1 | powershell | archive | — |
| 641 | `rename_files_batch` | Renommer des fichiers en lot (prefixe) | `renomme en lot {prefix}`, `batch rename {prefix}`, `renomme les fichiers {prefix}` | powershell | prefix | Oui |
| 642 | `find_large_files` | Trouver les plus gros fichiers (top 20) | `plus gros fichiers`, `fichiers les plus lourds`, `big files` +1 | powershell | — | — |
| 643 | `find_old_files` | Trouver les fichiers non modifies depuis 90 jours | `vieux fichiers`, `fichiers anciens`, `old files` +1 | powershell | — | — |
| 644 | `motherboard_info` | Informations sur la carte mere | `carte mere`, `motherboard`, `quelle carte mere` +1 | powershell | — | — |
| 645 | `ram_details` | Details des barrettes RAM | `details ram`, `barrettes memoire`, `ram details` +1 | powershell | — | — |
| 646 | `windows_license` | Statut de la licence Windows | `licence windows`, `windows active`, `statut activation` +1 | powershell | — | — |
| 647 | `boot_config` | Configuration de demarrage (BCD) | `config demarrage`, `boot config`, `bcd edit` +1 | powershell | — | — |
| 648 | `locale_current` | Afficher les parametres regionaux actuels | `parametres regionaux`, `quelle locale`, `region actuelle` | powershell | — | — |
| 649 | `timezone_current` | Afficher le fuseau horaire actuel | `quel fuseau horaire`, `timezone`, `quelle heure on est` +1 | powershell | — | — |
| 650 | `timezone_list` | Lister les fuseaux horaires disponibles | `liste fuseaux horaires`, `timezones disponibles`, `quels fuseaux` | powershell | — | — |
| 651 | `wifi_profiles` | Lister les profils Wi-Fi enregistres | `profils wifi`, `reseaux wifi enregistres`, `wifi profiles` +1 | powershell | — | — |
| 652 | `wifi_password` | Voir le mot de passe d'un reseau Wi-Fi | `mot de passe wifi {ssid}`, `password wifi {ssid}`, `cle wifi {ssid}` +1 | powershell | ssid | — |
| 653 | `wifi_signal_strength` | Force du signal Wi-Fi actuel | `force du wifi`, `signal wifi`, `qualite wifi` +1 | powershell | — | — |
| 654 | `wifi_disconnect` | Deconnecter le Wi-Fi | `deconnecte le wifi`, `coupe le wifi`, `wifi off` | powershell | — | — |
| 655 | `hyperv_vms_list` | Lister les VMs Hyper-V | `liste les vms`, `machines virtuelles`, `hyper v vms` +1 | powershell | — | — |
| 656 | `hyperv_vm_start` | Demarrer une VM Hyper-V | `demarre la vm {nom}`, `start vm {nom}`, `lance la vm {nom}` | powershell | nom | Oui |
| 657 | `hyperv_vm_stop` | Arreter une VM Hyper-V | `arrete la vm {nom}`, `stop vm {nom}`, `eteins la vm {nom}` | powershell | nom | Oui |
| 658 | `wsl_list_distros` | Lister les distributions WSL installees | `quelles distros wsl`, `linux installes`, `wsl distributions` | powershell | — | — |
| 659 | `eventlog_critical` | Evenements critiques des dernieres 24h | `evenements critiques`, `erreurs critiques`, `crashes recents` +1 | powershell | — | — |
| 660 | `eventlog_app_crashes` | Applications qui ont plante recemment | `applis qui ont plante`, `crashes d'applis`, `app crashes` +1 | powershell | — | — |
| 661 | `eventlog_logins` | Connexions recentes au systeme | `qui s'est connecte`, `logins recents`, `connexions recentes` +1 | powershell | — | — |
| 662 | `eventlog_shutdowns` | Historique des arrets et redemarrages | `historique arrets`, `quand le pc s'est eteint`, `shutdown history` +1 | powershell | — | — |
| 663 | `shares_list` | Lister les dossiers partages | `dossiers partages`, `partages reseau`, `shares` +1 | powershell | — | — |
| 664 | `shares_connections` | Voir les connexions aux partages | `qui est connecte aux partages`, `connexions smb`, `sessions partage` | powershell | — | — |
| 665 | `mapped_drives` | Lister les lecteurs reseau mappes | `lecteurs reseau`, `mapped drives`, `disques reseau` +1 | powershell | — | — |
| 666 | `printer_queue` | Voir la file d'attente de l'imprimante par defaut | `file d'impression`, `queue imprimante`, `travaux d'impression` +1 | powershell | — | — |
| 667 | `printer_test_page` | Imprimer une page de test | `page de test imprimante`, `test print`, `imprime une page test` | powershell | — | Oui |
| 668 | `jobs_list` | Lister les jobs PowerShell en arriere-plan | `jobs en cours`, `taches en arriere plan`, `background jobs` +1 | powershell | — | — |
| 669 | `jobs_clean` | Nettoyer les jobs termines | `nettoie les jobs`, `clean jobs`, `supprime les jobs finis` | powershell | — | — |

## Trading

**19 commandes**

| # | Nom | Description | Declencheurs | Type | Params | Confirm |
|---|-----|-------------|--------------|------|--------|---------|
| 1 | `scanner_marche` | Scanner le marche MEXC | `scanne le marche`, `scanner le marche`, `lance le scanner` +3 | script | — | — |
| 2 | `detecter_breakout` | Detecter les breakouts | `detecte les breakouts`, `cherche les breakouts`, `breakout detector` +2 | script | — | — |
| 3 | `pipeline_trading` | Lancer le pipeline intensif | `lance le pipeline`, `pipeline intensif`, `demarre le pipeline` +6 | script | — | Oui |
| 4 | `sniper_breakout` | Lancer le sniper breakout | `lance le sniper`, `sniper breakout`, `demarre le sniper` +1 | script | — | Oui |
| 5 | `river_scalp` | Lancer le River Scalp 1min | `lance river scalp`, `river scalp`, `scalp 1 minute` +2 | script | — | Oui |
| 6 | `hyper_scan` | Lancer l'hyper scan V2 | `lance hyper scan`, `hyper scan`, `scan intensif` +1 | script | — | — |
| 7 | `statut_cluster` | Statut du cluster IA | `statut du cluster`, `etat du cluster`, `statut cluster` +3 | jarvis_tool | — | — |
| 8 | `modeles_charges` | Modeles charges sur le cluster | `quels modeles sont charges`, `liste les modeles`, `modeles charges` +2 | jarvis_tool | — | — |
| 9 | `ollama_status` | Statut du backend Ollama | `statut ollama`, `etat ollama`, `status ollama` +3 | jarvis_tool | — | — |
| 10 | `ollama_modeles` | Modeles Ollama disponibles | `modeles ollama`, `liste modeles ollama`, `quels modeles ollama` | jarvis_tool | — | — |
| 11 | `recherche_web_ia` | Recherche web via Ollama cloud | `recherche web {requete}`, `cherche sur le web {requete}`, `recherche internet {requete}` +1 | jarvis_tool | requete | — |
| 12 | `consensus_ia` | Consensus multi-IA | `consensus sur {question}`, `demande un consensus sur {question}`, `lance un consensus {question}` +1 | jarvis_tool | question | — |
| 13 | `query_ia` | Interroger une IA locale | `demande a {node} {prompt}`, `interroge {node} sur {prompt}`, `pose a {node} la question {prompt}` | jarvis_tool | node, prompt | — |
| 14 | `signaux_trading` | Signaux de trading en attente | `signaux en attente`, `quels signaux`, `signaux trading` +2 | jarvis_tool | — | — |
| 15 | `positions_trading` | Positions de trading ouvertes | `mes positions`, `positions ouvertes`, `quelles positions` +2 | jarvis_tool | — | — |
| 16 | `statut_trading` | Statut global du trading | `statut trading`, `etat du trading`, `status trading` +2 | jarvis_tool | — | — |
| 17 | `executer_signal` | Executer un signal de trading | `execute le signal {id}`, `lance le signal {id}`, `trade le signal {id}` +1 | jarvis_tool | id | Oui |
| 18 | `cluster_health` | Health check rapide du cluster IA | `health check cluster`, `verifie le cluster ia`, `est ce que le cluster va bien` +3 | powershell | — | — |
| 19 | `ollama_running` | Modeles Ollama actuellement en memoire | `quels modeles ollama tournent`, `ollama running`, `modeles en memoire ollama` +1 | powershell | — | — |

---

## Statistiques

| Categorie | Commandes | Pipelines |
|-----------|-----------|-----------|
| Accessibilite | 10 | 0 |
| App | 23 | 0 |
| Clipboard | 13 | 0 |
| Developpement & Outils | 268 | 0 |
| Gestion des Fenetres | 13 | 0 |
| Fichiers | 45 | 0 |
| Jarvis | 12 | 0 |
| Launcher | 12 | 0 |
| Media & Volume | 7 | 0 |
| Navigation Web | 323 | 0 |
| Pipelines Multi-Etapes | 0 | 278 |
| Saisie | 3 | 0 |
| Systeme & Maintenance | 669 | 0 |
| Trading | 19 | 0 |
| **TOTAL** | **1417** | **278** |

> **Grand total: 1695 commandes vocales**
