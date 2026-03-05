"""Windows Update Manager — Windows Update history and status.

Read update history via Get-HotFix + Windows Update COM API.
Designed for JARVIS autonomous update monitoring.
"""

from __future__ import annotations

import json
import logging
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("jarvis.windows_update_manager")

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


@dataclass
class WindowsUpdate:
    """A Windows Update entry."""
    title: str
    kb_article: str = ""
    date: str = ""
    result_code: int = 0


@dataclass
class WUEvent:
    """Record of a Windows Update action."""
    action: str
    detail: str = ""
    timestamp: float = field(default_factory=time.time)
    success: bool = True


class WindowsUpdateManager:
    """Windows Update history reader (read-only)."""

    def __init__(self) -> None:
        self._events: list[WUEvent] = []
        self._lock = threading.Lock()

    def get_update_history(self, limit: int = 30) -> list[dict[str, Any]]:
        """Get recent Windows Update history via COM Session."""
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "$session = New-Object -ComObject Microsoft.Update.Session; "
                 "$searcher = $session.CreateUpdateSearcher(); "
                 f"$history = $searcher.QueryHistory(0, {min(limit, 100)}); "
                 "$out = @(); foreach($h in $history) { "
                 "$out += @{Title=$h.Title; Date=$h.Date.ToString('yyyy-MM-dd HH:mm'); "
                 "ResultCode=$h.ResultCode; UpdateID=$h.UpdateIdentity.UpdateID} }; "
                 "ConvertTo-Json $out -Depth 1 -Compress"],
                capture_output=True, text=True, timeout=20,
                creationflags=_NO_WINDOW,
                encoding="utf-8", errors="replace",
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                if isinstance(data, dict):
                    data = [data]
                updates = []
                for u in data:
                    title = u.get("Title", "") or ""
                    updates.append({
                        "title": title,
                        "date": u.get("Date", "") or "",
                        "result_code": u.get("ResultCode", 0),
                        "update_id": u.get("UpdateID", "") or "",
                    })
                self._record("get_update_history", True, f"{len(updates)} updates")
                return updates
        except Exception as e:
            self._record("get_update_history", False, str(e))
        return []

    def get_pending_updates(self) -> list[dict[str, Any]]:
        """Get pending (not yet installed) updates."""
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "$session = New-Object -ComObject Microsoft.Update.Session; "
                 "$searcher = $session.CreateUpdateSearcher(); "
                 "$results = $searcher.Search('IsInstalled=0'); "
                 "$out = @(); foreach($u in $results.Updates) { "
                 "$out += @{Title=$u.Title; IsDownloaded=$u.IsDownloaded; "
                 "IsMandatory=$u.IsMandatory} }; "
                 "ConvertTo-Json $out -Depth 1 -Compress"],
                capture_output=True, text=True, timeout=30,
                creationflags=_NO_WINDOW,
                encoding="utf-8", errors="replace",
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                if isinstance(data, dict):
                    data = [data]
                pending = []
                for u in data:
                    pending.append({
                        "title": u.get("Title", "") or "",
                        "is_downloaded": u.get("IsDownloaded", False),
                        "is_mandatory": u.get("IsMandatory", False),
                    })
                self._record("get_pending_updates", True, f"{len(pending)} pending")
                return pending
        except Exception as e:
            self._record("get_pending_updates", False, str(e))
        return []

    def search_history(self, query: str) -> list[dict[str, Any]]:
        """Search update history by title."""
        q = query.lower()
        return [u for u in self.get_update_history(100) if q in u.get("title", "").lower()]

    def _record(self, action: str, success: bool, detail: str = "") -> None:
        with self._lock:
            self._events.append(WUEvent(action=action, success=success, detail=detail))

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


windows_update_manager = WindowsUpdateManager()
