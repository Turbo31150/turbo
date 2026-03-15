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
    "ports-check": {
        "name": "Vérifier Ports",
        "triggers": ["vérifier les ports", "ports ouverts", "qui écoute", "ports actifs"],
        "category": "system",
        "steps": [
            {"type": "bash", "command": "ss -tlnp 2>/dev/null | grep -E ':(1234|9742|18800|18789|11434|8080|9000)' || echo 'Aucun port JARVIS actif'", "label": "JARVIS ports"},
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
