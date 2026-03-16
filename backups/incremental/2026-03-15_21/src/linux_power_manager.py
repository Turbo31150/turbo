"""Linux Power Manager — Power management, CPU governor, battery status.

systemctl suspend/hibernate, cpupower, TLP, power supply info.
Designed for JARVIS autonomous power management.
"""

from __future__ import annotations

import glob
import logging
import os
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Any


__all__ = [
    "PowerEvent",
    "PowerPlan",
    "LinuxPowerManager",
]

logger = logging.getLogger("jarvis.linux_power_manager")


@dataclass
class PowerPlan:
    """A power plan entry."""
    name: str
    guid: str = ""
    is_active: bool = False


@dataclass
class PowerEvent:
    """Record of a power plan action."""
    action: str
    detail: str = ""
    timestamp: float = field(default_factory=time.time)
    success: bool = True


class LinuxPowerManager:
    """Linux power management."""

    def __init__(self) -> None:
        self._events: list[PowerEvent] = []
        self._lock = threading.Lock()

    # ── Power Plans / Profiles ────────────────────────────────────────────

    def list_plans(self) -> list[dict[str, Any]]:
        """List power profiles via powerprofilesctl or CPU governors."""
        # Essayer powerprofilesctl (GNOME Power Profiles Daemon)
        plans = self._list_powerprofiles()
        if plans:
            return plans
        # Fallback : CPU governors
        return self._list_cpu_governors()

    def _list_powerprofiles(self) -> list[dict[str, Any]]:
        """List via powerprofilesctl."""
        try:
            result = subprocess.run(
                ["powerprofilesctl", "list"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                # Obtenir le profil actif
                active_profile = ""
                try:
                    r2 = subprocess.run(
                        ["powerprofilesctl", "get"],
                        capture_output=True, text=True, timeout=5,
                    )
                    active_profile = r2.stdout.strip()
                except Exception:
                    pass
                plans = []
                for line in result.stdout.splitlines():
                    # Les profils sont sur les lignes qui finissent par ":"
                    # Format: "* performance:" ou "  balanced:"
                    stripped = line.rstrip()
                    if stripped.endswith(":"):
                        name = stripped.lstrip("* ").rstrip(":").strip()
                        is_active = (name == active_profile) or stripped.startswith("*")
                        plans.append({
                            "name": name,
                            "is_active": is_active,
                            "guid": "powerprofiles",
                        })
                return plans
        except FileNotFoundError:
            pass
        except Exception:
            pass
        return []

    def _list_cpu_governors(self) -> list[dict[str, Any]]:
        """List CPU frequency governors."""
        try:
            # Lire les governors disponibles
            gov_path = "/sys/devices/system/cpu/cpu0/cpufreq/scaling_available_governors"
            current_path = "/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor"
            available = ""
            current = ""
            if os.path.exists(gov_path):
                with open(gov_path) as f:
                    available = f.read().strip()
            if os.path.exists(current_path):
                with open(current_path) as f:
                    current = f.read().strip()
            if available:
                plans = []
                for gov in available.split():
                    plans.append({
                        "name": gov,
                        "is_active": gov == current,
                        "guid": "cpufreq",
                    })
                return plans
        except Exception:
            pass
        return [{"name": "default", "is_active": True, "guid": "unknown"}]

    # ── Battery ───────────────────────────────────────────────────────────

    def get_battery_status(self) -> dict[str, Any]:
        """Get battery status from /sys/class/power_supply/."""
        bat_dirs = glob.glob("/sys/class/power_supply/BAT*")
        if not bat_dirs:
            return {
                "name": "No Battery",
                "charge_percent": 100,
                "status": "AC",
                "has_battery": False,
            }
        bat = bat_dirs[0]
        try:
            capacity = self._read_sysfs(os.path.join(bat, "capacity"), "0")
            status = self._read_sysfs(os.path.join(bat, "status"), "Unknown")
            model = self._read_sysfs(os.path.join(bat, "model_name"), "Battery")
            return {
                "name": model,
                "charge_percent": int(capacity),
                "status": status,
                "has_battery": True,
            }
        except Exception:
            return {"name": "Battery", "charge_percent": 0, "status": "Unknown", "has_battery": True}

    def _read_sysfs(self, path: str, default: str = "") -> str:
        """Read a sysfs file safely."""
        try:
            if os.path.exists(path):
                with open(path) as f:
                    return f.read().strip()
        except Exception:
            pass
        return default

    # ── CPU Info ──────────────────────────────────────────────────────────

    def get_cpu_frequency(self) -> dict[str, Any]:
        """Get current CPU frequency info."""
        try:
            result = subprocess.run(
                ["cpupower", "frequency-info"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                return {"detail": result.stdout.strip()[:500]}
        except FileNotFoundError:
            pass
        except Exception:
            pass
        # Fallback: lire /proc/cpuinfo
        try:
            freqs: list[float] = []
            with open("/proc/cpuinfo") as f:
                for line in f:
                    if line.startswith("cpu MHz"):
                        val = line.split(":")[1].strip()
                        freqs.append(float(val))
            if freqs:
                return {
                    "min_mhz": round(min(freqs), 1),
                    "max_mhz": round(max(freqs), 1),
                    "avg_mhz": round(sum(freqs) / len(freqs), 1),
                    "cores": len(freqs),
                }
        except Exception:
            pass
        return {}

    # ── TLP ───────────────────────────────────────────────────────────────

    def get_tlp_status(self) -> dict[str, Any]:
        """Get TLP power management status (if installed)."""
        try:
            result = subprocess.run(
                ["tlp-stat", "-s"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                return {
                    "installed": True,
                    "detail": result.stdout.strip()[:500],
                }
        except FileNotFoundError:
            return {"installed": False}
        except Exception:
            return {"installed": False}

    # ── Actions ───────────────────────────────────────────────────────────

    def suspend(self) -> bool:
        """Suspend the system."""
        try:
            result = subprocess.run(
                ["systemctl", "suspend"],
                capture_output=True, text=True, timeout=10,
            )
            success = result.returncode == 0
            self._record("suspend", success)
            return success
        except Exception as e:
            self._record("suspend", False, str(e))
            return False

    def hibernate(self) -> bool:
        """Hibernate the system."""
        try:
            result = subprocess.run(
                ["systemctl", "hibernate"],
                capture_output=True, text=True, timeout=10,
            )
            success = result.returncode == 0
            self._record("hibernate", success)
            return success
        except Exception as e:
            self._record("hibernate", False, str(e))
            return False

    # ── Query ─────────────────────────────────────────────────────────────

    def _record(self, action: str, success: bool, detail: str = "") -> None:
        with self._lock:
            self._events.append(PowerEvent(action=action, success=success, detail=detail))

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


linux_power_manager = LinuxPowerManager()
