"""Gestion paquets Linux (apt, dnf, pacman)."""
from __future__ import annotations

import logging
import shutil
import subprocess

log = logging.getLogger(__name__)


def _detect_manager() -> str | None:
    for mgr in ["apt", "dnf", "pacman", "zypper"]:
        if shutil.which(mgr):
            return mgr
    return None


def list_installed(pattern: str = "") -> list[dict]:
    """Liste les paquets installés."""
    mgr = _detect_manager()
    if not mgr:
        return []

    try:
        if mgr == "apt":
            cmd = ["dpkg", "-l"]
            if pattern:
                cmd.extend(["--pattern", f"*{pattern}*"])
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            packages = []
            for line in result.stdout.splitlines():
                if line.startswith("ii"):
                    parts = line.split(None, 3)
                    if len(parts) >= 3:
                        packages.append({"name": parts[1], "version": parts[2]})
            return packages
        elif mgr == "dnf":
            result = subprocess.run(
                ["dnf", "list", "installed"], capture_output=True, text=True, timeout=15,
            )
            packages = []
            for line in result.stdout.splitlines()[1:]:
                parts = line.split()
                if len(parts) >= 2:
                    packages.append({"name": parts[0], "version": parts[1]})
            return packages
    except Exception as e:
        log.error("Erreur list packages: %s", e)
    return []


def check_updates() -> list[dict]:
    """Vérifie les mises à jour disponibles."""
    mgr = _detect_manager()
    if not mgr:
        return []

    try:
        if mgr == "apt":
            subprocess.run(["apt", "update"], capture_output=True, timeout=60)
            result = subprocess.run(
                ["apt", "list", "--upgradable"], capture_output=True, text=True, timeout=15,
            )
            updates = []
            for line in result.stdout.splitlines()[1:]:
                if "/" in line:
                    name = line.split("/")[0]
                    updates.append({"name": name, "line": line.strip()})
            return updates
        elif mgr == "dnf":
            result = subprocess.run(
                ["dnf", "check-update"], capture_output=True, text=True, timeout=30,
            )
            updates = []
            for line in result.stdout.splitlines():
                parts = line.split()
                if len(parts) >= 2 and "." in parts[0]:
                    updates.append({"name": parts[0], "version": parts[1]})
            return updates
    except Exception as e:
        log.error("Erreur check updates: %s", e)
    return []


def search_package(name: str) -> list[dict]:
    """Cherche un paquet."""
    mgr = _detect_manager()
    if not mgr:
        return []

    try:
        if mgr == "apt":
            result = subprocess.run(
                ["apt-cache", "search", name], capture_output=True, text=True, timeout=10,
            )
            return [
                {"name": l.split(" - ")[0], "description": l.split(" - ")[1] if " - " in l else ""}
                for l in result.stdout.strip().splitlines()[:20]
            ]
        elif mgr == "dnf":
            result = subprocess.run(
                ["dnf", "search", name], capture_output=True, text=True, timeout=10,
            )
            return [{"name": l.split(":")[0], "description": ""} for l in result.stdout.strip().splitlines()[:20]]
    except Exception as e:
        log.error("Erreur search: %s", e)
    return []
