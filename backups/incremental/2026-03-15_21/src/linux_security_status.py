"""Linux Security Status — Firewall, antivirus, rootkit detection status.

Monitor ufw, fail2ban, clamav, rkhunter, AppArmor/SELinux.
Designed for JARVIS autonomous security monitoring.
"""

from __future__ import annotations

import logging
import os
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Any


__all__ = [
    "SecurityEvent",
    "SecurityInfo",
    "LinuxSecurityStatus",
]

logger = logging.getLogger("jarvis.linux_security_status")


@dataclass
class SecurityInfo:
    """Security status information."""
    firewall_active: bool = False
    fail2ban_active: bool = False
    antivirus_installed: bool = False


@dataclass
class SecurityEvent:
    """Record of a security action."""
    action: str
    detail: str = ""
    timestamp: float = field(default_factory=time.time)
    success: bool = True


class LinuxSecurityStatus:
    """Linux security status monitoring (read-only)."""

    def __init__(self) -> None:
        self._events: list[SecurityEvent] = []
        self._lock = threading.Lock()

    def get_status(self) -> dict[str, Any]:
        """Get comprehensive security status."""
        status: dict[str, Any] = {}

        # UFW (firewall)
        status.update(self._get_ufw_status())
        # Fail2ban
        status.update(self._get_fail2ban_status())
        # ClamAV
        status.update(self._get_clamav_status())
        # AppArmor / SELinux
        status.update(self._get_mac_status())

        # Synthèse : est-on protégé ?
        status["antivirus_enabled"] = status.get("clamav_installed", False)
        status["realtime_protection"] = status.get("firewall_active", False)

        self._record("get_status", True)
        return status

    def _get_ufw_status(self) -> dict[str, Any]:
        """Get UFW firewall status."""
        try:
            result = subprocess.run(
                ["ufw", "status", "verbose"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                output = result.stdout.lower()
                active = "status: active" in output
                return {
                    "firewall_active": active,
                    "firewall_backend": "ufw",
                    "firewall_detail": result.stdout.strip()[:300],
                }
        except FileNotFoundError:
            pass
        except Exception:
            pass
        # Fallback: iptables
        try:
            result = subprocess.run(
                ["iptables", "-L", "-n", "--line-numbers"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                lines = result.stdout.strip().splitlines()
                has_rules = len(lines) > 6  # Plus que les headers par défaut
                return {
                    "firewall_active": has_rules,
                    "firewall_backend": "iptables",
                    "firewall_detail": f"{len(lines)} lines",
                }
        except Exception:
            pass
        return {"firewall_active": False, "firewall_backend": "none"}

    def _get_fail2ban_status(self) -> dict[str, Any]:
        """Get fail2ban status."""
        try:
            result = subprocess.run(
                ["fail2ban-client", "status"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                output = result.stdout.strip()
                # Extraire le nombre de jails
                jail_count = 0
                for line in output.splitlines():
                    if "Number of jail:" in line:
                        try:
                            jail_count = int(line.split(":")[-1].strip())
                        except ValueError:
                            pass
                return {
                    "fail2ban_active": True,
                    "fail2ban_jails": jail_count,
                    "fail2ban_detail": output[:200],
                }
        except FileNotFoundError:
            pass
        except Exception:
            pass
        return {"fail2ban_active": False, "fail2ban_jails": 0}

    def _get_clamav_status(self) -> dict[str, Any]:
        """Get ClamAV antivirus status."""
        installed = False
        daemon_running = False
        signature_version = ""
        try:
            result = subprocess.run(
                ["clamscan", "--version"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                installed = True
                signature_version = result.stdout.strip()[:100]
        except FileNotFoundError:
            pass
        except Exception:
            pass
        # Vérifier le daemon clamd
        try:
            result = subprocess.run(
                ["systemctl", "is-active", "clamav-daemon"],
                capture_output=True, text=True, timeout=5,
            )
            daemon_running = result.stdout.strip() == "active"
        except Exception:
            pass
        return {
            "clamav_installed": installed,
            "clamav_daemon_running": daemon_running,
            "signature_version": signature_version,
        }

    def _get_mac_status(self) -> dict[str, Any]:
        """Get Mandatory Access Control status (AppArmor or SELinux)."""
        # AppArmor
        try:
            result = subprocess.run(
                ["aa-status", "--json"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                return {
                    "mac_system": "AppArmor",
                    "mac_active": True,
                    "mac_detail": result.stdout[:200],
                }
        except FileNotFoundError:
            pass
        except Exception:
            pass
        # AppArmor fallback
        if os.path.exists("/sys/module/apparmor"):
            return {"mac_system": "AppArmor", "mac_active": True}
        # SELinux
        try:
            result = subprocess.run(
                ["getenforce"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                mode = result.stdout.strip()
                return {
                    "mac_system": "SELinux",
                    "mac_active": mode.lower() != "disabled",
                    "mac_mode": mode,
                }
        except FileNotFoundError:
            pass
        except Exception:
            pass
        return {"mac_system": "none", "mac_active": False}

    def get_threat_history(self) -> list[dict[str, Any]]:
        """Get recent threat detections from ClamAV logs."""
        threats: list[dict[str, Any]] = []
        log_path = "/var/log/clamav/clamav.log"
        try:
            if os.path.exists(log_path):
                with open(log_path, "r", errors="replace") as f:
                    lines = f.readlines()
                for line in reversed(lines[-200:]):
                    if "FOUND" in line:
                        threats.append({
                            "threat_id": 0,
                            "process": "",
                            "user": "",
                            "detected": line[:20].strip(),
                            "action_success": True,
                            "detail": line.strip()[:200],
                        })
                        if len(threats) >= 20:
                            break
        except Exception:
            pass
        return threats

    def is_protected(self) -> bool:
        """Quick check: is the system reasonably protected?"""
        status = self.get_status()
        return (
            status.get("firewall_active", False)
            and (status.get("fail2ban_active", False) or status.get("mac_active", False))
        )

    def _record(self, action: str, success: bool, detail: str = "") -> None:
        with self._lock:
            self._events.append(SecurityEvent(action=action, success=success, detail=detail))

    def get_events(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {"action": e.action, "timestamp": e.timestamp,
                 "success": e.success, "detail": e.detail}
                for e in self._events[-limit:]
            ]

    def get_stats(self) -> dict[str, Any]:
        with self._lock:
            return {"total_events": len(self._events)}


linux_security_status = LinuxSecurityStatus()
