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
]
