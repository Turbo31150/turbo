"""Audit des commandes vocales — classifie par plateforme."""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, ".")

DB_PATH = Path("data/jarvis.db")


def audit():
    if not DB_PATH.exists():
        print(f"DB non trouvée: {DB_PATH}")
        return

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM voice_commands").fetchall()
    conn.close()

    stats = {"windows": 0, "linux": 0, "both": 0}
    windows_indicators = [
        "powershell", "Get-", "Set-", "Start-Process", "Stop-Process",
        "regedit", "taskkill", "C:\\\\", "C:/Users", "explorer.exe",
        ".exe", "wmic", "schtasks", "netsh",
    ]
    linux_indicators = [
        "systemctl", "journalctl", "apt ", "dnf ", "pacman",
        "xdg-open", "notify-send", "xdotool", "wmctrl",
        "/proc/", "/sys/", "xrandr",
    ]

    to_port = []

    for row in rows:
        cmd = dict(row)
        action = cmd.get("action", "") or ""
        action_type = cmd.get("action_type", "") or ""

        is_win = any(ind in action for ind in windows_indicators) or action_type == "powershell"
        is_linux = any(ind in action for ind in linux_indicators)

        if is_win and not is_linux:
            stats["windows"] += 1
            to_port.append(cmd.get("trigger", "unknown"))
        elif is_linux and not is_win:
            stats["linux"] += 1
        else:
            stats["both"] += 1

    total = sum(stats.values())
    print(f"\n=== Audit Commandes Vocales ({total} total) ===")
    print(f"  Cross-platform (both): {stats['both']}")
    print(f"  Windows-only:          {stats['windows']}")
    print(f"  Linux-only:            {stats['linux']}")
    print(f"\n  À porter vers Linux:   {len(to_port)}")
    if to_port[:10]:
        print(f"\n  Exemples à porter:")
        for t in to_port[:10]:
            print(f"    - {t}")

    out = Path("data/audit_commands_platform.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"stats": stats, "to_port": to_port}, indent=2, ensure_ascii=False))
    print(f"\n  Rapport sauvegardé: {out}")


if __name__ == "__main__":
    audit()
