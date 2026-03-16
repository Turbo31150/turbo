"""Dominos Linux — pipelines en langage conversationnel."""
from __future__ import annotations

LINUX_PIPELINES: dict[str, dict] = {
    "health-check": {
        "name": "Health Check Système",
        "triggers": ["vérifie la santé du système", "health check", "état du système", "santé système"],
        "category": "system",
        "steps": [
            {"type": "bash", "command": "nvidia-smi --query-gpu=name,temperature.gpu,utilization.gpu,memory.used,memory.total --format=csv,noheader 2>/dev/null || echo 'Pas de GPU NVIDIA'", "label": "GPU Status"},
            {"type": "bash", "command": "systemctl --user list-units 'jarvis-*' --no-pager --plain 2>/dev/null || echo 'Pas de services jarvis'", "label": "Services JARVIS"},
            {"type": "bash", "command": "df -h / /home --output=target,size,used,avail,pcent 2>/dev/null", "label": "Espace disque"},
            {"type": "bash", "command": "free -h", "label": "Mémoire RAM"},
            {"type": "bash", "command": "uptime", "label": "Uptime"},
        ],
    },
    "cluster-status": {
        "name": "État du Cluster",
        "triggers": ["état du cluster", "cluster status", "vérifie le cluster", "les noeuds sont up"],
        "category": "cluster",
        "steps": [
            {"type": "bash", "command": "curl -s --max-time 5 http://127.0.0.1:1234/v1/models 2>/dev/null && echo 'M1 OK' || echo 'M1 OFFLINE'", "label": "M1"},
            {"type": "bash", "command": "curl -s --max-time 5 http://192.168.1.26:1234/v1/models 2>/dev/null && echo 'M2 OK' || echo 'M2 OFFLINE'", "label": "M2"},
            {"type": "bash", "command": "curl -s --max-time 5 http://192.168.1.113:1234/v1/models 2>/dev/null && echo 'M3 OK' || echo 'M3 OFFLINE'", "label": "M3"},
            {"type": "bash", "command": "curl -s --max-time 5 http://127.0.0.1:11434/api/tags 2>/dev/null && echo 'OL1 OK' || echo 'OL1 OFFLINE'", "label": "OL1"},
        ],
    },
    "gpu-thermal": {
        "name": "Température GPU",
        "triggers": ["température gpu", "gpu thermal", "les gpu sont chauds", "thermal gpu"],
        "category": "system",
        "steps": [
            {"type": "bash", "command": "nvidia-smi --query-gpu=index,name,temperature.gpu,fan.speed,power.draw --format=csv,noheader 2>/dev/null || echo 'Pas de GPU'", "label": "Thermal"},
        ],
    },
    "restart-service": {
        "name": "Redémarrer Service",
        "triggers": ["redémarre {service}", "restart {service}", "relance {service}"],
        "category": "system",
        "steps": [
            {"type": "bash", "command": "systemctl --user restart jarvis-{service} && systemctl --user status jarvis-{service} --no-pager", "label": "Restart"},
        ],
    },
    "logs-service": {
        "name": "Logs Service",
        "triggers": ["montre les logs de {service}", "logs {service}", "journal {service}"],
        "category": "system",
        "steps": [
            {"type": "bash", "command": "journalctl --user -u jarvis-{service} -n 50 --no-pager", "label": "Logs"},
        ],
    },
    "disk-usage": {
        "name": "Espace Disque",
        "triggers": ["espace disque", "disk usage", "combien de place", "stockage"],
        "category": "system",
        "steps": [
            {"type": "bash", "command": "df -h --output=target,size,used,avail,pcent / /home 2>/dev/null", "label": "Partitions"},
            {"type": "bash", "command": "du -sh ~/jarvis/data/ ~/jarvis/cowork/ ~/jarvis/src/ 2>/dev/null | sort -rh", "label": "Dossiers JARVIS"},
        ],
    },
    "network-check": {
        "name": "État Réseau",
        "triggers": ["état réseau", "network check", "réseau ok", "ping cluster"],
        "category": "system",
        "steps": [
            {"type": "bash", "command": "ip -br addr show | grep -v lo", "label": "Interfaces"},
            {"type": "bash", "command": "ping -c 1 -W 2 192.168.1.26 >/dev/null 2>&1 && echo 'M2: OK' || echo 'M2: OFFLINE'", "label": "Ping M2"},
            {"type": "bash", "command": "ping -c 1 -W 2 192.168.1.113 >/dev/null 2>&1 && echo 'M3: OK' || echo 'M3: OFFLINE'", "label": "Ping M3"},
        ],
    },
    "process-list": {
        "name": "Processus Actifs",
        "triggers": ["processus actifs", "process list", "top processus", "qui consomme"],
        "category": "system",
        "steps": [
            {"type": "bash", "command": "ps aux --sort=-%cpu | head -15", "label": "Top CPU"},
            {"type": "bash", "command": "ps aux --sort=-%mem | head -10", "label": "Top RAM"},
        ],
    },
    "check-updates": {
        "name": "Vérifier Mises à Jour",
        "triggers": ["vérifie les mises à jour", "check updates", "mises à jour disponibles"],
        "category": "system",
        "steps": [
            {"type": "bash", "command": "apt list --upgradable 2>/dev/null | head -20 || dnf check-update 2>/dev/null | head -20", "label": "Updates"},
        ],
    },
    "backup-db": {
        "name": "Sauvegarde Bases de Données",
        "triggers": ["sauvegarde les bases", "backup db", "backup databases", "sauvegarde sqlite"],
        "category": "system",
        "steps": [
            {"type": "bash", "command": "mkdir -p ~/jarvis/backups/$(date +%Y%m%d) && for db in ~/jarvis/data/*.db; do [ -f \"$db\" ] && sqlite3 \"$db\" \".backup ~/jarvis/backups/$(date +%Y%m%d)/$(basename $db)\" 2>/dev/null && echo \"OK: $(basename $db)\" || echo \"SKIP: $(basename $db)\"; done", "label": "Backup"},
        ],
    },
    "quick-ask": {
        "name": "Question Rapide",
        "triggers": ["demande à {noeud} {question}", "quick ask {noeud}", "pose la question à {noeud}"],
        "category": "cluster",
        "steps": [
            {"type": "bash", "command": "curl -s --max-time 30 http://127.0.0.1:1234/api/v1/chat -H 'Content-Type: application/json' -d '{\"model\":\"qwen/qwen3-8b\",\"input\":\"/nothink\\n{question}\",\"temperature\":0.2,\"max_output_tokens\":1024,\"stream\":false,\"store\":false}'", "label": "Ask M1"},
        ],
    },
    "benchmark-quick": {
        "name": "Benchmark Rapide",
        "triggers": ["benchmark rapide", "bench cluster", "teste la vitesse", "latence cluster"],
        "category": "cluster",
        "steps": [
            {"type": "bash", "command": "start=$(date +%s%N) && curl -s --max-time 10 http://127.0.0.1:1234/api/v1/chat -H 'Content-Type: application/json' -d '{\"model\":\"qwen/qwen3-8b\",\"input\":\"/nothink\\nReponds OK\",\"max_output_tokens\":10,\"stream\":false,\"store\":false}' >/dev/null && echo \"M1: $((( $(date +%s%N) - start ) / 1000000))ms\"", "label": "Bench M1"},
            {"type": "bash", "command": "start=$(date +%s%N) && curl -s --max-time 10 http://127.0.0.1:11434/api/chat -d '{\"model\":\"qwen3:1.7b\",\"messages\":[{\"role\":\"user\",\"content\":\"Reponds OK\"}],\"stream\":false,\"think\":false}' >/dev/null && echo \"OL1: $((( $(date +%s%N) - start ) / 1000000))ms\"", "label": "Bench OL1"},
        ],
    },
    "trading-scan": {
        "name": "Scan Trading",
        "triggers": ["scan trading", "lance le trading", "trading scan", "analyse crypto"],
        "category": "trading",
        "steps": [
            {"type": "bash", "command": "cd ~/jarvis && uv run python scripts/trading_v2/gpu_pipeline.py --quick --json 2>/dev/null || echo 'Pipeline trading non disponible'", "label": "GPU Pipeline"},
        ],
    },
    "git-status": {
        "name": "État du Repo",
        "triggers": ["état du repo", "git status", "git quoi de neuf", "changements git"],
        "category": "dev",
        "steps": [
            {"type": "bash", "command": "cd ~/jarvis && git status --short | head -30", "label": "Status"},
            {"type": "bash", "command": "cd ~/jarvis && git log --oneline -5", "label": "Last commits"},
        ],
    },
    "run-tests": {
        "name": "Lancer les Tests",
        "triggers": ["lance les tests", "run tests", "pytest", "teste le code"],
        "category": "dev",
        "steps": [
            {"type": "bash", "command": "cd ~/jarvis && uv run pytest -x --tb=short -q 2>&1 | tail -20", "label": "Tests"},
        ],
    },
    "audit-system": {
        "name": "Audit Système Complet",
        "triggers": ["audit système", "audit complet", "system audit", "vérifie tout"],
        "category": "dev",
        "steps": [
            {"type": "bash", "command": "cd ~/jarvis && uv run python scripts/system_audit.py --quick 2>&1 | tail -40", "label": "Audit"},
        ],
    },
    # === VOIX / INTERACTION ===
    "voice-learn": {
        "name": "Apprendre Commande",
        "triggers": ["apprends cette commande", "enregistre cette action", "sauvegarde cette commande", "mémorise ça"],
        "category": "voice",
        "steps": [
            {"type": "python", "command": "from src.learned_actions import LearnedActionsEngine; e = LearnedActionsEngine(); print(f'Actions apprises: {len(e.list_actions())}')", "label": "Count actions"},
        ],
    },
    "voice-list": {
        "name": "Liste Commandes Apprises",
        "triggers": ["liste mes commandes", "commandes apprises", "actions enregistrées", "ce que tu sais faire"],
        "category": "voice",
        "steps": [
            {"type": "bash", "command": "sqlite3 ~/jarvis/data/learned_actions.db \"SELECT canonical_name, category, success_count FROM learned_actions ORDER BY success_count DESC LIMIT 30\"", "label": "Actions"},
        ],
    },
    "voice-stats": {
        "name": "Stats Commandes",
        "triggers": ["stats commandes", "statistiques vocales", "combien de commandes"],
        "category": "voice",
        "steps": [
            {"type": "bash", "command": "sqlite3 ~/jarvis/data/learned_actions.db \"SELECT category, COUNT(*) as nb, SUM(success_count) as total_exec FROM learned_actions GROUP BY category ORDER BY total_exec DESC\"", "label": "Stats par catégorie"},
        ],
    },
    # === CLUSTER AVANCÉ ===
    "model-swap": {
        "name": "Changer de Modèle",
        "triggers": ["change de modèle", "swap model", "charge un autre modèle", "modèle suivant"],
        "category": "cluster",
        "steps": [
            {"type": "bash", "command": "curl -s http://127.0.0.1:1234/v1/models | python3 -c \"import sys,json; d=json.load(sys.stdin); [print(f'  {m[\\\"id\\\"]}') for m in d.get('data',[])]\" 2>/dev/null || echo 'M1 non disponible'", "label": "Modèles actuels"},
        ],
    },
    "ollama-models": {
        "name": "Modèles Ollama",
        "triggers": ["modèles ollama", "ollama models", "liste ollama", "quels modèles ollama"],
        "category": "cluster",
        "steps": [
            {"type": "bash", "command": "curl -s http://127.0.0.1:11434/api/tags | python3 -c \"import sys,json; d=json.load(sys.stdin); [print(f'  {m[\\\"name\\\"]} ({m[\\\"size\\\"]//1e9:.1f}GB)') for m in d.get('models',[])]\" 2>/dev/null || echo 'Ollama non disponible'", "label": "Models OL1"},
        ],
    },
    "consensus-quick": {
        "name": "Consensus Rapide",
        "triggers": ["consensus sur {question}", "demande à tous", "avis du cluster"],
        "category": "cluster",
        "steps": [
            {"type": "bash", "command": "echo '=== M1 ===' && curl -s --max-time 15 http://127.0.0.1:1234/api/v1/chat -H 'Content-Type: application/json' -d '{\"model\":\"qwen/qwen3-8b\",\"input\":\"/nothink\\n{question}\",\"max_output_tokens\":256,\"stream\":false,\"store\":false}' 2>/dev/null | python3 -c \"import sys,json; d=json.load(sys.stdin); [print(o.get('content','')) for o in d.get('output',[]) if o.get('type')=='message']\" 2>/dev/null || echo 'M1 timeout'", "label": "M1"},
            {"type": "bash", "command": "echo '=== OL1 ===' && curl -s --max-time 15 http://127.0.0.1:11434/api/chat -d '{\"model\":\"qwen3:1.7b\",\"messages\":[{\"role\":\"user\",\"content\":\"{question}\"}],\"stream\":false,\"think\":false}' 2>/dev/null | python3 -c \"import sys,json; print(json.load(sys.stdin).get('message',{}).get('content',''))\" 2>/dev/null || echo 'OL1 timeout'", "label": "OL1"},
        ],
    },
    # === MONITORING AVANCÉ ===
    "docker-status": {
        "name": "État Docker",
        "triggers": ["état docker", "docker status", "containers actifs", "docker ps"],
        "category": "system",
        "steps": [
            {"type": "bash", "command": "docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' 2>/dev/null || echo 'Docker non disponible'", "label": "Containers"},
            {"type": "bash", "command": "docker stats --no-stream --format 'table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}' 2>/dev/null | head -10 || true", "label": "Stats"},
        ],
    },
    "systemd-timers": {
        "name": "Timers Systemd",
        "triggers": ["timers actifs", "tâches planifiées", "cron systemd", "systemd timers"],
        "category": "system",
        "steps": [
            {"type": "bash", "command": "systemctl --user list-timers --no-pager 2>/dev/null || echo 'Pas de timers utilisateur'", "label": "User timers"},
            {"type": "bash", "command": "systemctl list-timers --no-pager 2>/dev/null | head -15 || echo 'Pas de timers système'", "label": "System timers"},
        ],
    },
    "journal-errors": {
        "name": "Erreurs Récentes",
        "triggers": ["erreurs récentes", "journal errors", "bugs système", "quoi de cassé"],
        "category": "system",
        "steps": [
            {"type": "bash", "command": "journalctl --priority=err --since='24 hours ago' --no-pager | tail -30", "label": "Errors 24h"},
        ],
    },
    # === DEVOPS ===
    "pip-outdated": {
        "name": "Paquets Obsolètes",
        "triggers": ["paquets obsolètes", "pip outdated", "mises à jour python", "dépendances à jour"],
        "category": "dev",
        "steps": [
            {"type": "bash", "command": "cd ~/jarvis && uv pip list --outdated 2>/dev/null | head -20 || pip list --outdated 2>/dev/null | head -20", "label": "Outdated"},
        ],
    },
    "git-branches": {
        "name": "Branches Git",
        "triggers": ["branches git", "git branches", "liste des branches"],
        "category": "dev",
        "steps": [
            {"type": "bash", "command": "cd ~/jarvis && git branch -a --sort=-committerdate | head -15", "label": "Branches"},
        ],
    },
    "git-diff": {
        "name": "Différences Git",
        "triggers": ["différences git", "git diff", "changements en cours", "quoi de modifié"],
        "category": "dev",
        "steps": [
            {"type": "bash", "command": "cd ~/jarvis && git diff --stat | tail -20", "label": "Diff stats"},
        ],
    },
    "test-coverage": {
        "name": "Couverture Tests",
        "triggers": ["couverture tests", "test coverage", "taux de couverture"],
        "category": "dev",
        "steps": [
            {"type": "bash", "command": "cd ~/jarvis && uv run pytest --co -q 2>/dev/null | tail -3", "label": "Test count"},
        ],
    },
    "manage-timers": {
        "name": "Gérer Timers JARVIS",
        "triggers": ["timers jarvis", "crons jarvis", "tâches planifiées jarvis", "jarvis timers"],
        "category": "system",
        "steps": [
            {"type": "bash", "command": "systemctl --user list-timers --no-pager 2>/dev/null | grep jarvis || echo 'Aucun timer JARVIS actif'", "label": "Active timers"},
        ],
    },
    "ports-check": {
        "name": "Vérifier Ports",
        "triggers": ["vérifier les ports", "ports ouverts", "qui écoute", "ports actifs"],
        "category": "system",
        "steps": [
            {"type": "bash", "command": "ss -tlnp 2>/dev/null | grep -E ':(1234|9742|18800|18789|11434|8080|9000)' || echo 'Aucun port JARVIS actif'", "label": "JARVIS ports"},
        ],
    },
    # === TRADING AVANCÉ ===
    "trading-positions": {
        "name": "Positions Trading",
        "triggers": ["positions trading", "mes positions", "trades ouverts", "portefeuille"],
        "category": "trading",
        "steps": [
            {"type": "bash", "command": "cd ~/jarvis && uv run python -c \"from src.trading_flow import get_positions; import json; print(json.dumps(get_positions(), indent=2, default=str))\" 2>/dev/null || echo 'Module trading non disponible'", "label": "Positions"},
        ],
    },
    "trading-signals": {
        "name": "Signaux Trading",
        "triggers": ["signaux trading", "derniers signaux", "alertes trading", "signals crypto"],
        "category": "trading",
        "steps": [
            {"type": "bash", "command": "cd ~/jarvis && sqlite3 data/sniper.db \"SELECT coin, signal_type, confidence, created_at FROM signals ORDER BY created_at DESC LIMIT 10\" 2>/dev/null || echo 'DB sniper non disponible'", "label": "Signals"},
        ],
    },
    "trading-pnl": {
        "name": "P&L Trading",
        "triggers": ["profit et perte", "pnl trading", "combien j'ai gagné", "résultats trading"],
        "category": "trading",
        "steps": [
            {"type": "bash", "command": "cd ~/jarvis && sqlite3 data/sniper.db \"SELECT SUM(pnl_usd) as total_pnl, COUNT(*) as trades FROM positions WHERE status='closed'\" 2>/dev/null || echo 'Pas de données P&L'", "label": "PnL"},
        ],
    },
    # === NOTIFICATIONS ===
    "notify-desktop": {
        "name": "Notification Desktop",
        "triggers": ["notification {message}", "notifie {message}", "alerte {message}"],
        "category": "system",
        "steps": [
            {"type": "bash", "command": "notify-send 'JARVIS' '{message}' --icon=dialog-information 2>/dev/null || echo 'notify-send non disponible'", "label": "Notify"},
        ],
    },
    "telegram-send": {
        "name": "Envoyer Telegram",
        "triggers": ["envoie sur telegram {message}", "telegram {message}", "message telegram"],
        "category": "system",
        "steps": [
            {"type": "bash", "command": "cd ~/jarvis && uv run python -c \"from src.telegram_sender import send_message; send_message('{message}')\" 2>/dev/null || echo 'Telegram non configuré'", "label": "Telegram"},
        ],
    },
    # === WORKFLOW AVANCÉ ===
    "morning-routine": {
        "name": "Routine du Matin",
        "triggers": ["routine du matin", "bonjour jarvis", "morning check", "démarre la journée"],
        "category": "system",
        "steps": [
            {"type": "bash", "command": "echo '=== SANTÉ SYSTÈME ===' && free -h && df -h / --output=avail | tail -1", "label": "System"},
            {"type": "bash", "command": "echo '=== CLUSTER ===' && curl -s --max-time 3 http://127.0.0.1:1234/v1/models >/dev/null 2>&1 && echo 'M1 OK' || echo 'M1 OFF'", "label": "Cluster"},
            {"type": "bash", "command": "echo '=== GPU ===' && nvidia-smi --query-gpu=temperature.gpu,utilization.gpu --format=csv,noheader 2>/dev/null || echo 'Pas de GPU'", "label": "GPU"},
            {"type": "bash", "command": "echo '=== GIT ===' && cd ~/jarvis && git log --oneline -3", "label": "Git"},
            {"type": "bash", "command": "echo '=== TRADING ===' && cd ~/jarvis && sqlite3 data/sniper.db \"SELECT COUNT(*) || ' signaux dernières 24h' FROM signals WHERE created_at > datetime('now', '-1 day')\" 2>/dev/null || echo 'Pas de données'", "label": "Trading"},
        ],
    },
    "night-shutdown": {
        "name": "Shutdown Soirée",
        "triggers": ["bonne nuit jarvis", "shutdown soirée", "ferme tout", "night mode"],
        "category": "system",
        "steps": [
            {"type": "bash", "command": "echo '=== SAUVEGARDE ===' && cd ~/jarvis && mkdir -p backups/$(date +%Y%m%d) && for db in data/*.db; do sqlite3 \"$db\" \".backup backups/$(date +%Y%m%d)/$(basename $db)\" 2>/dev/null && echo \"OK: $(basename $db)\"; done", "label": "Backup"},
            {"type": "bash", "command": "echo '=== STATS JOURNÉE ===' && cd ~/jarvis && sqlite3 data/learned_actions.db \"SELECT COUNT(*) || ' actions exécutées aujourd\\'hui' FROM action_executions WHERE executed_at > date('now')\" 2>/dev/null", "label": "Stats"},
        ],
    },
    "full-diagnostic": {
        "name": "Diagnostic Complet",
        "triggers": ["diagnostic complet", "full diagnostic", "tout vérifier", "check everything"],
        "category": "system",
        "steps": [
            {"type": "bash", "command": "echo '=== SYSTÈME ===' && uname -a && free -h && df -h / /home --output=target,avail", "label": "System"},
            {"type": "bash", "command": "echo '=== GPU ===' && nvidia-smi --query-gpu=index,name,temperature.gpu,utilization.gpu,memory.used --format=csv,noheader 2>/dev/null || echo 'No GPU'", "label": "GPU"},
            {"type": "bash", "command": "echo '=== SERVICES ===' && systemctl --user list-units 'jarvis-*' --no-pager --plain 2>/dev/null || echo 'No services'", "label": "Services"},
            {"type": "bash", "command": "echo '=== CLUSTER ===' && for url in http://127.0.0.1:1234 http://192.168.1.26:1234 http://192.168.1.113:1234 http://127.0.0.1:11434; do curl -s --max-time 3 $url/v1/models >/dev/null 2>&1 && echo \"$url OK\" || echo \"$url OFFLINE\"; done", "label": "Cluster"},
            {"type": "bash", "command": "echo '=== DOCKER ===' && docker ps --format '{{.Names}}: {{.Status}}' 2>/dev/null || echo 'Docker off'", "label": "Docker"},
            {"type": "bash", "command": "echo '=== PORTS ===' && ss -tlnp 2>/dev/null | grep -E ':(1234|9742|18800|18789|11434)' || echo 'No JARVIS ports'", "label": "Ports"},
            {"type": "bash", "command": "echo '=== TESTS ===' && cd ~/jarvis && uv run pytest tests/test_learned_actions.py tests/test_domino_pipelines_linux.py -q 2>&1 | tail -3", "label": "Tests"},
        ],
    },
    "cleanup-system": {
        "name": "Nettoyage Système",
        "triggers": ["nettoie le système", "cleanup", "libère de l'espace", "ménage système"],
        "category": "system",
        "steps": [
            {"type": "bash", "command": "echo '=== AVANT ===' && df -h / --output=avail | tail -1", "label": "Before"},
            {"type": "bash", "command": "find /tmp -maxdepth 1 -type f -mtime +3 -delete 2>/dev/null; echo 'tmp nettoyé'", "label": "Tmp"},
            {"type": "bash", "command": "find ~/jarvis/data/logs -name '*.log' -mtime +14 -delete 2>/dev/null; echo 'vieux logs nettoyés'", "label": "Logs"},
            {"type": "bash", "command": "docker system prune -f 2>/dev/null || true; echo 'docker pruné'", "label": "Docker"},
            {"type": "bash", "command": "echo '=== APRÈS ===' && df -h / --output=avail | tail -1", "label": "After"},
        ],
    },
    "who-is-connected": {
        "name": "Qui est Connecté",
        "triggers": ["qui est connecté", "connexions actives", "who is connected", "clients actifs"],
        "category": "system",
        "steps": [
            {"type": "bash", "command": "who 2>/dev/null || echo 'who non dispo'", "label": "Users"},
            {"type": "bash", "command": "ss -tn state established 2>/dev/null | grep -E ':(9742|18800|18789)' | wc -l | xargs -I{} echo '{} connexions JARVIS actives'", "label": "JARVIS connections"},
        ],
    },
    # === WORKFLOWS CHAÎNÉS AVANCÉS ===
    "deploy-check": {
        "name": "Vérification Pré-Déploiement",
        "triggers": ["vérifie avant déploiement", "pre-deploy check", "prêt pour déployer", "check deploy"],
        "category": "dev",
        "steps": [
            {"type": "bash", "command": "cd ~/jarvis && git status --porcelain | wc -l | xargs -I{} echo '{} fichiers non commités'", "label": "Git clean"},
            {"type": "bash", "command": "cd ~/jarvis && uv run pytest tests/test_learned_actions.py tests/test_domino_pipelines_linux.py tests/test_platform_dispatch.py -q 2>&1 | tail -3", "label": "Core tests"},
            {"type": "bash", "command": "nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader 2>/dev/null | awk '{if($1>75) print \"WARNING: GPU \"NR\" at \"$1\"C\"; else print \"GPU \"NR\": \"$1\"C OK\"}'", "label": "GPU thermal"},
            {"type": "bash", "command": "curl -s --max-time 5 http://127.0.0.1:1234/v1/models >/dev/null 2>&1 && echo 'M1: READY' || echo 'M1: OFFLINE — deploy blocked'", "label": "Cluster ready"},
            {"type": "bash", "command": "df -h / --output=avail | tail -1 | awk '{if(int($1)<5) print \"WARNING: <5GB free\"; else print \"Disk: \"$1\" free OK\"}'", "label": "Disk space"},
        ],
    },
    "git-sync": {
        "name": "Synchroniser Git",
        "triggers": ["synchronise git", "git sync", "push et pull", "met à jour le repo"],
        "category": "dev",
        "steps": [
            {"type": "bash", "command": "cd ~/jarvis && git stash list | head -5 2>/dev/null", "label": "Stash check"},
            {"type": "bash", "command": "cd ~/jarvis && git fetch --all --prune 2>&1 | tail -5", "label": "Fetch"},
            {"type": "bash", "command": "cd ~/jarvis && git status --short | head -20", "label": "Status"},
            {"type": "bash", "command": "cd ~/jarvis && git log --oneline origin/main..HEAD 2>/dev/null | head -10 || echo 'Rien à pousser'", "label": "Unpushed"},
        ],
    },
    "cluster-warm-up": {
        "name": "Préchauffer le Cluster",
        "triggers": ["préchauffe le cluster", "warm up cluster", "démarre le cluster", "allume tout"],
        "category": "cluster",
        "steps": [
            {"type": "bash", "command": "echo '=== Vérification noeuds ===' && for url in http://127.0.0.1:1234 http://192.168.1.26:1234 http://192.168.1.113:1234 http://127.0.0.1:11434; do curl -s --max-time 3 $url/v1/models >/dev/null 2>&1 && echo \"$url: UP\" || echo \"$url: DOWN\"; done", "label": "Check nodes"},
            {"type": "bash", "command": "echo '=== Warm-up M1 ===' && curl -s --max-time 15 http://127.0.0.1:1234/api/v1/chat -H 'Content-Type: application/json' -d '{\"model\":\"qwen/qwen3-8b\",\"input\":\"/nothink\\nReponds OK en un mot\",\"max_output_tokens\":5,\"stream\":false,\"store\":false}' 2>/dev/null | python3 -c \"import sys,json; d=json.load(sys.stdin); print('M1 warm: OK')\" 2>/dev/null || echo 'M1 warm: SKIP'", "label": "Warm M1"},
            {"type": "bash", "command": "echo '=== Warm-up OL1 ===' && curl -s --max-time 15 http://127.0.0.1:11434/api/chat -d '{\"model\":\"qwen3:1.7b\",\"messages\":[{\"role\":\"user\",\"content\":\"OK\"}],\"stream\":false,\"think\":false}' 2>/dev/null | python3 -c \"import sys,json; print('OL1 warm: OK')\" 2>/dev/null || echo 'OL1 warm: SKIP'", "label": "Warm OL1"},
        ],
    },
    "security-scan": {
        "name": "Scan Sécurité",
        "triggers": ["scan sécurité", "security scan", "vérifie la sécurité", "audit sécurité"],
        "category": "system",
        "steps": [
            {"type": "bash", "command": "echo '=== Fichiers sensibles ===' && find ~/jarvis -name '.env' -o -name '*.key' -o -name '*.pem' 2>/dev/null | head -10 || echo 'Aucun fichier sensible exposé'", "label": "Sensitive files"},
            {"type": "bash", "command": "echo '=== Ports ouverts ===' && ss -tlnp 2>/dev/null | grep LISTEN | head -15", "label": "Open ports"},
            {"type": "bash", "command": "echo '=== Permissions larges ===' && find ~/jarvis -perm -o+w -type f 2>/dev/null | head -10 || echo 'Aucun fichier world-writable'", "label": "Permissions"},
            {"type": "bash", "command": "echo '=== Dernières connexions ===' && last -5 2>/dev/null || echo 'last non disponible'", "label": "Logins"},
            {"type": "bash", "command": "echo '=== Secrets dans git ===' && cd ~/jarvis && git log --diff-filter=A --name-only --pretty=format: HEAD~5..HEAD 2>/dev/null | grep -iE '\\.env|\\.key|\\.pem|secret|password|token' || echo 'Aucun secret détecté dans les 5 derniers commits'", "label": "Git secrets"},
        ],
    },
    "performance-report": {
        "name": "Rapport Performance",
        "triggers": ["rapport performance", "performance report", "comment va le système", "stats performance"],
        "category": "system",
        "steps": [
            {"type": "bash", "command": "echo '=== LOAD ===' && uptime", "label": "Load"},
            {"type": "bash", "command": "echo '=== CPU ===' && grep 'model name' /proc/cpuinfo | head -1 && echo \"Cores: $(nproc)\"", "label": "CPU"},
            {"type": "bash", "command": "echo '=== RAM ===' && free -h | grep Mem", "label": "RAM"},
            {"type": "bash", "command": "echo '=== SWAP/ZRAM ===' && free -h | grep Swap && zramctl 2>/dev/null || true", "label": "Swap"},
            {"type": "bash", "command": "echo '=== DISK I/O ===' && iostat -d 1 1 2>/dev/null | head -10 || echo 'iostat non disponible (apt install sysstat)'", "label": "IO"},
            {"type": "bash", "command": "echo '=== GPU ===' && nvidia-smi --query-gpu=name,temperature.gpu,utilization.gpu,memory.used,memory.total,power.draw --format=csv,noheader 2>/dev/null || echo 'No GPU'", "label": "GPU"},
            {"type": "bash", "command": "echo '=== NETWORK ===' && ip -s link show | grep -A2 'state UP' | head -10", "label": "Network"},
        ],
    },
    "jarvis-status": {
        "name": "Status JARVIS Complet",
        "triggers": ["status jarvis", "état de jarvis", "jarvis status", "comment va jarvis"],
        "category": "system",
        "steps": [
            {"type": "bash", "command": "echo '=== SERVICES ===' && systemctl --user list-units 'jarvis-*' --no-pager --plain 2>/dev/null | head -10 || echo 'Pas de services systemd'", "label": "Services"},
            {"type": "bash", "command": "echo '=== DOCKER ===' && docker ps --filter name=jarvis --format '{{.Names}}: {{.Status}}' 2>/dev/null || echo 'Docker off'", "label": "Docker"},
            {"type": "bash", "command": "echo '=== LEARNED ACTIONS ===' && sqlite3 ~/jarvis/data/learned_actions.db \"SELECT COUNT(*) || ' actions, ' || SUM(success_count) || ' exécutions' FROM learned_actions\" 2>/dev/null || echo 'DB non dispo'", "label": "Actions"},
            {"type": "bash", "command": "echo '=== CLUSTER ===' && for n in M1:127.0.0.1:1234 M2:192.168.1.26:1234 M3:192.168.1.113:1234 OL1:127.0.0.1:11434; do name=${n%%:*}; url=${n#*:}; curl -s --max-time 3 http://$url/v1/models >/dev/null 2>&1 && echo \"$name: UP\" || echo \"$name: DOWN\"; done", "label": "Cluster"},
            {"type": "bash", "command": "echo '=== TIMERS ===' && systemctl --user list-timers --no-pager 2>/dev/null | grep jarvis || echo 'Pas de timers'", "label": "Timers"},
            {"type": "bash", "command": "echo '=== DERNIÈRE ACTIVITÉ ===' && sqlite3 ~/jarvis/data/learned_actions.db \"SELECT canonical_name, status, duration_ms||'ms' FROM action_executions ORDER BY executed_at DESC LIMIT 5\" 2>/dev/null || echo 'Pas d activité récente'", "label": "Recent"},
        ],
    },
}


def get_pipeline(name: str) -> dict | None:
    return LINUX_PIPELINES.get(name)


def search_pipeline(text: str) -> dict | None:
    text_lower = text.lower()
    for name, pipeline in LINUX_PIPELINES.items():
        for trigger in pipeline["triggers"]:
            if "{" in trigger:
                continue
            if trigger in text_lower or text_lower in trigger:
                return {"key": name, **pipeline}
    return None


def list_pipelines(category: str | None = None) -> list[dict]:
    results = []
    for name, pipeline in LINUX_PIPELINES.items():
        if category and pipeline["category"] != category:
            continue
        results.append({"key": name, **pipeline})
    return results
