"""Gestion des programmes au démarrage sous Linux (systemd user services)."""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)

SYSTEMD_USER_DIR = Path.home() / ".config" / "systemd" / "user"


def list_startup_items() -> list[dict]:
    """Liste les services utilisateur activés au démarrage."""
    items = []
    try:
        result = subprocess.run(
            ["systemctl", "--user", "list-unit-files", "--type=service", "--state=enabled", "--no-pager", "--plain"],
            capture_output=True, text=True, timeout=10,
        )
        for line in result.stdout.strip().splitlines()[1:]:  # Skip header
            parts = line.split()
            if len(parts) >= 2:
                items.append({"name": parts[0], "state": parts[1]})
    except Exception as e:
        log.warning("Erreur liste startup: %s", e)
    return items


def add_startup_item(service_name: str, exec_command: str, description: str = "") -> bool:
    """Crée un service systemd utilisateur pour démarrage auto."""
    SYSTEMD_USER_DIR.mkdir(parents=True, exist_ok=True)
    unit_file = SYSTEMD_USER_DIR / f"{service_name}.service"
    unit_content = f"""[Unit]
Description={description or service_name}
After=default.target

[Service]
Type=simple
ExecStart={exec_command}
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
"""
    unit_file.write_text(unit_content)
    try:
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=True, timeout=10)
        subprocess.run(["systemctl", "--user", "enable", service_name], check=True, timeout=10)
        log.info("Service %s ajouté au démarrage", service_name)
        return True
    except subprocess.CalledProcessError as e:
        log.error("Erreur ajout startup %s: %s", service_name, e)
        return False


def remove_startup_item(service_name: str) -> bool:
    """Supprime un service du démarrage."""
    try:
        subprocess.run(["systemctl", "--user", "disable", service_name], check=True, timeout=10)
        unit_file = SYSTEMD_USER_DIR / f"{service_name}.service"
        if unit_file.exists():
            unit_file.unlink()
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=True, timeout=10)
        return True
    except Exception as e:
        log.error("Erreur suppression startup %s: %s", service_name, e)
        return False


def is_enabled(service_name: str) -> bool:
    """Vérifie si un service est activé au démarrage."""
    try:
        result = subprocess.run(
            ["systemctl", "--user", "is-enabled", service_name],
            capture_output=True, text=True, timeout=5,
        )
        return result.stdout.strip() == "enabled"
    except Exception:
        return False
