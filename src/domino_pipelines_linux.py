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
