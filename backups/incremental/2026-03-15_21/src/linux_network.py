"""Gestion réseau Linux (ip, nmcli, ss)."""
from __future__ import annotations

import logging
import subprocess

log = logging.getLogger(__name__)


def get_interfaces() -> list[dict]:
    """Liste les interfaces réseau."""
    interfaces = []
    try:
        result = subprocess.run(
            ["ip", "-br", "addr", "show"], capture_output=True, text=True, timeout=5,
        )
        for line in result.stdout.strip().splitlines():
            parts = line.split()
            if len(parts) >= 2:
                interfaces.append({
                    "name": parts[0],
                    "state": parts[1],
                    "addresses": parts[2:],
                })
    except Exception as e:
        log.error("Erreur interfaces: %s", e)
    return interfaces


def get_wifi_networks() -> list[dict]:
    """Liste les réseaux WiFi disponibles."""
    networks = []
    try:
        result = subprocess.run(
            ["nmcli", "-t", "-f", "SSID,SIGNAL,SECURITY", "dev", "wifi", "list"],
            capture_output=True, text=True, timeout=10,
        )
        for line in result.stdout.strip().splitlines():
            parts = line.split(":")
            if len(parts) >= 3 and parts[0]:
                networks.append({
                    "ssid": parts[0],
                    "signal": int(parts[1]) if parts[1].isdigit() else 0,
                    "security": parts[2],
                })
    except FileNotFoundError:
        log.warning("nmcli non disponible")
    except Exception as e:
        log.error("Erreur wifi: %s", e)
    return networks


def get_active_connections() -> list[dict]:
    """Connexions réseau actives."""
    connections = []
    try:
        result = subprocess.run(
            ["ss", "-tunap"], capture_output=True, text=True, timeout=5,
        )
        for line in result.stdout.strip().splitlines()[1:]:  # Skip header
            parts = line.split()
            if len(parts) >= 5:
                connections.append({
                    "proto": parts[0],
                    "state": parts[1],
                    "local": parts[4],
                    "remote": parts[5] if len(parts) > 5 else "",
                })
    except Exception as e:
        log.error("Erreur connections: %s", e)
    return connections


def ping_host(host: str, count: int = 1, timeout: int = 2) -> dict:
    """Ping un hôte."""
    try:
        result = subprocess.run(
            ["ping", "-c", str(count), "-W", str(timeout), host],
            capture_output=True, text=True, timeout=timeout + 5,
        )
        return {
            "host": host,
            "reachable": result.returncode == 0,
            "output": result.stdout.strip().splitlines()[-1] if result.stdout else "",
        }
    except Exception:
        return {"host": host, "reachable": False, "output": "timeout"}


def get_dns_servers() -> list[str]:
    """Serveurs DNS configurés."""
    try:
        result = subprocess.run(
            ["resolvectl", "status"], capture_output=True, text=True, timeout=5,
        )
        servers = []
        for line in result.stdout.splitlines():
            if "DNS Servers" in line:
                servers.extend(line.split(":")[1].strip().split())
        return servers
    except Exception:
        try:
            from pathlib import Path
            resolv = Path("/etc/resolv.conf").read_text()
            return [l.split()[1] for l in resolv.splitlines() if l.startswith("nameserver")]
        except Exception:
            return []
