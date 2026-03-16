"""Linux Share Manager — Network share management via Samba, NFS, SSHFS.

List local shares, mounted network shares, manage connections.
Designed for JARVIS autonomous network share management.
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
    "ShareEvent",
    "ShareInfo",
    "LinuxShareManager",
]

logger = logging.getLogger("jarvis.linux_share_manager")


@dataclass
class ShareInfo:
    """A network share."""
    name: str
    path: str = ""
    remark: str = ""
    share_type: str = ""  # samba, nfs, sshfs


@dataclass
class ShareEvent:
    """Record of a share action."""
    action: str
    detail: str = ""
    timestamp: float = field(default_factory=time.time)
    success: bool = True


class LinuxShareManager:
    """Linux network share management."""

    def __init__(self) -> None:
        self._events: list[ShareEvent] = []
        self._lock = threading.Lock()

    # ── Local Shares ───────────────────────────────────────────────────

    def list_shares(self) -> list[dict[str, Any]]:
        """List local shared folders (Samba + NFS)."""
        shares: list[dict[str, Any]] = []
        shares.extend(self._list_samba_shares())
        shares.extend(self._list_nfs_exports())
        self._record("list_shares", True, f"{len(shares)} shares")
        return shares

    def _list_samba_shares(self) -> list[dict[str, Any]]:
        """List Samba user shares."""
        shares: list[dict[str, Any]] = []
        # net usershare list
        try:
            result = subprocess.run(
                ["net", "usershare", "list"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                for name in result.stdout.strip().splitlines():
                    name = name.strip()
                    if name:
                        # Détails du partage
                        info = self._get_samba_share_info(name)
                        shares.append({
                            "name": name,
                            "path": info.get("path", ""),
                            "description": info.get("comment", ""),
                            "type": "samba",
                        })
        except FileNotFoundError:
            pass
        except Exception:
            pass
        # Fallback: lire smb.conf
        if not shares:
            shares.extend(self._parse_smb_conf())
        return shares

    def _get_samba_share_info(self, share_name: str) -> dict[str, str]:
        """Get details of a single Samba user share."""
        try:
            result = subprocess.run(
                ["net", "usershare", "info", share_name],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                info: dict[str, str] = {}
                for line in result.stdout.splitlines():
                    if "=" in line:
                        k, v = line.split("=", 1)
                        info[k.strip().lower()] = v.strip()
                return info
        except Exception:
            pass
        return {}

    def _parse_smb_conf(self) -> list[dict[str, Any]]:
        """Parse /etc/samba/smb.conf for share definitions."""
        conf_path = "/etc/samba/smb.conf"
        shares: list[dict[str, Any]] = []
        if not os.path.exists(conf_path):
            return shares
        try:
            current_section = ""
            current_path = ""
            current_comment = ""
            with open(conf_path, "r", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("[") and line.endswith("]"):
                        # Sauver la section précédente
                        if current_section and current_section not in ("global", "printers", "print$"):
                            shares.append({
                                "name": current_section,
                                "path": current_path,
                                "description": current_comment,
                                "type": "samba",
                            })
                        current_section = line[1:-1]
                        current_path = ""
                        current_comment = ""
                    elif "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip().lower()
                        v = v.strip()
                        if k == "path":
                            current_path = v
                        elif k == "comment":
                            current_comment = v
                # Dernière section
                if current_section and current_section not in ("global", "printers", "print$"):
                    shares.append({
                        "name": current_section,
                        "path": current_path,
                        "description": current_comment,
                        "type": "samba",
                    })
        except Exception:
            pass
        return shares

    def _list_nfs_exports(self) -> list[dict[str, Any]]:
        """List NFS exports from /etc/exports."""
        exports: list[dict[str, Any]] = []
        exports_path = "/etc/exports"
        if not os.path.exists(exports_path):
            return exports
        try:
            with open(exports_path, "r", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("#") or not line:
                        continue
                    parts = line.split()
                    if parts:
                        exports.append({
                            "name": os.path.basename(parts[0]) or parts[0],
                            "path": parts[0],
                            "description": " ".join(parts[1:]) if len(parts) > 1 else "",
                            "type": "nfs",
                        })
        except Exception:
            pass
        return exports

    # ── Mounted Network Shares ─────────────────────────────────────────

    def list_mapped_drives(self) -> list[dict[str, Any]]:
        """List mounted network shares (CIFS/NFS/SSHFS)."""
        drives: list[dict[str, Any]] = []
        try:
            with open("/proc/mounts", "r") as f:
                for line in f:
                    parts = line.split()
                    if len(parts) >= 3:
                        device = parts[0]
                        mount = parts[1]
                        fstype = parts[2]
                        if fstype in ("cifs", "nfs", "nfs4", "smbfs", "fuse.sshfs"):
                            drives.append({
                                "status": "OK",
                                "drive": mount,
                                "remote": device,
                                "type": fstype,
                            })
            self._record("list_mapped_drives", True, f"{len(drives)} drives")
        except Exception as e:
            self._record("list_mapped_drives", False, str(e))
        return drives

    # ── Search ─────────────────────────────────────────────────────────

    def search_shares(self, query: str) -> list[dict[str, Any]]:
        """Search shares by name."""
        q = query.lower()
        return [s for s in self.list_shares() if q in s.get("name", "").lower()]

    # ── Query ──────────────────────────────────────────────────────────

    def _record(self, action: str, success: bool, detail: str = "") -> None:
        with self._lock:
            self._events.append(ShareEvent(
                action=action, success=success, detail=detail,
            ))

    def get_events(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {"action": e.action, "timestamp": e.timestamp,
                 "success": e.success, "detail": e.detail}
                for e in self._events[-limit:]
            ]

    def get_stats(self) -> dict[str, Any]:
        with self._lock:
            return {
                "total_events": len(self._events),
            }


# ── Singleton ───────────────────────────────────────────────────────
linux_share_manager = LinuxShareManager()
