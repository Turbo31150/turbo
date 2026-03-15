"""Génère les fichiers systemd timer+service pour les crons JARVIS."""
from __future__ import annotations

from pathlib import Path

SYSTEMD_DIR = Path.home() / ".config" / "systemd" / "user"

# Crons JARVIS à convertir en timers
JARVIS_TIMERS = [
    {
        "name": "jarvis-health",
        "description": "JARVIS cluster health check",
        "command": "cd ~/jarvis && uv run python -c 'from src.learned_actions import LearnedActionsEngine; e = LearnedActionsEngine(); print(e.match(\"health check\"))'",
        "schedule": "*:0/15",  # Toutes les 15 min
    },
    {
        "name": "jarvis-backup",
        "description": "JARVIS database backup",
        "command": "cd ~/jarvis && mkdir -p backups/$(date +%%Y%%m%%d) && for db in data/*.db; do sqlite3 \"$db\" \".backup backups/$(date +%%Y%%m%%d)/$(basename $db)\" 2>/dev/null; done",
        "schedule": "daily",  # 1x/jour (00:00)
    },
    {
        "name": "jarvis-thermal",
        "description": "JARVIS GPU thermal monitoring",
        "command": "nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader 2>/dev/null | while read temp; do [ \"$temp\" -gt 80 ] && echo \"GPU WARN: ${temp}C\" >> ~/jarvis/data/thermal_alerts.log; done",
        "schedule": "*:0/5",  # Toutes les 5 min
    },
    {
        "name": "jarvis-log-rotate",
        "description": "JARVIS log rotation",
        "command": "find ~/jarvis/data/logs -name '*.log' -mtime +7 -delete 2>/dev/null; find ~/jarvis/cowork/dev/reports -name '*.md' -mtime +30 -delete 2>/dev/null",
        "schedule": "weekly",
    },
    {
        "name": "jarvis-pipeline-check",
        "description": "JARVIS pipeline status check",
        "command": "systemctl --user is-active jarvis-pipeline.service >/dev/null 2>&1 || systemctl --user restart jarvis-pipeline.service",
        "schedule": "*:0/10",  # Toutes les 10 min
    },
]


def generate_service(timer: dict) -> str:
    return f"""[Unit]
Description={timer['description']}

[Service]
Type=oneshot
ExecStart=/bin/bash -c '{timer['command']}'
WorkingDirectory=%h/jarvis
"""


def generate_timer(timer: dict) -> str:
    if timer["schedule"] == "daily":
        on_calendar = "daily"
    elif timer["schedule"] == "weekly":
        on_calendar = "weekly"
    else:
        on_calendar = timer["schedule"]

    return f"""[Unit]
Description={timer['description']} timer

[Timer]
OnCalendar={on_calendar}
Persistent=true
RandomizedDelaySec=30

[Install]
WantedBy=timers.target
"""


def main():
    SYSTEMD_DIR.mkdir(parents=True, exist_ok=True)

    for timer in JARVIS_TIMERS:
        name = timer["name"]

        # Service
        svc_path = SYSTEMD_DIR / f"{name}.service"
        svc_path.write_text(generate_service(timer))
        print(f"  Created: {svc_path}")

        # Timer
        tmr_path = SYSTEMD_DIR / f"{name}.timer"
        tmr_path.write_text(generate_timer(timer))
        print(f"  Created: {tmr_path}")

    print(f"\n{len(JARVIS_TIMERS)} timers générés dans {SYSTEMD_DIR}")
    print("\nPour activer:")
    print("  systemctl --user daemon-reload")
    for t in JARVIS_TIMERS:
        print(f"  systemctl --user enable --now {t['name']}.timer")
    print("\nPour vérifier:")
    print("  systemctl --user list-timers")


if __name__ == "__main__":
    main()
