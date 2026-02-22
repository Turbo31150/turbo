
## 812 Commandes Vocales — Liste Complete

**1497 commandes** au total dont **246 pipelines** multi-etapes.
Reparties en **14 categories**.

| Categorie | Nb | Description |
|-----------|-----|------------|
| **accessibilite** | 10 | taille_texte_grand, clavier_virtuel, filtre_couleur... |
| **app** | 23 | ouvrir_vscode, ouvrir_terminal, ouvrir_lmstudio... |
| **clipboard** | 13 | copier, coller, couper... |
| **dev** | 218 | docker_ps, docker_images, docker_stop_all... |
| **fenetre** | 13 | minimiser_tout, alt_tab, fermer_fenetre... |
| **fichiers** | 47 | ouvrir_documents, ouvrir_bureau, ouvrir_dossier... |
| **jarvis** | 12 | historique_commandes, jarvis_aide, jarvis_stop... |
| **launcher** | 12 | launch_pipeline_10, launch_sniper_10, launch_sniper_breakout... |
| **media** | 7 | media_play_pause, media_next, media_previous... |
| **navigation** | 272 | ouvrir_chrome, ouvrir_comet, aller_sur_site... |
| **pipeline** | 246 | range_bureau, va_sur_mails_comet, mode_travail... |
| **saisie** | 4 | texte_majuscule, texte_minuscule, ouvrir_emojis... |
| **systeme** | 601 | verrouiller, eteindre, redemarrer... |
| **trading** | 19 | scanner_marche, detecter_breakout, pipeline_trading... |

<details>
<summary><strong>Liste complete des 812 commandes (cliquez pour derouler)</strong></summary>

### ACCESSIBILITE (10)

| Commande | Type | Description | Triggers |
|----------|------|-------------|----------|
| `taille_texte_grand` | ms_settings | Agrandir la taille du texte systeme | texte plus grand, agrandis le texte |
| `clavier_virtuel` | powershell | Ouvrir le clavier virtuel | clavier virtuel, ouvre le clavier virtuel |
| `filtre_couleur` | ms_settings | Activer/desactiver le filtre de couleur | filtre de couleur, active le filtre couleur |
| `sous_titres` | ms_settings | Parametres des sous-titres | sous-titres, parametres sous-titres |
| `contraste_eleve_toggle` | powershell | Activer/desactiver le contraste eleve | contraste eleve, high contrast |
| `sous_titres_live` | powershell | Activer les sous-titres en direct | sous titres en direct, live captions |
| `filtre_couleur_toggle` | powershell | Activer les filtres de couleur | filtre de couleur, color filter |
| `taille_curseur` | powershell | Changer la taille du curseur | agrandis le curseur, curseur plus grand |
| `narrateur_toggle` | powershell | Activer/desactiver le narrateur | active le narrateur, narrateur windows |
| `sticky_keys_toggle` | powershell | Activer/desactiver les touches remanentes | active les touches remanentes, desactive les touches remanentes |

### APP (23)

| Commande | Type | Description | Triggers |
|----------|------|-------------|----------|
| `ouvrir_vscode` | app_open | Ouvrir Visual Studio Code | ouvre vscode, ouvrir vscode |
| `ouvrir_terminal` | app_open | Ouvrir un terminal | ouvre le terminal, ouvrir le terminal |
| `ouvrir_lmstudio` | app_open | Ouvrir LM Studio | ouvre lm studio, lance lm studio |
| `ouvrir_discord` | app_open | Ouvrir Discord | ouvre discord, lance discord |
| `ouvrir_spotify` | app_open | Ouvrir Spotify | ouvre spotify, lance spotify |
| `ouvrir_task_manager` | app_open | Ouvrir le gestionnaire de taches | ouvre le gestionnaire de taches, task manager |
| `ouvrir_notepad` | app_open | Ouvrir Notepad | ouvre notepad, ouvre bloc notes |
| `ouvrir_calculatrice` | app_open | Ouvrir la calculatrice | ouvre la calculatrice, lance la calculatrice |
| `fermer_app` | jarvis_tool | Fermer une application | ferme {app}, fermer {app} |
| `ouvrir_app` | app_open | Ouvrir une application par nom | ouvre {app}, ouvrir {app} |
| `ouvrir_paint` | app_open | Ouvrir Paint | ouvre paint, lance paint |
| `ouvrir_wordpad` | app_open | Ouvrir WordPad | ouvre wordpad, lance wordpad |
| `ouvrir_snipping` | app_open | Ouvrir l'Outil Capture | ouvre l'outil capture, lance l'outil capture |
| `ouvrir_magnifier` | hotkey | Ouvrir la loupe Windows | ouvre la loupe windows, loupe windows |
| `fermer_loupe` | hotkey | Fermer la loupe Windows | ferme la loupe, desactive la loupe |
| `ouvrir_obs` | app_open | Ouvrir OBS Studio | ouvre obs, lance obs |
| `ouvrir_vlc` | app_open | Ouvrir VLC Media Player | ouvre vlc, lance vlc |
| `ouvrir_7zip` | app_open | Ouvrir 7-Zip | ouvre 7zip, lance 7zip |
| `store_ouvrir` | powershell | Ouvrir le Microsoft Store | ouvre le store, microsoft store |
| `store_updates` | powershell | Verifier les mises a jour du Store | mises a jour store, store updates |
| `ouvrir_phone_link` | powershell | Ouvrir Phone Link (liaison telephone) | ouvre phone link, liaison telephone |
| `terminal_settings` | powershell | Ouvrir les parametres Windows Terminal | parametres du terminal, reglages terminal |
| `copilot_lancer` | hotkey | Lancer Windows Copilot | lance copilot, ouvre copilot |

### CLIPBOARD (13)

| Commande | Type | Description | Triggers |
|----------|------|-------------|----------|
| `copier` | hotkey | Copier la selection | copie, copier |
| `coller` | hotkey | Coller le contenu | colle, coller |
| `couper` | hotkey | Couper la selection | coupe, couper |
| `tout_selectionner` | hotkey | Selectionner tout | selectionne tout, tout selectionner |
| `annuler` | hotkey | Annuler la derniere action | annule, annuler |
| `ecrire_texte` | jarvis_tool | Ecrire du texte au clavier | ecris {texte}, tape {texte} |
| `sauvegarder` | hotkey | Sauvegarder le fichier actif | sauvegarde, enregistre |
| `refaire` | hotkey | Refaire la derniere action annulee | refais, redo |
| `recherche_page` | hotkey | Rechercher dans la page | recherche dans la page, cherche dans la page |
| `lire_presse_papier` | jarvis_tool | Lire le contenu du presse-papier | lis le presse-papier, qu'est-ce qui est copie |
| `historique_clipboard` | hotkey | Historique du presse-papier | historique du presse-papier, clipboard history |
| `clipboard_historique` | hotkey | Ouvrir l'historique du presse-papier | historique presse papier, clipboard history |
| `coller_sans_format` | hotkey | Coller sans mise en forme | colle sans format, coller sans mise en forme |

### DEV (218)

| Commande | Type | Description | Triggers |
|----------|------|-------------|----------|
| `docker_ps` | powershell | Lister les conteneurs Docker | liste les conteneurs, docker ps |
| `docker_images` | powershell | Lister les images Docker | images docker, docker images |
| `docker_stop_all` | powershell | Arreter tous les conteneurs Docker | arrete tous les conteneurs, docker stop all |
| `git_status` | powershell | Git status du projet courant | git status, statut git |
| `git_log` | powershell | Git log recent | git log, historique git |
| `git_pull` | powershell | Git pull origin main | git pull, tire les changements |
| `git_push` | powershell | Git push origin main | git push, pousse les commits |
| `pip_list` | powershell | Lister les packages Python installes | pip list, packages python |
| `python_version` | powershell | Version Python et uv | version python, quelle version python |
| `ouvrir_n8n` | browser | Ouvrir n8n dans le navigateur | ouvre n8n, lance n8n |
| `lm_studio_restart` | powershell | Relancer LM Studio | relance lm studio, redemarre lm studio |
| `ouvrir_jupyter` | browser | Ouvrir Jupyter dans le navigateur | ouvre jupyter, lance jupyter |
| `wsl_lancer` | powershell | Lancer WSL (Windows Subsystem for Linux) | lance wsl, ouvre wsl |
| `wsl_liste` | powershell | Lister les distributions WSL installees | liste les distributions wsl, wsl liste |
| `wsl_shutdown` | powershell | Arreter toutes les distributions WSL | arrete wsl, stoppe wsl |
| `git_branches` | powershell | Lister les branches git | branches git, quelles branches |
| `git_diff` | powershell | Voir les modifications non commitees | git diff, modifications en cours |
| `git_stash` | powershell | Sauvegarder les modifications en stash | git stash, stash les changements |
| `git_stash_pop` | powershell | Restaurer les modifications du stash | git stash pop, restaure le stash |
| `git_last_commit` | powershell | Voir le dernier commit en detail | dernier commit, last commit |
| `git_count` | powershell | Compter les commits du projet | combien de commits, nombre de commits |
| `node_version` | powershell | Version de Node.js | version node, quelle version node |
| `npm_list_global` | powershell | Packages NPM globaux | packages npm globaux, npm global |
| `ollama_restart` | powershell | Redemarrer Ollama | redemarre ollama, restart ollama |
| `ollama_pull` | powershell | Telecharger un modele Ollama | telecharge le modele {model}, ollama pull {model} |
| `ollama_list` | powershell | Lister les modeles Ollama installes | liste les modeles ollama, modeles ollama installes |
| `ollama_remove` | powershell | Supprimer un modele Ollama | supprime le modele {model}, ollama rm {model} |
| `lm_studio_models` | powershell | Modeles charges dans LM Studio (M1, M2, M3) | modeles lm studio, quels modeles lm studio |
| `uv_sync` | powershell | Synchroniser les dependances uv | uv sync, synchronise les dependances |
| `python_test` | powershell | Lancer les tests Python du projet | lance les tests, run tests |
| `python_lint` | powershell | Verifier le code avec ruff | lint le code, ruff check |
| `docker_logs` | powershell | Voir les logs d'un conteneur Docker | logs docker de {container}, docker logs {container} |
| `docker_restart` | powershell | Redemarrer un conteneur Docker | redemarre le conteneur {container}, docker restart {container} |
| `docker_prune` | powershell | Nettoyer les ressources Docker inutilisees | nettoie docker, docker prune |
| `docker_stats` | powershell | Statistiques des conteneurs Docker | stats docker, docker stats |
| `turbo_lines` | powershell | Compter les lignes de code du projet turbo | combien de lignes de code, lignes de code turbo |
| `turbo_size` | powershell | Taille totale du projet turbo | taille du projet turbo, poids du projet |
| `turbo_files` | powershell | Compter les fichiers du projet turbo | combien de fichiers turbo, nombre de fichiers |
| `lms_status` | powershell | Statut du serveur LM Studio local | statut lm studio, lm studio status |
| `lms_list_loaded` | powershell | Modeles actuellement charges dans LM Studio local | modeles charges locaux, lms loaded |
| `lms_load_model` | powershell | Charger un modele dans LM Studio local | charge le modele {model}, lms load {model} |
| `lms_unload_model` | powershell | Decharger un modele de LM Studio local | decharge le modele {model}, lms unload {model} |
| `lms_list_available` | powershell | Lister les modeles disponibles sur le disque | modeles disponibles lm studio, lms list |
| `git_status_turbo` | powershell | Statut git du projet turbo | git status, statut git |
| `git_log_short` | powershell | Derniers 10 commits (resume) | historique git, git log |
| `git_remote_info` | powershell | Informations sur le remote git | remote git, git remote |
| `ouvrir_telegram` | app_open | Ouvrir Telegram Desktop | ouvre telegram, lance telegram |
| `ouvrir_whatsapp` | app_open | Ouvrir WhatsApp Desktop | ouvre whatsapp, lance whatsapp |
| `ouvrir_slack` | app_open | Ouvrir Slack Desktop | ouvre slack, lance slack |
| `ouvrir_teams` | app_open | Ouvrir Microsoft Teams | ouvre teams, lance teams |
| `ouvrir_zoom` | app_open | Ouvrir Zoom | ouvre zoom, lance zoom |
| `bun_version` | powershell | Version de Bun | version bun, quelle version bun |
| `deno_version` | powershell | Version de Deno | version deno, quelle version deno |
| `rust_version` | powershell | Version de Rust/Cargo | version rust, quelle version rust |
| `python_uv_version` | powershell | Version de Python et uv | version python, quelle version python |
| `turbo_recent_changes` | powershell | Fichiers modifies recemment dans turbo | fichiers recents turbo, modifications recentes |
| `turbo_todo` | powershell | Lister les TODO dans le code turbo | liste les todo, todo dans le code |
| `git_blame_file` | powershell | Git blame sur un fichier | git blame de {fichier}, blame {fichier} |
| `git_clean_branches` | powershell | Nettoyer les branches git mergees | nettoie les branches, clean branches |
| `git_contributors` | powershell | Lister les contributeurs du projet | contributeurs git, qui a contribue |
| `git_file_history` | powershell | Historique d'un fichier | historique du fichier {fichier}, git log de {fichier} |
| `git_undo_last` | powershell | Annuler le dernier commit (soft reset) | annule le dernier commit, undo last commit |
| `npm_audit` | powershell | Audit de securite NPM | npm audit, audit securite npm |
| `npm_outdated` | powershell | Packages NPM obsoletes | npm outdated, packages npm a jour |
| `pip_outdated` | powershell | Packages Python obsoletes | pip outdated, packages python a mettre a jour |
| `python_repl` | powershell | Lancer un REPL Python | lance python, python repl |
| `kill_port` | powershell | Tuer le processus sur un port specifique | tue le port {port}, kill port {port} |
| `qui_ecoute_port` | powershell | Quel processus ecoute sur un port | qui ecoute sur le port {port}, quel process sur {port} |
| `ports_dev_status` | powershell | Statut des ports dev courants (3000, 5173, 8080, 8000, 9742) | statut des ports dev, ports dev |
| `ollama_vram_detail` | powershell | Detail VRAM utilisee par chaque modele Ollama | vram ollama detail, ollama vram |
| `ollama_stop_all` | powershell | Decharger tous les modeles Ollama de la VRAM | decharge tous les modeles ollama, ollama stop all |
| `git_reflog` | powershell | Voir le reflog git (historique complet) | git reflog, reflog |
| `git_tag_list` | powershell | Lister les tags git | tags git, git tags |
| `git_search_commits` | powershell | Rechercher dans les messages de commit | cherche dans les commits {requete}, git search {requete} |
| `git_repo_size` | powershell | Taille du depot git | taille du repo git, poids du git |
| `git_stash_list` | powershell | Lister les stash git | liste les stash, git stash list |
| `git_diff_staged` | powershell | Voir les modifications stagees (pret a commit) | diff staged, git diff staged |
| `docker_images_list` | powershell | Lister les images Docker locales | images docker, docker images |
| `docker_volumes` | powershell | Lister les volumes Docker | volumes docker, docker volumes |
| `docker_networks` | powershell | Lister les reseaux Docker | reseaux docker, docker networks |
| `docker_disk_usage` | powershell | Espace disque utilise par Docker | espace docker, docker disk usage |
| `winget_search` | powershell | Rechercher un package via winget | winget search {requete}, cherche {requete} sur winget |
| `winget_list_installed` | powershell | Lister les apps installees via winget | winget list, apps winget |
| `winget_upgrade_all` | powershell | Mettre a jour toutes les apps via winget | winget upgrade all, mets a jour tout winget |
| `code_extensions_list` | powershell | Lister les extensions VSCode installees | extensions vscode, liste les extensions |
| `code_install_ext` | powershell | Installer une extension VSCode | installe l'extension {ext}, vscode install {ext} |
| `ssh_keys_list` | powershell | Lister les cles SSH | cles ssh, ssh keys |
| `npm_cache_clean` | powershell | Nettoyer le cache NPM | nettoie le cache npm, npm cache clean |
| `uv_pip_tree` | powershell | Arbre de dependances Python du projet | arbre de dependances, pip tree |
| `pip_show_package` | powershell | Details d'un package Python installe | details du package {package}, pip show {package} |
| `turbo_imports` | powershell | Imports utilises dans le projet turbo | imports du projet, quels imports |
| `python_format_check` | powershell | Verifier le formatage Python avec ruff format | verifie le formatage, ruff format check |
| `python_type_check` | powershell | Verifier les types Python (pyright/mypy) | verifie les types, type check |
| `curl_test_endpoint` | powershell | Tester un endpoint HTTP | teste l'endpoint {url}, curl {url} |
| `n8n_workflows_list` | powershell | Lister les workflows n8n actifs | workflows n8n, liste les workflows |
| `git_worktree_list` | powershell | Lister les worktrees git | worktrees git, git worktrees |
| `git_submodule_status` | powershell | Statut des submodules git | submodules git, git submodules |
| `git_cherry_unpicked` | powershell | Commits non cherry-picked entre branches | git cherry, commits non picks |
| `git_branch_age` | powershell | Age de chaque branche git | age des branches, branches vieilles |
| `git_commit_stats` | powershell | Statistiques de commits (par jour/semaine) | stats commits, frequence commits |
| `docker_compose_up` | powershell | Docker compose up (demarrer les services) | docker compose up, lance les conteneurs |
| `docker_compose_down` | powershell | Docker compose down (arreter les services) | docker compose down, arrete les conteneurs |
| `docker_compose_logs` | powershell | Voir les logs Docker Compose | logs docker compose, compose logs |
| `docker_compose_ps` | powershell | Statut des services Docker Compose | services docker compose, compose ps |
| `uv_cache_clean` | powershell | Nettoyer le cache uv | nettoie le cache uv, uv cache clean |
| `uv_pip_install` | powershell | Installer un package Python via uv | installe {package} python, uv pip install {package} |
| `turbo_test_file` | powershell | Lancer un fichier de test specifique | teste le fichier {fichier}, pytest {fichier} |
| `turbo_coverage` | powershell | Couverture de tests du projet turbo | coverage turbo, couverture de tests |
| `process_tree` | powershell | Arbre des processus actifs | arbre des processus, process tree |
| `openssl_version` | powershell | Version d'OpenSSL | version openssl, openssl version |
| `git_version` | powershell | Version de Git | version git, git version |
| `cuda_version` | powershell | Version de CUDA installee | version cuda, cuda version |
| `powershell_version` | powershell | Version de PowerShell | version powershell, powershell version |
| `dotnet_version` | powershell | Versions de .NET installees | version dotnet, dotnet version |
| `turbo_skills_count` | powershell | Compter les skills et commandes vocales du projet | combien de skills, nombre de commandes vocales |
| `turbo_find_duplicates` | powershell | Detecter les commandes vocales en doublon | cherche les doublons, duplicates commands |
| `turbo_generate_docs` | powershell | Regenerer la documentation des commandes vocales | regenere la doc, update la doc vocale |
| `turbo_generate_readme` | powershell | Regenerer la section commandes du README | regenere le readme, update le readme |
| `check_all_versions` | powershell | Toutes les versions d'outils installes | toutes les versions, all versions |
| `env_check_paths` | powershell | Verifier que les outils essentiels sont dans le PATH | check le path, outils disponibles |
| `disk_space_summary` | powershell | Resume espace disque pour le dev | espace disque dev, combien de place pour coder |
| `git_today` | powershell | Commits d'aujourd'hui | commits du jour, git today |
| `git_this_week` | powershell | Commits de cette semaine | commits de la semaine, git this week |
| `git_push_turbo` | powershell | Pusher les commits du projet turbo | push turbo, git push |
| `git_pull_turbo` | powershell | Puller les commits du projet turbo | pull turbo, git pull |
| `wt_split_horizontal` | powershell | Diviser le terminal Windows horizontalement | split terminal horizontal, divise le terminal |
| `wt_split_vertical` | powershell | Diviser le terminal Windows verticalement | split terminal vertical, divise le terminal vertical |
| `wt_new_tab` | powershell | Nouvel onglet dans Windows Terminal | nouvel onglet terminal, new tab terminal |
| `wt_new_tab_powershell` | powershell | Nouvel onglet PowerShell dans Windows Terminal | terminal powershell, onglet powershell |
| `wt_new_tab_cmd` | powershell | Nouvel onglet CMD dans Windows Terminal | terminal cmd, onglet cmd |
| `wt_quake_mode` | hotkey | Ouvrir le terminal en mode quake (dropdown) | terminal quake, quake mode |
| `vscode_zen_mode` | hotkey | Activer le mode zen dans VSCode | mode zen vscode, zen mode |
| `vscode_format_document` | hotkey | Formater le document dans VSCode | formate le document, format code |
| `vscode_word_wrap` | hotkey | Basculer le retour a la ligne dans VSCode | word wrap vscode, retour a la ligne |
| `vscode_minimap` | powershell | Afficher/masquer la minimap VSCode | minimap vscode, toggle minimap |
| `vscode_multi_cursor_down` | hotkey | Ajouter un curseur en dessous dans VSCode | multi curseur bas, curseur en dessous |
| `vscode_multi_cursor_up` | hotkey | Ajouter un curseur au dessus dans VSCode | multi curseur haut, curseur au dessus |
| `vscode_rename_symbol` | hotkey | Renommer un symbole dans VSCode (refactoring) | renomme le symbole, rename symbol |
| `vscode_go_to_definition` | hotkey | Aller a la definition dans VSCode | va a la definition, go to definition |
| `vscode_peek_definition` | hotkey | Apercu de la definition (peek) dans VSCode | peek definition, apercu definition |
| `vscode_find_all_references` | hotkey | Trouver toutes les references dans VSCode | toutes les references, find references |
| `vscode_fold_all` | hotkey | Plier tout le code dans VSCode | plie tout le code, fold all |
| `vscode_unfold_all` | hotkey | Deplier tout le code dans VSCode | deplie tout le code, unfold all |
| `vscode_toggle_comment` | hotkey | Commenter/decommenter la ligne ou selection | commente, decommente |
| `vscode_problems_panel` | hotkey | Ouvrir le panneau des problemes VSCode | panneau problemes, errors vscode |
| `docker_ps_all` | powershell | Lister tous les conteneurs Docker | tous les conteneurs, docker ps all |
| `docker_logs_last` | powershell | Logs du dernier conteneur lance | logs docker, docker logs |
| `pytest_turbo` | powershell | Lancer les tests pytest du projet turbo | lance les tests, pytest |
| `pytest_last_failed` | powershell | Relancer les tests qui ont echoue | relance les tests echoues, pytest lf |
| `ruff_check` | powershell | Lancer ruff (linter Python) sur turbo | ruff check, lint python |
| `ruff_format` | powershell | Formater le code Python avec ruff format | ruff format, formate le python |
| `mypy_check` | powershell | Verifier les types Python avec mypy | mypy check, verifie les types |
| `pip_list_turbo` | powershell | Lister les packages Python du projet turbo | packages python, pip list |
| `count_lines_python` | powershell | Compter les lignes de code Python du projet | combien de lignes de code, lignes python |
| `sqlite_jarvis` | powershell | Ouvrir la base JARVIS en SQLite | ouvre la base jarvis, sqlite jarvis |
| `sqlite_etoile` | powershell | Explorer la base etoile.db | ouvre etoile db, base etoile |
| `sqlite_tables` | powershell | Lister les tables d'une base SQLite | tables sqlite {db}, quelles tables dans {db} |
| `redis_ping` | powershell | Ping Redis local | ping redis, redis ok |
| `redis_info` | powershell | Informations Redis (memoire, clients) | info redis, redis info |
| `turbo_file_count` | powershell | Nombre de fichiers par type dans turbo | combien de fichiers turbo, types de fichiers |
| `turbo_todo_scan` | powershell | Scanner les TODO/FIXME/HACK dans le code | trouve les todo, scan todo |
| `turbo_import_graph` | powershell | Voir les imports entre modules turbo | graph des imports, imports turbo |
| `git_cherry_pick` | powershell | Cherry-pick un commit specifique | cherry pick {hash}, git cherry pick {hash} |
| `git_tags` | powershell | Lister les tags git | tags git, quels tags |
| `git_branch_create` | powershell | Creer une nouvelle branche git | cree une branche {branch}, nouvelle branche {branch} |
| `git_branch_delete` | powershell | Supprimer une branche git locale | supprime la branche {branch}, delete branch {branch} |
| `git_branch_switch` | powershell | Changer de branche git | va sur la branche {branch}, switch {branch} |
| `git_merge_branch` | powershell | Merger une branche dans la branche actuelle | merge {branch}, fusionne {branch} |
| `ssh_keygen` | powershell | Generer une nouvelle cle SSH | genere une cle ssh, ssh keygen |
| `ssh_pubkey` | powershell | Afficher la cle publique SSH | montre ma cle ssh, cle publique ssh |
| `ssh_known_hosts` | powershell | Voir les hosts SSH connus | hosts ssh connus, known hosts |
| `cargo_build` | powershell | Compiler un projet Rust (cargo build) | cargo build, compile en rust |
| `cargo_test` | powershell | Lancer les tests Rust (cargo test) | cargo test, tests rust |
| `cargo_clippy` | powershell | Lancer le linter Rust (clippy) | cargo clippy, lint rust |
| `npm_run_dev` | powershell | Lancer npm run dev | npm run dev, lance le dev node |
| `npm_run_build` | powershell | Lancer npm run build | npm run build, build node |
| `python_profile_turbo` | powershell | Profiler le startup de JARVIS | profile jarvis, temps de demarrage |
| `python_memory_usage` | powershell | Mesurer la memoire Python du projet | memoire python, python memory |
| `uv_add_package` | powershell | Ajouter un package Python avec uv | uv add {package}, installe {package} |
| `uv_remove_package` | powershell | Supprimer un package Python avec uv | uv remove {package}, desinstalle {package} |
| `uv_lock` | powershell | Regenerer le lockfile uv | uv lock, lock les deps |
| `port_in_use` | powershell | Trouver quel processus utilise un port | qui utilise le port {port}, port {port} occupe |
| `env_var_get` | powershell | Lire une variable d'environnement | variable {var}, env {var} |
| `tree_turbo` | powershell | Arborescence du projet turbo (2 niveaux) | arborescence turbo, tree turbo |
| `gh_create_issue` | powershell | Creer une issue GitHub | cree une issue {titre}, nouvelle issue {titre} |
| `gh_list_issues` | powershell | Lister les issues GitHub ouvertes | liste les issues, issues ouvertes |
| `gh_list_prs` | powershell | Lister les pull requests GitHub | liste les pr, pull requests |
| `gh_view_pr` | powershell | Voir les details d'une PR | montre la pr {num}, detail pr {num} |
| `gh_pr_checks` | powershell | Voir les checks d'une PR | checks de la pr {num}, status pr {num} |
| `gh_repo_view` | powershell | Voir les infos du repo GitHub courant | info du repo, github repo info |
| `gh_workflow_list` | powershell | Lister les workflows GitHub Actions | workflows github, github actions |
| `gh_release_list` | powershell | Lister les releases GitHub | releases github, liste les releases |
| `go_build` | powershell | Compiler un projet Go | go build, compile en go |
| `go_test` | powershell | Lancer les tests Go | go test, tests go |
| `go_fmt` | powershell | Formater le code Go | go fmt, formate le go |
| `go_mod_tidy` | powershell | Nettoyer les dependances Go | go mod tidy, nettoie les deps go |
| `venv_create` | powershell | Creer un environnement virtuel Python | cree un venv, nouveau virtualenv |
| `venv_activate` | powershell | Activer le virtualenv courant | active le venv, activate venv |
| `conda_list_envs` | powershell | Lister les environnements Conda | conda envs, liste les envs conda |
| `conda_install_pkg` | powershell | Installer un package Conda | conda install {package}, installe avec conda {package} |
| `curl_get` | powershell | Faire un GET sur une URL | curl get {url}, requete get {url} |
| `curl_post_json` | powershell | Faire un POST JSON sur une URL | curl post {url}, post json {url} |
| `api_health_check` | powershell | Verifier si une API repond (ping HTTP) | ping api {url}, api en ligne {url} |
| `api_response_time` | powershell | Mesurer le temps de reponse d'une URL | temps de reponse {url}, latence de {url} |
| `lint_ruff_check` | powershell | Linter Python avec Ruff | ruff check, lint python |
| `lint_ruff_fix` | powershell | Auto-fixer les erreurs Ruff | ruff fix, fixe le lint |
| `format_black` | powershell | Formater Python avec Black | black format, formate avec black |
| `lint_mypy` | powershell | Verifier les types Python avec mypy | mypy check, verifie les types |
| `lint_eslint` | powershell | Linter JavaScript avec ESLint | eslint, lint javascript |
| `format_prettier` | powershell | Formater JS/TS avec Prettier | prettier format, formate avec prettier |
| `logs_turbo` | powershell | Voir les derniers logs JARVIS | logs jarvis, dernieres logs |
| `logs_windows_errors` | powershell | Voir les erreurs recentes Windows | erreurs windows, logs erreurs systeme |
| `logs_clear_turbo` | powershell | Vider les logs JARVIS | vide les logs, efface les logs |
| `logs_search` | powershell | Chercher dans les logs JARVIS | cherche dans les logs {pattern}, grep les logs {pattern} |
| `netstat_listen` | powershell | Voir les ports en ecoute | ports en ecoute, quels ports ouverts |
| `whois_domain` | powershell | Whois d'un domaine | whois {domaine}, info domaine {domaine} |
| `ssl_check` | powershell | Verifier le certificat SSL d'un site | check ssl {domaine}, certificat ssl {domaine} |
| `dns_lookup` | powershell | Resoudre un domaine (DNS lookup complet) | dns {domaine}, resoudre {domaine} |

### FENETRE (13)

| Commande | Type | Description | Triggers |
|----------|------|-------------|----------|
| `minimiser_tout` | hotkey | Minimiser toutes les fenetres | minimise tout, montre le bureau |
| `alt_tab` | hotkey | Basculer entre les fenetres | change de fenetre, fenetre suivante |
| `fermer_fenetre` | hotkey | Fermer la fenetre active | ferme la fenetre, ferme ca |
| `maximiser_fenetre` | hotkey | Maximiser la fenetre active | maximise, plein ecran |
| `minimiser_fenetre` | hotkey | Minimiser la fenetre active | minimise, reduis la fenetre |
| `fenetre_gauche` | hotkey | Fenetre a gauche | fenetre a gauche, mets a gauche |
| `fenetre_droite` | hotkey | Fenetre a droite | fenetre a droite, mets a droite |
| `focus_fenetre` | jarvis_tool | Mettre le focus sur une fenetre | focus sur {titre}, va sur la fenetre {titre} |
| `liste_fenetres` | jarvis_tool | Lister les fenetres ouvertes | quelles fenetres sont ouvertes, liste les fenetres |
| `fenetre_haut_gauche` | powershell | Fenetre en haut a gauche | fenetre en haut a gauche, snap haut gauche |
| `fenetre_haut_droite` | powershell | Fenetre en haut a droite | fenetre en haut a droite, snap haut droite |
| `fenetre_bas_gauche` | powershell | Fenetre en bas a gauche | fenetre en bas a gauche, snap bas gauche |
| `fenetre_bas_droite` | powershell | Fenetre en bas a droite | fenetre en bas a droite, snap bas droite |

### FICHIERS (47)

| Commande | Type | Description | Triggers |
|----------|------|-------------|----------|
| `ouvrir_documents` | powershell | Ouvrir le dossier Documents | ouvre mes documents, ouvrir mes documents |
| `ouvrir_bureau` | powershell | Ouvrir le dossier Bureau | ouvre le bureau, ouvrir le bureau |
| `ouvrir_dossier` | powershell | Ouvrir un dossier specifique | ouvre le dossier {dossier}, ouvrir le dossier {dossier} |
| `ouvrir_telechargements` | powershell | Ouvrir Telechargements | ouvre les telechargements, ouvre mes telechargements |
| `ouvrir_images` | powershell | Ouvrir le dossier Images | ouvre mes images, ouvre mes photos |
| `ouvrir_musique` | powershell | Ouvrir le dossier Musique | ouvre ma musique, ouvre le dossier musique |
| `ouvrir_projets` | powershell | Ouvrir le dossier projets | ouvre mes projets, va dans les projets |
| `ouvrir_explorateur` | hotkey | Ouvrir l'explorateur de fichiers | ouvre l'explorateur, ouvre l'explorateur de fichiers |
| `lister_dossier` | jarvis_tool | Lister le contenu d'un dossier | que contient {dossier}, liste le dossier {dossier} |
| `creer_dossier` | jarvis_tool | Creer un nouveau dossier | cree un dossier {nom}, nouveau dossier {nom} |
| `chercher_fichier` | jarvis_tool | Chercher un fichier | cherche le fichier {nom}, trouve le fichier {nom} |
| `ouvrir_recents` | powershell | Ouvrir les fichiers recents | fichiers recents, ouvre les recents |
| `ouvrir_temp` | powershell | Ouvrir le dossier temporaire | ouvre le dossier temp, fichiers temporaires |
| `ouvrir_appdata` | powershell | Ouvrir le dossier AppData | ouvre appdata, dossier appdata |
| `espace_dossier` | powershell | Taille d'un dossier | taille du dossier {dossier}, combien pese {dossier} |
| `nombre_fichiers` | powershell | Compter les fichiers dans un dossier | combien de fichiers dans {dossier}, nombre de fichiers {dossier} |
| `compresser_dossier` | powershell | Compresser un dossier en ZIP | compresse {dossier}, zip {dossier} |
| `decompresser_zip` | powershell | Decompresser un fichier ZIP | decompresse {fichier}, unzip {fichier} |
| `hash_fichier` | powershell | Calculer le hash SHA256 d'un fichier | hash de {fichier}, sha256 de {fichier} |
| `chercher_contenu` | powershell | Chercher du texte dans les fichiers | cherche {texte} dans les fichiers, grep {texte} |
| `derniers_fichiers` | powershell | Derniers fichiers modifies | derniers fichiers modifies, fichiers recents |
| `doublons_fichiers` | powershell | Trouver les fichiers en double | fichiers en double, doublons |
| `gros_fichiers` | powershell | Trouver les plus gros fichiers | plus gros fichiers, fichiers les plus lourds |
| `fichiers_type` | powershell | Lister les fichiers d'un type | fichiers {ext}, tous les {ext} |
| `renommer_masse` | powershell | Renommer des fichiers en masse | renomme les fichiers {ancien} en {nouveau}, remplace {ancien} par {nouveau} dans les noms |
| `dossiers_vides` | powershell | Trouver les dossiers vides | dossiers vides, repertoires vides |
| `proprietes_fichier` | powershell | Proprietes detaillees d'un fichier | proprietes de {fichier}, details de {fichier} |
| `copier_fichier` | powershell | Copier un fichier vers un dossier | copie {source} dans {destination}, copie {source} vers {destination} |
| `deplacer_fichier` | powershell | Deplacer un fichier | deplace {source} dans {destination}, deplace {source} vers {destination} |
| `explorer_nouvel_onglet` | powershell | Nouvel onglet dans l'Explorateur | nouvel onglet explorateur, onglet explorateur |
| `dossier_captures` | powershell | Ouvrir le dossier captures d'ecran | dossier captures, ouvre les captures |
| `taille_dossiers_bureau` | powershell | Taille de chaque dossier dans F:\BUREAU | taille des projets, poids des dossiers bureau |
| `compresser_fichier` | powershell | Compresser un dossier en ZIP | compresse en zip, zip le dossier |
| `decompresser_fichier` | powershell | Decompresser un fichier ZIP | decompresse le zip, unzip |
| `compresser_turbo` | powershell | Compresser le projet turbo en ZIP (sans .git ni venv) | zip turbo, archive turbo |
| `vider_dossier_temp` | powershell | Supprimer les fichiers temporaires | vide le temp, nettoie les temporaires |
| `lister_fichiers_recents` | powershell | Lister les 20 fichiers les plus recents sur le bureau | fichiers recents, derniers fichiers |
| `chercher_gros_fichiers` | powershell | Trouver les fichiers > 100 MB sur F: | gros fichiers partout, fichiers enormes |
| `doublons_bureau` | powershell | Detecter les doublons potentiels par nom dans F:\BUREAU | doublons bureau, fichiers en double |
| `taille_telechargements` | powershell | Taille du dossier Telechargements | taille telechargements, poids downloads |
| `vider_telechargements` | powershell | Vider le dossier Telechargements (fichiers > 30 jours) | vide les telechargements, nettoie les downloads |
| `lister_telechargements` | powershell | Derniers fichiers telecharges | derniers telechargements, quoi de telecharge |
| `ouvrir_telechargements` | powershell | Ouvrir le dossier Telechargements | ouvre les telechargements, dossier downloads |
| `ouvrir_documents` | powershell | Ouvrir le dossier Documents | ouvre les documents, dossier documents |
| `ouvrir_bureau_dossier` | powershell | Ouvrir F:\BUREAU dans l'explorateur | ouvre le bureau, dossier bureau |
| `fichier_recent_modifie` | powershell | Trouver le dernier fichier modifie partout | dernier fichier modifie, quoi vient de changer |
| `compter_fichiers_type` | powershell | Compter les fichiers par extension dans un dossier | compte les fichiers par type, extensions dans {path} |

### JARVIS (12)

| Commande | Type | Description | Triggers |
|----------|------|-------------|----------|
| `historique_commandes` | powershell | Voir l'historique des commandes JARVIS | historique des commandes, quelles commandes j'ai utilise |
| `jarvis_aide` | list_commands | Afficher l'aide JARVIS | aide, help |
| `jarvis_stop` | exit | Arreter JARVIS | jarvis stop, jarvis arrete |
| `jarvis_repete` | jarvis_repeat | Repeter la derniere reponse | repete, redis |
| `jarvis_scripts` | jarvis_tool | Lister les scripts disponibles | quels scripts sont disponibles, liste les scripts |
| `jarvis_projets` | jarvis_tool | Lister les projets indexes | quels projets existent, liste les projets |
| `jarvis_notification` | jarvis_tool | Envoyer une notification | notifie {message}, notification {message} |
| `jarvis_skills` | list_commands | Lister les skills/pipelines appris | quels skills existent, liste les skills |
| `jarvis_suggestions` | list_commands | Suggestions d'actions | que me suggeres tu, suggestions |
| `jarvis_brain_status` | jarvis_tool | Etat du cerveau JARVIS | etat du cerveau, brain status |
| `jarvis_brain_learn` | jarvis_tool | Apprendre de nouveaux patterns | apprends, brain learn |
| `jarvis_brain_suggest` | jarvis_tool | Demander une suggestion de skill a l'IA | suggere un skill, brain suggest |

### LAUNCHER (12)

| Commande | Type | Description | Triggers |
|----------|------|-------------|----------|
| `launch_pipeline_10` | script | Lancer le Pipeline 10 Cycles | lance le pipeline 10 cycles, pipeline 10 cycles |
| `launch_sniper_10` | script | Lancer le Sniper 10 Cycles | lance le sniper 10 cycles, sniper 10 cycles |
| `launch_sniper_breakout` | script | Lancer le Sniper Breakout | lance sniper breakout, sniper breakout |
| `launch_trident` | script | Lancer Trident Execute (dry run) | lance trident, trident execute |
| `launch_hyper_scan` | script | Lancer l'Hyper Scan V2 | lance hyper scan, hyper scan v2 |
| `launch_monitor_river` | script | Lancer le Monitor RIVER Scalp | lance river, monitor river |
| `launch_command_center` | script | Ouvrir le JARVIS Command Center (GUI) | ouvre le command center, command center |
| `launch_electron_app` | script | Ouvrir JARVIS Electron App | lance electron, jarvis electron |
| `launch_widget` | script | Ouvrir le Widget JARVIS | lance le widget jarvis, jarvis widget |
| `launch_disk_cleaner` | script | Lancer le nettoyeur de disque | nettoie le disque, disk cleaner |
| `launch_master_node` | script | Lancer le Master Interaction Node | lance le master node, master interaction |
| `launch_fs_agent` | script | Lancer l'agent fichiers JARVIS | lance l'agent fichiers, fs agent |

### MEDIA (7)

| Commande | Type | Description | Triggers |
|----------|------|-------------|----------|
| `media_play_pause` | hotkey | Play/Pause media | play, pause |
| `media_next` | hotkey | Piste suivante | suivant, piste suivante |
| `media_previous` | hotkey | Piste precedente | precedent, piste precedente |
| `volume_haut` | hotkey | Augmenter le volume | monte le volume, augmente le volume |
| `volume_bas` | hotkey | Baisser le volume | baisse le volume, diminue le volume |
| `muet` | hotkey | Couper/activer le son | coupe le son, mute |
| `volume_precis` | powershell | Mettre le volume a un niveau precis | mets le volume a {niveau}, volume a {niveau} |

### NAVIGATION (272)

| Commande | Type | Description | Triggers |
|----------|------|-------------|----------|
| `ouvrir_chrome` | app_open | Ouvrir Google Chrome | ouvre chrome, ouvrir chrome |
| `ouvrir_comet` | app_open | Ouvrir Comet Browser | ouvre comet, ouvrir comet |
| `aller_sur_site` | browser | Naviguer vers un site web | va sur {site}, ouvre {site} |
| `chercher_google` | browser | Rechercher sur Google | cherche {requete}, recherche {requete} |
| `chercher_youtube` | browser | Rechercher sur YouTube | cherche sur youtube {requete}, youtube {requete} |
| `ouvrir_gmail` | browser | Ouvrir Gmail | ouvre gmail, ouvrir gmail |
| `ouvrir_youtube` | browser | Ouvrir YouTube | ouvre youtube, va sur youtube |
| `ouvrir_github` | browser | Ouvrir GitHub | ouvre github, va sur github |
| `ouvrir_tradingview` | browser | Ouvrir TradingView | ouvre tradingview, va sur tradingview |
| `ouvrir_mexc` | browser | Ouvrir MEXC | ouvre mexc, va sur mexc |
| `nouvel_onglet` | hotkey | Ouvrir un nouvel onglet | nouvel onglet, nouveau tab |
| `fermer_onglet` | hotkey | Fermer l'onglet actif | ferme l'onglet, ferme cet onglet |
| `mode_incognito` | powershell | Ouvrir Chrome en mode incognito | mode incognito, navigation privee |
| `historique_chrome` | hotkey | Ouvrir l'historique Chrome | historique chrome, ouvre l'historique |
| `favoris_chrome` | hotkey | Ouvrir les favoris Chrome | ouvre les favoris, favoris |
| `telecharger_chrome` | hotkey | Ouvrir les telechargements Chrome | telechargements chrome, ouvre les downloads |
| `nouvel_onglet` | hotkey | Ouvrir un nouvel onglet Chrome | nouvel onglet, ouvre un onglet |
| `onglet_precedent` | hotkey | Onglet precedent Chrome | onglet precedent, tab precedent |
| `onglet_suivant` | hotkey | Onglet suivant Chrome | onglet suivant, tab suivant |
| `rouvrir_onglet` | hotkey | Rouvrir le dernier onglet ferme | rouvre l'onglet, rouvrir onglet |
| `chrome_favoris` | hotkey | Ouvrir les favoris Chrome | ouvre les favoris, mes favoris |
| `chrome_telechargements` | hotkey | Ouvrir les telechargements Chrome | telechargements chrome, mes telechargements chrome |
| `chrome_plein_ecran` | hotkey | Chrome en plein ecran (F11) | plein ecran, chrome plein ecran |
| `chrome_zoom_plus` | hotkey | Zoom avant Chrome | zoom avant chrome, agrandir la page |
| `chrome_zoom_moins` | hotkey | Zoom arriere Chrome | zoom arriere chrome, reduire la page |
| `chrome_zoom_reset` | hotkey | Reinitialiser le zoom Chrome | zoom normal, zoom 100 |
| `meteo` | browser | Afficher la meteo | meteo, la meteo |
| `ouvrir_twitter` | browser | Ouvrir Twitter/X | ouvre twitter, va sur twitter |
| `ouvrir_reddit` | browser | Ouvrir Reddit | ouvre reddit, va sur reddit |
| `ouvrir_linkedin` | browser | Ouvrir LinkedIn | ouvre linkedin, va sur linkedin |
| `ouvrir_instagram` | browser | Ouvrir Instagram | ouvre instagram, va sur instagram |
| `ouvrir_tiktok` | browser | Ouvrir TikTok | ouvre tiktok, va sur tiktok |
| `ouvrir_twitch` | browser | Ouvrir Twitch | ouvre twitch, va sur twitch |
| `ouvrir_chatgpt` | browser | Ouvrir ChatGPT | ouvre chatgpt, va sur chatgpt |
| `ouvrir_claude` | browser | Ouvrir Claude AI | ouvre claude, va sur claude |
| `ouvrir_perplexity` | browser | Ouvrir Perplexity | ouvre perplexity, va sur perplexity |
| `ouvrir_huggingface` | browser | Ouvrir Hugging Face | ouvre hugging face, va sur hugging face |
| `ouvrir_wikipedia` | browser | Ouvrir Wikipedia | ouvre wikipedia, va sur wikipedia |
| `ouvrir_amazon` | browser | Ouvrir Amazon | ouvre amazon, va sur amazon |
| `ouvrir_leboncoin` | browser | Ouvrir Leboncoin | ouvre leboncoin, va sur leboncoin |
| `ouvrir_netflix` | browser | Ouvrir Netflix | ouvre netflix, va sur netflix |
| `ouvrir_spotify_web` | browser | Ouvrir Spotify Web Player | ouvre spotify web, spotify web |
| `ouvrir_disney_plus` | browser | Ouvrir Disney+ | ouvre disney plus, va sur disney plus |
| `ouvrir_stackoverflow` | browser | Ouvrir Stack Overflow | ouvre stackoverflow, va sur stackoverflow |
| `ouvrir_npmjs` | browser | Ouvrir NPM | ouvre npm, va sur npm |
| `ouvrir_pypi` | browser | Ouvrir PyPI | ouvre pypi, va sur pypi |
| `ouvrir_docker_hub` | browser | Ouvrir Docker Hub | ouvre docker hub, va sur docker hub |
| `ouvrir_google_drive` | browser | Ouvrir Google Drive | ouvre google drive, va sur google drive |
| `ouvrir_google_docs` | browser | Ouvrir Google Docs | ouvre google docs, va sur google docs |
| `ouvrir_google_sheets` | browser | Ouvrir Google Sheets | ouvre google sheets, va sur google sheets |
| `ouvrir_google_maps` | browser | Ouvrir Google Maps | ouvre google maps, va sur google maps |
| `ouvrir_google_calendar` | browser | Ouvrir Google Calendar | ouvre google calendar, ouvre l'agenda |
| `ouvrir_notion` | browser | Ouvrir Notion | ouvre notion, va sur notion |
| `chercher_images` | browser | Rechercher des images sur Google | cherche des images de {requete}, images de {requete} |
| `chercher_reddit` | browser | Rechercher sur Reddit | cherche sur reddit {requete}, reddit {requete} |
| `chercher_wikipedia` | browser | Rechercher sur Wikipedia | cherche sur wikipedia {requete}, wikipedia {requete} |
| `chercher_amazon` | browser | Rechercher sur Amazon | cherche sur amazon {requete}, amazon {requete} |
| `ouvrir_tradingview_web` | browser | Ouvrir TradingView | ouvre tradingview, va sur tradingview |
| `ouvrir_coingecko` | browser | Ouvrir CoinGecko | ouvre coingecko, va sur coingecko |
| `ouvrir_coinmarketcap` | browser | Ouvrir CoinMarketCap | ouvre coinmarketcap, va sur coinmarketcap |
| `ouvrir_mexc_exchange` | browser | Ouvrir MEXC Exchange | ouvre mexc, va sur mexc |
| `ouvrir_dexscreener` | browser | Ouvrir DexScreener | ouvre dexscreener, va sur dexscreener |
| `ouvrir_telegram_web` | browser | Ouvrir Telegram Web | ouvre telegram web, telegram web |
| `ouvrir_whatsapp_web` | browser | Ouvrir WhatsApp Web | ouvre whatsapp web, whatsapp web |
| `ouvrir_slack_web` | browser | Ouvrir Slack Web | ouvre slack web, slack web |
| `ouvrir_teams_web` | browser | Ouvrir Microsoft Teams Web | ouvre teams web, teams web |
| `ouvrir_youtube_music` | browser | Ouvrir YouTube Music | ouvre youtube music, youtube music |
| `ouvrir_prime_video` | browser | Ouvrir Amazon Prime Video | ouvre prime video, va sur prime video |
| `ouvrir_crunchyroll` | browser | Ouvrir Crunchyroll | ouvre crunchyroll, va sur crunchyroll |
| `ouvrir_github_web` | browser | Ouvrir GitHub | ouvre github, va sur github |
| `ouvrir_vercel` | browser | Ouvrir Vercel | ouvre vercel, va sur vercel |
| `ouvrir_crates_io` | browser | Ouvrir crates.io (Rust packages) | ouvre crates io, va sur crates |
| `chercher_video_youtube` | browser | Rechercher sur YouTube | cherche sur youtube {requete}, youtube {requete} |
| `chercher_github` | browser | Rechercher sur GitHub | cherche sur github {requete}, github {requete} |
| `chercher_stackoverflow` | browser | Rechercher sur Stack Overflow | cherche sur stackoverflow {requete}, stackoverflow {requete} |
| `chercher_npm` | browser | Rechercher un package NPM | cherche sur npm {requete}, npm {requete} |
| `chercher_pypi` | browser | Rechercher un package PyPI | cherche sur pypi {requete}, pypi {requete} |
| `ouvrir_google_translate` | browser | Ouvrir Google Translate | ouvre google translate, traducteur |
| `ouvrir_google_news` | browser | Ouvrir Google Actualites | ouvre google news, google actualites |
| `ouvrir_figma` | browser | Ouvrir Figma | ouvre figma, va sur figma |
| `ouvrir_canva` | browser | Ouvrir Canva | ouvre canva, va sur canva |
| `ouvrir_pinterest` | browser | Ouvrir Pinterest | ouvre pinterest, va sur pinterest |
| `ouvrir_udemy` | browser | Ouvrir Udemy | ouvre udemy, va sur udemy |
| `ouvrir_regex101` | browser | Ouvrir Regex101 (testeur de regex) | ouvre regex101, testeur regex |
| `ouvrir_jsonformatter` | browser | Ouvrir un formatteur JSON en ligne | ouvre json formatter, formatte du json |
| `ouvrir_speedtest` | browser | Ouvrir Speedtest | ouvre speedtest, lance un speed test |
| `ouvrir_excalidraw` | browser | Ouvrir Excalidraw (tableau blanc) | ouvre excalidraw, tableau blanc |
| `ouvrir_soundcloud` | browser | Ouvrir SoundCloud | ouvre soundcloud, va sur soundcloud |
| `ouvrir_google_scholar` | browser | Ouvrir Google Scholar | ouvre google scholar, google scholar |
| `chercher_traduction` | browser | Traduire un texte via Google Translate | traduis {requete}, traduction de {requete} |
| `chercher_google_scholar` | browser | Rechercher sur Google Scholar | cherche sur scholar {requete}, article sur {requete} |
| `chercher_huggingface` | browser | Rechercher un modele sur Hugging Face | cherche sur hugging face {requete}, modele {requete} huggingface |
| `chercher_docker_hub` | browser | Rechercher une image Docker Hub | cherche sur docker hub {requete}, image docker {requete} |
| `ouvrir_gmail_web` | browser | Ouvrir Gmail | ouvre gmail, va sur gmail |
| `ouvrir_google_keep` | browser | Ouvrir Google Keep (notes) | ouvre google keep, ouvre keep |
| `ouvrir_google_photos` | browser | Ouvrir Google Photos | ouvre google photos, va sur google photos |
| `ouvrir_google_meet` | browser | Ouvrir Google Meet | ouvre google meet, lance meet |
| `ouvrir_deepl` | browser | Ouvrir DeepL Traducteur | ouvre deepl, va sur deepl |
| `ouvrir_wayback_machine` | browser | Ouvrir la Wayback Machine (archive web) | ouvre wayback machine, wayback machine |
| `ouvrir_codepen` | browser | Ouvrir CodePen | ouvre codepen, va sur codepen |
| `ouvrir_jsfiddle` | browser | Ouvrir JSFiddle | ouvre jsfiddle, va sur jsfiddle |
| `ouvrir_dev_to` | browser | Ouvrir dev.to (communaute dev) | ouvre dev to, va sur dev to |
| `ouvrir_medium` | browser | Ouvrir Medium | ouvre medium, va sur medium |
| `ouvrir_hacker_news` | browser | Ouvrir Hacker News | ouvre hacker news, va sur hacker news |
| `ouvrir_producthunt` | browser | Ouvrir Product Hunt | ouvre product hunt, va sur product hunt |
| `ouvrir_coursera` | browser | Ouvrir Coursera | ouvre coursera, va sur coursera |
| `ouvrir_kaggle` | browser | Ouvrir Kaggle | ouvre kaggle, va sur kaggle |
| `ouvrir_arxiv` | browser | Ouvrir arXiv (articles scientifiques) | ouvre arxiv, va sur arxiv |
| `ouvrir_gitlab` | browser | Ouvrir GitLab | ouvre gitlab, va sur gitlab |
| `ouvrir_bitbucket` | browser | Ouvrir Bitbucket | ouvre bitbucket, va sur bitbucket |
| `ouvrir_leetcode` | browser | Ouvrir LeetCode | ouvre leetcode, va sur leetcode |
| `ouvrir_codewars` | browser | Ouvrir Codewars | ouvre codewars, va sur codewars |
| `chercher_deepl` | browser | Traduire via DeepL | traduis avec deepl {requete}, deepl {requete} |
| `chercher_arxiv` | browser | Rechercher sur arXiv | cherche sur arxiv {requete}, arxiv {requete} |
| `chercher_kaggle` | browser | Rechercher sur Kaggle | cherche sur kaggle {requete}, kaggle {requete} |
| `chercher_leetcode` | browser | Rechercher un probleme LeetCode | cherche sur leetcode {requete}, leetcode {requete} |
| `chercher_medium` | browser | Rechercher sur Medium | cherche sur medium {requete}, medium {requete} |
| `chercher_hacker_news` | browser | Rechercher sur Hacker News | cherche sur hacker news {requete}, hn {requete} |
| `ouvrir_linear` | browser | Ouvrir Linear (gestion de projet dev) | ouvre linear, va sur linear |
| `ouvrir_miro` | browser | Ouvrir Miro (whiteboard collaboratif) | ouvre miro, va sur miro |
| `ouvrir_loom` | browser | Ouvrir Loom (enregistrement ecran) | ouvre loom, va sur loom |
| `ouvrir_supabase` | browser | Ouvrir Supabase | ouvre supabase, va sur supabase |
| `ouvrir_firebase` | browser | Ouvrir Firebase Console | ouvre firebase, va sur firebase |
| `ouvrir_railway` | browser | Ouvrir Railway (deploy) | ouvre railway, va sur railway |
| `ouvrir_cloudflare` | browser | Ouvrir Cloudflare Dashboard | ouvre cloudflare, va sur cloudflare |
| `ouvrir_render` | browser | Ouvrir Render (hosting) | ouvre render, va sur render |
| `ouvrir_fly_io` | browser | Ouvrir Fly.io | ouvre fly io, va sur fly |
| `ouvrir_mdn` | browser | Ouvrir MDN Web Docs | ouvre mdn, va sur mdn |
| `ouvrir_devdocs` | browser | Ouvrir DevDocs.io (toute la doc dev) | ouvre devdocs, va sur devdocs |
| `ouvrir_can_i_use` | browser | Ouvrir Can I Use (compatibilite navigateurs) | ouvre can i use, can i use |
| `ouvrir_bundlephobia` | browser | Ouvrir Bundlephobia (taille des packages) | ouvre bundlephobia, bundlephobia |
| `ouvrir_w3schools` | browser | Ouvrir W3Schools | ouvre w3schools, va sur w3schools |
| `ouvrir_python_docs` | browser | Ouvrir la documentation Python officielle | ouvre la doc python, doc python |
| `ouvrir_rust_docs` | browser | Ouvrir la documentation Rust (The Book) | ouvre la doc rust, doc rust |
| `ouvrir_replit` | browser | Ouvrir Replit (IDE en ligne) | ouvre replit, va sur replit |
| `ouvrir_codesandbox` | browser | Ouvrir CodeSandbox | ouvre codesandbox, va sur codesandbox |
| `ouvrir_stackblitz` | browser | Ouvrir StackBlitz | ouvre stackblitz, va sur stackblitz |
| `ouvrir_typescript_playground` | browser | Ouvrir TypeScript Playground | ouvre typescript playground, typescript playground |
| `ouvrir_rust_playground` | browser | Ouvrir Rust Playground | ouvre rust playground, rust playground |
| `ouvrir_google_trends` | browser | Ouvrir Google Trends | ouvre google trends, google trends |
| `ouvrir_alternativeto` | browser | Ouvrir AlternativeTo (alternatives logiciels) | ouvre alternativeto, alternativeto |
| `ouvrir_downdetector` | browser | Ouvrir DownDetector (status services) | ouvre downdetector, downdetector |
| `ouvrir_virustotal` | browser | Ouvrir VirusTotal (scan fichiers/URLs) | ouvre virustotal, virustotal |
| `ouvrir_haveibeenpwned` | browser | Ouvrir Have I Been Pwned (verification email) | ouvre have i been pwned, haveibeenpwned |
| `chercher_crates_io` | browser | Rechercher un crate Rust | cherche sur crates {requete}, crate rust {requete} |
| `chercher_alternativeto` | browser | Chercher une alternative a un logiciel | alternative a {requete}, cherche une alternative a {requete} |
| `chercher_mdn` | browser | Rechercher sur MDN Web Docs | cherche sur mdn {requete}, mdn {requete} |
| `chercher_can_i_use` | browser | Verifier la compatibilite d'une feature web | can i use {requete}, compatibilite de {requete} |
| `ouvrir_chatgpt_plugins` | browser | Ouvrir ChatGPT (avec GPTs) | ouvre les gpts, chatgpt gpts |
| `ouvrir_anthropic_console` | browser | Ouvrir la console Anthropic API | ouvre anthropic console, console anthropic |
| `ouvrir_openai_platform` | browser | Ouvrir la plateforme OpenAI API | ouvre openai platform, console openai |
| `ouvrir_google_colab` | browser | Ouvrir Google Colab | ouvre google colab, colab |
| `ouvrir_overleaf` | browser | Ouvrir Overleaf (LaTeX en ligne) | ouvre overleaf, va sur overleaf |
| `ouvrir_whimsical` | browser | Ouvrir Whimsical (diagrams & flowcharts) | ouvre whimsical, whimsical |
| `ouvrir_grammarly` | browser | Ouvrir Grammarly | ouvre grammarly, grammarly |
| `ouvrir_remove_bg` | browser | Ouvrir Remove.bg (supprimer arriere-plan) | ouvre remove bg, supprime l'arriere plan |
| `ouvrir_tinypng` | browser | Ouvrir TinyPNG (compression images) | ouvre tinypng, compresse une image |
| `ouvrir_draw_io` | browser | Ouvrir draw.io (diagrammes) | ouvre draw io, drawio |
| `ouvrir_notion_calendar` | browser | Ouvrir Notion Calendar | ouvre notion calendar, calendrier notion |
| `ouvrir_todoist` | browser | Ouvrir Todoist (gestion de taches) | ouvre todoist, va sur todoist |
| `ouvrir_google_finance` | browser | Ouvrir Google Finance | ouvre google finance, google finance |
| `ouvrir_yahoo_finance` | browser | Ouvrir Yahoo Finance | ouvre yahoo finance, yahoo finance |
| `ouvrir_coindesk` | browser | Ouvrir CoinDesk (news crypto) | ouvre coindesk, news crypto |
| `ouvrir_meteo` | browser | Ouvrir la meteo | ouvre la meteo, quel temps fait il |
| `chercher_google_colab` | browser | Rechercher un notebook Colab | cherche un notebook {requete}, colab {requete} |
| `chercher_perplexity` | browser | Rechercher sur Perplexity AI | cherche sur perplexity {requete}, perplexity {requete} |
| `chercher_google_maps` | browser | Rechercher sur Google Maps | cherche sur maps {requete}, maps {requete} |
| `ouvrir_impots` | browser | Ouvrir impots.gouv.fr | ouvre les impots, impots gouv |
| `ouvrir_ameli` | browser | Ouvrir Ameli (Assurance Maladie) | ouvre ameli, assurance maladie |
| `ouvrir_caf` | browser | Ouvrir la CAF | ouvre la caf, allocations familiales |
| `ouvrir_sncf` | browser | Ouvrir SNCF Connect (trains) | ouvre sncf, billets de train |
| `ouvrir_doctolib` | browser | Ouvrir Doctolib (rendez-vous medical) | ouvre doctolib, prends un rdv medical |
| `ouvrir_la_poste` | browser | Ouvrir La Poste (suivi colis) | ouvre la poste, suivi colis |
| `ouvrir_pole_emploi` | browser | Ouvrir France Travail (ex Pole Emploi) | ouvre pole emploi, france travail |
| `ouvrir_service_public` | browser | Ouvrir Service-Public.fr | service public, demarches administratives |
| `ouvrir_fnac` | browser | Ouvrir Fnac.com | ouvre la fnac, va sur la fnac |
| `ouvrir_cdiscount` | browser | Ouvrir Cdiscount | ouvre cdiscount, va sur cdiscount |
| `ouvrir_amazon_fr` | browser | Ouvrir Amazon France | ouvre amazon france, amazon fr |
| `ouvrir_boursorama` | browser | Ouvrir Boursorama (banque/bourse) | ouvre boursorama, va sur boursorama |
| `ouvrir_free_mobile` | browser | Ouvrir Free Mobile (espace client) | ouvre free, espace client free |
| `ouvrir_edf` | browser | Ouvrir EDF (electricite) | ouvre edf, mon compte edf |
| `ouvrir_aws_console` | browser | Ouvrir AWS Console | ouvre aws, console aws |
| `ouvrir_azure_portal` | browser | Ouvrir Azure Portal | ouvre azure, portal azure |
| `ouvrir_gcp_console` | browser | Ouvrir Google Cloud Console | ouvre google cloud, gcp console |
| `ouvrir_netlify` | browser | Ouvrir Netlify (deploiement) | ouvre netlify, va sur netlify |
| `ouvrir_digitalocean` | browser | Ouvrir DigitalOcean | ouvre digitalocean, va sur digital ocean |
| `ouvrir_le_monde` | browser | Ouvrir Le Monde | ouvre le monde, actualites le monde |
| `ouvrir_le_figaro` | browser | Ouvrir Le Figaro | ouvre le figaro, actualites figaro |
| `ouvrir_liberation` | browser | Ouvrir Liberation | ouvre liberation, actualites liberation |
| `ouvrir_france_info` | browser | Ouvrir France Info | ouvre france info, actualites france |
| `ouvrir_techcrunch` | browser | Ouvrir TechCrunch (tech news) | ouvre techcrunch, news tech |
| `ouvrir_hackernews` | browser | Ouvrir Hacker News | ouvre hacker news, va sur hacker news |
| `ouvrir_ars_technica` | browser | Ouvrir Ars Technica | ouvre ars technica, va sur ars technica |
| `ouvrir_the_verge` | browser | Ouvrir The Verge | ouvre the verge, va sur the verge |
| `ouvrir_deezer` | browser | Ouvrir Deezer | ouvre deezer, va sur deezer |
| `ouvrir_mycanal` | browser | Ouvrir MyCanal | ouvre canal plus, va sur mycanal |
| `chercher_leboncoin` | browser | Rechercher sur Leboncoin | cherche sur leboncoin {requete}, leboncoin {requete} |
| `ouvrir_khan_academy` | browser | Ouvrir Khan Academy | ouvre khan academy, va sur khan academy |
| `ouvrir_edx` | browser | Ouvrir edX | ouvre edx, va sur edx |
| `ouvrir_freecodecamp` | browser | Ouvrir freeCodeCamp | ouvre freecodecamp, va sur freecodecamp |
| `ouvrir_caniuse` | browser | Ouvrir Can I Use (compatibilite navigateur) | ouvre can i use, compatibilite navigateur |
| `ouvrir_frandroid` | browser | Ouvrir Frandroid (tech FR) | ouvre frandroid, va sur frandroid |
| `ouvrir_numerama` | browser | Ouvrir Numerama (tech FR) | ouvre numerama, va sur numerama |
| `ouvrir_les_numeriques` | browser | Ouvrir Les Numeriques (tests produits) | ouvre les numeriques, les numeriques |
| `ouvrir_01net` | browser | Ouvrir 01net (tech FR) | ouvre 01net, va sur 01 net |
| `ouvrir_journal_du_net` | browser | Ouvrir Le Journal du Net | ouvre journal du net, jdn |
| `ouvrir_binance` | browser | Ouvrir Binance | ouvre binance, va sur binance |
| `ouvrir_coinbase` | browser | Ouvrir Coinbase | ouvre coinbase, va sur coinbase |
| `ouvrir_kraken` | browser | Ouvrir Kraken | ouvre kraken, va sur kraken |
| `ouvrir_etherscan` | browser | Ouvrir Etherscan (explorateur Ethereum) | ouvre etherscan, etherscan |
| `ouvrir_booking` | browser | Ouvrir Booking.com (hotels) | ouvre booking, reserve un hotel |
| `ouvrir_airbnb` | browser | Ouvrir Airbnb | ouvre airbnb, va sur airbnb |
| `ouvrir_google_flights` | browser | Ouvrir Google Flights (vols) | ouvre google flights, billets d'avion |
| `ouvrir_tripadvisor` | browser | Ouvrir TripAdvisor | ouvre tripadvisor, avis restaurants |
| `ouvrir_blablacar` | browser | Ouvrir BlaBlaCar (covoiturage) | ouvre blablacar, covoiturage |
| `ouvrir_legifrance` | browser | Ouvrir Legifrance (textes de loi) | ouvre legifrance, textes de loi |
| `ouvrir_ants` | browser | Ouvrir ANTS (carte d'identite, permis) | ouvre ants, carte d'identite |
| `ouvrir_prefecture` | browser | Ouvrir la prise de RDV en prefecture | rendez vous prefecture, ouvre la prefecture |
| `ouvrir_steam_store` | browser | Ouvrir le Steam Store | ouvre le store steam, magasin steam |
| `ouvrir_epic_games` | browser | Ouvrir Epic Games Store | ouvre epic games, va sur epic games |
| `ouvrir_gog` | browser | Ouvrir GOG.com (jeux sans DRM) | ouvre gog, va sur gog |
| `ouvrir_humble_bundle` | browser | Ouvrir Humble Bundle | ouvre humble bundle, humble bundle |
| `ouvrir_vidal` | browser | Ouvrir Vidal (medicaments) | ouvre vidal, notice medicament |
| `ouvrir_doctissimo` | browser | Ouvrir Doctissimo (sante) | ouvre doctissimo, symptomes |
| `chercher_github_repos` | browser | Rechercher un repo sur GitHub | cherche un repo {requete}, github repo {requete} |
| `chercher_huggingface_models` | browser | Rechercher un modele sur Hugging Face | cherche un modele {requete}, huggingface model {requete} |
| `ouvrir_grafana_cloud` | browser | Ouvrir Grafana Cloud | ouvre grafana, va sur grafana |
| `ouvrir_datadog` | browser | Ouvrir Datadog | ouvre datadog, va sur datadog |
| `ouvrir_sentry` | browser | Ouvrir Sentry (error tracking) | ouvre sentry, va sur sentry |
| `ouvrir_pagerduty` | browser | Ouvrir PagerDuty (alerting) | ouvre pagerduty, alertes pagerduty |
| `ouvrir_newrelic` | browser | Ouvrir New Relic (APM) | ouvre new relic, va sur newrelic |
| `ouvrir_uptime_robot` | browser | Ouvrir UptimeRobot (monitoring) | ouvre uptime robot, status sites |
| `ouvrir_prometheus_docs` | browser | Ouvrir la doc Prometheus | doc prometheus, prometheus documentation |
| `ouvrir_jenkins` | browser | Ouvrir Jenkins | ouvre jenkins, va sur jenkins |
| `ouvrir_circleci` | browser | Ouvrir CircleCI | ouvre circleci, circle ci |
| `ouvrir_travis_ci` | browser | Ouvrir Travis CI | ouvre travis, travis ci |
| `ouvrir_gitlab_ci` | browser | Ouvrir GitLab CI/CD | ouvre gitlab ci, gitlab pipelines |
| `ouvrir_postman_web` | browser | Ouvrir Postman Web | ouvre postman, va sur postman |
| `ouvrir_swagger_editor` | browser | Ouvrir Swagger Editor | ouvre swagger, swagger editor |
| `ouvrir_rapidapi` | browser | Ouvrir RapidAPI (marketplace API) | ouvre rapidapi, va sur rapidapi |
| `ouvrir_httpbin` | browser | Ouvrir HTTPBin (test HTTP) | ouvre httpbin, test http |
| `ouvrir_reqbin` | browser | Ouvrir ReqBin (HTTP client en ligne) | ouvre reqbin, client http en ligne |
| `ouvrir_malt` | browser | Ouvrir Malt (freelance FR) | ouvre malt, va sur malt |
| `ouvrir_fiverr` | browser | Ouvrir Fiverr | ouvre fiverr, va sur fiverr |
| `ouvrir_upwork` | browser | Ouvrir Upwork | ouvre upwork, va sur upwork |
| `ouvrir_welcome_jungle` | browser | Ouvrir Welcome to the Jungle (emploi tech) | ouvre welcome to the jungle, offres d'emploi tech |
| `ouvrir_indeed` | browser | Ouvrir Indeed | ouvre indeed, va sur indeed |
| `ouvrir_uber_eats` | browser | Ouvrir Uber Eats | ouvre uber eats, commande uber eats |
| `ouvrir_deliveroo` | browser | Ouvrir Deliveroo | ouvre deliveroo, commande deliveroo |
| `ouvrir_just_eat` | browser | Ouvrir Just Eat | ouvre just eat, commande just eat |
| `ouvrir_tf1_plus` | browser | Ouvrir TF1+ (replay TF1) | ouvre tf1, replay tf1 |
| `ouvrir_france_tv` | browser | Ouvrir France.tv (replay France TV) | ouvre france tv, replay france tv |
| `ouvrir_arte_replay` | browser | Ouvrir Arte.tv (replay) | ouvre arte, replay arte |
| `ouvrir_bfm_tv` | browser | Ouvrir BFM TV en direct | ouvre bfm, bfm tv |
| `ouvrir_cnews` | browser | Ouvrir CNews | ouvre cnews, c news |
| `ouvrir_mediapart` | browser | Ouvrir Mediapart | ouvre mediapart, va sur mediapart |
| `ouvrir_trello` | browser | Ouvrir Trello | ouvre trello, va sur trello |
| `ouvrir_asana` | browser | Ouvrir Asana | ouvre asana, va sur asana |
| `ouvrir_monday` | browser | Ouvrir Monday.com | ouvre monday, va sur monday |
| `ouvrir_clickup` | browser | Ouvrir ClickUp | ouvre clickup, va sur clickup |
| `ouvrir_darty` | browser | Ouvrir Darty | ouvre darty, va sur darty |
| `ouvrir_boulanger` | browser | Ouvrir Boulanger | ouvre boulanger, va sur boulanger |
| `ouvrir_leroy_merlin` | browser | Ouvrir Leroy Merlin (bricolage) | ouvre leroy merlin, bricolage |
| `ouvrir_castorama` | browser | Ouvrir Castorama (bricolage) | ouvre castorama, va sur castorama |
| `ouvrir_vinted` | browser | Ouvrir Vinted | ouvre vinted, va sur vinted |
| `ouvrir_revolut` | browser | Ouvrir Revolut | ouvre revolut, va sur revolut |
| `ouvrir_n26` | browser | Ouvrir N26 (banque en ligne) | ouvre n26, va sur n26 |
| `ouvrir_bankin` | browser | Ouvrir Bankin (agrégateur comptes) | ouvre bankin, va sur bankin |
| `ouvrir_dribbble` | browser | Ouvrir Dribbble (inspiration design) | ouvre dribbble, inspiration design |
| `ouvrir_unsplash` | browser | Ouvrir Unsplash (photos libres) | ouvre unsplash, photos gratuites |
| `ouvrir_coolors` | browser | Ouvrir Coolors (palettes couleurs) | ouvre coolors, palette de couleurs |
| `ouvrir_fontawesome` | browser | Ouvrir Font Awesome (icones) | ouvre font awesome, icones font awesome |

### PIPELINE (246)

| Commande | Type | Description | Triggers |
|----------|------|-------------|----------|
| `range_bureau` | pipeline | Ranger le bureau (minimiser toutes les fenetres) | range mon bureau, range le bureau |
| `va_sur_mails_comet` | pipeline | Ouvrir Comet et aller sur Gmail | va sur mes mails, ouvre mes mails sur comet |
| `mode_travail` | pipeline | Mode travail: VSCode + Terminal | mode travail, mode dev |
| `mode_trading` | pipeline | Mode trading: TradingView + MEXC + Dashboard | mode trading, ouvre mon setup trading |
| `rapport_matin` | pipeline | Rapport du matin: Gmail Comet + TradingView + Dashboard | rapport du matin, routine du matin |
| `bonne_nuit` | pipeline | Bonne nuit: minimiser tout + verrouiller le PC | bonne nuit, bonne nuit jarvis |
| `mode_focus` | pipeline | Mode focus: minimiser tout + ne pas deranger | mode focus, mode concentration |
| `mode_cinema` | pipeline | Mode cinema: minimiser tout + ouvrir Netflix | mode cinema, mode film |
| `ouvre_youtube_comet` | pipeline | Ouvrir YouTube dans Comet | ouvre youtube sur comet, youtube comet |
| `ouvre_github_comet` | pipeline | Ouvrir GitHub dans Comet | ouvre github sur comet, ouvre github comet |
| `ouvre_cluster` | pipeline | Ouvrir Dashboard cluster + LM Studio | ouvre le cluster, lance le cluster |
| `ferme_tout` | pipeline | Fermer toutes les fenetres | ferme tout, ferme toutes les fenetres |
| `mode_musique` | pipeline | Mode musique: minimiser tout + ouvrir Spotify | mode musique, lance la musique en fond |
| `mode_gaming` | pipeline | Mode gaming: haute performance + Steam + Game Bar | mode gaming, mode jeu |
| `mode_stream` | pipeline | Mode stream: minimiser tout + OBS + Spotify | mode stream, lance le stream |
| `mode_presentation` | pipeline | Mode presentation: dupliquer ecran + PowerPoint | mode presentation, lance la presentation |
| `mode_lecture` | pipeline | Mode lecture: nuit + minimiser + Comet | mode lecture, mode lire |
| `mode_reunion` | pipeline | Mode reunion: Discord + focus assist | mode reunion, lance la reunion |
| `mode_code_turbo` | pipeline | Mode dev turbo: VSCode + Terminal + LM Studio + Dashboard | mode code turbo, setup dev complet |
| `mode_detente` | pipeline | Mode detente: minimiser + Spotify + lumiere nocturne | mode detente, mode relax |
| `routine_soir` | pipeline | Routine du soir: TradingView + night light + minimiser | routine du soir, routine soir |
| `check_trading_rapide` | pipeline | Check trading: TradingView + MEXC en parallele | check trading rapide, check rapide trading |
| `setup_ia` | pipeline | Setup IA: LM Studio + Dashboard + Terminal | setup ia, lance le setup ia |
| `nettoyage_express` | pipeline | Nettoyage express: corbeille + temp + DNS | nettoyage express, nettoyage rapide |
| `diagnostic_complet` | pipeline | Diagnostic complet: systeme + GPU + RAM + disques | diagnostic complet, diagnostic du pc |
| `debug_reseau` | pipeline | Debug reseau: flush DNS + ping + diagnostic | debug reseau, debug le reseau |
| `veille_securisee` | pipeline | Veille securisee: minimiser + verrouiller + veille | veille securisee, mets en veille en securite |
| `ouvre_reddit_comet` | pipeline | Ouvrir Reddit dans Comet | ouvre reddit sur comet, reddit comet |
| `ouvre_twitter_comet` | pipeline | Ouvrir Twitter/X dans Comet | ouvre twitter sur comet, twitter comet |
| `ouvre_chatgpt_comet` | pipeline | Ouvrir ChatGPT dans Comet | ouvre chatgpt sur comet, chatgpt comet |
| `ouvre_claude_comet` | pipeline | Ouvrir Claude AI dans Comet | ouvre claude sur comet, claude comet |
| `ouvre_linkedin_comet` | pipeline | Ouvrir LinkedIn dans Comet | ouvre linkedin sur comet, linkedin comet |
| `ouvre_amazon_comet` | pipeline | Ouvrir Amazon dans Comet | ouvre amazon sur comet, amazon comet |
| `ouvre_twitch_comet` | pipeline | Ouvrir Twitch dans Comet | ouvre twitch sur comet, twitch comet |
| `ouvre_social_comet` | pipeline | Ouvrir les reseaux sociaux dans Comet (Twitter + Reddit + Discord) | ouvre les reseaux sociaux comet, social comet |
| `ouvre_perplexity_comet` | pipeline | Ouvrir Perplexity dans Comet | ouvre perplexity sur comet, perplexity comet |
| `ouvre_huggingface_comet` | pipeline | Ouvrir Hugging Face dans Comet | ouvre hugging face sur comet, huggingface comet |
| `mode_crypto` | pipeline | Mode crypto: TradingView + MEXC + CoinGecko | mode crypto, mode trading crypto |
| `mode_ia_complet` | pipeline | Mode IA complet: LM Studio + Dashboard + Claude + HuggingFace | mode ia complet, ouvre tout le cluster ia |
| `mode_debug` | pipeline | Mode debug: Terminal + GPU monitoring + logs systeme | mode debug, mode debogage |
| `mode_monitoring` | pipeline | Mode monitoring: Dashboard + GPU + cluster health | mode monitoring, mode surveillance |
| `mode_communication` | pipeline | Mode communication: Discord + Telegram + WhatsApp | mode communication, mode com |
| `mode_documentation` | pipeline | Mode documentation: Notion + Google Docs + Drive | mode documentation, mode docs |
| `mode_focus_total` | pipeline | Mode focus total: minimiser + focus assist + nuit + VSCode | mode focus total, concentration maximale |
| `mode_review` | pipeline | Mode review: VSCode + navigateur Git + Terminal | mode review, mode revue de code |
| `routine_matin` | pipeline | Routine du matin: cluster + dashboard + trading + mails | routine du matin, routine matin |
| `backup_express` | pipeline | Backup express: git add + commit du projet turbo | backup express, sauvegarde rapide |
| `reboot_cluster` | pipeline | Reboot cluster: redemarre Ollama + ping LM Studio | reboot le cluster, redemarre le cluster |
| `pause_travail` | pipeline | Pause: minimiser + verrouiller ecran + Spotify | pause travail, je fais une pause |
| `fin_journee` | pipeline | Fin de journee: backup + nuit + fermer apps dev | fin de journee, termine la journee |
| `ouvre_github_via_comet` | pipeline | Ouvrir GitHub dans Comet | ouvre github sur comet, github comet |
| `ouvre_youtube_via_comet` | pipeline | Ouvrir YouTube dans Comet | ouvre youtube sur comet, youtube comet |
| `ouvre_tradingview_comet` | pipeline | Ouvrir TradingView dans Comet | ouvre tradingview sur comet, tradingview comet |
| `ouvre_coingecko_comet` | pipeline | Ouvrir CoinGecko dans Comet | ouvre coingecko sur comet, coingecko comet |
| `ouvre_ia_comet` | pipeline | Ouvrir toutes les IA dans Comet (ChatGPT + Claude + Perplexity) | ouvre toutes les ia comet, ia comet |
| `mode_cinema_complet` | pipeline | Mode cinema complet: minimiser + nuit + plein ecran + Netflix | mode cinema complet, soiree film |
| `mode_workout` | pipeline | Mode workout: Spotify energique + YouTube fitness + timer | mode workout, mode sport |
| `mode_etude` | pipeline | Mode etude: focus + Wikipedia + Pomodoro mindset | mode etude, mode revision |
| `mode_diner` | pipeline | Mode diner: minimiser + ambiance calme + Spotify | mode diner, ambiance diner |
| `routine_depart` | pipeline | Routine depart: sauvegarder + minimiser + verrouiller + economie | routine depart, je pars |
| `routine_retour` | pipeline | Routine retour: performance + cluster + mails + dashboard | routine retour, je suis rentre |
| `mode_nuit_totale` | pipeline | Mode nuit: fermer tout + nuit + volume bas + verrouiller | mode nuit totale, dodo |
| `dev_morning_setup` | pipeline | Dev morning: git pull + Docker + VSCode + browser tabs travail | dev morning, setup dev du matin |
| `dev_deep_work` | pipeline | Deep work: fermer distractions + VSCode + focus + terminal | deep work, travail profond |
| `dev_standup_prep` | pipeline | Standup prep: git log hier + board + dashboard | standup prep, prepare le standup |
| `dev_deploy_check` | pipeline | Pre-deploy check: tests + git status + Docker status | check avant deploy, pre deploy |
| `dev_friday_report` | pipeline | Rapport vendredi: stats git semaine + dashboard + todos | rapport vendredi, friday report |
| `dev_code_review_setup` | pipeline | Code review setup: GitHub PRs + VSCode + diff terminal | setup code review, prepare la review |
| `audit_securite_complet` | pipeline | Audit securite: Defender + ports + connexions + firewall + autorun | audit securite complet, scan securite total |
| `rapport_systeme_complet` | pipeline | Rapport systeme: CPU + RAM + GPU + disques + uptime + reseau | rapport systeme complet, rapport systeme |
| `maintenance_totale` | pipeline | Maintenance totale: corbeille + temp + prefetch + DNS + thumbnails + check updates | maintenance totale, grand nettoyage |
| `sauvegarde_tous_projets` | pipeline | Backup tous projets: git commit turbo + carV1 + serveur | sauvegarde tous les projets, backup tous les projets |
| `pomodoro_start` | pipeline | Pomodoro: fermer distractions + focus + VSCode + timer 25min | pomodoro, lance un pomodoro |
| `pomodoro_break` | pipeline | Pause Pomodoro: minimiser + Spotify + 5 min | pause pomodoro, break pomodoro |
| `mode_entretien` | pipeline | Mode entretien/call: fermer musique + focus + navigateur | mode entretien, j'ai un call |
| `mode_recherche` | pipeline | Mode recherche: Perplexity + Google Scholar + Wikipedia + Claude | mode recherche, lance le mode recherche |
| `mode_youtube` | pipeline | Mode YouTube: minimiser + plein ecran + YouTube | mode youtube, lance youtube en grand |
| `mode_spotify_focus` | pipeline | Spotify focus: minimiser + Spotify + focus assist | spotify focus, musique et concentration |
| `ouvre_tout_dev_web` | pipeline | Dev web complet: VSCode + terminal + localhost + npm docs | dev web complet, setup dev web |
| `mode_twitch_stream` | pipeline | Mode stream Twitch: OBS + Twitch dashboard + Spotify + chat | mode twitch, setup stream twitch |
| `mode_email_productif` | pipeline | Email productif: Gmail + Calendar + fermer distractions | mode email, traite les mails |
| `mode_podcast` | pipeline | Mode podcast: minimiser + Spotify + volume confortable | mode podcast, lance un podcast |
| `mode_apprentissage` | pipeline | Mode apprentissage: focus + Udemy/Coursera + notes | mode apprentissage, mode formation |
| `mode_news` | pipeline | Mode news: Google Actualites + Reddit + Twitter | mode news, mode actualites |
| `mode_shopping` | pipeline | Mode shopping: Amazon + Leboncoin + comparateur | mode shopping, mode achats |
| `mode_design` | pipeline | Mode design: Figma + Pinterest + Canva | mode design, mode graphisme |
| `mode_musique_decouverte` | pipeline | Decouverte musicale: Spotify + YouTube Music + SoundCloud | decouverte musicale, explore la musique |
| `routine_weekend` | pipeline | Routine weekend: relax + news + musique + Netflix | routine weekend, mode weekend |
| `mode_social_complet` | pipeline | Social complet: Twitter + Reddit + Instagram + LinkedIn + Discord | mode social complet, tous les reseaux |
| `mode_planning` | pipeline | Mode planning: Calendar + Notion + Google Tasks | mode planning, mode planification |
| `mode_brainstorm` | pipeline | Mode brainstorm: Claude + Notion + timer | mode brainstorm, session brainstorm |
| `nettoyage_downloads` | pipeline | Nettoyer les vieux telechargements (>30 jours) | nettoie les telechargements, clean downloads |
| `rapport_reseau_complet` | pipeline | Rapport reseau: IP + DNS + latence + ports + WiFi | rapport reseau complet, rapport reseau |
| `verif_toutes_mises_a_jour` | pipeline | Verifier MAJ: Windows Update + pip + npm + ollama | verifie toutes les mises a jour, check toutes les updates |
| `snapshot_systeme` | pipeline | Snapshot systeme: sauvegarder toutes les stats dans un fichier | snapshot systeme, capture l'etat du systeme |
| `dev_hotfix` | pipeline | Hotfix: nouvelle branche + VSCode + tests | hotfix, lance un hotfix |
| `dev_new_feature` | pipeline | Nouvelle feature: branche + VSCode + terminal + tests | nouvelle feature, dev new feature |
| `dev_merge_prep` | pipeline | Preparation merge: lint + tests + git status + diff | prepare le merge, pre merge |
| `dev_database_check` | pipeline | Check databases: taille + tables de jarvis.db et etoile.db | check les databases, verifie les bases de donnees |
| `dev_live_coding` | pipeline | Live coding: OBS + VSCode + terminal + navigateur localhost | live coding, mode live code |
| `dev_cleanup` | pipeline | Dev cleanup: git clean + cache Python + node_modules check | dev cleanup, nettoie le projet |
| `mode_double_ecran_dev` | pipeline | Double ecran dev: etendre + VSCode gauche + navigateur droite | mode double ecran dev, setup double ecran |
| `mode_presentation_zoom` | pipeline | Presentation Zoom/Teams: fermer distractions + dupliquer ecran + app | mode presentation zoom, setup presentation teams |
| `mode_dashboard_complet` | pipeline | Dashboard complet: JARVIS + TradingView + cluster + n8n | dashboard complet, ouvre tous les dashboards |
| `ferme_tout_sauf_code` | pipeline | Fermer tout sauf VSCode et terminal | ferme tout sauf le code, garde juste vscode |
| `mode_detox_digital` | pipeline | Detox digitale: fermer TOUT + verrouiller + night light | detox digitale, mode detox |
| `mode_musique_travail` | pipeline | Musique de travail: Spotify + focus assist (pas de distractions) | musique de travail, met de la musique pour bosser |
| `check_tout_rapide` | pipeline | Check rapide tout: cluster + GPU + RAM + disques en 1 commande | check tout rapide, etat rapide de tout |
| `mode_hackathon` | pipeline | Mode hackathon: timer + VSCode + terminal + GitHub + Claude | mode hackathon, lance le hackathon |
| `mode_data_science` | pipeline | Mode data science: Jupyter + Kaggle + docs Python + terminal | mode data science, mode datascience |
| `mode_devops` | pipeline | Mode DevOps: Docker + dashboard + terminal + GitHub Actions | mode devops, mode ops |
| `mode_securite_audit` | pipeline | Mode audit securite: Defender + ports + connexions + terminal | mode securite, mode audit securite |
| `mode_trading_scalp` | pipeline | Mode scalping: TradingView multi-timeframe + MEXC + terminal | mode scalping, mode scalp |
| `routine_midi` | pipeline | Routine midi: pause + news + trading check rapide | routine midi, pause midi |
| `routine_nuit_urgence` | pipeline | Mode urgence nuit: tout fermer + sauvegarder + veille immediate | urgence nuit, extinction d'urgence |
| `setup_meeting_rapide` | pipeline | Meeting rapide: micro check + fermer musique + Teams/Discord | meeting rapide, setup meeting |
| `mode_veille_tech` | pipeline | Veille tech: Hacker News + dev.to + Product Hunt + Reddit/programming | veille tech, mode veille technologique |
| `mode_freelance` | pipeline | Mode freelance: factures + mails + calendar + Notion | mode freelance, mode client |
| `mode_debug_production` | pipeline | Debug prod: logs + monitoring + terminal + dashboard | debug production, mode debug prod |
| `mode_apprentissage_code` | pipeline | Mode apprentissage code: LeetCode + VSCode + docs + timer | mode apprentissage code, session leetcode |
| `mode_tutorial` | pipeline | Mode tutorial: YouTube + VSCode + terminal + docs | mode tutorial, mode tuto |
| `mode_backup_total` | pipeline | Backup total: tous les projets + snapshot systeme + rapport | backup total, sauvegarde totale |
| `ouvre_dashboards_trading` | pipeline | Tous les dashboards trading: TV + MEXC + CoinGecko + CoinMarketCap + DexScreener | tous les dashboards trading, ouvre tout le trading |
| `mode_photo_edit` | pipeline | Mode retouche photo: Paint + navigateur refs + Pinterest | mode photo, mode retouche |
| `mode_writing` | pipeline | Mode ecriture: Google Docs + focus + nuit + Claude aide | mode ecriture, mode redaction |
| `mode_video_marathon` | pipeline | Mode marathon video: Netflix + nuit + plein ecran + snacks time | mode marathon, marathon video |
| `ouvre_kaggle_comet` | pipeline | Ouvrir Kaggle dans Comet | ouvre kaggle sur comet, kaggle comet |
| `ouvre_arxiv_comet` | pipeline | Ouvrir arXiv dans Comet | ouvre arxiv sur comet, arxiv comet |
| `ouvre_notion_comet` | pipeline | Ouvrir Notion dans Comet | ouvre notion sur comet, notion comet |
| `ouvre_stackoverflow_comet` | pipeline | Ouvrir Stack Overflow dans Comet | ouvre stackoverflow sur comet, stackoverflow comet |
| `ouvre_medium_comet` | pipeline | Ouvrir Medium dans Comet | ouvre medium sur comet, medium comet |
| `ouvre_gmail_comet` | pipeline | Ouvrir Gmail dans Comet | ouvre gmail sur comet, gmail comet |
| `mode_go_live` | pipeline | Go Live: OBS + Twitch dashboard + Spotify + chat overlay | go live, lance le stream maintenant |
| `mode_end_stream` | pipeline | End stream: fermer OBS + Twitch + recap | arrete le stream, fin du live |
| `mode_daily_report` | pipeline | Daily report: git log + stats code + dashboard + Google Sheets | rapport quotidien, daily report |
| `mode_api_test` | pipeline | Mode API testing: terminal + navigateur API docs + outils test | mode api test, teste les api |
| `mode_conference_full` | pipeline | Conference: fermer distractions + Teams + micro + focus assist | mode conference, mode visio complete |
| `mode_end_meeting` | pipeline | Fin meeting: fermer Teams/Discord/Zoom + restaurer musique | fin du meeting, fin de la reunion |
| `mode_home_theater` | pipeline | Home theater: minimiser + nuit + volume max + Disney+/Netflix plein ecran | mode home theater, mode cinema maison |
| `mode_refactoring` | pipeline | Mode refactoring: VSCode + ruff + tests + git diff | mode refactoring, session refactoring |
| `mode_testing_complet` | pipeline | Mode tests complet: pytest + coverage + lint + terminal | mode testing complet, lance tous les tests |
| `mode_deploy_checklist` | pipeline | Checklist deploy: tests + lint + status git + build check | checklist deploy, mode deploy |
| `mode_documentation_code` | pipeline | Mode doc code: VSCode + readthedocs + terminal + Notion | mode documentation code, documente le code |
| `mode_open_source` | pipeline | Mode open source: GitHub issues + PRs + VSCode + terminal | mode open source, mode contribution |
| `mode_side_project` | pipeline | Mode side project: VSCode + navigateur + terminal + timer 2h | mode side project, mode projet perso |
| `mode_admin_sys` | pipeline | Mode sysadmin: terminal + Event Viewer + services + ports | mode sysadmin, mode administrateur |
| `mode_reseau_complet` | pipeline | Mode reseau complet: ping + DNS + WiFi + ports + IP | mode reseau complet, diagnostic reseau total |
| `mode_finance` | pipeline | Mode finance: banque + budget + trading + calculatrice | mode finance, mode budget |
| `mode_voyage` | pipeline | Mode voyage: Google Flights + Maps + Booking + meteo | mode voyage, planifie un voyage |
| `routine_aperitif` | pipeline | Routine apero: fermer le travail + musique + ambiance | routine apero, aperitif |
| `mode_cuisine` | pipeline | Mode cuisine: YouTube recettes + timer + Spotify musique | mode cuisine, je fais a manger |
| `mode_meditation` | pipeline | Mode meditation: minimiser + nuit + sons relaxants | mode meditation, medite |
| `mode_pair_programming` | pipeline | Pair programming: VSCode Live Share + terminal + Discord | mode pair programming, pair prog |
| `mode_retrospective` | pipeline | Retrospective: bilan semaine + git stats + Notion + Calendar | mode retro, retrospective |
| `mode_demo` | pipeline | Mode demo: dupliquer ecran + navigateur + dashboard + presentation | mode demo, prepare la demo |
| `mode_scrum_master` | pipeline | Mode Scrum: board + standup + Calendar + timer | mode scrum, mode scrum master |
| `sim_reveil_complet` | pipeline | Simulation reveil: cluster + mails + trading + news + dashboard + café | demarre la journee complete, simulation reveil |
| `sim_check_matinal` | pipeline | Check matinal rapide: cluster health + GPU + RAM + trading | check matinal, tout va bien ce matin |
| `sim_start_coding` | pipeline | Demarrer une session de code: git pull + VSCode + terminal + snap | je commence a coder, start coding session |
| `sim_code_and_test` | pipeline | Code + test: lancer les tests + lint + afficher résultats | teste mon code, code and test |
| `sim_commit_and_push` | pipeline | Commiter et pusher le code | commit et push, sauvegarde et pousse |
| `sim_debug_session` | pipeline | Session debug: devtools + terminal + logs + monitoring | session debug complete, je debug |
| `sim_avant_reunion` | pipeline | Avant reunion: fermer distractions + notes + agenda + micro check | prepare la reunion, avant le meeting |
| `sim_rejoindre_reunion` | pipeline | Rejoindre: ouvrir Discord/Teams + partage ecran pret | rejoins la reunion, join meeting |
| `sim_presenter_ecran` | pipeline | Presenter: dupliquer ecran + ouvrir dashboard + plein ecran | presente mon ecran, partage ecran presentation |
| `sim_apres_reunion` | pipeline | Après reunion: fermer visio + restaurer musique + reprendre le dev | reunion terminee reprends, apres le meeting |
| `sim_pause_cafe` | pipeline | Pause cafe: minimiser + verrouiller + 10 min | pause cafe, je prends un cafe |
| `sim_pause_longue` | pipeline | Pause longue: save + musique + nuit + verrouiller | longue pause, grande pause |
| `sim_retour_pause` | pipeline | Retour de pause: performance + rouvrir le dev + check cluster | je suis de retour, retour de pause |
| `sim_recherche_intensive` | pipeline | Recherche intensive: Claude + Perplexity + Scholar + Wikipedia + notes | recherche intensive, session recherche complete |
| `sim_formation_video` | pipeline | Formation video: YouTube + notes + VSCode + timer 2h | formation video complete, session formation |
| `sim_analyse_trading` | pipeline | Analyse trading: multi-timeframe + indicateurs + news crypto | analyse trading complete, session analyse trading |
| `sim_execution_trading` | pipeline | Execution trading: MEXC + TradingView + terminal signaux | execute le trading, passe les ordres |
| `sim_monitoring_positions` | pipeline | Monitoring positions: MEXC + alertes + DexScreener | surveille mes positions, monitoring trading |
| `sim_layout_dev_split` | pipeline | Layout dev split: VSCode gauche + navigateur droite | layout dev split, code a gauche navigateur a droite |
| `sim_layout_triple` | pipeline | Layout triple: code + terminal + navigateur en quadrants | layout triple, trois fenetres organisees |
| `sim_tout_fermer_propre` | pipeline | Fermeture propre: sauvegarder + fermer apps + minimiser + night light | ferme tout proprement, clean shutdown apps |
| `sim_fin_journee_complete` | pipeline | Fin de journee complete: backup + stats + nuit + economie + verrouiller | fin de journee complete, termine la journee proprement |
| `sim_weekend_mode` | pipeline | Mode weekend: fermer tout le dev + musique + news + Netflix | mode weekend complet, c'est le weekend enfin |
| `sim_urgence_gpu` | pipeline | Urgence GPU: check temperatures + vram + killprocess gourmand | urgence gpu, les gpu chauffent trop |
| `sim_urgence_reseau` | pipeline | Urgence reseau: flush DNS + reset adapter + ping + diagnostic | urgence reseau, internet ne marche plus |
| `sim_urgence_espace` | pipeline | Urgence espace disque: taille disques + temp + downloads + cache | urgence espace disque, plus de place |
| `sim_urgence_performance` | pipeline | Urgence performance: CPU + RAM + processus zombies + services en echec | urgence performance, le pc rame |
| `sim_multitask_dev_trading` | pipeline | Multitask dev+trading: split code/charts + cluster monitoring | multitask dev et trading, code et trade en meme temps |
| `sim_multitask_email_code` | pipeline | Multitask email+code: mails a gauche + VSCode a droite | mails et code, email et dev |
| `sim_focus_extreme` | pipeline | Focus extreme: fermer TOUT sauf VSCode + mute + night + timer 3h | focus extreme, concentration absolue |
| `sim_soiree_gaming` | pipeline | Soiree gaming: fermer dev + performance + Steam + Game Bar | soiree gaming, session jeu video |
| `sim_soiree_film` | pipeline | Soiree film: fermer tout + nuit + volume + Netflix plein ecran | soiree film complete, on regarde un film |
| `sim_soiree_musique` | pipeline | Soiree musique: minimiser + Spotify + ambiance + volume | soiree musique, ambiance musicale complete |
| `sim_maintenance_hebdo` | pipeline | Maintenance hebdo: temp + cache + corbeille + DNS + logs + updates | maintenance hebdomadaire, grand nettoyage de la semaine |
| `sim_backup_hebdo` | pipeline | Backup hebdo: tous les projets + snapshot + stats | backup hebdomadaire, sauvegarde de la semaine |
| `sim_diag_reseau_complet` | pipeline | Diagnostic reseau: ping + DNS + traceroute + ports + IP publique | diagnostic reseau complet, probleme internet complet |
| `sim_diag_wifi` | pipeline | Diagnostic WiFi: signal + SSID + vitesse + DNS + latence | probleme wifi complet, diagnostic wifi |
| `sim_diag_cluster_deep` | pipeline | Diagnostic cluster profond: ping + models + GPU + latence | diagnostic cluster profond, debug cluster complet |
| `sim_audit_securite` | pipeline | Audit securite: ports + connexions + autorun + defender + RDP + admin | audit securite complet, check securite |
| `sim_hardening_check` | pipeline | Check durcissement: firewall + UAC + BitLocker + updates | check hardening, durcissement systeme |
| `sim_audit_mots_de_passe` | pipeline | Audit mots de passe: politique + comptes + expiration | audit mots de passe, politique password |
| `sim_new_project_python` | pipeline | Nouveau projet Python: dossier + venv + git + VSCode | nouveau projet python, init projet python |
| `sim_new_project_node` | pipeline | Nouveau projet Node.js: dossier + npm init + git + VSCode | nouveau projet node, init projet javascript |
| `sim_clone_and_setup` | pipeline | Cloner un repo et l'ouvrir: git clone + VSCode + install deps | clone et setup {repo}, git clone et ouvre {repo} |
| `sim_grand_nettoyage_disque` | pipeline | Grand nettoyage: temp + cache + corbeille + thumbnails + crash dumps + pycache | grand nettoyage du disque, mega clean |
| `sim_archive_vieux_projets` | pipeline | Archiver les projets non modifies depuis 30 jours | archive les vieux projets, zip les anciens projets |
| `sim_scan_fichiers_orphelins` | pipeline | Scanner fichiers orphelins: gros fichiers + doublons + anciens | scan fichiers orphelins, nettoyage intelligent |
| `sim_design_review` | pipeline | Design review: screen ruler + color picker + text extractor + screenshot | review design complet, analyse visuelle |
| `sim_layout_productif` | pipeline | Layout productif: FancyZones + always on top + snap windows | layout productif, arrange mon ecran |
| `sim_copier_texte_image` | pipeline | Copier du texte depuis une image: OCR + clipboard + notification | copie le texte de l'image, ocr et copie |
| `sim_db_health_check` | pipeline | Health check bases: jarvis.db + etoile.db + taille + integrite | health check des bases, check les db |
| `sim_db_backup` | pipeline | Backup toutes les bases de donnees | backup les bases, sauvegarde les db |
| `sim_db_stats` | pipeline | Statistiques des bases: tables, lignes, taille par table | stats des bases, metriques db |
| `sim_docker_full_status` | pipeline | Status Docker complet: containers + images + volumes + espace | status docker complet, etat complet docker |
| `sim_docker_cleanup` | pipeline | Nettoyage Docker: prune containers + images + volumes + build cache | nettoie docker a fond, docker cleanup total |
| `sim_docker_restart_all` | pipeline | Redemarrer tous les conteneurs Docker | redemarre docker, restart all containers |
| `sim_code_review_prep` | pipeline | Preparer une code review: git diff + VSCode + browser GitHub | prepare la code review, session review |
| `sim_code_review_split` | pipeline | Layout code review: VSCode gauche + GitHub droite | layout review, split code review |
| `sim_learn_topic` | pipeline | Session apprentissage: YouTube + docs + notes | session apprentissage {topic}, je veux apprendre {topic} |
| `sim_learn_python` | pipeline | Apprentissage Python: docs + exercices + REPL | apprends moi python, session python |
| `sim_learn_rust` | pipeline | Apprentissage Rust: The Book + playground | apprends moi rust, session rust |
| `sim_layout_4_quadrants` | pipeline | Layout 4 quadrants: Code + Terminal + Browser + Dashboard | 4 quadrants, layout quatre fenetres |
| `sim_layout_trading_full` | pipeline | Layout trading: MEXC + CoinGecko + Terminal + Dashboard | layout trading complet, ecran trading |
| `sim_layout_recherche` | pipeline | Layout recherche: Perplexity + Claude + Notes | layout recherche, ecran recherche |
| `sim_remote_work_start` | pipeline | Setup teletravail: VPN + Slack + Gmail + VSCode + focus | mode teletravail, start remote work |
| `sim_standup_meeting` | pipeline | Preparer le standup: git log hier + today + blocker check | prepare le standup, daily standup |
| `sim_crypto_research` | pipeline | Recherche crypto: CoinGecko + CoinDesk + Etherscan + Reddit | recherche crypto complete, analyse crypto |
| `sim_trading_session` | pipeline | Session trading: MEXC + TradingView + Terminal signaux | session trading complete, lance le trading |
| `sim_post_crash_recovery` | pipeline | Post-crash: check disques + logs + services + GPU + cluster | recovery apres crash, le pc a plante |
| `sim_repair_system` | pipeline | Reparation systeme: DISM + SFC + services restart | repare le systeme, system repair |
| `sim_fullstack_build` | pipeline | Build complet: lint + tests + build + rapport | build complet du projet, full build |
| `sim_deploy_check` | pipeline | Pre-deploy: git status + tests + deps check + commit | check avant deploiement, pre deploy check |
| `sim_git_release` | pipeline | Release: tag + changelog + push tags | fais une release, prepare la release |
| `sim_api_test_session` | pipeline | Session API: Postman + docs + terminal HTTP | session test api, teste les apis |
| `sim_api_endpoints_check` | pipeline | Verifier tous les endpoints locaux (cluster) | check tous les endpoints, verifie les apis du cluster |
| `sim_social_all` | pipeline | Ouvrir tous les reseaux sociaux | ouvre tous les reseaux sociaux, social media complet |
| `sim_content_creation` | pipeline | Setup creation contenu: Canva + Unsplash + notes | setup creation contenu, je vais creer du contenu |
| `sim_design_session` | pipeline | Session design: Figma + Dribbble + Coolors + Font Awesome | session design, mode design |
| `sim_ui_inspiration` | pipeline | Inspiration UI: Dribbble + Behance + Awwwards | inspiration ui, inspiration design |
| `sim_optimize_full` | pipeline | Optimisation: temp + startup + services + defrag check | optimise le systeme, full optimization |
| `sim_cleanup_aggressive` | pipeline | Nettoyage agressif: temp + cache + logs + recycle bin | nettoyage agressif, nettoie tout a fond |
| `sim_learn_coding` | pipeline | Learning code: YouTube + MDN + W3Schools + exercism | session apprentissage code, je veux apprendre |
| `sim_learn_ai` | pipeline | Learning IA: HuggingFace + Papers + Cours + Playground | session apprentissage ia, apprendre le machine learning |
| `sim_pomodoro_25` | pipeline | Pomodoro 25min: timer + focus assist + notification | lance un pomodoro, pomodoro 25 minutes |
| `sim_backup_turbo` | pipeline | Backup turbo: git bundle + zip data + rapport | backup le projet, sauvegarde turbo |
| `sim_backup_verify` | pipeline | Verifier les backups: taille + date + integrite | verifie les backups, check les sauvegardes |
| `sim_morning_routine` | pipeline | Routine matin: meteo + news + mails + cluster + standup | routine du matin, bonjour jarvis |
| `sim_evening_shutdown` | pipeline | Routine soir: git status + save + clear temp + veille | routine du soir, bonsoir jarvis |
| `sim_freelance_setup` | pipeline | Setup freelance: Malt + factures + timer + mail | mode freelance, setup freelance |
| `sim_client_meeting` | pipeline | Prep meeting client: Teams + notes + projet + timer | prepare le meeting client, meeting client |

### SAISIE (4)

| Commande | Type | Description | Triggers |
|----------|------|-------------|----------|
| `texte_majuscule` | powershell | Convertir le presse-papier en majuscules | en majuscules, tout en majuscules |
| `texte_minuscule` | powershell | Convertir le presse-papier en minuscules | en minuscules, tout en minuscules |
| `ouvrir_emojis` | hotkey | Ouvrir le panneau emojis | ouvre les emojis, panneau emojis |
| `ouvrir_dictee` | hotkey | Activer la dictee vocale Windows | dicte, dictee windows |

### SYSTEME (601)

| Commande | Type | Description | Triggers |
|----------|------|-------------|----------|
| `verrouiller` | powershell | Verrouiller le PC | verrouille le pc, verrouille l'ecran |
| `eteindre` | powershell | Eteindre le PC | eteins le pc, eteindre le pc |
| `redemarrer` | powershell | Redemarrer le PC | redemarre le pc, redemarrer le pc |
| `veille` | powershell | Mettre en veille | mets en veille, veille |
| `capture_ecran` | hotkey | Capture d'ecran | capture ecran, screenshot |
| `info_systeme` | jarvis_tool | Infos systeme | info systeme, infos systeme |
| `info_gpu` | jarvis_tool | Infos GPU | info gpu, infos gpu |
| `info_reseau` | jarvis_tool | Infos reseau | info reseau, infos reseau |
| `processus` | jarvis_tool | Lister les processus | liste les processus, montre les processus |
| `kill_process` | jarvis_tool | Tuer un processus | tue le processus {nom}, kill {nom} |
| `wifi_scan` | jarvis_tool | Scanner les reseaux Wi-Fi | scan wifi, wifi scan |
| `ping_host` | jarvis_tool | Ping un hote | ping {host}, teste la connexion a {host} |
| `vider_corbeille` | powershell | Vider la corbeille | vide la corbeille, nettoie la corbeille |
| `mode_nuit` | hotkey | Activer/desactiver le mode nuit | mode nuit, lumiere bleue |
| `ouvrir_run` | hotkey | Ouvrir la boite Executer | ouvre executer, boite de dialogue executer |
| `recherche_windows` | hotkey | Recherche Windows | recherche windows, cherche sur le pc |
| `centre_notifications` | hotkey | Ouvrir le centre de notifications | ouvre les notifications, notifications |
| `ouvrir_widgets` | hotkey | Ouvrir les widgets | ouvre les widgets, widgets |
| `ouvrir_emojis` | hotkey | Ouvrir le panneau emojis | ouvre les emojis, emojis |
| `projeter_ecran` | hotkey | Projeter l'ecran | projette l'ecran, duplique l'ecran |
| `vue_taches` | hotkey | Vue des taches / bureaux virtuels | vue des taches, bureaux virtuels |
| `bureau_suivant` | hotkey | Passer au bureau virtuel suivant | bureau suivant, prochain bureau |
| `bureau_precedent` | hotkey | Passer au bureau virtuel precedent | bureau precedent, bureau virtuel precedent |
| `ouvrir_parametres` | ms_settings | Ouvrir les parametres Windows | ouvre les parametres, parametres |
| `param_wifi` | ms_settings | Parametres Wi-Fi | parametres wifi, reglages wifi |
| `param_bluetooth` | ms_settings | Parametres Bluetooth | parametres bluetooth, reglages bluetooth |
| `param_affichage` | ms_settings | Parametres d'affichage | parametres affichage, reglages ecran |
| `param_son` | ms_settings | Parametres son | parametres son, reglages audio |
| `param_stockage` | ms_settings | Espace disque et stockage | espace disque, stockage |
| `param_mises_a_jour` | ms_settings | Mises a jour Windows | mises a jour, windows update |
| `param_alimentation` | ms_settings | Parametres d'alimentation | parametres alimentation, economie energie |
| `bluetooth_on` | powershell | Activer le Bluetooth | active le bluetooth, allume bluetooth |
| `bluetooth_off` | powershell | Desactiver le Bluetooth | desactive le bluetooth, coupe bluetooth |
| `luminosite_haut` | powershell | Augmenter la luminosite | augmente la luminosite, plus lumineux |
| `luminosite_bas` | powershell | Baisser la luminosite | baisse la luminosite, moins lumineux |
| `lister_services` | jarvis_tool | Lister les services Windows | liste les services, services windows |
| `demarrer_service` | jarvis_tool | Demarrer un service Windows | demarre le service {nom}, start service {nom} |
| `arreter_service` | jarvis_tool | Arreter un service Windows | arrete le service {nom}, stop service {nom} |
| `resolution_ecran` | jarvis_tool | Resolution de l'ecran | resolution ecran, quelle resolution |
| `taches_planifiees` | jarvis_tool | Taches planifiees Windows | taches planifiees, taches automatiques |
| `mode_avion_on` | ms_settings | Activer le mode avion | active le mode avion, mode avion |
| `micro_mute` | powershell | Couper le microphone | coupe le micro, mute le micro |
| `micro_unmute` | powershell | Reactiver le microphone | reactive le micro, unmute micro |
| `param_camera` | ms_settings | Parametres camera | parametres camera, reglages camera |
| `nouveau_bureau` | hotkey | Creer un nouveau bureau virtuel | nouveau bureau, cree un bureau |
| `fermer_bureau` | hotkey | Fermer le bureau virtuel actif | ferme le bureau, ferme ce bureau |
| `zoom_avant` | hotkey | Zoomer | zoom avant, zoom plus |
| `zoom_arriere` | hotkey | Dezoomer | zoom arriere, zoom moins |
| `zoom_reset` | hotkey | Reinitialiser le zoom | zoom normal, zoom reset |
| `imprimer` | hotkey | Imprimer | imprime, imprimer |
| `renommer` | hotkey | Renommer le fichier selectionne | renomme, renommer |
| `supprimer` | hotkey | Supprimer le fichier/element selectionne | supprime, supprimer |
| `proprietes` | hotkey | Proprietes du fichier selectionne | proprietes, proprietes du fichier |
| `actualiser` | hotkey | Actualiser la page ou le dossier | actualise, rafraichis |
| `verrouiller_rapide` | hotkey | Verrouiller le PC rapidement | verrouille, lock |
| `loupe` | hotkey | Activer la loupe / zoom accessibilite | active la loupe, loupe |
| `loupe_off` | hotkey | Desactiver la loupe | desactive la loupe, ferme la loupe |
| `narrateur` | hotkey | Activer/desactiver le narrateur | active le narrateur, narrateur |
| `clavier_visuel` | powershell | Ouvrir le clavier visuel | clavier visuel, ouvre le clavier |
| `dictee` | hotkey | Activer la dictee vocale Windows | dictee, dictee vocale |
| `contraste_eleve` | hotkey | Activer le mode contraste eleve | contraste eleve, high contrast |
| `param_accessibilite` | ms_settings | Parametres d'accessibilite | parametres accessibilite, reglages accessibilite |
| `enregistrer_ecran` | hotkey | Enregistrer l'ecran (Xbox Game Bar) | enregistre l'ecran, lance l'enregistrement |
| `game_bar` | hotkey | Ouvrir la Xbox Game Bar | ouvre la game bar, game bar |
| `snap_layout` | hotkey | Ouvrir les dispositions Snap | snap layout, disposition fenetre |
| `plan_performance` | powershell | Activer le mode performances | mode performance, performances maximales |
| `plan_equilibre` | powershell | Activer le mode equilibre | mode equilibre, plan equilibre |
| `plan_economie` | powershell | Activer le mode economie d'energie | mode economie, economie d'energie |
| `ipconfig` | jarvis_tool | Afficher la configuration IP | montre l'ip, quelle est mon adresse ip |
| `vider_dns` | powershell | Vider le cache DNS | vide le cache dns, flush dns |
| `param_vpn` | ms_settings | Parametres VPN | parametres vpn, reglages vpn |
| `param_proxy` | ms_settings | Parametres proxy | parametres proxy, reglages proxy |
| `etendre_ecran` | powershell | Etendre l'affichage sur un second ecran | etends l'ecran, double ecran |
| `dupliquer_ecran` | powershell | Dupliquer l'affichage | duplique l'ecran, meme image |
| `ecran_principal_seul` | powershell | Afficher uniquement sur l'ecran principal | ecran principal seulement, un seul ecran |
| `ecran_secondaire_seul` | powershell | Afficher uniquement sur le second ecran | ecran secondaire seulement, second ecran uniquement |
| `focus_assist_on` | powershell | Activer l'aide a la concentration (ne pas deranger) | ne pas deranger, focus assist |
| `focus_assist_off` | powershell | Desactiver l'aide a la concentration | desactive ne pas deranger, reactive les notifications |
| `taskbar_hide` | powershell | Masquer la barre des taches | cache la barre des taches, masque la taskbar |
| `taskbar_show` | powershell | Afficher la barre des taches | montre la barre des taches, affiche la taskbar |
| `night_light_on` | powershell | Activer l'eclairage nocturne | active la lumiere nocturne, night light on |
| `night_light_off` | powershell | Desactiver l'eclairage nocturne | desactive la lumiere nocturne, night light off |
| `info_disques` | powershell | Afficher l'espace disque | espace disque, info disques |
| `vider_temp` | powershell | Vider les fichiers temporaires | vide les fichiers temporaires, nettoie les temp |
| `ouvrir_alarmes` | app_open | Ouvrir l'application Horloge/Alarmes | ouvre les alarmes, alarme |
| `historique_activite` | ms_settings | Ouvrir l'historique d'activite Windows | historique activite, timeline |
| `param_clavier` | ms_settings | Parametres clavier | parametres clavier, reglages clavier |
| `param_souris` | ms_settings | Parametres souris | parametres souris, reglages souris |
| `param_batterie` | ms_settings | Parametres batterie | parametres batterie, etat batterie |
| `param_comptes` | ms_settings | Parametres des comptes utilisateur | parametres comptes, comptes utilisateur |
| `param_heure` | ms_settings | Parametres date et heure | parametres heure, reglages heure |
| `param_langue` | ms_settings | Parametres de langue | parametres langue, changer la langue |
| `windows_security` | app_open | Ouvrir Windows Security | ouvre la securite, securite windows |
| `pare_feu` | ms_settings | Parametres du pare-feu | parametres pare-feu, firewall |
| `partage_proximite` | ms_settings | Parametres de partage a proximite | partage a proximite, nearby sharing |
| `hotspot` | ms_settings | Activer le point d'acces mobile | point d'acces, hotspot |
| `defrag_disque` | powershell | Optimiser les disques (defragmentation) | defragmente, optimise les disques |
| `gestion_disques` | powershell | Ouvrir le gestionnaire de disques | gestionnaire de disques, gestion des disques |
| `variables_env` | powershell | Ouvrir les variables d'environnement | variables d'environnement, variables env |
| `evenements_windows` | powershell | Ouvrir l'observateur d'evenements | observateur d'evenements, event viewer |
| `moniteur_ressources` | powershell | Ouvrir le moniteur de ressources | moniteur de ressources, resource monitor |
| `info_systeme_detaille` | powershell | Ouvrir les informations systeme detaillees | informations systeme detaillees, msinfo |
| `nettoyage_disque` | powershell | Ouvrir le nettoyage de disque Windows | nettoyage de disque, disk cleanup |
| `gestionnaire_peripheriques` | powershell | Ouvrir le gestionnaire de peripheriques | gestionnaire de peripheriques, device manager |
| `connexions_reseau` | powershell | Ouvrir les connexions reseau | connexions reseau, adaptateurs reseau |
| `programmes_installees` | ms_settings | Ouvrir programmes et fonctionnalites | programmes installes, applications installees |
| `demarrage_apps` | ms_settings | Gerer les applications au demarrage | applications demarrage, programmes au demarrage |
| `param_confidentialite` | ms_settings | Parametres de confidentialite | parametres confidentialite, privacy |
| `param_reseau_avance` | ms_settings | Parametres reseau avances | parametres reseau avances, reseau avance |
| `partager_ecran` | hotkey | Partager l'ecran via Miracast | partage l'ecran, miracast |
| `param_imprimantes` | ms_settings | Parametres imprimantes et scanners | parametres imprimantes, imprimante |
| `param_fond_ecran` | ms_settings | Personnaliser le fond d'ecran | fond d'ecran, change le fond |
| `param_couleurs` | ms_settings | Personnaliser les couleurs Windows | couleurs windows, couleur d'accent |
| `param_ecran_veille` | ms_settings | Parametres ecran de verrouillage | ecran de veille, ecran de verrouillage |
| `param_polices` | ms_settings | Gerer les polices installees | polices, fonts |
| `param_themes` | ms_settings | Gerer les themes Windows | themes windows, change le theme |
| `mode_sombre` | powershell | Activer le mode sombre Windows | active le mode sombre, dark mode on |
| `mode_clair` | powershell | Activer le mode clair Windows | active le mode clair, light mode on |
| `param_son_avance` | ms_settings | Parametres audio avances | parametres audio avances, son avance |
| `param_hdr` | ms_settings | Parametres HDR | parametres hdr, active le hdr |
| `ouvrir_regedit` | powershell | Ouvrir l'editeur de registre | ouvre le registre, regedit |
| `ouvrir_mmc` | powershell | Ouvrir la console de gestion (MMC) | console de gestion, mmc |
| `ouvrir_politique_groupe` | powershell | Ouvrir l'editeur de strategie de groupe | politique de groupe, group policy |
| `taux_rafraichissement` | ms_settings | Parametres taux de rafraichissement ecran | taux de rafraichissement, hertz ecran |
| `param_notifications_avance` | ms_settings | Parametres notifications avances | parametres notifications avances, gere les notifications |
| `param_multitache` | ms_settings | Parametres multitache Windows | parametres multitache, multitasking |
| `apps_par_defaut` | ms_settings | Gerer les applications par defaut | applications par defaut, apps par defaut |
| `param_stockage_avance` | ms_settings | Gestion du stockage et assistant | assistant stockage, nettoyage automatique |
| `sauvegarder_windows` | ms_settings | Parametres de sauvegarde Windows | sauvegarde windows, backup windows |
| `restauration_systeme` | powershell | Ouvrir la restauration du systeme | restauration systeme, point de restauration |
| `a_propos_pc` | ms_settings | Informations sur le PC (A propos) | a propos du pc, about pc |
| `param_ethernet` | ms_settings | Parametres Ethernet | parametres ethernet, cable reseau |
| `param_data_usage` | ms_settings | Utilisation des donnees reseau | utilisation donnees, data usage |
| `tracert` | powershell | Tracer la route vers un hote | trace la route vers {host}, traceroute {host} |
| `netstat` | powershell | Afficher les connexions reseau actives | connexions actives, netstat |
| `uptime` | powershell | Temps de fonctionnement du PC | uptime, depuis quand le pc tourne |
| `temperature_cpu` | powershell | Temperature du processeur | temperature cpu, temperature processeur |
| `liste_utilisateurs` | powershell | Lister les utilisateurs du PC | liste les utilisateurs, quels utilisateurs |
| `adresse_mac` | powershell | Afficher les adresses MAC | adresse mac, mac address |
| `vitesse_reseau` | powershell | Tester la vitesse de la carte reseau | vitesse reseau, speed test |
| `param_optionnel` | ms_settings | Gerer les fonctionnalites optionnelles Windows | fonctionnalites optionnelles, optional features |
| `ouvrir_sandbox` | powershell | Ouvrir Windows Sandbox | ouvre la sandbox, sandbox |
| `verifier_fichiers` | powershell | Verifier l'integrite des fichiers systeme | verifie les fichiers systeme, sfc scan |
| `wifi_connecter` | powershell | Se connecter a un reseau Wi-Fi | connecte moi au wifi {ssid}, connecte au wifi {ssid} |
| `wifi_deconnecter` | powershell | Se deconnecter du Wi-Fi | deconnecte le wifi, deconnecte du wifi |
| `wifi_profils` | powershell | Lister les profils Wi-Fi sauvegardes | profils wifi, wifi sauvegardes |
| `clipboard_vider` | powershell | Vider le presse-papier | vide le presse-papier, efface le clipboard |
| `clipboard_compter` | powershell | Compter les caracteres du presse-papier | combien de caracteres dans le presse-papier, taille du presse-papier |
| `recherche_everywhere` | powershell | Rechercher partout sur le PC | recherche partout {terme}, cherche partout {terme} |
| `tache_planifier` | powershell | Creer une tache planifiee | planifie une tache {nom}, cree une tache planifiee {nom} |
| `variables_utilisateur` | powershell | Afficher les variables d'environnement utilisateur | variables utilisateur, mes variables |
| `chemin_path` | powershell | Afficher le PATH systeme | montre le path, affiche le path |
| `deconnexion_windows` | powershell | Deconnexion de la session Windows | deconnecte moi, deconnexion |
| `hibernation` | powershell | Mettre en hibernation | hiberne, hibernation |
| `planifier_arret` | powershell | Planifier un arret dans X minutes | eteins dans {minutes} minutes, arret dans {minutes} minutes |
| `annuler_arret` | powershell | Annuler un arret programme | annule l'arret, annuler shutdown |
| `heure_actuelle` | powershell | Donner l'heure actuelle | quelle heure est-il, quelle heure |
| `date_actuelle` | powershell | Donner la date actuelle | quelle date, quel jour on est |
| `ecran_externe_etendre` | powershell | Etendre sur ecran externe | etends l'ecran, ecran etendu |
| `ecran_duplique` | powershell | Dupliquer l'ecran | duplique l'ecran, ecran duplique |
| `ecran_interne_seul` | powershell | Ecran interne uniquement | ecran principal seulement, ecran interne seul |
| `ecran_externe_seul` | powershell | Ecran externe uniquement | ecran externe seulement, ecran externe seul |
| `ram_usage` | powershell | Utilisation de la RAM | utilisation ram, combien de ram |
| `cpu_usage` | powershell | Utilisation du processeur | utilisation cpu, charge du processeur |
| `cpu_info` | powershell | Informations sur le processeur | quel processeur, info cpu |
| `ram_info` | powershell | Informations detaillees sur la RAM | info ram, details ram |
| `batterie_niveau` | powershell | Niveau de batterie | niveau de batterie, combien de batterie |
| `disque_sante` | powershell | Sante des disques (SMART) | sante des disques, etat des disques |
| `carte_mere` | powershell | Informations carte mere | info carte mere, quelle carte mere |
| `bios_info` | powershell | Informations BIOS | info bios, version bios |
| `top_ram` | powershell | Top 10 processus par RAM | quoi consomme la ram, top ram |
| `top_cpu` | powershell | Top 10 processus par CPU | quoi consomme le cpu, top cpu |
| `carte_graphique` | powershell | Informations carte graphique | quelle carte graphique, info gpu detaille |
| `windows_version` | powershell | Version exacte de Windows | version de windows, quelle version windows |
| `dns_changer_google` | powershell | Changer DNS vers Google (8.8.8.8) | mets le dns google, change le dns en google |
| `dns_changer_cloudflare` | powershell | Changer DNS vers Cloudflare (1.1.1.1) | mets le dns cloudflare, change le dns en cloudflare |
| `dns_reset` | powershell | Remettre le DNS en automatique | dns automatique, reset le dns |
| `ports_ouverts` | powershell | Lister les ports ouverts | ports ouverts, quels ports sont ouverts |
| `ip_publique` | powershell | Obtenir l'IP publique | mon ip publique, quelle est mon ip publique |
| `partage_reseau` | powershell | Lister les partages reseau | partages reseau, dossiers partages |
| `connexions_actives` | powershell | Connexions reseau actives | connexions actives, qui est connecte |
| `vitesse_reseau` | powershell | Vitesse de la carte reseau | vitesse reseau, debit carte reseau |
| `arp_table` | powershell | Afficher la table ARP | table arp, arp |
| `test_port` | powershell | Tester si un port est ouvert sur une machine | teste le port {port} sur {host}, port {port} ouvert sur {host} |
| `route_table` | powershell | Afficher la table de routage | table de routage, routes reseau |
| `nslookup` | powershell | Resolution DNS d'un domaine | nslookup {domaine}, resous {domaine} |
| `certificat_ssl` | powershell | Verifier le certificat SSL d'un site | certificat ssl de {site}, check ssl {site} |
| `voir_logs` | powershell | Voir les logs systeme ou JARVIS | les logs, voir les logs |
| `ouvrir_widgets` | hotkey | Ouvrir le panneau Widgets Windows | ouvre les widgets, widgets windows |
| `partage_proximite_on` | powershell | Activer le partage de proximite | active le partage de proximite, nearby sharing on |
| `screen_recording` | hotkey | Lancer l'enregistrement d'ecran (Game Bar) | enregistre l'ecran, screen recording |
| `game_bar` | hotkey | Ouvrir la Game Bar Xbox | ouvre la game bar, game bar |
| `parametres_notifications` | powershell | Ouvrir les parametres de notifications | parametres notifications, gere les notifications |
| `parametres_apps_defaut` | powershell | Ouvrir les apps par defaut | apps par defaut, applications par defaut |
| `parametres_about` | powershell | A propos de ce PC | a propos du pc, about this pc |
| `verifier_sante_disque` | powershell | Verifier la sante des disques | sante des disques, health check disque |
| `vitesse_internet` | powershell | Tester la vitesse internet | test de vitesse, speed test |
| `historique_mises_a_jour` | powershell | Voir l'historique des mises a jour Windows | historique updates, dernieres mises a jour |
| `taches_planifiees` | powershell | Lister les taches planifiees | taches planifiees, scheduled tasks |
| `demarrage_apps` | powershell | Voir les apps au demarrage | apps au demarrage, startup apps |
| `certificats_ssl` | powershell | Verifier un certificat SSL | verifie le ssl de {site}, certificat ssl {site} |
| `audio_sortie` | powershell | Changer la sortie audio | change la sortie audio, sortie audio |
| `audio_entree` | powershell | Configurer le microphone | configure le micro, entree audio |
| `volume_app` | powershell | Mixer de volume par application | mixer volume, volume par application |
| `micro_mute_toggle` | powershell | Couper/reactiver le micro | coupe le micro, mute le micro |
| `liste_imprimantes` | powershell | Lister les imprimantes | liste les imprimantes, quelles imprimantes |
| `imprimante_defaut` | powershell | Voir l'imprimante par defaut | imprimante par defaut, quelle imprimante |
| `param_imprimantes` | powershell | Ouvrir les parametres imprimantes | parametres imprimantes, settings imprimantes |
| `sandbox_ouvrir` | powershell | Ouvrir Windows Sandbox | ouvre la sandbox, windows sandbox |
| `plan_alimentation_actif` | powershell | Voir le plan d'alimentation actif | quel plan alimentation, power plan actif |
| `batterie_rapport` | powershell | Generer un rapport de batterie | rapport batterie, battery report |
| `ecran_timeout` | powershell | Configurer la mise en veille ecran | timeout ecran, ecran en veille apres |
| `detecter_ecrans` | powershell | Detecter les ecrans connectes | detecte les ecrans, detect displays |
| `param_affichage` | powershell | Ouvrir les parametres d'affichage | parametres affichage, settings display |
| `kill_process_nom` | powershell | Tuer un processus par nom | tue le processus {nom}, kill {nom} |
| `processus_details` | powershell | Details d'un processus | details du processus {nom}, info processus {nom} |
| `diagnostic_reseau` | powershell | Lancer un diagnostic reseau complet | diagnostic reseau, diagnostique le reseau |
| `wifi_mot_de_passe` | powershell | Afficher le mot de passe WiFi actuel | mot de passe wifi, password wifi |
| `ouvrir_evenements` | powershell | Ouvrir l'observateur d'evenements | observateur evenements, event viewer |
| `ouvrir_services` | powershell | Ouvrir les services Windows | ouvre les services, services windows |
| `ouvrir_moniteur_perf` | powershell | Ouvrir le moniteur de performances | moniteur de performance, performance monitor |
| `ouvrir_fiabilite` | powershell | Ouvrir le moniteur de fiabilite | moniteur de fiabilite, reliability monitor |
| `action_center` | hotkey | Ouvrir le centre de notifications | centre de notifications, notification center |
| `quick_settings` | hotkey | Ouvrir les parametres rapides | parametres rapides, quick settings |
| `search_windows` | hotkey | Ouvrir la recherche Windows | recherche windows, windows search |
| `hyper_v_manager` | powershell | Ouvrir le gestionnaire Hyper-V | ouvre hyper-v, lance hyper-v |
| `storage_sense` | powershell | Activer l'assistant de stockage | active l'assistant de stockage, storage sense |
| `creer_point_restauration` | powershell | Creer un point de restauration systeme | cree un point de restauration, point de restauration |
| `voir_hosts` | powershell | Afficher le fichier hosts | montre le fichier hosts, affiche hosts |
| `dxdiag` | powershell | Lancer le diagnostic DirectX | lance dxdiag, diagnostic directx |
| `memoire_diagnostic` | powershell | Lancer le diagnostic memoire Windows | diagnostic memoire, teste la memoire |
| `reset_reseau` | powershell | Reinitialiser la pile reseau | reinitialise le reseau, reset reseau |
| `bitlocker_status` | powershell | Verifier le statut BitLocker | statut bitlocker, etat bitlocker |
| `windows_update_pause` | powershell | Mettre en pause les mises a jour Windows | pause les mises a jour, suspends les mises a jour |
| `mode_developpeur` | powershell | Activer/desactiver le mode developpeur | active le mode developpeur, mode developpeur |
| `remote_desktop` | powershell | Parametres Bureau a distance | bureau a distance, remote desktop |
| `credential_manager` | powershell | Ouvrir le gestionnaire d'identifiants | gestionnaire d'identifiants, credential manager |
| `certmgr` | powershell | Ouvrir le gestionnaire de certificats | gestionnaire de certificats, certificats windows |
| `chkdsk_check` | powershell | Verifier les erreurs du disque | verifie le disque, check disk |
| `file_history` | powershell | Parametres historique des fichiers | historique des fichiers, file history |
| `troubleshoot_reseau` | powershell | Lancer le depannage reseau | depanne le reseau, depannage reseau |
| `troubleshoot_audio` | powershell | Lancer le depannage audio | depanne le son, depannage audio |
| `troubleshoot_update` | powershell | Lancer le depannage Windows Update | depanne windows update, depannage mises a jour |
| `power_options` | powershell | Options d'alimentation avancees | options d'alimentation, power options |
| `copilot_parametres` | ms_settings | Parametres de Copilot | parametres copilot, reglages copilot |
| `cortana_desactiver` | powershell | Desactiver Cortana | desactive cortana, coupe cortana |
| `capture_fenetre` | hotkey | Capturer la fenetre active | capture la fenetre, screenshot fenetre |
| `capture_retardee` | powershell | Capture d'ecran avec delai | capture retardee, screenshot retarde |
| `planificateur_ouvrir` | powershell | Ouvrir le planificateur de taches | planificateur de taches, ouvre le planificateur |
| `creer_tache_planifiee` | powershell | Creer une tache planifiee | cree une tache planifiee, nouvelle tache planifiee |
| `lister_usb` | powershell | Lister les peripheriques USB connectes | liste les usb, peripheriques usb |
| `ejecter_usb` | powershell | Ejecter un peripherique USB en securite | ejecte l'usb, ejecter usb |
| `peripheriques_connectes` | powershell | Lister tous les peripheriques connectes | peripheriques connectes, liste les peripheriques |
| `lister_adaptateurs` | powershell | Lister les adaptateurs reseau | liste les adaptateurs reseau, adaptateurs reseau |
| `desactiver_wifi_adaptateur` | powershell | Desactiver l'adaptateur Wi-Fi | desactive le wifi, coupe l'adaptateur wifi |
| `activer_wifi_adaptateur` | powershell | Activer l'adaptateur Wi-Fi | active l'adaptateur wifi, reactive le wifi |
| `firewall_status` | powershell | Afficher le statut du pare-feu | statut pare-feu, statut firewall |
| `firewall_regles` | powershell | Lister les regles du pare-feu | regles pare-feu, regles firewall |
| `firewall_reset` | powershell | Reinitialiser le pare-feu | reinitialise le pare-feu, reset firewall |
| `ajouter_langue` | ms_settings | Ajouter une langue au systeme | ajoute une langue, installer une langue |
| `ajouter_clavier` | ms_settings | Ajouter une disposition de clavier | ajoute un clavier, nouveau clavier |
| `langues_installees` | powershell | Lister les langues installees | langues installees, quelles langues |
| `synchroniser_heure` | powershell | Synchroniser l'heure avec le serveur NTP | synchronise l'heure, sync heure |
| `serveur_ntp` | powershell | Afficher le serveur NTP configure | serveur ntp, quel serveur ntp |
| `windows_hello` | ms_settings | Parametres Windows Hello | windows hello, hello biometrique |
| `securite_comptes` | ms_settings | Securite des comptes Windows | securite des comptes, securite compte |
| `activation_windows` | powershell | Verifier l'activation Windows | activation windows, windows active |
| `recuperation_systeme` | ms_settings | Options de recuperation systeme | recuperation systeme, options de recuperation |
| `gpu_temperatures` | powershell | Temperatures GPU via nvidia-smi | temperatures gpu, gpu temperature |
| `vram_usage` | powershell | Utilisation VRAM de toutes les GPU | utilisation vram, vram utilisee |
| `disk_io` | powershell | Activite I/O des disques | activite des disques, io disques |
| `network_io` | powershell | Debit reseau en temps reel | debit reseau, trafic reseau |
| `services_failed` | powershell | Services Windows en echec | services en echec, services plantes |
| `event_errors` | powershell | Dernières erreurs systeme (Event Log) | erreurs systeme recentes, derniers errors |
| `boot_time` | powershell | Temps de demarrage du dernier boot | temps de demarrage, boot time |
| `nettoyer_prefetch` | powershell | Nettoyer le dossier Prefetch | nettoie prefetch, vide prefetch |
| `nettoyer_thumbnails` | powershell | Nettoyer le cache des miniatures | nettoie les miniatures, vide le cache miniatures |
| `nettoyer_logs` | powershell | Nettoyer les vieux logs | nettoie les logs, supprime les vieux logs |
| `scan_ports_local` | powershell | Scanner les ports ouverts localement | scan mes ports, scan ports local |
| `connexions_suspectes` | powershell | Verifier les connexions sortantes suspectes | connexions suspectes, qui se connecte dehors |
| `autorun_check` | powershell | Verifier les programmes au demarrage | quoi se lance au demarrage, autorun check |
| `defender_scan_rapide` | powershell | Lancer un scan rapide Windows Defender | scan antivirus, lance un scan defender |
| `defender_status` | powershell | Statut de Windows Defender | statut defender, etat antivirus |
| `top_cpu_processes` | powershell | Top 10 processus par CPU | top cpu, processus gourmands cpu |
| `top_ram_processes` | powershell | Top 10 processus par RAM | top ram, processus gourmands ram |
| `uptime_system` | powershell | Uptime du systeme Windows | uptime, depuis combien de temps le pc tourne |
| `windows_update_check` | powershell | Verifier les mises a jour Windows disponibles | mises a jour windows, windows update |
| `ip_publique_externe` | powershell | Obtenir l'adresse IP publique | ip publique, quelle est mon ip |
| `latence_cluster` | powershell | Ping de latence vers les noeuds du cluster | latence cluster, ping le cluster ia |
| `wifi_info` | powershell | Informations sur la connexion WiFi active | info wifi, quel wifi |
| `espace_disques` | powershell | Espace libre sur tous les disques | espace disque, combien d'espace libre |
| `gros_fichiers_bureau` | powershell | Top 10 plus gros fichiers du bureau | plus gros fichiers, gros fichiers bureau |
| `processus_zombies` | powershell | Detecter les processus qui ne repondent pas | processus zombies, processus bloques |
| `dernier_crash` | powershell | Dernier crash ou erreur critique Windows | dernier crash, derniere erreur critique |
| `temps_allumage_apps` | powershell | Depuis combien de temps chaque app tourne | duree des apps, depuis quand les apps tournent |
| `taille_cache_navigateur` | powershell | Taille des caches navigateur Chrome/Edge | taille cache navigateur, cache chrome |
| `nettoyer_cache_navigateur` | powershell | Vider les caches Chrome et Edge | vide le cache navigateur, nettoie le cache chrome |
| `nettoyer_crash_dumps` | powershell | Supprimer les crash dumps Windows | nettoie les crash dumps, supprime les dumps |
| `nettoyer_windows_old` | powershell | Taille du dossier Windows.old (ancien systeme) | taille windows old, windows old |
| `gpu_power_draw` | powershell | Consommation electrique des GPU | consommation gpu, watt gpu |
| `gpu_fan_speed` | powershell | Vitesse des ventilateurs GPU | ventilateurs gpu, fans gpu |
| `gpu_driver_version` | powershell | Version du driver NVIDIA | version driver nvidia, driver gpu |
| `cluster_latence_detaillee` | powershell | Latence detaillee de chaque noeud du cluster avec modeles | latence detaillee cluster, ping detaille cluster |
| `installed_apps_list` | powershell | Lister les applications installees | liste les applications, apps installees |
| `hotfix_history` | powershell | Historique des correctifs Windows installes | historique hotfix, correctifs installes |
| `scheduled_tasks_active` | powershell | Taches planifiees actives | taches planifiees actives, scheduled tasks |
| `tpm_info` | powershell | Informations sur le module TPM | info tpm, tpm status |
| `printer_list` | powershell | Imprimantes installees et leur statut | liste les imprimantes, imprimantes installees |
| `startup_impact` | powershell | Impact des programmes au demarrage sur le boot | impact demarrage, startup impact |
| `system_info_detaille` | powershell | Infos systeme detaillees (OS, BIOS, carte mere) | infos systeme detaillees, system info |
| `ram_slots_detail` | powershell | Details des barrettes RAM (type, vitesse, slots) | details ram, barrettes ram |
| `cpu_details` | powershell | Details du processeur (coeurs, threads, frequence) | details cpu, info processeur |
| `network_adapters_list` | powershell | Adaptateurs reseau actifs et leur configuration | adaptateurs reseau, interfaces reseau |
| `dns_cache_view` | powershell | Voir le cache DNS local | cache dns, dns cache |
| `recycle_bin_size` | powershell | Taille de la corbeille | taille corbeille, poids corbeille |
| `temp_folder_size` | powershell | Taille du dossier temporaire | taille du temp, dossier temp |
| `last_shutdown_time` | powershell | Heure du dernier arret du PC | dernier arret, quand le pc s'est eteint |
| `bluescreen_history` | powershell | Historique des ecrans bleus (BSOD) | ecrans bleus, bsod |
| `disk_smart_health` | powershell | Etat de sante SMART des disques | sante disques, smart disques |
| `firewall_rules_count` | powershell | Nombre de regles firewall par profil | regles firewall, combien de regles pare-feu |
| `env_variables_key` | powershell | Variables d'environnement cles (PATH, TEMP, etc.) | variables environnement, env vars |
| `sfc_scan` | powershell | Lancer un scan d'integrite systeme (sfc /scannow) | scan integrite, sfc scannow |
| `dism_health_check` | powershell | Verifier la sante de l'image Windows (DISM) | dism health, sante windows |
| `system_restore_points` | powershell | Lister les points de restauration systeme | points de restauration, restore points |
| `usb_devices_list` | powershell | Lister les peripheriques USB connectes | peripheriques usb, usb connectes |
| `bluetooth_devices` | powershell | Lister les peripheriques Bluetooth | peripheriques bluetooth, bluetooth connectes |
| `certificates_list` | powershell | Certificats systeme installes (racine) | certificats installes, certificates |
| `page_file_info` | powershell | Configuration du fichier de pagination (swap) | page file, fichier de pagination |
| `windows_features` | powershell | Fonctionnalites Windows activees | fonctionnalites windows, features windows |
| `power_plan_active` | powershell | Plan d'alimentation actif et ses details | plan alimentation, power plan |
| `bios_version` | powershell | Version du BIOS et date | version bios, bios info |
| `windows_version_detail` | powershell | Version detaillee de Windows (build, edition) | version windows, quelle version windows |
| `network_connections_count` | powershell | Nombre de connexions reseau actives par etat | connexions reseau actives, combien de connexions |
| `drivers_probleme` | powershell | Pilotes en erreur ou problematiques | pilotes en erreur, drivers probleme |
| `shared_folders` | powershell | Dossiers partages sur ce PC | dossiers partages, partages reseau |
| `focus_app_name` | powershell | Mettre le focus sur une application par son nom | va sur {app}, bascule sur {app} |
| `fermer_app_name` | powershell | Fermer une application par son nom | ferme {app}, tue {app} |
| `liste_fenetres_ouvertes` | powershell | Lister toutes les fenetres ouvertes avec leur titre | quelles fenetres sont ouvertes, liste les fenetres |
| `fenetre_toujours_visible` | powershell | Rendre la fenetre active always-on-top | toujours visible, always on top |
| `deplacer_fenetre_moniteur` | hotkey | Deplacer la fenetre active vers l'autre moniteur | fenetre autre ecran, deplace sur l'autre ecran |
| `centrer_fenetre` | powershell | Centrer la fenetre active sur l'ecran | centre la fenetre, fenetre au centre |
| `switch_audio_output` | powershell | Lister et changer la sortie audio | change la sortie audio, switch audio |
| `toggle_wifi` | powershell | Activer/desactiver le WiFi | toggle wifi, active le wifi |
| `toggle_bluetooth` | powershell | Activer/desactiver le Bluetooth | toggle bluetooth, active le bluetooth |
| `toggle_dark_mode` | powershell | Basculer entre mode sombre et mode clair | mode sombre, dark mode |
| `taper_date` | powershell | Taper la date du jour automatiquement | tape la date, ecris la date |
| `taper_heure` | powershell | Taper l'heure actuelle automatiquement | tape l'heure, ecris l'heure |
| `vider_clipboard` | powershell | Vider le presse-papier | vide le presse papier, clear clipboard |
| `dismiss_notifications` | hotkey | Fermer toutes les notifications Windows | ferme les notifications, dismiss notifications |
| `ouvrir_gestionnaire_peripheriques` | powershell | Ouvrir le Gestionnaire de peripheriques | gestionnaire de peripheriques, device manager |
| `ouvrir_gestionnaire_disques` | powershell | Ouvrir la Gestion des disques | gestion des disques, disk management |
| `ouvrir_services_windows` | powershell | Ouvrir la console Services Windows | services windows, console services |
| `ouvrir_registre` | powershell | Ouvrir l'editeur de registre | editeur de registre, regedit |
| `ouvrir_event_viewer` | powershell | Ouvrir l'observateur d'evenements | observateur d'evenements, event viewer |
| `hibernation_profonde` | powershell | Mettre le PC en hibernation profonde | hiberne le pc maintenant, hibernation profonde |
| `restart_bios` | powershell | Redemarrer vers le BIOS/UEFI | redemarre dans le bios, restart bios |
| `taskbar_app_1` | hotkey | Lancer la 1ere app epinglee dans la taskbar | premiere app taskbar, app 1 taskbar |
| `taskbar_app_2` | hotkey | Lancer la 2eme app epinglee dans la taskbar | deuxieme app taskbar, app 2 taskbar |
| `taskbar_app_3` | hotkey | Lancer la 3eme app epinglee dans la taskbar | troisieme app taskbar, app 3 taskbar |
| `taskbar_app_4` | hotkey | Lancer la 4eme app epinglee dans la taskbar | quatrieme app taskbar, app 4 taskbar |
| `taskbar_app_5` | hotkey | Lancer la 5eme app epinglee dans la taskbar | cinquieme app taskbar, app 5 taskbar |
| `fenetre_autre_bureau` | hotkey | Deplacer la fenetre vers le bureau virtuel suivant | fenetre bureau suivant, deplace la fenetre sur l'autre bureau |
| `browser_retour` | hotkey | Page precedente dans le navigateur | page precedente, retour arriere |
| `browser_avancer` | hotkey | Page suivante dans le navigateur | page suivante, avance |
| `browser_rafraichir` | hotkey | Rafraichir la page web | rafraichis la page, reload |
| `browser_hard_refresh` | hotkey | Rafraichir sans cache | hard refresh, rafraichis sans cache |
| `browser_private` | hotkey | Ouvrir une fenetre de navigation privee | navigation privee, fenetre privee |
| `browser_bookmark` | hotkey | Ajouter la page aux favoris | ajoute aux favoris, bookmark |
| `browser_address_bar` | hotkey | Aller dans la barre d'adresse | barre d'adresse, address bar |
| `browser_fermer_tous_onglets` | powershell | Fermer tous les onglets sauf l'actif | ferme tous les onglets, close all tabs |
| `browser_epingler_onglet` | powershell | Epingler/detacher l'onglet actif | epingle l'onglet, pin tab |
| `texte_debut_ligne` | hotkey | Aller au debut de la ligne | debut de ligne, home |
| `texte_fin_ligne` | hotkey | Aller a la fin de la ligne | fin de ligne, end |
| `texte_debut_document` | hotkey | Aller au debut du document | debut du document, tout en haut |
| `texte_fin_document` | hotkey | Aller a la fin du document | fin du document, tout en bas |
| `texte_selectionner_ligne` | hotkey | Selectionner la ligne entiere | selectionne la ligne, select line |
| `texte_supprimer_ligne` | hotkey | Supprimer la ligne entiere (VSCode) | supprime la ligne, delete line |
| `texte_dupliquer_ligne` | hotkey | Dupliquer la ligne (VSCode) | duplique la ligne, duplicate line |
| `texte_deplacer_ligne_haut` | hotkey | Deplacer la ligne vers le haut (VSCode) | monte la ligne, move line up |
| `texte_deplacer_ligne_bas` | hotkey | Deplacer la ligne vers le bas (VSCode) | descends la ligne, move line down |
| `vscode_palette` | hotkey | Ouvrir la palette de commandes VSCode | palette de commandes, command palette |
| `vscode_terminal` | hotkey | Ouvrir/fermer le terminal VSCode | terminal vscode, ouvre le terminal intergre |
| `vscode_sidebar` | hotkey | Afficher/masquer la sidebar VSCode | sidebar vscode, panneau lateral |
| `vscode_go_to_file` | hotkey | Rechercher et ouvrir un fichier dans VSCode | ouvre un fichier vscode, go to file |
| `vscode_go_to_line` | hotkey | Aller a une ligne dans VSCode | va a la ligne, go to line |
| `vscode_split_editor` | hotkey | Diviser l'editeur VSCode en deux | divise l'editeur, split editor |
| `vscode_close_all` | hotkey | Fermer tous les fichiers ouverts dans VSCode | ferme tous les fichiers vscode, close all tabs vscode |
| `explorer_dossier_parent` | hotkey | Remonter au dossier parent dans l'Explorateur | dossier parent, remonte d'un dossier |
| `explorer_nouveau_dossier` | hotkey | Creer un nouveau dossier dans l'Explorateur | nouveau dossier, cree un dossier |
| `explorer_afficher_caches` | powershell | Afficher les fichiers caches dans l'Explorateur | montre les fichiers caches, fichiers caches |
| `explorer_masquer_caches` | powershell | Masquer les fichiers caches | cache les fichiers caches, masque les fichiers invisibles |
| `scroll_haut` | hotkey | Scroller vers le haut | scroll up, monte la page |
| `scroll_bas` | hotkey | Scroller vers le bas | scroll down, descends la page |
| `page_haut` | hotkey | Page precedente (Page Up) | page up, page precedente |
| `page_bas` | hotkey | Page suivante (Page Down) | page down, page suivante |
| `scroll_rapide_haut` | hotkey | Scroller rapidement vers le haut (5 pages) | scroll rapide haut, monte vite |
| `scroll_rapide_bas` | hotkey | Scroller rapidement vers le bas (5 pages) | scroll rapide bas, descends vite |
| `snap_gauche` | hotkey | Ancrer la fenetre a gauche (moitie ecran) | fenetre a gauche, snap left |
| `snap_droite` | hotkey | Ancrer la fenetre a droite (moitie ecran) | fenetre a droite, snap right |
| `snap_haut_gauche` | hotkey | Ancrer la fenetre en haut a gauche (quart ecran) | fenetre haut gauche, snap top left |
| `snap_bas_gauche` | hotkey | Ancrer la fenetre en bas a gauche (quart ecran) | fenetre bas gauche, snap bottom left |
| `snap_haut_droite` | hotkey | Ancrer la fenetre en haut a droite (quart ecran) | fenetre haut droite, snap top right |
| `snap_bas_droite` | hotkey | Ancrer la fenetre en bas a droite (quart ecran) | fenetre bas droite, snap bottom right |
| `restaurer_fenetre` | hotkey | Restaurer la fenetre a sa taille precedente | restaure la fenetre, taille normale |
| `onglet_1` | hotkey | Aller au 1er onglet | onglet 1, premier onglet |
| `onglet_2` | hotkey | Aller au 2eme onglet | onglet 2, deuxieme onglet |
| `onglet_3` | hotkey | Aller au 3eme onglet | onglet 3, troisieme onglet |
| `onglet_4` | hotkey | Aller au 4eme onglet | onglet 4, quatrieme onglet |
| `onglet_5` | hotkey | Aller au 5eme onglet | onglet 5, cinquieme onglet |
| `onglet_dernier` | hotkey | Aller au dernier onglet | dernier onglet, last tab |
| `nouvel_onglet_vierge` | hotkey | Ouvrir un nouvel onglet vierge | nouvel onglet vierge, new tab blank |
| `mute_onglet` | powershell | Couper le son de l'onglet (clic droit requis) | mute l'onglet, coupe le son de l'onglet |
| `browser_devtools` | hotkey | Ouvrir les DevTools du navigateur | ouvre les devtools, developer tools |
| `browser_devtools_console` | hotkey | Ouvrir la console DevTools directement | ouvre la console navigateur, console chrome |
| `browser_source_view` | hotkey | Voir le code source de la page | voir le code source, view source |
| `curseur_mot_gauche` | hotkey | Deplacer le curseur d'un mot a gauche | mot precedent, word left |
| `curseur_mot_droite` | hotkey | Deplacer le curseur d'un mot a droite | mot suivant, word right |
| `selectionner_mot` | hotkey | Selectionner le mot sous le curseur | selectionne le mot, select word |
| `selectionner_mot_gauche` | hotkey | Etendre la selection d'un mot a gauche | selection mot gauche, select word left |
| `selectionner_mot_droite` | hotkey | Etendre la selection d'un mot a droite | selection mot droite, select word right |
| `selectionner_tout` | hotkey | Selectionner tout le contenu | selectionne tout, select all |
| `copier_texte` | hotkey | Copier la selection | copie, copy |
| `couper_texte` | hotkey | Couper la selection | coupe, cut |
| `coller_texte` | hotkey | Coller le contenu du presse-papier | colle, paste |
| `annuler_action` | hotkey | Annuler la derniere action (undo) | annule, undo |
| `retablir_action` | hotkey | Retablir l'action annulee (redo) | retablis, redo |
| `rechercher_dans_page` | hotkey | Ouvrir la recherche dans la page | cherche dans la page, find |
| `rechercher_et_remplacer` | hotkey | Ouvrir rechercher et remplacer | cherche et remplace, find replace |
| `supprimer_mot_gauche` | hotkey | Supprimer le mot precedent | supprime le mot precedent, delete word left |
| `supprimer_mot_droite` | hotkey | Supprimer le mot suivant | supprime le mot suivant, delete word right |
| `menu_contextuel` | hotkey | Ouvrir le menu contextuel (clic droit) | clic droit, menu contextuel |
| `valider_entree` | hotkey | Appuyer sur Entree (valider) | entree, valide |
| `echapper` | hotkey | Appuyer sur Echap (annuler/fermer) | echap, escape |
| `tabulation` | hotkey | Naviguer au champ suivant (Tab) | tab, champ suivant |
| `tabulation_inverse` | hotkey | Naviguer au champ precedent (Shift+Tab) | shift tab, champ precedent |
| `ouvrir_selection` | hotkey | Ouvrir/activer l'element selectionne (Espace) | espace, active |
| `media_suivant` | powershell | Piste suivante | piste suivante, next track |
| `media_precedent` | powershell | Piste precedente | piste precedente, previous track |
| `screenshot_complet` | hotkey | Capture d'ecran complete (dans presse-papier) | screenshot, capture d'ecran |
| `screenshot_fenetre` | hotkey | Capture d'ecran de la fenetre active | screenshot fenetre, capture la fenetre |
| `snip_screen` | hotkey | Outil de capture d'ecran (selection libre) | snip, outil capture |
| `task_view` | hotkey | Ouvrir la vue des taches (Task View) | task view, vue des taches |
| `creer_bureau_virtuel` | hotkey | Creer un nouveau bureau virtuel | nouveau bureau virtuel, cree un bureau |
| `fermer_bureau_virtuel` | hotkey | Fermer le bureau virtuel actuel | ferme le bureau virtuel, supprime ce bureau |
| `zoom_in` | hotkey | Zoomer (agrandir) | zoom in, zoome |
| `zoom_out` | hotkey | Dezoomer (reduire) | zoom out, dezoome |
| `switch_app` | hotkey | Basculer entre les applications (Alt+Tab) | switch app, alt tab |
| `switch_app_inverse` | hotkey | Basculer en arriere entre les apps | app precedente alt tab, reverse alt tab |
| `ouvrir_start_menu` | hotkey | Ouvrir le menu Demarrer | ouvre le menu demarrer, start menu |
| `ouvrir_centre_notifications` | hotkey | Ouvrir le centre de notifications | ouvre les notifications, centre de notifications |
| `ouvrir_clipboard_history` | hotkey | Ouvrir l'historique du presse-papier | historique presse papier, clipboard history |
| `ouvrir_emojis_clavier` | hotkey | Ouvrir le panneau emojis | panneau emojis, emoji keyboard |
| `plein_ecran_toggle` | hotkey | Basculer en plein ecran (F11) | plein ecran, fullscreen |
| `renommer_fichier` | hotkey | Renommer le fichier/dossier selectionne (F2) | renomme, rename |
| `supprimer_selection` | hotkey | Supprimer la selection | supprime, delete |
| `ouvrir_proprietes` | hotkey | Voir les proprietes du fichier selectionne | proprietes, properties |
| `fermer_fenetre_active` | hotkey | Fermer la fenetre/app active (Alt+F4) | ferme la fenetre, close window |
| `ouvrir_parametres_systeme` | hotkey | Ouvrir les Parametres Windows | ouvre les parametres, parametres windows |
| `ouvrir_centre_accessibilite` | hotkey | Ouvrir les options d'accessibilite | accessibilite, options accessibilite |
| `dictee_vocale_windows` | hotkey | Activer la dictee vocale Windows | dictee vocale, voice typing |
| `projection_ecran` | hotkey | Options de projection ecran (etendre, dupliquer) | projection ecran, project screen |
| `connecter_appareil` | hotkey | Ouvrir le panneau de connexion d'appareils (Cast) | connecter un appareil, cast screen |
| `ouvrir_game_bar_direct` | hotkey | Ouvrir la Xbox Game Bar | game bar directe, xbox game bar |
| `powertoys_color_picker` | hotkey | Lancer le Color Picker PowerToys | color picker, pipette couleur |
| `powertoys_text_extractor` | hotkey | Extraire du texte de l'ecran (OCR PowerToys) | text extractor, ocr ecran |
| `powertoys_screen_ruler` | hotkey | Mesurer des distances a l'ecran (Screen Ruler) | screen ruler, regle ecran |
| `powertoys_always_on_top` | hotkey | Epingler la fenetre au premier plan (PowerToys) | pin powertoys, epingle powertoys |
| `powertoys_paste_plain` | hotkey | Coller en texte brut (PowerToys) | colle en texte brut, paste plain |
| `powertoys_fancyzones` | hotkey | Activer FancyZones layout editor | fancy zones, editeur de zones |
| `powertoys_peek` | hotkey | Apercu rapide de fichier (PowerToys Peek) | peek fichier, apercu rapide |
| `powertoys_launcher` | hotkey | Ouvrir PowerToys Run (lanceur rapide) | powertoys run, lanceur rapide |
| `traceroute_google` | powershell | Traceroute vers Google DNS | traceroute, trace la route |
| `ping_google` | powershell | Ping Google pour tester la connexion | ping google, teste internet |
| `ping_cluster_complet` | powershell | Ping tous les noeuds du cluster IA | ping tout le cluster, tous les noeuds repondent |
| `netstat_ecoute` | powershell | Ports en ecoute avec processus associes | netstat listen, ports en ecoute |
| `flush_dns` | powershell | Purger le cache DNS | flush dns, purge dns |
| `flush_arp` | powershell | Purger la table ARP | flush arp, vide la table arp |
| `ip_config_complet` | powershell | Configuration IP complete de toutes les interfaces | ipconfig all, config ip complete |
| `speed_test_rapide` | powershell | Test de debit internet rapide (download) | speed test, test de vitesse |
| `vpn_status` | powershell | Verifier l'etat des connexions VPN actives | etat vpn, vpn status |
| `shutdown_timer_30` | powershell | Programmer l'extinction dans 30 minutes | eteins dans 30 minutes, shutdown dans 30 min |
| `shutdown_timer_60` | powershell | Programmer l'extinction dans 1 heure | eteins dans une heure, shutdown dans 1h |
| `shutdown_timer_120` | powershell | Programmer l'extinction dans 2 heures | eteins dans deux heures, shutdown dans 2h |
| `annuler_shutdown` | powershell | Annuler l'extinction programmee | annule l'extinction, cancel shutdown |
| `restart_timer_30` | powershell | Programmer un redemarrage dans 30 minutes | redemarre dans 30 minutes, restart dans 30 min |
| `rappel_vocal` | powershell | Creer un rappel vocal avec notification | rappelle moi dans {minutes} minutes, timer {minutes} min |
| `generer_mot_de_passe` | powershell | Generer un mot de passe securise aleatoire | genere un mot de passe, password random |
| `audit_rdp` | powershell | Verifier si le Bureau a distance est active | rdp actif, bureau a distance |
| `audit_admin_users` | powershell | Lister les utilisateurs administrateurs | qui est admin, utilisateurs administrateurs |
| `sessions_actives` | powershell | Lister les sessions utilisateur actives | sessions actives, qui est connecte |
| `check_hash_fichier` | powershell | Calculer le hash SHA256 d'un fichier | hash du fichier {path}, sha256 {path} |
| `audit_software_recent` | powershell | Logiciels installes recemment (30 derniers jours) | logiciels recemment installes, quoi de neuf installe |
| `firewall_toggle_profil` | powershell | Activer/desactiver le pare-feu pour le profil actif | toggle firewall, active le pare feu |
| `luminosite_haute` | powershell | Monter la luminosite au maximum | luminosite max, brightness max |
| `luminosite_basse` | powershell | Baisser la luminosite au minimum | luminosite min, brightness low |
| `luminosite_moyenne` | powershell | Luminosite a 50% | luminosite moyenne, brightness medium |
| `info_moniteurs` | powershell | Informations sur les moniteurs connectes | info moniteurs, quels ecrans |
| `batterie_info` | powershell | Etat de la batterie (si laptop) | etat batterie, battery status |
| `power_events_recent` | powershell | Historique veille/reveil des dernieres 24h | historique veille, quand le pc s'est endormi |
| `night_light_toggle` | powershell | Basculer l'eclairage nocturne | lumiere de nuit, night light |
| `imprimer_page` | hotkey | Imprimer la page/document actif | imprime, print |
| `file_impression` | powershell | Voir la file d'attente d'impression | file d'impression, print queue |
| `annuler_impressions` | powershell | Annuler toutes les impressions en attente | annule les impressions, cancel print |
| `imprimante_par_defaut` | powershell | Voir l'imprimante par defaut | quelle imprimante par defaut, default printer |
| `kill_chrome` | powershell | Forcer la fermeture de Chrome | tue chrome, kill chrome |
| `kill_edge` | powershell | Forcer la fermeture d'Edge | tue edge, kill edge |
| `kill_discord` | powershell | Forcer la fermeture de Discord | tue discord, kill discord |
| `kill_spotify` | powershell | Forcer la fermeture de Spotify | tue spotify, kill spotify |
| `kill_steam` | powershell | Forcer la fermeture de Steam | tue steam, kill steam |
| `priorite_haute` | powershell | Passer la fenetre active en priorite haute CPU | priorite haute, high priority |
| `processus_reseau` | powershell | Processus utilisant le reseau actuellement | qui utilise le reseau, processus reseau |
| `wsl_status` | powershell | Voir les distributions WSL installees | distributions wsl, wsl list |
| `wsl_start` | powershell | Demarrer WSL (distribution par defaut) | lance wsl, demarre linux |
| `wsl_disk_usage` | powershell | Espace disque utilise par WSL | taille wsl, espace wsl |
| `loupe_activer` | hotkey | Activer la loupe Windows | active la loupe, zoom ecran |
| `loupe_desactiver` | hotkey | Desactiver la loupe Windows | desactive la loupe, arrete le zoom |
| `haut_contraste_toggle` | hotkey | Basculer en mode haut contraste | haut contraste, high contrast |
| `touches_remanentes` | powershell | Activer/desactiver les touches remanentes | touches remanentes, sticky keys |
| `taille_texte_plus` | powershell | Augmenter la taille du texte systeme | texte plus grand, agrandis le texte |
| `ouvrir_melangeur_audio` | powershell | Ouvrir le melangeur de volume | melangeur audio, volume mixer |
| `ouvrir_param_son` | powershell | Ouvrir les parametres de son | parametres son, reglages audio |
| `lister_audio_devices` | powershell | Lister les peripheriques audio | peripheriques audio, quelles sorties son |
| `volume_50` | powershell | Mettre le volume a 50% | volume a 50, moitie volume |
| `volume_25` | powershell | Mettre le volume a 25% | volume a 25, volume bas |
| `volume_max` | powershell | Mettre le volume au maximum | volume a fond, volume maximum |
| `storage_sense_on` | powershell | Activer Storage Sense (nettoyage auto) | active storage sense, nettoyage automatique |
| `disk_cleanup` | powershell | Lancer le nettoyage de disque Windows (cleanmgr) | nettoyage de disque, disk cleanup |
| `defrag_status` | powershell | Voir l'etat de fragmentation des disques | etat defragmentation, defrag status |
| `optimiser_disques` | powershell | Optimiser/defragmenter les disques | optimise les disques, defragmente |
| `focus_assist_alarms` | powershell | Focus Assist mode alarmes seulement | alarmes seulement, focus alarms only |
| `startup_apps_list` | powershell | Lister les apps qui demarrent au boot | apps au demarrage, startup apps |
| `startup_settings` | powershell | Ouvrir les parametres des apps au demarrage | parametres demarrage, startup settings |
| `credential_list` | powershell | Lister les identifiants Windows enregistres | liste les identifiants, quels mots de passe |
| `dns_serveurs` | powershell | Voir les serveurs DNS configures | quels serveurs dns, dns configures |
| `sync_horloge` | powershell | Synchroniser l'horloge avec le serveur NTP | synchronise l'horloge, sync ntp |
| `timezone_info` | powershell | Voir le fuseau horaire actuel | quel fuseau horaire, timezone |
| `calendrier_mois` | powershell | Afficher le calendrier du mois en cours | calendrier, montre le calendrier |
| `ouvrir_rdp` | powershell | Ouvrir le client Remote Desktop | ouvre remote desktop, lance rdp |
| `rdp_connect` | powershell | Connexion Remote Desktop a une machine | connecte en rdp a {host}, remote desktop {host} |
| `ssh_connect` | powershell | Connexion SSH a un serveur | connecte en ssh a {host}, ssh {host} |
| `changer_clavier` | hotkey | Changer la disposition clavier (FR/EN) | change le clavier, switch keyboard |
| `clavier_suivant` | hotkey | Passer a la disposition clavier suivante | clavier suivant, next keyboard |
| `taskbar_cacher` | powershell | Cacher la barre des taches automatiquement | cache la taskbar, hide taskbar |
| `wallpaper_info` | powershell | Voir le fond d'ecran actuel | quel fond d'ecran, wallpaper actuel |
| `icones_bureau_toggle` | powershell | Afficher/masquer les icones du bureau | cache les icones, montre les icones |
| `sandbox_launch` | powershell | Lancer Windows Sandbox | lance la sandbox, windows sandbox |
| `hyperv_list_vms` | powershell | Lister les machines virtuelles Hyper-V | liste les vms, virtual machines |
| `hyperv_start_vm` | powershell | Demarrer une VM Hyper-V | demarre la vm {vm}, start vm {vm} |
| `hyperv_stop_vm` | powershell | Arreter une VM Hyper-V | arrete la vm {vm}, stop vm {vm} |
| `service_start` | powershell | Demarrer un service Windows | demarre le service {svc}, start service {svc} |
| `service_stop` | powershell | Arreter un service Windows | arrete le service {svc}, stop service {svc} |
| `service_restart` | powershell | Redemarrer un service Windows | redemarre le service {svc}, restart service {svc} |
| `service_status` | powershell | Voir l'etat d'un service Windows | etat du service {svc}, status service {svc} |
| `partitions_list` | powershell | Lister toutes les partitions | liste les partitions, partitions disque |
| `disques_physiques` | powershell | Voir les disques physiques installes | disques physiques, quels disques |
| `clipboard_contenu` | powershell | Voir le contenu actuel du presse-papier | quoi dans le presse papier, clipboard content |
| `clipboard_en_majuscules` | powershell | Convertir le texte du clipboard en majuscules | clipboard en majuscules, texte en majuscules |
| `clipboard_en_minuscules` | powershell | Convertir le texte du clipboard en minuscules | clipboard en minuscules, texte en minuscules |
| `clipboard_compter_mots` | powershell | Compter les mots dans le presse-papier | combien de mots copies, word count clipboard |
| `clipboard_trim` | powershell | Nettoyer les espaces du texte clipboard | nettoie le clipboard, trim clipboard |
| `param_camera` | powershell | Parametres de confidentialite camera | parametres camera, privacy camera |
| `param_microphone` | powershell | Parametres de confidentialite microphone | parametres microphone, privacy micro |
| `param_localisation` | powershell | Parametres de localisation/GPS | parametres localisation, privacy location |
| `param_gaming` | powershell | Parametres de jeu Windows | parametres gaming, game settings |
| `param_comptes` | powershell | Parametres des comptes utilisateur | parametres comptes, account settings |
| `param_connexion` | powershell | Parametres de connexion (PIN, mot de passe) | options de connexion, sign in options |
| `param_apps_defaut` | powershell | Parametres des apps par defaut | apps par defaut, default apps |
| `param_fonctionnalites_optionnelles` | powershell | Fonctionnalites optionnelles Windows | fonctionnalites optionnelles, optional features |
| `param_souris` | powershell | Parametres de la souris | parametres souris, mouse settings |
| `param_clavier` | powershell | Parametres du clavier | parametres clavier, keyboard settings |
| `param_phone_link` | powershell | Ouvrir Phone Link (connexion telephone) | phone link, lien telephone |
| `param_notifications_apps` | powershell | Parametres notifications par application | notifications par app, gerer les notifications |
| `param_multitache` | powershell | Parametres multitache (snap, bureaux virtuels) | parametres multitache, multitasking settings |
| `param_stockage` | powershell | Parametres de stockage (espace disque) | parametres stockage, storage settings |
| `param_proxy` | powershell | Parametres de proxy reseau | parametres proxy, proxy settings |
| `param_vpn_settings` | powershell | Parametres VPN Windows | parametres vpn, vpn settings |
| `param_wifi_settings` | powershell | Parametres WiFi avances | parametres wifi, wifi settings |
| `param_update_avance` | powershell | Parametres Windows Update avances | update avance, windows update settings |
| `param_recovery` | powershell | Options de recuperation systeme | recovery options, reinitialiser le pc |
| `param_developeurs` | powershell | Parametres developpeur Windows | mode developpeur, developer settings |
| `calculatrice_standard` | powershell | Ouvrir la calculatrice Windows | ouvre la calculatrice, calculatrice |
| `calculer_expression` | powershell | Calculer une expression mathematique | calcule {expr}, combien fait {expr} |
| `convertir_temperature` | powershell | Convertir Celsius en Fahrenheit et inversement | convertis {temp} degres, celsius en fahrenheit {temp} |
| `convertir_octets` | powershell | Convertir des octets en unites lisibles | convertis {bytes} octets, combien de go fait {bytes} |
| `clipboard_base64_encode` | powershell | Encoder le clipboard en Base64 | encode en base64, base64 encode |
| `clipboard_base64_decode` | powershell | Decoder le clipboard depuis Base64 | decode le base64, base64 decode |
| `clipboard_url_encode` | powershell | Encoder le clipboard en URL (percent-encode) | url encode, encode l'url |
| `clipboard_json_format` | powershell | Formatter le JSON du clipboard avec indentation | formate le json, json pretty |
| `clipboard_md5` | powershell | Calculer le MD5 du texte dans le clipboard | md5 du clipboard, hash md5 texte |
| `clipboard_sort_lines` | powershell | Trier les lignes du clipboard par ordre alphabetique | trie les lignes, sort lines clipboard |
| `clipboard_unique_lines` | powershell | Supprimer les lignes dupliquees du clipboard | deduplique les lignes, unique lines |
| `clipboard_reverse` | powershell | Inverser le texte du clipboard | inverse le texte, reverse clipboard |
| `power_performance` | powershell | Activer le plan d'alimentation Haute Performance | mode performance, high performance |
| `power_equilibre` | powershell | Activer le plan d'alimentation Equilibre | mode equilibre, balanced power |
| `power_economie` | powershell | Activer le plan d'alimentation Economie d'energie | mode economie, power saver |
| `power_plans_list` | powershell | Lister les plans d'alimentation disponibles | quels plans alimentation, power plans |
| `sleep_timer_30` | powershell | Mettre le PC en veille dans 30 minutes | veille dans 30 minutes, sleep dans 30 min |
| `network_reset` | powershell | Reset complet de la pile reseau Windows | reset reseau, reinitialise le reseau |
| `network_troubleshoot` | powershell | Lancer le depanneur reseau Windows | depanne le reseau, network troubleshoot |
| `arp_table` | powershell | Afficher la table ARP (machines sur le reseau local) | table arp, machines sur le reseau |
| `nslookup_domain` | powershell | Resoudre un nom de domaine (nslookup) | nslookup {domain}, resous {domain} |

### TRADING (19)

| Commande | Type | Description | Triggers |
|----------|------|-------------|----------|
| `scanner_marche` | script | Scanner le marche MEXC | scanne le marche, scanner le marche |
| `detecter_breakout` | script | Detecter les breakouts | detecte les breakouts, cherche les breakouts |
| `pipeline_trading` | script | Lancer le pipeline intensif | lance le pipeline, pipeline intensif |
| `sniper_breakout` | script | Lancer le sniper breakout | lance le sniper, sniper breakout |
| `river_scalp` | script | Lancer le River Scalp 1min | lance river scalp, river scalp |
| `hyper_scan` | script | Lancer l'hyper scan V2 | lance hyper scan, hyper scan |
| `statut_cluster` | jarvis_tool | Statut du cluster IA | statut du cluster, etat du cluster |
| `modeles_charges` | jarvis_tool | Modeles charges sur le cluster | quels modeles sont charges, liste les modeles |
| `ollama_status` | jarvis_tool | Statut du backend Ollama | statut ollama, etat ollama |
| `ollama_modeles` | jarvis_tool | Modeles Ollama disponibles | modeles ollama, liste modeles ollama |
| `recherche_web_ia` | jarvis_tool | Recherche web via Ollama cloud | recherche web {requete}, cherche sur le web {requete} |
| `consensus_ia` | jarvis_tool | Consensus multi-IA | consensus sur {question}, demande un consensus sur {question} |
| `query_ia` | jarvis_tool | Interroger une IA locale | demande a {node} {prompt}, interroge {node} sur {prompt} |
| `signaux_trading` | jarvis_tool | Signaux de trading en attente | signaux en attente, quels signaux |
| `positions_trading` | jarvis_tool | Positions de trading ouvertes | mes positions, positions ouvertes |
| `statut_trading` | jarvis_tool | Statut global du trading | statut trading, etat du trading |
| `executer_signal` | jarvis_tool | Executer un signal de trading | execute le signal {id}, lance le signal {id} |
| `cluster_health` | powershell | Health check rapide du cluster IA | health check cluster, verifie le cluster ia |
| `ollama_running` | powershell | Modeles Ollama actuellement en memoire | quels modeles ollama tournent, ollama running |

</details>
