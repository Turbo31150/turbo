"""Commandes maintenance Linux — équivalents de commands_maintenance.py (PowerShell → bash)."""
from __future__ import annotations

LINUX_MAINTENANCE_COMMANDS: dict[str, dict] = {
    "list-services": {
        "command": "systemctl --user list-units --type=service --no-pager --plain",
        "description": "Liste les services utilisateur actifs",
        "category": "services",
    },
    "stopped-services": {
        "command": "systemctl --user list-units --type=service --state=inactive --no-pager",
        "description": "Services arrêtés",
        "category": "services",
    },
    "top-cpu": {
        "command": "ps aux --sort=-%cpu | head -15",
        "description": "Top processus par CPU",
        "category": "processes",
    },
    "top-memory": {
        "command": "ps aux --sort=-%mem | head -15",
        "description": "Top processus par mémoire",
        "category": "processes",
    },
    "active-connections": {
        "command": "ss -tunapl 2>/dev/null | head -30",
        "description": "Connexions réseau actives",
        "category": "network",
    },
    "listening-ports": {
        "command": "ss -tlnp 2>/dev/null",
        "description": "Ports en écoute",
        "category": "network",
    },
    "disk-health": {
        "command": "df -h --output=target,fstype,size,used,avail,pcent | sort -k6 -rn",
        "description": "Santé disques",
        "category": "storage",
    },
    "temp-cleanup": {
        "command": "find /tmp -maxdepth 1 -type f -mtime +7 2>/dev/null | wc -l && echo 'fichiers tmp > 7 jours'",
        "description": "Fichiers temp anciens (lecture seule)",
        "category": "storage",
    },
    "system-logs-errors": {
        "command": "journalctl --priority=err --since='1 hour ago' --no-pager | tail -20",
        "description": "Erreurs système dernière heure",
        "category": "logs",
    },
    "memory-detail": {
        "command": "free -h && echo '---' && cat /proc/meminfo | head -10",
        "description": "Détail mémoire",
        "category": "memory",
    },
    "gpu-processes": {
        "command": "nvidia-smi --query-compute-apps=pid,name,used_memory --format=csv,noheader 2>/dev/null || echo 'Pas de GPU'",
        "description": "Processus GPU",
        "category": "gpu",
    },
    "zram-status": {
        "command": "cat /proc/swaps 2>/dev/null && zramctl 2>/dev/null || echo 'Pas de ZRAM'",
        "description": "Status ZRAM/swap",
        "category": "memory",
    },
    "systemd-failed": {
        "command": "systemctl --failed --no-pager",
        "description": "Services en échec",
        "category": "services",
    },
    "kernel-info": {
        "command": "uname -a && echo '---' && lsb_release -a 2>/dev/null || cat /etc/os-release",
        "description": "Info kernel et distribution",
        "category": "system",
    },
    "cron-list": {
        "command": "crontab -l 2>/dev/null && echo '---' && systemctl --user list-timers --no-pager 2>/dev/null",
        "description": "Tâches planifiées",
        "category": "scheduler",
    },
}
