"""JARVIS — Commandes developpement et outils techniques."""

from __future__ import annotations

from src.commands import JarvisCommand

DEV_COMMANDS: list[JarvisCommand] = [
    # ══════════════════════════════════════════════════════════════════════
    # GIT AVANCE
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("git_branches", "dev", "Lister les branches git", [
        "branches git", "quelles branches", "liste les branches",
        "git branches", "git branch",
    ], "powershell", "cd F:\\BUREAU\\turbo; git branch -a"),
    JarvisCommand("git_diff", "dev", "Voir les modifications non commitees", [
        "git diff", "modifications en cours", "quelles modifications",
        "montre les changements", "diff git",
    ], "powershell", "cd F:\\BUREAU\\turbo; git diff --stat"),
    JarvisCommand("git_stash", "dev", "Sauvegarder les modifications en stash", [
        "git stash", "stash les changements", "sauvegarde les modifs",
        "mets de cote les changements",
    ], "powershell", "cd F:\\BUREAU\\turbo; git stash; 'Modifications sauvegardees en stash'"),
    JarvisCommand("git_stash_pop", "dev", "Restaurer les modifications du stash", [
        "git stash pop", "restaure le stash", "recupere le stash",
        "pop le stash",
    ], "powershell", "cd F:\\BUREAU\\turbo; git stash pop"),
    JarvisCommand("git_last_commit", "dev", "Voir le dernier commit en detail", [
        "dernier commit", "last commit", "montre le dernier commit",
        "qu'est ce qui a ete commite",
    ], "powershell", "cd F:\\BUREAU\\turbo; git log -1 --format='%H%n%an%n%s%n%ai' --stat"),
    JarvisCommand("git_count", "dev", "Compter les commits du projet", [
        "combien de commits", "nombre de commits", "git count",
        "total commits",
    ], "powershell", "cd F:\\BUREAU\\turbo; $c = (git rev-list --count HEAD); \"$c commits au total\""),

    # ══════════════════════════════════════════════════════════════════════
    # NODE / NPM / BUN
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("node_version", "dev", "Version de Node.js", [
        "version node", "quelle version node", "node version",
        "node js version",
    ], "powershell", "node --version"),
    JarvisCommand("npm_list_global", "dev", "Packages NPM globaux", [
        "packages npm globaux", "npm global", "npm list global",
        "quels packages npm",
    ], "powershell", "npm list -g --depth=0 2>$null | Out-String"),

    # ══════════════════════════════════════════════════════════════════════
    # OLLAMA / LM STUDIO
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("ollama_restart", "dev", "Redemarrer Ollama", [
        "redemarre ollama", "restart ollama", "relance ollama",
        "reboot ollama",
    ], "powershell", "Stop-Process -Name 'ollama' -Force -ErrorAction SilentlyContinue; Start-Sleep 2; Start-Process 'ollama' -ArgumentList 'serve'; 'Ollama relance'"),
    JarvisCommand("ollama_pull", "dev", "Telecharger un modele Ollama", [
        "telecharge le modele {model}", "ollama pull {model}",
        "installe le modele {model}", "download {model} ollama",
    ], "powershell", "ollama pull {model}", ["model"]),
    JarvisCommand("ollama_list", "dev", "Lister les modeles Ollama installes", [
        "liste les modeles ollama", "modeles ollama installes",
        "ollama list", "quels modeles ollama locaux",
    ], "powershell", "ollama list"),
    JarvisCommand("ollama_remove", "dev", "Supprimer un modele Ollama", [
        "supprime le modele {model}", "ollama rm {model}",
        "desinstalle le modele {model}", "enleve {model} ollama",
    ], "powershell", "ollama rm {model}; 'Modele {model} supprime'", ["model"], confirm=True),
    JarvisCommand("lm_studio_models", "dev", "Modeles charges dans LM Studio (M1, M2, M3)", [
        "modeles lm studio", "quels modeles lm studio",
        "modeles charges lm studio",
    ], "powershell", "$m2 = try{(Invoke-RestMethod -Uri 'http://192.168.1.26:1234/api/v1/models' -Headers @{'Authorization'='Bearer sk-lm-keRZkUya:St9kRjCg3VXTX6Getdp4'} -TimeoutSec 5).data | ForEach-Object { \"M2: $($_.id)\" }}catch{'M2: OFFLINE'}; $m3 = try{(Invoke-RestMethod -Uri 'http://192.168.1.113:1234/api/v1/models' -TimeoutSec 5).data | ForEach-Object { \"M3: $($_.id)\" }}catch{'M3: OFFLINE'}; $m2; $m3"),

    # ══════════════════════════════════════════════════════════════════════
    # PYTHON / UV
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("uv_sync", "dev", "Synchroniser les dependances uv", [
        "uv sync", "synchronise les dependances", "sync les packages",
        "installe les dependances",
    ], "powershell", "cd F:\\BUREAU\\turbo; & 'C:\\Users\\franc\\.local\\bin\\uv.exe' sync"),
    JarvisCommand("python_test", "dev", "Lancer les tests Python du projet", [
        "lance les tests", "run tests", "pytest",
        "teste le projet", "lance pytest",
    ], "powershell", "cd F:\\BUREAU\\turbo; & 'C:\\Users\\franc\\.local\\bin\\uv.exe' run pytest -x -v 2>&1 | Select -First 30 | Out-String"),
    JarvisCommand("python_lint", "dev", "Verifier le code avec ruff", [
        "lint le code", "ruff check", "verifie le code",
        "lance ruff", "check code quality",
    ], "powershell", "cd F:\\BUREAU\\turbo; & 'C:\\Users\\franc\\.local\\bin\\uv.exe' run ruff check src/ 2>&1 | Select -First 30 | Out-String"),

    # ══════════════════════════════════════════════════════════════════════
    # DOCKER AVANCE
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("docker_logs", "dev", "Voir les logs d'un conteneur Docker", [
        "logs docker de {container}", "docker logs {container}",
        "montre les logs de {container}",
    ], "powershell", "docker logs --tail 30 {container}", ["container"]),
    JarvisCommand("docker_restart", "dev", "Redemarrer un conteneur Docker", [
        "redemarre le conteneur {container}", "docker restart {container}",
        "relance {container}",
    ], "powershell", "docker restart {container}; 'Conteneur {container} redemarre'", ["container"]),
    JarvisCommand("docker_prune", "dev", "Nettoyer les ressources Docker inutilisees", [
        "nettoie docker", "docker prune", "clean docker",
        "libere l'espace docker",
    ], "powershell", "docker system prune -f | Out-String", confirm=True),
    JarvisCommand("docker_stats", "dev", "Statistiques des conteneurs Docker", [
        "stats docker", "docker stats", "ressources docker",
        "performance docker",
    ], "powershell", "docker stats --no-stream --format 'table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}' | Out-String"),

    # ══════════════════════════════════════════════════════════════════════
    # PROJET TURBO — RACCOURCIS
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("turbo_lines", "dev", "Compter les lignes de code du projet turbo", [
        "combien de lignes de code", "lignes de code turbo",
        "lines of code", "taille du code", "loc turbo",
    ], "powershell", "cd F:\\BUREAU\\turbo; $py = (Get-ChildItem src/*.py -Recurse | Get-Content | Measure-Object -Line).Lines; $total = (Get-ChildItem *.py,src/*.py -Recurse | Get-Content | Measure-Object -Line).Lines; \"Python src/: $py lignes | Total: $total lignes\""),
    JarvisCommand("turbo_size", "dev", "Taille totale du projet turbo", [
        "taille du projet turbo", "poids du projet", "combien pese turbo",
        "espace turbo",
    ], "powershell", "$s = (Get-ChildItem 'F:\\BUREAU\\turbo' -Recurse -File -ErrorAction SilentlyContinue | Where { $_.FullName -notmatch '(node_modules|__pycache__|.git|dist)' } | Measure-Object Length -Sum).Sum; \"Projet turbo: $([math]::Round($s/1MB,1)) MB\""),
    JarvisCommand("turbo_files", "dev", "Compter les fichiers du projet turbo", [
        "combien de fichiers turbo", "nombre de fichiers",
        "fichiers du projet", "count files turbo",
    ], "powershell", "cd F:\\BUREAU\\turbo; $py = (Get-ChildItem -Recurse -Filter '*.py' | Where { $_.FullName -notmatch '__pycache__' }).Count; $js = (Get-ChildItem -Recurse -Filter '*.js' | Where { $_.FullName -notmatch 'node_modules' }).Count; $ts = (Get-ChildItem -Recurse -Filter '*.ts' | Where { $_.FullName -notmatch 'node_modules' }).Count; \"Python: $py | JS: $js | TS: $ts\""),

    # ══════════════════════════════════════════════════════════════════════
    # LM STUDIO CLI (lms.exe)
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("lms_status", "dev", "Statut du serveur LM Studio local", [
        "statut lm studio", "lm studio status", "etat lm studio",
        "lm studio marche", "lms status",
    ], "powershell", "& 'C:\\Users\\franc\\.lmstudio\\bin\\lms.exe' status 2>&1 | Out-String"),
    JarvisCommand("lms_list_loaded", "dev", "Modeles actuellement charges dans LM Studio local", [
        "modeles charges locaux", "lms loaded", "quels modeles tourment",
        "modeles en cours lm studio", "lms list loaded",
    ], "powershell", "& 'C:\\Users\\franc\\.lmstudio\\bin\\lms.exe' ps 2>&1 | Out-String"),
    JarvisCommand("lms_load_model", "dev", "Charger un modele dans LM Studio local", [
        "charge le modele {model}", "lms load {model}",
        "load {model} dans lm studio", "monte le modele {model}",
    ], "powershell", "& 'C:\\Users\\franc\\.lmstudio\\bin\\lms.exe' load {model} 2>&1 | Out-String", ["model"]),
    JarvisCommand("lms_unload_model", "dev", "Decharger un modele de LM Studio local", [
        "decharge le modele {model}", "lms unload {model}",
        "unload {model}", "libere le modele {model}",
    ], "powershell", "& 'C:\\Users\\franc\\.lmstudio\\bin\\lms.exe' unload {model} 2>&1 | Out-String", ["model"]),
    JarvisCommand("lms_list_available", "dev", "Lister les modeles disponibles sur le disque", [
        "modeles disponibles lm studio", "lms list",
        "quels modeles j'ai", "modeles telecharges",
    ], "powershell", "& 'C:\\Users\\franc\\.lmstudio\\bin\\lms.exe' ls 2>&1 | Out-String"),

    # ══════════════════════════════════════════════════════════════════════
    # GIT AVANCE — Supplementaire
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("git_status_turbo", "dev", "Statut git du projet turbo", [
        "git status", "statut git", "etat du repo",
        "quoi de neuf en git",
    ], "powershell", "cd F:\\BUREAU\\turbo; git status -sb"),
    JarvisCommand("git_log_short", "dev", "Derniers 10 commits (resume)", [
        "historique git", "git log", "derniers commits",
        "montre l'historique", "log git recent",
    ], "powershell", "cd F:\\BUREAU\\turbo; git log --oneline -10"),
    JarvisCommand("git_remote_info", "dev", "Informations sur le remote git", [
        "remote git", "git remote", "quel remote",
        "url du repo", "origine git",
    ], "powershell", "cd F:\\BUREAU\\turbo; git remote -v"),

    # ══════════════════════════════════════════════════════════════════════
    # COMMUNICATION — Apps desktop
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("ouvrir_telegram", "dev", "Ouvrir Telegram Desktop", [
        "ouvre telegram", "lance telegram", "va sur telegram",
        "ouvrir telegram",
    ], "app_open", "telegram"),
    JarvisCommand("ouvrir_whatsapp", "dev", "Ouvrir WhatsApp Desktop", [
        "ouvre whatsapp", "lance whatsapp", "va sur whatsapp",
        "ouvrir whatsapp",
    ], "app_open", "whatsapp"),
    JarvisCommand("ouvrir_slack", "dev", "Ouvrir Slack Desktop", [
        "ouvre slack", "lance slack", "va sur slack",
        "ouvrir slack",
    ], "app_open", "slack"),
    JarvisCommand("ouvrir_teams", "dev", "Ouvrir Microsoft Teams", [
        "ouvre teams", "lance teams", "va sur teams",
        "ouvrir teams", "ouvre microsoft teams",
    ], "app_open", "teams"),
    JarvisCommand("ouvrir_zoom", "dev", "Ouvrir Zoom", [
        "ouvre zoom", "lance zoom", "va sur zoom",
        "ouvrir zoom",
    ], "app_open", "zoom"),

    # ══════════════════════════════════════════════════════════════════════
    # BUN / DENO / RUST
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("bun_version", "dev", "Version de Bun", [
        "version bun", "quelle version bun", "bun version",
    ], "powershell", "bun --version 2>&1 | Out-String"),
    JarvisCommand("deno_version", "dev", "Version de Deno", [
        "version deno", "quelle version deno", "deno version",
    ], "powershell", "deno --version 2>&1 | Out-String"),
    JarvisCommand("rust_version", "dev", "Version de Rust/Cargo", [
        "version rust", "quelle version rust", "rustc version",
        "version cargo", "cargo version",
    ], "powershell", "rustc --version; cargo --version 2>&1 | Out-String"),
    JarvisCommand("python_uv_version", "dev", "Version de Python et uv", [
        "version python", "quelle version python", "python version",
        "version uv",
    ], "powershell", "python --version; & 'C:\\Users\\franc\\.local\\bin\\uv.exe' --version 2>&1 | Out-String"),

    # ══════════════════════════════════════════════════════════════════════
    # PROJET TURBO — Commandes supplementaires
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("turbo_recent_changes", "dev", "Fichiers modifies recemment dans turbo", [
        "fichiers recents turbo", "modifications recentes",
        "quoi de modifie recemment", "derniers fichiers touches",
    ], "powershell", "cd F:\\BUREAU\\turbo; git diff --name-only HEAD~5 2>&1 | Out-String"),
    JarvisCommand("turbo_todo", "dev", "Lister les TODO dans le code turbo", [
        "liste les todo", "todo dans le code", "quels todo reste",
        "cherche les todo", "todo turbo",
    ], "powershell", "cd F:\\BUREAU\\turbo; Select-String -Path 'src\\*.py' -Pattern 'TODO|FIXME|HACK|XXX' | Select-Object Filename, LineNumber, Line | Format-Table -AutoSize | Out-String -Width 200"),

    # ══════════════════════════════════════════════════════════════════════
    # GIT — Commandes supplementaires
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("git_blame_file", "dev", "Git blame sur un fichier", [
        "git blame de {fichier}", "blame {fichier}",
        "qui a modifie {fichier}", "auteur de {fichier}",
    ], "powershell", "cd F:\\BUREAU\\turbo; git blame {fichier} | Select -Last 15 | Out-String", ["fichier"]),
    JarvisCommand("git_clean_branches", "dev", "Nettoyer les branches git mergees", [
        "nettoie les branches", "clean branches", "supprime les branches mergees",
        "git clean branches",
    ], "powershell", "cd F:\\BUREAU\\turbo; git branch --merged main | Where { $_ -notmatch 'main' } | ForEach { git branch -d $_.Trim() 2>&1 } | Out-String"),
    JarvisCommand("git_contributors", "dev", "Lister les contributeurs du projet", [
        "contributeurs git", "qui a contribue", "git contributors",
        "auteurs du projet",
    ], "powershell", "cd F:\\BUREAU\\turbo; git shortlog -sn --all | Out-String"),
    JarvisCommand("git_file_history", "dev", "Historique d'un fichier", [
        "historique du fichier {fichier}", "git log de {fichier}",
        "modifications de {fichier}",
    ], "powershell", "cd F:\\BUREAU\\turbo; git log --oneline -10 -- {fichier} | Out-String", ["fichier"]),
    JarvisCommand("git_undo_last", "dev", "Annuler le dernier commit (soft reset)", [
        "annule le dernier commit", "undo last commit", "git undo",
        "defais le dernier commit",
    ], "powershell", "cd F:\\BUREAU\\turbo; git reset --soft HEAD~1; 'Dernier commit annule (changements gardes)'", confirm=True),

    # ══════════════════════════════════════════════════════════════════════
    # NPM / BUN AVANCÉ
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("npm_audit", "dev", "Audit de securite NPM", [
        "npm audit", "audit securite npm", "vulnerabilites npm",
        "scan npm",
    ], "powershell", "npm audit --omit=dev 2>&1 | Select -Last 15 | Out-String"),
    JarvisCommand("npm_outdated", "dev", "Packages NPM obsoletes", [
        "npm outdated", "packages npm a jour", "quels packages npm a mettre a jour",
        "npm perime",
    ], "powershell", "npm outdated -g 2>&1 | Out-String"),

    # ══════════════════════════════════════════════════════════════════════
    # PYTHON AVANCÉ
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("pip_outdated", "dev", "Packages Python obsoletes", [
        "pip outdated", "packages python a mettre a jour",
        "quels packages python perime",
    ], "powershell", "& 'C:\\Users\\franc\\.local\\bin\\uv.exe' pip list --outdated 2>&1 | Select -First 15 | Out-String"),
    JarvisCommand("python_repl", "dev", "Lancer un REPL Python", [
        "lance python", "python repl", "ouvre python",
        "interprete python",
    ], "powershell", "python -i -c \"print('Python REPL JARVIS')\""),

    # ══════════════════════════════════════════════════════════════════════
    # RÉSEAU & PORTS — Dev operations
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("kill_port", "dev", "Tuer le processus sur un port specifique", [
        "tue le port {port}", "kill port {port}", "libere le port {port}",
        "ferme le port {port}",
    ], "powershell", "$pid = (Get-NetTCPConnection -LocalPort {port} -ErrorAction SilentlyContinue).OwningProcess | Select -First 1; if($pid){$name = (Get-Process -Id $pid).Name; Stop-Process -Id $pid -Force; \"Port {port}: processus $name (PID $pid) tue\"}else{\"Port {port}: aucun processus\"}", ["port"], confirm=True),
    JarvisCommand("qui_ecoute_port", "dev", "Quel processus ecoute sur un port", [
        "qui ecoute sur le port {port}", "quel process sur {port}",
        "port {port} utilise par", "check port {port}",
    ], "powershell", "$c = Get-NetTCPConnection -LocalPort {port} -State Listen -ErrorAction SilentlyContinue; if($c){$name = (Get-Process -Id $c.OwningProcess[0]).Name; \"Port {port}: $name (PID $($c.OwningProcess[0]))\"}else{\"Port {port}: libre\"}", ["port"]),
    JarvisCommand("ports_dev_status", "dev", "Statut des ports dev courants (3000, 5173, 8080, 8000, 9742)", [
        "statut des ports dev", "ports dev", "quels ports dev tournent",
        "services dev actifs",
    ], "powershell", "@(3000,5173,8080,8000,9742,5678,1234) | ForEach-Object { $c = Get-NetTCPConnection -LocalPort $_ -State Listen -ErrorAction SilentlyContinue; if($c){ $name = (Get-Process -Id $c.OwningProcess[0] -ErrorAction SilentlyContinue).Name; \"Port $($_): $name\" } else { \"Port $($_): libre\" } } | Out-String"),

    # ══════════════════════════════════════════════════════════════════════
    # OLLAMA AVANCÉ
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("ollama_vram_detail", "dev", "Detail VRAM utilisee par chaque modele Ollama", [
        "vram ollama detail", "ollama vram", "memoire ollama",
        "combien de vram ollama utilise",
    ], "powershell", "(Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/ps' -TimeoutSec 5).models | ForEach-Object { \"$($_.name): $([math]::Round($_.size_vram/1GB,2)) GB VRAM | expires: $($_.expires_at)\" } | Out-String"),
    JarvisCommand("ollama_stop_all", "dev", "Decharger tous les modeles Ollama de la VRAM", [
        "decharge tous les modeles ollama", "ollama stop all",
        "libere la vram ollama", "vide ollama",
    ], "powershell", "$models = (Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/ps' -TimeoutSec 5).models; $models | ForEach-Object { Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:11434/api/generate' -Body ('{\"model\":\"' + $_.name + '\",\"keep_alive\":0}') -ContentType 'application/json' }; \"$($models.Count) modeles decharges\"", confirm=True),

    # ══════════════════════════════════════════════════════════════════════
    # GIT AVANCÉ — Compléments
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("git_reflog", "dev", "Voir le reflog git (historique complet)", [
        "git reflog", "reflog", "historique complet git",
        "undo avance git",
    ], "powershell", "cd F:\\BUREAU\\turbo; git reflog -15 | Out-String"),
    JarvisCommand("git_tag_list", "dev", "Lister les tags git", [
        "tags git", "git tags", "liste les tags",
        "versions git", "releases git",
    ], "powershell", "cd F:\\BUREAU\\turbo; git tag -l --sort=-version:refname | Select -First 15 | Out-String"),
    JarvisCommand("git_search_commits", "dev", "Rechercher dans les messages de commit", [
        "cherche dans les commits {requete}", "git search {requete}",
        "commit contenant {requete}", "git log search {requete}",
    ], "powershell", "cd F:\\BUREAU\\turbo; git log --oneline --grep='{requete}' -15 | Out-String", ["requete"]),
    JarvisCommand("git_repo_size", "dev", "Taille du depot git", [
        "taille du repo git", "poids du git", "git size",
        "combien pese le git",
    ], "powershell", "cd F:\\BUREAU\\turbo; $s = (Get-ChildItem .git -Recurse -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum; \"Depot .git: $([math]::Round($s/1MB,1)) MB\""),
    JarvisCommand("git_stash_list", "dev", "Lister les stash git", [
        "liste les stash", "git stash list", "stash en attente",
        "quels stash j'ai",
    ], "powershell", "cd F:\\BUREAU\\turbo; $s = git stash list 2>&1; if($s){$s | Out-String}else{'Aucun stash'}"),
    JarvisCommand("git_diff_staged", "dev", "Voir les modifications stagees (pret a commit)", [
        "diff staged", "git diff staged", "quoi va etre commite",
        "modifications stagees",
    ], "powershell", "cd F:\\BUREAU\\turbo; git diff --cached --stat | Out-String"),

    # ══════════════════════════════════════════════════════════════════════
    # DOCKER AVANCÉ — Compléments
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("docker_images_list", "dev", "Lister les images Docker locales", [
        "images docker", "docker images", "liste les images docker",
        "quelles images docker",
    ], "powershell", "docker images --format 'table {{.Repository}}\t{{.Tag}}\t{{.Size}}' | Out-String"),
    JarvisCommand("docker_volumes", "dev", "Lister les volumes Docker", [
        "volumes docker", "docker volumes", "liste les volumes docker",
        "stockage docker",
    ], "powershell", "docker volume ls --format 'table {{.Name}}\t{{.Driver}}' | Out-String"),
    JarvisCommand("docker_networks", "dev", "Lister les reseaux Docker", [
        "reseaux docker", "docker networks", "liste les networks docker",
        "network docker",
    ], "powershell", "docker network ls --format 'table {{.Name}}\t{{.Driver}}\t{{.Scope}}' | Out-String"),
    JarvisCommand("docker_disk_usage", "dev", "Espace disque utilise par Docker", [
        "espace docker", "docker disk usage", "combien pese docker",
        "taille docker",
    ], "powershell", "docker system df | Out-String"),

    # ══════════════════════════════════════════════════════════════════════
    # WSL & WINGET — Gestionnaires systeme
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("wsl_status", "dev", "Statut de WSL et distributions installees", [
        "statut wsl", "wsl status", "distributions wsl",
        "quelles distros linux", "wsl installees",
    ], "powershell", "wsl --list --verbose 2>&1 | Out-String"),
    JarvisCommand("winget_search", "dev", "Rechercher un package via winget", [
        "winget search {requete}", "cherche {requete} sur winget",
        "package winget {requete}", "installe {requete} winget",
    ], "powershell", "winget search {requete} --count 10 2>&1 | Out-String", ["requete"]),
    JarvisCommand("winget_list_installed", "dev", "Lister les apps installees via winget", [
        "winget list", "apps winget", "inventaire winget",
        "quelles apps winget",
    ], "powershell", "winget list --count 20 2>&1 | Out-String"),
    JarvisCommand("winget_upgrade_all", "dev", "Mettre a jour toutes les apps via winget", [
        "winget upgrade all", "mets a jour tout winget",
        "update tout winget", "upgrade winget",
    ], "powershell", "winget upgrade --all --accept-source-agreements --accept-package-agreements 2>&1 | Out-String", confirm=True),

    # ══════════════════════════════════════════════════════════════════════
    # VSCODE & SSH — Outils dev
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("code_extensions_list", "dev", "Lister les extensions VSCode installees", [
        "extensions vscode", "liste les extensions", "vscode extensions",
        "quelles extensions j'ai",
    ], "powershell", "code --list-extensions 2>&1 | Out-String"),
    JarvisCommand("code_install_ext", "dev", "Installer une extension VSCode", [
        "installe l'extension {ext}", "vscode install {ext}",
        "ajoute l'extension {ext}", "code install {ext}",
    ], "powershell", "code --install-extension {ext} 2>&1 | Out-String", ["ext"]),
    JarvisCommand("ssh_keys_list", "dev", "Lister les cles SSH", [
        "cles ssh", "ssh keys", "liste les cles ssh",
        "quelles cles ssh j'ai",
    ], "powershell", "Get-ChildItem $env:USERPROFILE\\.ssh\\*.pub -ErrorAction SilentlyContinue | ForEach-Object { \"$($_.Name): $(Get-Content $_.FullName | Select -First 1)\" } | Out-String"),
    JarvisCommand("npm_cache_clean", "dev", "Nettoyer le cache NPM", [
        "nettoie le cache npm", "npm cache clean", "clean npm cache",
        "purge npm",
    ], "powershell", "npm cache clean --force 2>&1 | Out-String"),

    # ══════════════════════════════════════════════════════════════════════
    # PYTHON / UV — Compléments
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("uv_pip_tree", "dev", "Arbre de dependances Python du projet", [
        "arbre de dependances", "pip tree", "dependency tree",
        "dependances python", "uv tree",
    ], "powershell", "cd F:\\BUREAU\\turbo; & 'C:\\Users\\franc\\.local\\bin\\uv.exe' tree 2>&1 | Select -First 40 | Out-String"),
    JarvisCommand("pip_show_package", "dev", "Details d'un package Python installe", [
        "details du package {package}", "pip show {package}",
        "info sur {package}", "version de {package}",
    ], "powershell", "& 'C:\\Users\\franc\\.local\\bin\\uv.exe' pip show {package} 2>&1 | Out-String", ["package"]),
    JarvisCommand("turbo_imports", "dev", "Imports utilises dans le projet turbo", [
        "imports du projet", "quels imports", "dependances importees",
        "analyse les imports",
    ], "powershell", "cd F:\\BUREAU\\turbo; Select-String -Path 'src\\*.py' -Pattern '^(import |from )' | ForEach-Object { $_.Line.Trim() } | Sort -Unique | Out-String"),
    JarvisCommand("python_format_check", "dev", "Verifier le formatage Python avec ruff format", [
        "verifie le formatage", "ruff format check", "check formatting",
        "code bien formate",
    ], "powershell", "cd F:\\BUREAU\\turbo; & 'C:\\Users\\franc\\.local\\bin\\uv.exe' run ruff format --check src/ 2>&1 | Out-String"),
    JarvisCommand("python_type_check", "dev", "Verifier les types Python (pyright/mypy)", [
        "verifie les types", "type check", "pyright check",
        "mypy check", "typage python",
    ], "powershell", "cd F:\\BUREAU\\turbo; & 'C:\\Users\\franc\\.local\\bin\\uv.exe' run pyright src/ 2>&1 | Select -Last 10 | Out-String"),

    # ══════════════════════════════════════════════════════════════════════
    # RÉSEAU & SERVICES — Compléments dev
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("curl_test_endpoint", "dev", "Tester un endpoint HTTP", [
        "teste l'endpoint {url}", "curl {url}", "ping http {url}",
        "test api {url}",
    ], "powershell", "$r = Invoke-WebRequest -Uri '{url}' -TimeoutSec 10 -UseBasicParsing -ErrorAction Stop; \"Status: $($r.StatusCode) | Taille: $($r.Content.Length) bytes\"", ["url"]),
    JarvisCommand("n8n_workflows_list", "dev", "Lister les workflows n8n actifs", [
        "workflows n8n", "liste les workflows", "n8n actifs",
        "quels workflows tournent",
    ], "powershell", "$r = Invoke-RestMethod -Uri 'http://127.0.0.1:5678/api/v1/workflows' -TimeoutSec 5 -ErrorAction SilentlyContinue; $r.data | Select id, name, active | Format-Table -AutoSize | Out-String"),
]
