"""Gestion services systemd Linux."""
from __future__ import annotations

import logging
import subprocess

log = logging.getLogger(__name__)


def list_services(user: bool = True) -> list[dict]:
    """Liste les services (user ou system)."""
    cmd = ["systemctl"]
    if user:
        cmd.append("--user")
    cmd.extend(["list-units", "--type=service", "--no-pager", "--plain", "--no-legend"])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        services = []
        for line in result.stdout.strip().splitlines():
            parts = line.split(None, 4)
            if len(parts) >= 4:
                services.append({
                    "name": parts[0],
                    "load": parts[1],
                    "active": parts[2],
                    "sub": parts[3],
                    "description": parts[4] if len(parts) > 4 else "",
                })
        return services
    except Exception as e:
        log.error("Erreur list services: %s", e)
        return []


def start_service(name: str, user: bool = True) -> bool:
    cmd = ["systemctl"]
    if user:
        cmd.append("--user")
    cmd.extend(["start", name])
    try:
        subprocess.run(cmd, check=True, timeout=10)
        return True
    except Exception as e:
        log.error("Erreur start %s: %s", name, e)
        return False


def stop_service(name: str, user: bool = True) -> bool:
    cmd = ["systemctl"]
    if user:
        cmd.append("--user")
    cmd.extend(["stop", name])
    try:
        subprocess.run(cmd, check=True, timeout=10)
        return True
    except Exception as e:
        log.error("Erreur stop %s: %s", name, e)
        return False


def restart_service(name: str, user: bool = True) -> bool:
    cmd = ["systemctl"]
    if user:
        cmd.append("--user")
    cmd.extend(["restart", name])
    try:
        subprocess.run(cmd, check=True, timeout=10)
        return True
    except Exception as e:
        log.error("Erreur restart %s: %s", name, e)
        return False


def service_status(name: str, user: bool = True) -> dict:
    cmd = ["systemctl"]
    if user:
        cmd.append("--user")
    cmd.extend(["show", name, "--no-pager"])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        status = {}
        for line in result.stdout.splitlines():
            if "=" in line:
                key, _, val = line.partition("=")
                status[key] = val
        return status
    except Exception as e:
        log.error("Erreur status %s: %s", name, e)
        return {}


def get_logs(name: str, lines: int = 50, user: bool = True) -> str:
    cmd = ["journalctl"]
    if user:
        cmd.append("--user")
    cmd.extend(["-u", name, "-n", str(lines), "--no-pager"])
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return result.stdout
    except Exception as e:
        log.error("Erreur logs %s: %s", name, e)
        return ""
